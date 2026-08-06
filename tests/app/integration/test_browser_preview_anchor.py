import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

_PORT = 8207
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
        pytest.skip(f"real-browser anchor suite is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser anchor suite")
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
            instance = driver.chromium.launch(channel="chrome")
        except Exception as launch_failure:
            pytest.skip(f"no Chrome available for the browser suite: {launch_failure}")
        yield instance, served_app
        instance.close()


def _all_show_token() -> str:
    from rtt.app.editor import Editor
    from rtt.app.page_assets import _encode_state

    editor = Editor()
    editor.set_all_show(True)
    return _encode_state(editor.serialize())


@contextmanager
def _page(browser):
    instance, url = browser
    page = instance.new_page(viewport={"width": 1700, "height": 1100})
    page.add_init_script("try { localStorage.setItem('rttTourSeen', '1'); } catch (e) {}")
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{url}/?state={_all_show_token()}", wait_until="networkidle")
    page.wait_for_selector(".rtt-gridcontent", timeout=15000)
    page.evaluate("document.querySelector('.rtt-tour-root')?.remove()")
    try:
        yield page, errors
    finally:
        page.close()


class TestHoverAnchor:
    def _hover_holds_still(self, page, eid):
        start = page.evaluate(
            f"(() => {{ const e = document.querySelector('[data-eid=\"{eid}\"]');"
            " const r = e.getBoundingClientRect(); window.__ev = [];"
            " e.addEventListener('mouseenter', () => window.__ev.push('enter'));"
            " e.addEventListener('mouseleave', () => window.__ev.push('leave'));"
            " return {x: r.left + r.width / 2, y: r.top + 10, left: r.left}; })()"
        )
        page.mouse.move(start["x"] - 200, start["y"] + 250)
        page.wait_for_timeout(120)
        page.mouse.move(start["x"], start["y"], steps=5)
        page.wait_for_timeout(1800)
        return start, page.evaluate(
            f"(() => {{ const e = document.querySelector('[data-eid=\"{eid}\"]');"
            "  return {left: e ? e.getBoundingClientRect().left : null,"
            "          events: window.__ev.join(','),"
            "          rings: document.querySelectorAll('.rtt-preview-remove').length}; })()"
        )

    def test_a_preview_that_inserts_a_column_never_moves_the_control_under_the_cursor(self, browser):
        with _page(browser) as (page, errors):
            start, during = self._hover_holds_still(page, "comma_minus:0")
            assert during["rings"], "the hover previews its removal"
            assert abs(during["left"] - start["left"]) < 0.5, (
                "the born generator column must grow leftward: the hovered − keeps its exact place, "
                "so the browser never fires a spurious mouseleave"
            )
            assert during["events"] == "enter", (
                "one enter and no leave — a shifted control would cycle enter/leave forever"
            )
            assert not errors

    def test_leaving_a_held_still_control_still_ends_the_preview(self, browser):
        with _page(browser) as (page, errors):
            start, _ = self._hover_holds_still(page, "comma_minus:0")
            page.mouse.move(start["x"] - 500, start["y"] + 400, steps=6)
            page.wait_for_timeout(900)
            assert page.evaluate(
                "document.querySelectorAll('.rtt-preview-remove, .rtt-preview-change').length"
            ) == 0
            assert not errors

    def test_hovering_undo_previews_the_rebirth_green_and_the_leave_reverts_it(self, browser):
        with _page(browser) as (page, errors):
            page.locator('[data-eid="target_minus:0"] .rtt-glyph').click(force=True)
            page.wait_for_timeout(1200)
            assert page.evaluate(
                "document.querySelectorAll('[data-eid^=\"target_minus:\"]').length") == 7
            undo = page.locator(".rtt-hk-undo").bounding_box()
            x, y = undo["x"] + undo["width"] / 2, undo["y"] + undo["height"] / 2
            page.mouse.move(x - 120, y + 120)
            page.wait_for_timeout(80)
            page.mouse.move(x, y, steps=5)
            page.wait_for_timeout(900)
            during = page.evaluate(
                "({greens: document.querySelectorAll('.rtt-preview-add').length,"
                "  targets: document.querySelectorAll('[data-eid^=\"target_minus:\"]').length,"
                "  undoDisabled: !!document.querySelector('.rtt-hk-undo:disabled')})"
            )
            assert during["targets"] == 8, "the undone removal's target is back in the preview"
            assert during["greens"], "...ringed green as a birth"
            assert not during["undoDisabled"], \
                "the preview must not disable undo under the cursor (a disabled button drops its own mouseleave)"
            page.mouse.move(100, 800, steps=8)
            page.wait_for_timeout(900)
            after = page.evaluate(
                "({greens: document.querySelectorAll('.rtt-preview-add').length,"
                "  targets: document.querySelectorAll('[data-eid^=\"target_minus:\"]').length})"
            )
            assert after == {"greens": 0, "targets": 7}, "leaving undo reverts the preview"
            assert not errors

    def test_garbage_typed_into_a_vector_cell_toasts_and_reverts_on_blur(self, browser):
        with _page(browser) as (page, errors):
            selector = '[data-eid="cell:vector:targets:0:1"] input'
            field = page.locator(selector).first
            original = field.input_value()
            field.click()
            field.fill("")
            field.type("4z", delay=30)
            page.evaluate(f"document.querySelector('{selector}').blur()")
            page.wait_for_timeout(1200)
            toast = page.evaluate(
                "[...document.querySelectorAll('.q-notification')].map(n => n.innerText).join('|')"
            )
            assert "whole number" in toast
            assert field.input_value() == original, "the rejected text reverts instead of sticking"
