import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

_MATRIX_PORT = 8203
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN = "RTT_BROWSER_SMOKE"
_SHOTS_DIR = Path(
    os.environ.get("RTT_BROWSER_MATRIX_DIR", str(_REPO_ROOT / ".browser-matrix"))
)

_ENGINES = ["chromium", "firefox", "webkit"]
_DESKTOP = {"label": "desktop", "viewport": {"width": 1440, "height": 900}, "mobile": False}
_MOBILE = {"label": "mobile", "device": "iPhone 13", "mobile": True}
_VIEWPORTS = [_DESKTOP, _MOBILE]


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
        pytest.skip(f"real-browser matrix is opt-in: set {_OPT_IN}=1 (needs playwright engines)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the matrix")
    if not _port_is_free(_MATRIX_PORT):
        pytest.skip(f"port {_MATRIX_PORT} is busy; free it for the browser matrix")
    url = f"http://127.0.0.1:{_MATRIX_PORT}"
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "PYTEST_CURRENT_TEST" and not key.startswith("NICEGUI_")
    }
    child_env["PORT"] = str(_MATRIX_PORT)
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


def _context_kwargs(driver, engine: str, viewport: dict) -> dict:
    if not viewport["mobile"]:
        return {"viewport": viewport["viewport"]}
    descriptor = dict(driver.devices[viewport["device"]])
    descriptor.pop("default_browser_type", None)
    if engine == "firefox":
        descriptor.pop("is_mobile", None)
        descriptor.pop("has_touch", None)
    return descriptor


class TestBrowserMatrix:
    @pytest.mark.parametrize("viewport", _VIEWPORTS, ids=lambda v: v["label"])
    @pytest.mark.parametrize("engine", _ENGINES)
    def test_renders_clean_across_engines_and_viewports(self, served_app, engine, viewport):
        from playwright.sync_api import sync_playwright

        label = f"{engine}-{viewport['label']}"
        client_errors: list[str] = []
        with sync_playwright() as driver:
            launcher = getattr(driver, engine)
            try:
                browser = launcher.launch()
            except Exception as launch_failure:
                pytest.skip(f"{engine} engine unavailable (run `playwright install {engine}`): {launch_failure}")
            context = browser.new_context(**_context_kwargs(driver, engine, viewport))
            page = context.new_page()
            page.on("console", lambda m: client_errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: client_errors.append(str(e)))
            page.goto(served_app, wait_until="networkidle")
            page.wait_for_selector(".rtt-gridcontent", timeout=20000)
            installed = page.evaluate(
                "() => ({"
                "  freeze: typeof window.rttFreeze,"
                "  audio:  typeof window.rttAudio,"
                "  tour:   typeof window.rttTour"
                "})"
            )
            _SHOTS_DIR.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(_SHOTS_DIR / f"{label}.png"))
            browser.close()

        assert not client_errors, (
            f"[{label}] the page logged client-JS errors this engine surfaces but Chrome-on-macOS "
            f"and the in-process suite never run: {client_errors}"
        )
        assert installed["freeze"] != "undefined", (
            f"[{label}] freeze.js did not install window.rttFreeze — the JS bundle failed to load or "
            f"threw on this engine. Got: {installed}"
        )
        assert installed["audio"] != "undefined" and installed["tour"] != "undefined", (
            f"[{label}] a client-JS module did not install its global on this engine: {installed}"
        )
