"""Real-browser coverage for pasting a whole ``n/d`` (or ``w.f``) into a stacked cell's FIRST field.

Typing the separator is handled by assets/stacked_edit.js's keydown seam, which the in-process User
suite cannot execute; a paste never raises a keydown at all, so the split has its own listener. These
drive real Chrome via Playwright and assert both fields land where the typed path would put them.

Opt-in like the rest of the browser suite: set RTT_BROWSER_SMOKE=1 (needs Chrome + playwright).
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

_PORT = 8209
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
        pytest.skip(f"real-browser stacked paste is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser stacked-paste suite")
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


def _weights_token() -> str:
    from rtt.app.editor import Editor
    from rtt.app.page_assets import _encode_state

    document = Editor().serialize()
    document["settings"].update({"custom_weights": True})
    return _encode_state(document)


@contextmanager
def _page(browser, query: str = ""):
    instance, url = browser
    page = instance.new_page(viewport={"width": 1700, "height": 1100})
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


_PASTE = (
    "([sel, text]) => { const i = document.querySelector(sel); i.focus(); i.select();"
    " const carrier = new DataTransfer(); carrier.setData('text/plain', text);"
    " i.dispatchEvent(new ClipboardEvent('paste', {clipboardData: carrier, bubbles: true, cancelable: true})); }"
)
_PARTS = (
    "([firstSel, secondSel, modeAttr]) => { const f = document.querySelector(firstSel), s = document.querySelector(secondSel);"
    " const field = f.closest('.rtt-fraction-edit, .rtt-decimal-edit');"
    " return {first: f.value, second: s.value, mode: field.dataset[modeAttr], flag: field.dataset.wholeSelect || '',"
    " focused: document.activeElement === s, caret: s.selectionStart}; }"
)


class TestBrowserStackedPaste:
    _NUM = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
    _DEN = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
    _WHOLE = '[data-eid="tuning:generator:1"]:not(.rtt-zoom-clone) .rtt-decimal-whole-input input'
    _FRAC = '[data-eid="tuning:generator:1"]:not(.rtt-zoom-clone) .rtt-decimal-fraction-input input'
    _MAP = '[data-eid="cell:mapping:0:0"]:not(.rtt-zoom-clone) input'

    def _paste(self, page, selector, text):
        page.evaluate(_PASTE, [selector, text])

    def _ratio_parts(self, page):
        return page.evaluate(_PARTS, [self._NUM, self._DEN, "fracmode"])

    def test_pasting_a_ratio_into_the_numerator_splits_it_across_both_fields(self, browser):
        with _page(browser) as (page, errors):
            assert self._ratio_parts(page)["first"] == "80"
            self._paste(page, self._NUM, "2048/2025")
            parts = self._ratio_parts(page)
            assert (parts["first"], parts["second"], parts["mode"]) == ("2048", "2025", "ratio"), parts
            assert parts["focused"] and parts["caret"] == 4, parts
            assert not errors

    def test_pasting_a_plain_number_over_a_whole_selected_ratio_clears_the_denominator(self, browser):
        with _page(browser) as (page, errors):
            page.click(self._NUM, click_count=3)
            assert self._ratio_parts(page)["flag"] == "1"
            self._paste(page, self._NUM, "5")
            parts = self._ratio_parts(page)
            assert (parts["second"], parts["mode"], parts["flag"]) == ("", "int", ""), parts
            assert not errors

    def test_pasting_a_ratio_over_a_whole_selected_ratio_replaces_both_fields(self, browser):
        with _page(browser) as (page, errors):
            page.click(self._NUM, click_count=3)
            self._paste(page, self._NUM, "2048/2025")
            parts = self._ratio_parts(page)
            assert (parts["first"], parts["second"], parts["flag"]) == ("2048", "2025", ""), parts
            assert not page.evaluate("(s) => document.querySelector(s).classList.contains('rtt-frac-selected')", self._DEN)
            assert not errors

    def test_pasting_a_decimal_into_the_whole_field_splits_it_across_both_parts(self, browser):
        with _page(browser, f"?state={_weights_token()}") as (page, errors):
            parts = page.evaluate(_PARTS, [self._WHOLE, self._FRAC, "decmode"])
            assert (parts["first"], parts["second"]) == ("696", "578"), parts
            self._paste(page, self._WHOLE, "701.955")
            parts = page.evaluate(_PARTS, [self._WHOLE, self._FRAC, "decmode"])
            assert (parts["first"], parts["second"]) == ("701", "955"), parts
            assert parts["mode"] != "int", parts
            assert not errors

    def test_a_pasted_ratio_carrying_stray_whitespace_still_splits_cleanly(self, browser):
        with _page(browser) as (page, errors):
            self._paste(page, self._NUM, "  2048 / 2025\n")
            parts = self._ratio_parts(page)
            assert (parts["first"], parts["second"]) == ("2048", "2025"), parts
            assert not errors

    def test_a_pasted_ratio_commits_as_the_cells_value(self, browser):
        with _page(browser) as (page, errors):
            self._paste(page, self._NUM, "2048/2025")
            page.evaluate("() => document.activeElement.blur()")
            page.wait_for_function(
                f"() => document.querySelector('{self._MAP}').value === '2'", timeout=10000
            )
            parts = self._ratio_parts(page)
            assert (parts["first"], parts["second"], parts["mode"]) == ("2048", "2025", "ratio"), parts
            assert not errors
