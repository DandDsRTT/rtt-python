"""Real-browser coverage for the comma-pump score modal (assets/score.js).

Split from test_browser_behavior.py for the structure-policy line cap; runs on its own port so
the two files' served apps never collide. Opt-in via RTT_BROWSER_SMOKE=1 like its siblings, and
listed in .github/workflows/merge-gate.yml so client JS stays gated on every merge.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

_PORT = 8206
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN = "RTT_BROWSER_SMOKE"


def _port_is_free(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


def _serving(url: str, timeout: float = 40.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="module")
def served_app():
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(f"real-browser score coverage is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser score suite")
    url = f"http://127.0.0.1:{_PORT}"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTEST_CURRENT_TEST" and not key.startswith("NICEGUI_")
    }
    child_env["PORT"] = str(_PORT)
    server = subprocess.Popen([sys.executable, "app.py"], cwd=_REPO_ROOT, env=child_env)
    try:
        if not _serving(f"{url}/"):
            pytest.fail(f"the app never began serving on {url}")
        yield url
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


@pytest.fixture(scope="module")
def browser(served_app):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as driver:
        try:
            instance = driver.chromium.launch(channel="chrome", args=["--mute-audio"])
        except Exception as launch_failure:
            pytest.skip(f"no Chrome available for the browser suite: {launch_failure}")
        yield instance, served_app
        instance.close()


@contextmanager
def _page(browser, query: str = "", *, width: int = 1700, height: int = 1100):
    instance, url = browser
    page = instance.new_page(viewport={"width": width, "height": height})
    page.add_init_script("try { localStorage.setItem('rttTourSeen', '1'); } catch (e) {}")
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{url}/{query}", wait_until="networkidle")
    page.wait_for_selector(".rtt-gridcontent", timeout=15000)
    page.evaluate("document.querySelector('.rtt-tour-root')?.remove()")
    try:
        yield page, errors
    finally:
        page.close()


class TestPumpScoreModal:
    def test_tempered_pump_click_opens_the_notated_score_and_esc_stops_it(self, browser):
        with _page(browser) as (page, errors):
            page.hover('.rtt-speaker[data-audio="vectors:commas"][data-idx="0"]')
            page.wait_for_timeout(150)
            assert page.evaluate("() => typeof window.Vex") == "undefined", "vexflow must not load before the first modal open"
            page.eval_on_selector('.rtt-pump-tempered', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:t"
            page.wait_for_selector('.rtt-score-root.rtt-score-on', state="attached")
            page.wait_for_selector('.rtt-score-svg svg', state="attached")
            state = page.evaluate(
                "() => ({ vex: typeof window.Vex, caption: document.querySelector('.rtt-score-caption').textContent,"
                " bars: document.querySelectorAll('.rtt-score-svg .vf-stavenote').length,"
                " labeled: document.querySelector('.rtt-score-svg svg').textContent.includes('~1/1'), ties: document.querySelectorAll('.rtt-score-svg .rtt-score-tie').length, tieLabels: document.querySelectorAll('.rtt-score-svg .rtt-score-tie-label').length,"
                " floatShown: document.querySelector('.rtt-speaker-float').classList.contains('rtt-speaker-float-on'),"
                " suppressed: getComputedStyle(document.querySelector('.rtt-speaker-float')).display,"
                " playing: document.querySelector('.rtt-score-root').classList.contains('rtt-score-playing') })"
            )
            assert state["vex"] == "object", "the modal lazy-loads the vendored vexflow bundle"
            assert state["caption"] == "81/80 pump"
            assert state["bars"] == 4, "the default meantone pump is four whole-note chords"
            assert state["labeled"], "each bar is labelled with its tilde-prefixed interval ratio"
            assert state["ties"] == 5, "three full move-ties plus the split wrap tie's two halves"
            assert state["tieLabels"] == 4, "every root motion is labelled, the wrap included"
            assert state["suppressed"] == "none", "the modal replaces the pump float (tooltips suppressed)"
            assert state["playing"], "the play cursor rides the loop as soon as it starts"
            page.keyboard.press("Escape")
            assert not page.evaluate("() => document.body.classList.contains('rtt-score-open')")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "Esc stops the pump as it closes the modal"
            page.keyboard.press("Space")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "closing ended the pump session — Space must not resurrect it"
            assert not errors

    def test_a_state_change_refreshes_every_pump_payload_even_on_visually_unchanged_cells(self, browser):
        with _page(browser) as (page, errors):
            page.wait_for_selector("[data-pump]", state="attached")
            before = page.evaluate(
                "() => Array.from(new Set(Array.from(document.querySelectorAll('[data-pump]')).map(e => e.dataset.pump)))"
            )
            assert len(before) == 1 and '"comma":"81/80"' in before[0]
            page.click('[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input', click_count=3)
            page.keyboard.type("250/243")
            page.keyboard.press("Enter")
            page.wait_for_function(
                "(old) => { const cs = Array.from(document.querySelectorAll('[data-pump]'));"
                " return cs.length > 0 && cs.every(e => e.dataset.pump !== old); }",
                arg=before[0],
                timeout=8000,
            )
            after = page.evaluate(
                "() => Array.from(new Set(Array.from(document.querySelectorAll('[data-pump]')).map(e => e.dataset.pump)))"
            )
            assert len(after) == 1, "the mapped-comma cells still display 0 after a comma swap — their stale payload must be flushed too"
            assert not errors
