import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

_PORT = 8204
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN = "RTT_BROWSER_SMOKE"

_ENGINES = ["chromium", "firefox"]
_TOLERANCE_PX = 8

_REVEAL = """() => {
  document.body.classList.remove('rtt-preload');
  document.querySelectorAll('.rtt-app').forEach((a) => { a.style.opacity = '1'; a.style.animation = 'none'; });
  if (window.rttReconcileStacked) window.rttReconcileStacked();
}"""

_MEASURE = """() => {
  const w = (sel) => { const el = document.querySelector(sel); return el ? Math.round(el.getBoundingClientRect().width) : null; };
  return {
    fieldSizingNative: CSS.supports('field-sizing', 'content'),
    fracNum: w('.rtt-fraction-numerator-input input'),
    fracDen: w('.rtt-fraction-denominator-input input'),
    decWhole: w('.rtt-decimal-whole-input input'),
  };
}"""


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
        pytest.skip(f"real-browser test is opt-in: set {_OPT_IN}=1 (needs playwright engines)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the cell-sizing test")
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


def _cell_widths(driver, engine: str, url: str) -> dict:
    launcher = getattr(driver, engine)
    launch_kwargs = {"channel": "chrome"} if engine == "chromium" else {}
    try:
        browser = launcher.launch(**launch_kwargs)
    except Exception as launch_failure:
        pytest.skip(f"{engine} engine unavailable (run `playwright install {engine}`): {launch_failure}")
    try:
        page = browser.new_page()
        page.add_init_script("try { localStorage.setItem('rttTourSeen', '1'); } catch (e) {}")
        page.goto(url, wait_until="networkidle")
        page.wait_for_selector(".rtt-fraction-numerator-input input", timeout=20000)
        page.evaluate(_REVEAL)
        page.wait_for_timeout(400)
        return page.evaluate(_MEASURE)
    finally:
        browser.close()


class TestEditableCellSizing:
    def test_firefox_hugs_editable_cell_digits_like_chromium(self, served_app):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as driver:
            widths = {engine: _cell_widths(driver, engine, served_app) for engine in _ENGINES}

        chromium, firefox = widths["chromium"], widths["firefox"]
        assert chromium["fieldSizingNative"], "chromium should size these inputs natively (the ground truth)"
        compared = 0
        for key in ("fracNum", "fracDen", "decWhole"):
            reference, actual = chromium[key], firefox[key]
            if reference is None or actual is None:
                continue
            compared += 1
            assert abs(actual - reference) <= _TOLERANCE_PX, (
                f"firefox {key} input is {actual}px but chromium sizes it to {reference}px — the "
                f"field-sizing fallback in stacked_edit.js is not hugging the digits (an un-sized "
                f"input is ~2x too wide). firefox field-sizing native={firefox['fieldSizingNative']}"
            )
        assert compared, f"no editable inputs were found to compare — selectors drifted? {chromium}"
