import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

_SMOKE_PORT = 8202
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


@pytest.fixture
def served_app():
    if os.environ.get(_OPT_IN) != "1":
        pytest.skip(f"real-browser smoke is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser smoke")
    if not _port_is_free(_SMOKE_PORT):
        pytest.skip(f"port {_SMOKE_PORT} is busy; free it for the browser smoke")
    url = f"http://127.0.0.1:{_SMOKE_PORT}"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTEST_CURRENT_TEST" and not key.startswith("NICEGUI_")
    }
    child_env["PORT"] = str(_SMOKE_PORT)
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


class TestBrowserSmoke:
    def test_real_browser_loads_the_page_and_runs_its_client_js(self, served_app):
        from playwright.sync_api import sync_playwright

        client_errors: list[str] = []
        with sync_playwright() as driver:
            try:
                browser = driver.chromium.launch(channel="chrome")
            except Exception as launch_failure:
                pytest.skip(f"no Chrome available for the browser smoke: {launch_failure}")
            page = browser.new_page()
            page.on("console", lambda m: client_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: client_errors.append(str(e)))
            page.goto(served_app, wait_until="networkidle")
            page.wait_for_selector(".rtt-gridcontent", timeout=15000)
            installed = page.evaluate(
                "() => ({"
                "  boot:    typeof window.rttBoot,"
                "  stacked: typeof window.rttStackedEditMode,"
                "  freeze:  typeof window.rttFreeze,"
                "  audio:   typeof window.rttAudio,"
                "  tour:    typeof window.rttTour,"
                "  ratioFont: window.rttFraction && window.rttFraction.ratioFont"
                "})"
            )
            browser.close()

        assert not client_errors, (
            "the page logged client-JS errors that the in-process User suite never executes: "
            f"{client_errors}"
        )
        assert installed["freeze"] != "undefined", (
            "freeze.js did not install window.rttFreeze in a real browser — the JS bundle failed to "
            f"load or threw on execution (in-process renders can't catch this). Got: {installed}"
        )
        assert installed["audio"] != "undefined" and installed["tour"] != "undefined", (
            f"a client-JS module did not install its global (bundle partially failed): {installed}"
        )
        assert installed["boot"] == "function" and installed["stacked"] == "function", (
            "a shared client-JS utility did not install — the fraction/decimal twins or the "
            f"freeze/activecell boot-retry would be dead: {installed}"
        )
        assert installed["ratioFont"], (
            "window.rttFraction.ratioFont was not stamped from the Python _RATIO_MAX_FONT, so the "
            f"ratio-view font pre-shrink falls back to its default: {installed}"
        )
