import os
import socket
import subprocess
import sys
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

_PORT = 8205
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
        pytest.skip(f"real-browser drag-select is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser drag-select suite")
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


@contextmanager
def _page(browser):
    instance, url = browser
    page = instance.new_page(viewport={"width": 1700, "height": 1100})
    page.add_init_script("try { localStorage.setItem('rttTourSeen', '1'); } catch (e) {}")
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{url}/", wait_until="networkidle")
    page.wait_for_selector(".rtt-gridcontent", timeout=15000)
    page.evaluate("document.querySelector('.rtt-tour-root')?.remove()")
    try:
        yield page, errors
    finally:
        page.close()


class TestBrowserRatioDragSelect:
    _NUM = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
    _DEN = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
    _WHOLE = (
        "(sels) => { const n = document.querySelector(sels[0]), d = document.querySelector(sels[1]);"
        " const lit = (i) => i.classList.contains('rtt-frac-selected');"
        " return {numSel: n.selectionStart === 0 && n.selectionEnd === n.value.length && n.value.length > 0,"
        " numLit: lit(n), denLit: lit(d), numFocused: document.activeElement === n,"
        " flag: n.closest('.rtt-fraction-edit').dataset.wholeSelect || ''}; }"
    )
    _PARTS = (
        "(sels) => { const n = document.querySelector(sels[0]), d = document.querySelector(sels[1]);"
        " const field = n.closest('.rtt-fraction-edit');"
        " return {num: n.value, den: d.value, mode: field.dataset.fracmode, flag: field.dataset.wholeSelect || ''}; }"
    )

    def _center(self, page, selector):
        box = page.locator(selector).bounding_box()
        return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2

    def _drag(self, page, source, target):
        sx, sy = self._center(page, source)
        tx, ty = self._center(page, target)
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(tx, ty, steps=6)
        page.mouse.up()

    def test_a_drag_from_numerator_into_denominator_selects_the_whole_ratio(self, browser):
        with _page(browser) as (page, errors):
            self._drag(page, self._NUM, self._DEN)
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state == {"numSel": True, "numLit": True, "denLit": True, "numFocused": True, "flag": "1"}, state
            page.keyboard.type("5")
            replaced = page.evaluate(self._PARTS, [self._NUM, self._DEN])
            assert replaced == {"num": "5", "den": "", "mode": "int", "flag": ""}, replaced
            box = page.locator(self._NUM).bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] + 12, steps=4)
            page.mouse.up()
            int_mode = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert int_mode["flag"] == "" and not int_mode["numLit"] and not int_mode["denLit"], int_mode
            assert not errors

    def test_a_drag_from_denominator_up_into_numerator_selects_the_whole_ratio(self, browser):
        with _page(browser) as (page, errors):
            self._drag(page, self._DEN, self._NUM)
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state == {"numSel": True, "numLit": True, "denLit": True, "numFocused": True, "flag": "1"}, state
            page.keyboard.press("Backspace")
            emptied = page.evaluate(self._PARTS, [self._NUM, self._DEN])
            assert emptied == {"num": "", "den": "", "mode": "int", "flag": ""}, emptied
            assert not errors

    def test_a_drag_across_and_back_does_not_whole_select(self, browser):
        with _page(browser) as (page, errors):
            sx, sy = self._center(page, self._NUM)
            tx, ty = self._center(page, self._DEN)
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(tx, ty, steps=4)
            page.mouse.move(sx, sy, steps=4)
            page.mouse.up()
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state["flag"] == "" and not state["numLit"] and not state["denLit"], state
            assert page.evaluate(self._PARTS, [self._NUM, self._DEN]) == {"num": "80", "den": "81", "mode": "ratio", "flag": ""}
            assert not errors

    def test_a_drag_never_whole_selects_a_half_open_denominator(self, browser):
        with _page(browser) as (page, errors):
            page.focus(self._DEN)
            page.eval_on_selector(self._DEN, "el => { el.value = ''; el.dispatchEvent(new Event('input', {bubbles: true})); }")
            opened = page.evaluate(self._PARTS, [self._NUM, self._DEN])
            assert opened == {"num": "80", "den": "", "mode": "ratio", "flag": ""}, opened
            self._drag(page, self._NUM, self._DEN)
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state["flag"] == "" and not state["numLit"] and not state["denLit"], state
            assert not errors

    def test_a_sloppy_release_just_below_the_numerator_keeps_the_partial_selection(self, browser):
        with _page(browser) as (page, errors):
            box = page.locator(self._NUM).bounding_box()
            page.mouse.move(box["x"] + 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] - 2, box["y"] + box["height"] + 3, steps=6)
            page.mouse.up()
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state["flag"] == "" and not state["numLit"] and not state["denLit"], state
            assert not errors

    def test_escape_mid_drag_disarms_the_pending_whole_select(self, browser):
        with _page(browser) as (page, errors):
            sx, sy = self._center(page, self._NUM)
            tx, ty = self._center(page, self._DEN)
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(tx, ty, steps=4)
            page.keyboard.press("Escape")
            page.mouse.up()
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state["flag"] == "" and not state["numLit"] and not state["denLit"], state
            assert page.evaluate(self._PARTS, [self._NUM, self._DEN]) == {"num": "80", "den": "81", "mode": "ratio", "flag": ""}
            assert not errors

    def test_a_drag_kept_inside_the_numerator_stays_a_native_partial_selection(self, browser):
        with _page(browser) as (page, errors):
            box = page.locator(self._NUM).bounding_box()
            y = box["y"] + box["height"] / 2
            page.mouse.move(box["x"] + 2, y)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] - 2, y, steps=6)
            page.mouse.up()
            state = page.evaluate(self._WHOLE, [self._NUM, self._DEN])
            assert state["flag"] == "" and not state["numLit"] and not state["denLit"], state
            assert state["numFocused"], state
            assert page.evaluate("(s) => { const n = document.querySelector(s); return n.selectionEnd > n.selectionStart; }", self._NUM), "the native in-input selection must survive the drag"
            den_untouched = page.evaluate(self._PARTS, [self._NUM, self._DEN])
            assert den_untouched == {"num": "80", "den": "81", "mode": "ratio", "flag": ""}, den_untouched
            assert not errors
