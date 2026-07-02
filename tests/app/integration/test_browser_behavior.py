"""Real-browser behavioral coverage for the client JS the in-process User suite cannot execute.

The render suite (test_web_render.py) asserts the Python element tree — the *server half* of every
Python<->JS seam (the data-attributes, classes and globals the scripts key off). It never runs the
scripts, so it cannot catch a regression in how the JS *consumes* that contract. These tests drive
real Chrome via Playwright and assert the scripts' observable behavior.

The headline guard is the mapping-demo overlay (assets/mapping_demo.js). It recomputes matrix
products from each value cell's number; it must read the model value (the server-stamped data-value),
never the rendered face — a stacked num-over-den fraction's textContent concatenates ("1/4" -> "14"),
the regression that motivated the data-value seam. The 4/3 = [2 -1 0] interval flowed through the
default meantone mapping [[1 1 0] [0 1 4]] gives row products (2, -1, 0) and (0, -1, 0); flowed
through the projection (whose prime entry is 1/4) the third row's product term is (1/4)*(-1) = -1/4,
which a corrupt read would turn into -14.

Opt-in, like test_browser_smoke.py: set RTT_BROWSER_SMOKE=1 (needs Chrome + playwright). The merge
gate runs them with that env set (see .github/workflows/merge-gate.yml), so client JS is gated on
every merge; a bare local `pytest` skips them.
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

_PORT = 8204
_REPO_ROOT = Path(__file__).resolve().parents[3]
_OPT_IN = "RTT_BROWSER_SMOKE"
_MINUS = "−"


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
        pytest.skip(f"real-browser behavior is opt-in: set {_OPT_IN}=1 (needs Chrome + playwright)")
    pytest.importorskip("playwright.sync_api", reason="playwright not installed for the browser suite")
    if not _port_is_free(_PORT):
        pytest.skip(f"port {_PORT} is busy; free it for the browser behavior suite")
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


def _token(**settings) -> str:
    """A ?state= token whose Show settings are turned on — the cleanest way to reach a feature state
    without driving the nested Show panel (the grid renders from the settings dict, chapter aside).
    A mapping_text key edits the temperament first (e.g. a nonstandard domain)."""
    from rtt.app.editor import Editor
    from rtt.app.page_assets import _encode_state

    editor = Editor()
    for key, value in settings.items():
        if key == "mapping_text":
            editor.try_edit_mapping_text(value)
        elif key == "interest":
            editor.set_interest_vectors(value)
    document = editor.serialize()
    reserved = ("mapping_text", "interest", "audio")
    document["settings"].update({k: v for k, v in settings.items() if k not in reserved})
    document["audio"].update(settings.get("audio", {}))
    return _encode_state(document)


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


def _overlay_texts(page):
    return page.evaluate(
        "() => { const s = document.querySelector('svg.rtt-demo-overlay');"
        " return (s && s.style.display !== 'none')"
        " ? [...s.querySelectorAll('text')].map(t => t.textContent) : null; }"
    )


class TestBrowserBehavior:
    def test_mapping_demos_toggle_gates_the_overlay(self, browser):
        with _page(browser, f"?state={_token(mapping_demos=False)}") as (page, errors):
            assert not page.evaluate("() => document.body.classList.contains('rtt-mapping-demos')")
            page.hover('[data-eid="cell:vector:targets:3:0"]')
            page.wait_for_timeout(150)
            assert _overlay_texts(page) is None, "overlay drew while mapping demos was off"
            assert not errors
        with _page(browser, f"?state={_token(mapping_demos=True)}") as (page, errors):
            assert page.evaluate("() => document.body.classList.contains('rtt-mapping-demos')")
            assert not errors

    def test_mapping_band_overlay_computes_the_row_products(self, browser):
        with _page(browser, f"?state={_token(mapping_demos=True)}") as (page, errors):
            page.hover('[data-eid="cell:vector:targets:3:0"]')
            page.wait_for_timeout(150)
            chips = _overlay_texts(page)
            assert chips, "the overlay did not draw on hovering the 4/3 interval vector"
            assert "2" in chips and f"{_MINUS}1" in chips, f"missing the mapping row products: {chips}"
            assert "14" not in chips and f"{_MINUS}14" not in chips, f"stacked-read corruption: {chips}"
            assert not errors

    def test_projection_band_reads_a_stacked_fraction_uncorrupted(self, browser):
        with _page(browser, f"?state={_token(mapping_demos=True, projection=True)}") as (page, errors):
            page.hover('[data-eid="cell:projection_targets:3:0"]')
            page.wait_for_timeout(150)
            chips = _overlay_texts(page)
            assert chips, "the overlay did not draw on hovering the projected 4/3"
            assert f"{_MINUS}1/4" in chips, f"expected the (1/4)*(-1) = -1/4 product chip; got {chips}"
            assert "14" not in chips and f"{_MINUS}14" not in chips, f"stacked-fraction read corrupted: {chips}"
            assert not errors

    def test_superspace_mapping_band_triggers_on_a_nonstandard_domain(self, browser):
        token = _token(mapping_text="2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]⧽", mapping_demos=True,
                       nonstandard_domain=True)
        with _page(browser, f"?state={token}", width=1800, height=1150) as (page, errors):
            result = page.evaluate(
                "() => { const e = [...document.querySelectorAll('[data-eid]')]"
                ".find(x => /^cell:superspace_mapping:(targets|held|interest|commas|detempering):/"
                ".test(x.getAttribute('data-eid'))); return e && e.getAttribute('data-eid'); }"
            )
            assert result, "no superspace-mapping result cell rendered for the nonstandard domain"
            page.hover(f'[data-eid="{result}"]')
            page.wait_for_timeout(200)
            chips = _overlay_texts(page)
            assert chips and "×" in chips, "the superspace-mapping band drew no overlay chips"
            assert not errors

    def test_dark_os_preference_never_flashes_light_before_reveal(self, browser):
        instance, url = browser
        page = instance.new_page(color_scheme="dark")
        try:
            page.goto(f"{url}/", wait_until="domcontentloaded")
            assert page.evaluate("() => window.__rttBootDark") is True
            assert page.evaluate(
                "() => getComputedStyle(document.documentElement).backgroundColor"
            ) == "rgb(21, 23, 26)", "the dark frame must be painted before anything renders, synchronously from the boot script in <head> — never a white first frame"
            page.wait_for_load_state("networkidle")
            page.wait_for_selector(".rtt-gridcontent", timeout=15000)
            assert page.evaluate("() => document.body.classList.contains('rtt-dark')")
            assert page.evaluate("() => document.body.classList.contains('rtt-themed')")
            assert page.evaluate("() => getComputedStyle(document.body).visibility") == "visible"
        finally:
            page.close()

    def test_light_os_preference_reveals_light_not_stuck_hidden(self, browser):
        instance, url = browser
        page = instance.new_page(color_scheme="light")
        try:
            page.goto(f"{url}/", wait_until="networkidle")
            page.wait_for_selector(".rtt-gridcontent", timeout=15000)
            assert page.evaluate("() => window.__rttBootDark") is False
            assert not page.evaluate("() => document.body.classList.contains('rtt-dark')")
            assert page.evaluate("() => document.body.classList.contains('rtt-themed')"), "a first-time light visitor must be revealed too — the seed reports light, not only dark"
            assert page.evaluate("() => getComputedStyle(document.body).visibility") == "visible"
        finally:
            page.close()

    def test_audio_mute_toggles_the_body_class(self, browser):
        with _page(browser) as (page, errors):
            page.evaluate("() => window.rttAudio.toggleMute()")
            assert page.evaluate("() => document.body.classList.contains('rtt-audio-muted')")
            page.evaluate("() => window.rttAudio.toggleMute()")
            assert not page.evaluate("() => document.body.classList.contains('rtt-audio-muted')")
            assert not errors

    def test_fraction_slash_opens_the_denominator(self, browser):
        with _page(browser, f"?state={_token(interval_ratios=True)}") as (page, errors):
            opened = page.evaluate(
                "() => { const num = document.querySelector('.rtt-fraction-numerator-input input');"
                " if (!num) return null; const field = num.closest('.rtt-fraction-edit'); num.focus();"
                " num.dispatchEvent(new KeyboardEvent('keydown', {key: '/', bubbles: true, cancelable: true}));"
                " const den = field.querySelector('.rtt-fraction-denominator-input input');"
                " return {mode: field.dataset.fracmode, denFocused: document.activeElement === den}; }"
            )
            assert opened == {"mode": "ratio", "denFocused": True}
            assert not errors

    def test_render_reconciles_a_stacked_fraction_stranded_in_ratio_mode(self, browser):
        state = _token(interval_ratios=True, interest=[(1, 0, 0), (-2, 0, 1)])
        with _page(browser, f"?state={state}") as (page, errors):
            cell = '[data-eid="interest:0"]:not(.rtt-zoom-clone)'
            stranded = page.evaluate(
                "(sel) => { const w = document.querySelector(sel);"
                " const field = w.querySelector('.rtt-fraction-edit'); field.dataset.fracmode = 'ratio';"
                " return getComputedStyle(field.querySelector('.rtt-fraction-bar')).display; }",
                cell,
            )
            assert stranded == "block", "manufactured the stranded bar over the integer's empty denominator"
            page.click('[data-eid="toggle:row:mapping"]')
            page.wait_for_function(
                "(sel) => { const w = document.querySelector(sel);"
                " const f = w && w.querySelector('.rtt-fraction-edit');"
                " return f && f.dataset.fracmode === 'int'; }",
                arg=cell,
                timeout=8000,
            )
            healed = page.evaluate(
                "(sel) => { const w = document.querySelector(sel);"
                " const field = w.querySelector('.rtt-fraction-edit');"
                " return {mode: field.dataset.fracmode,"
                " bar: getComputedStyle(field.querySelector('.rtt-fraction-bar')).display,"
                " den: w.querySelector('.rtt-fraction-denominator-input input').value}; }",
                cell,
            )
            assert healed == {"mode": "int", "bar": "none", "den": ""}, "the render reconciled it back to int"
            assert not errors

    def test_fraction_tab_and_arrows_walk_between_numerator_and_denominator(self, browser):
        with _page(browser) as (page, errors):
            num = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
            den = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
            focused = "(s) => document.activeElement === document.querySelector(s)"
            selected = "(s) => { const d = document.querySelector(s); return document.activeElement === d && d.selectionStart === 0 && d.selectionEnd === d.value.length && d.value.length > 0; }"
            page.click(num)
            page.keyboard.press("Tab")
            assert page.evaluate(selected, den), "Tab moves numerator->denominator and selects it"
            page.keyboard.press("ArrowUp")
            assert page.evaluate(focused, num), "ArrowUp moves denominator->numerator"
            page.keyboard.press("ArrowDown")
            assert page.evaluate(focused, den), "ArrowDown moves numerator->denominator"
            page.keyboard.press("Shift+Tab")
            assert page.evaluate(focused, num), "Shift+Tab moves denominator->numerator"
            assert not errors

    def test_backspacing_an_empty_denominator_collapses_up_into_the_numerator(self, browser):
        with _page(browser) as (page, errors):
            num = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
            den = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
            page.focus(den)
            page.evaluate(
                "(s) => { const d = document.querySelector(s); d.value = '';"
                " d.dispatchEvent(new Event('input', {bubbles: true})); }",
                den,
            )
            page.keyboard.press("Backspace")
            collapsed = page.evaluate(
                "(sels) => { const n = document.querySelector(sels[0]);"
                " const field = n.closest('.rtt-fraction-edit');"
                " return {numFocused: document.activeElement === n, num: n.value,"
                " mode: field.dataset.fracmode, caretAtEnd: n.selectionStart === n.value.length}; }",
                [num, den],
            )
            assert collapsed == {"numFocused": True, "num": "80", "mode": "int", "caretAtEnd": True}, collapsed
            page.keyboard.press("Backspace")
            assert page.evaluate("(s) => document.querySelector(s).value", num) == "8", "the next delete removes a numerator digit"
            page.keyboard.press("/")
            reopened = page.evaluate(
                "(sels) => { const n = document.querySelector(sels[0]), d = document.querySelector(sels[1]);"
                " return {mode: n.closest('.rtt-fraction-edit').dataset.fracmode, denFocused: document.activeElement === d}; }",
                [num, den],
            )
            assert reopened == {"mode": "ratio", "denFocused": True}, "typing / restores the vinculum view"
            assert not errors

    def test_triple_click_selects_the_whole_ratio_to_replace_it(self, browser):
        with _page(browser) as (page, errors):
            num = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
            den = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
            whole = (
                "(sels) => { const n = document.querySelector(sels[0]), d = document.querySelector(sels[1]);"
                " const lit = (i) => i.classList.contains('rtt-frac-selected') && getComputedStyle(i).backgroundImage === 'none'"
                "   && getComputedStyle(i).backgroundColor !== 'rgba(0, 0, 0, 0)';"
                " return {numSel: n.selectionStart === 0 && n.selectionEnd === n.value.length && n.value.length > 0,"
                " numLit: lit(n), denLit: lit(d), flag: n.closest('.rtt-fraction-edit').dataset.wholeSelect === '1'}; }"
            )
            page.click(num, click_count=3)
            assert page.evaluate(whole, [num, den]) == {"numSel": True, "numLit": True, "denLit": True, "flag": True}, "both parts really highlighted"
            page.keyboard.press("Shift")
            assert page.evaluate(whole, [num, den]) == {"numSel": True, "numLit": True, "denLit": True, "flag": True}, "a modifier key must not drop the whole-ratio selection"
            page.keyboard.type("5")
            replaced = page.evaluate(
                "(sels) => { const n = document.querySelector(sels[0]), d = document.querySelector(sels[1]);"
                " const field = n.closest('.rtt-fraction-edit');"
                " return {num: n.value, den: d.value, mode: field.dataset.fracmode,"
                " flag: field.dataset.wholeSelect || ''}; }",
                [num, den],
            )
            assert replaced == {"num": "5", "den": "", "mode": "int", "flag": ""}, replaced
            assert not errors

    def test_escape_reverts_a_cell_edit_instead_of_committing(self, browser):
        with _page(browser) as (page, errors):
            num = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
            den = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
            page.click(den)
            page.keyboard.type("2")
            assert page.evaluate("(s) => document.querySelector(s).value", den) != "81", "the edit changed the denominator"
            page.keyboard.press("Escape")
            page.wait_for_function("(s) => document.querySelector(s).value === '81'", arg=den, timeout=8000)
            reverted = page.evaluate(
                "(sels) => ({num: document.querySelector(sels[0]).value, den: document.querySelector(sels[1]).value,"
                " focused: document.activeElement === document.querySelector(sels[1])})",
                [num, den],
            )
            assert reverted == {"num": "80", "den": "81", "focused": False}, reverted
            mcell = '[data-eid="cell:mapping:1:2"]:not(.rtt-zoom-clone) input'
            page.click(mcell)
            page.keyboard.type("7")
            assert page.evaluate("(s) => document.querySelector(s).value", mcell) != "4", "the edit changed the mapping cell"
            page.keyboard.press("Escape")
            page.wait_for_function("(s) => document.querySelector(s).value === '4'", arg=mcell, timeout=8000)
            assert not errors

    def test_a_rejected_ratio_reselects_the_numerator_to_retype(self, browser):
        with _page(browser) as (page, errors):
            num = '[data-eid="comma:0"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input'
            page.click(num)
            page.keyboard.press("Control+a")
            page.keyboard.type("7")
            page.keyboard.press("Enter")
            page.wait_for_function(
                "(sel) => document.querySelector(sel).value === '80'", arg=num, timeout=8000
            )
            state = page.evaluate(
                "(sel) => { const n = document.querySelector(sel);"
                " return {focused: document.activeElement === n, value: n.value,"
                " selected: n.selectionStart === 0 && n.selectionEnd === n.value.length && n.value.length > 0}; }",
                num,
            )
            assert state["value"] == "80", f"the rejected 7/81 reverts to the committed 80: {state}"
            assert state["focused"] and state["selected"], f"the numerator is refocused and selected to retype: {state}"
            assert not errors

    def test_a_pending_ratio_draft_reads_blank_over_a_default_one(self, browser):
        with _page(browser, f"?state={_token(interval_ratios=True, interest=[(1, 0, 0)])}") as (page, errors):
            page.evaluate("() => document.querySelector('.rtt-hk-interest').click()")
            page.wait_for_selector('[data-eid="interest:pending"]')
            page.wait_for_timeout(200)
            draft = page.evaluate(
                "() => { const w = document.querySelector('[data-eid=\"interest:pending\"]:not(.rtt-zoom-clone)');"
                " const field = w.querySelector('.rtt-fraction-edit');"
                " const num = w.querySelector('.rtt-fraction-numerator-input input');"
                " num.focus();"
                " return {mode: field.dataset.fracmode, num: num.value,"
                " den: w.querySelector('.rtt-fraction-denominator-input input').value,"
                " bar: getComputedStyle(field.querySelector('.rtt-fraction-bar')).display}; }"
            )
            assert draft == {"mode": "ratio", "num": "", "den": "1", "bar": "block"}, "a blank numerator over a default 1, kept open even while the numerator is focused"
            page.keyboard.press("Tab")
            den = '[data-eid="interest:pending"]:not(.rtt-zoom-clone) .rtt-fraction-denominator-input input'
            assert page.evaluate("(s) => { const d = document.querySelector(s); return document.activeElement === d && d.selectionStart === 0 && d.selectionEnd === d.value.length; }", den), "Tab selects the default 1 to type over"
            assert not errors

    def test_a_reveal_under_a_still_pointer_does_not_trigger_a_remove_preview(self, browser):
        with _page(browser) as (page, errors):
            minus = '[data-eid="comma_minus:0"]'
            page.wait_for_selector(minus)
            reds = "() => document.querySelectorAll('.rtt-preview-remove').length"
            page.evaluate(
                "(sel) => { document.dispatchEvent(new PointerEvent('pointerdown', {bubbles: true}));"
                " document.querySelector(sel).dispatchEvent(new MouseEvent('mouseenter')); }",
                minus,
            )
            page.wait_for_timeout(300)
            assert page.evaluate(reds) == 0, "a minus revealed under a still pointer (no move since the press) previewed removal"
            page.evaluate(
                "(sel) => { document.dispatchEvent(new PointerEvent('pointermove', {bubbles: true}));"
                " document.querySelector(sel).dispatchEvent(new MouseEvent('mouseenter')); }",
                minus,
            )
            page.wait_for_function("() => document.querySelectorAll('.rtt-preview-remove').length > 0", timeout=8000)
            assert not errors

    def test_real_mouse_click_on_a_comma_reciprocate_flips_it(self, browser):
        with _page(browser) as (page, errors):
            rect = "() => { const op = document.querySelector("
            end = ").getBoundingClientRect(); return {x: op.x + op.width / 2, y: op.y + op.height / 2}; }"
            num = (
                "() => document.querySelector("
                "'[data-eid=\"comma:0\"]:not(.rtt-zoom-clone) .rtt-fraction-numerator-input input').value"
            )
            assert page.evaluate(num) == "80"
            cell = page.query_selector('[data-eid="comma:0"]:not(.rtt-zoom-clone)')
            box = cell.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(400)
            point = page.evaluate(
                rect + "'[data-eid=\"comma:0\"]:not(.rtt-zoom-clone) "
                ".rtt-ratio-operation-reciprocate'" + end
            )
            page.mouse.click(point["x"], point["y"])
            page.wait_for_timeout(600)
            assert page.evaluate(num) == "81", "the real click reached the op, not the cell"
            assert not errors

    def test_tab_walks_the_active_cell_along_its_matrix_orientation_line(self, browser):
        with _page(browser) as (page, errors):
            moved = page.evaluate(
                "() => { const SEL = '.rtt-cell[data-mx=\"vectors:commas\"] .rtt-cell-input-field input';"
                " const ins = [...document.querySelectorAll(SEL)].filter(i => !i.disabled && i.offsetParent);"
                " if (ins.length < 2) return null; ins[0].focus(); const before = document.activeElement;"
                " before.dispatchEvent(new KeyboardEvent('keydown', {key: 'Tab', bubbles: true, cancelable: true}));"
                " const now = document.activeElement;"
                " return now !== before && now.matches(SEL); }"
            )
            assert moved is True
            assert not errors

    def test_tab_chains_a_new_intervals_entry_numerator_denominator_then_vector(self, browser):
        # Entering an interval, Tab walks its data-entry fields in reading order — numerator ->
        # denominator -> that interval's vector cells — rather than the matrix-navigation line, which
        # would wander into unrelated tiles. Regression: the active-cell rewrite dropped this (it only
        # walked matrix lines), so Tab from a new target's numerator jumped to the mapping's quantities.
        token = _token(interval_ratios=True, interval_vectors=True, targets=True)
        with _page(browser, f"?state={token}") as (page, errors):
            page.evaluate("() => document.querySelector('[data-eid=\"target_plus\"] .rtt-glyph').click()")
            page.wait_for_selector('[data-eid="target:pending"] .rtt-fraction-numerator-input input')
            # type into the numerator, open the denominator with '/', then return focus to the numerator
            page.evaluate(
                "() => { const num = document.querySelector('[data-eid=\"target:pending\"] .rtt-fraction-numerator-input input');"
                " num.focus(); num.value = '5'; num.dispatchEvent(new Event('input', {bubbles: true}));"
                " num.dispatchEvent(new KeyboardEvent('keydown', {key: '/', bubbles: true, cancelable: true}));"
                " document.querySelector('[data-eid=\"target:pending\"] .rtt-fraction-numerator-input input').focus(); }"
            )
            where = (
                "() => { const a = document.activeElement, c = a && a.closest && a.closest('.rtt-cell');"
                " return {eid: c && c.getAttribute('data-eid'),"
                " nd: a.closest('.rtt-fraction-numerator-input') ? 'num'"
                " : (a.closest('.rtt-fraction-denominator-input') ? 'den' : '')}; }"
            )
            assert page.evaluate(where) == {"eid": "target:pending", "nd": "num"}
            page.keyboard.press("Tab")
            assert page.evaluate(where) == {"eid": "target:pending", "nd": "den"}, "Tab must step numerator -> denominator"
            page.keyboard.press("Tab")
            landed = page.evaluate(where)
            assert landed["eid"] and landed["eid"].startswith("cell:vector:targets:"), (
                f"Tab must step denominator -> the new interval's vector cells; got {landed}"
            )
            assert not errors

    def test_tour_start_builds_the_overlay_and_escape_dismisses_it(self, browser):
        with _page(browser) as (page, errors):
            started = page.evaluate(
                "() => { window.rttTour.stop(); window.rttTour.start();"
                " return {built: !!document.querySelector('.rtt-tour-root'),"
                "         title: (document.querySelector('.rtt-tour-title') || {}).textContent}; }"
            )
            assert started["built"] and started["title"]
            page.keyboard.press("Escape")
            page.wait_for_timeout(50)
            assert not page.evaluate("() => !!document.querySelector('.rtt-tour-root')")
            assert page.evaluate("() => localStorage.getItem('rttTourSeen')") == "1"
            assert not errors

    def test_tour_gates_each_do_this_step_until_the_learner_actually_does_it(self, browser):
        reads = "() => (document.querySelector('.rtt-chapter-reading') || {}).textContent === "
        titled = "() => (document.querySelector('.rtt-tour-title') || {}).textContent === "
        demos_on = "() => document.body.classList.contains('rtt-mapping-demos')"
        next_disabled = "() => { const b = document.querySelector('.rtt-tour-next'); return !!b && b.disabled; }"
        click_next = "() => document.querySelector('.rtt-tour-next').click()"
        with _page(browser) as (page, errors):
            page.evaluate("() => { window.rttTour.stop(); window.rttTour.start(); }")
            page.wait_for_function(demos_on, timeout=6000)
            assert page.evaluate(f"{reads} '2: Mappings'"), (
                "the tour teaches from the simplest chapter-2 grid; mapping demos (waited on above) is the "
                "tour-start signal now that chapter 2 is also the first-run default the reading can't flag")

            page.keyboard.press("ArrowRight")
            page.keyboard.press("ArrowRight")
            page.wait_for_function(f"{titled} 'Tempering out'", timeout=4000)
            page.wait_for_timeout(400)
            assert page.evaluate(next_disabled), "Next is blocked until the learner hovers the comma"
            page.evaluate(
                "() => { const c = document.querySelector('[data-eid^=\"cell:comma:\"]');"
                " c.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); }"
            )
            page.wait_for_function(f"() => !({next_disabled})()", timeout=4000)
            assert _overlay_texts(page) is not None, "hovering the comma animates the mapping demo"
            mapped = page.evaluate(
                "() => [...document.querySelectorAll('[data-eid^=\"cell:mapped_comma:\"]')]"
                ".map(c => (c.getAttribute('data-value') || c.textContent).trim())"
            )
            assert any(v == "0" for v in mapped) and all(v in ("", "0") for v in mapped), (
                f"the comma vanishes — every mapped-comma generator count is zero: {mapped}"
            )

            page.evaluate(click_next)
            page.wait_for_function(f"{titled} 'Try an edit'", timeout=4000)
            page.wait_for_timeout(300)
            assert page.evaluate(next_disabled), "Next is blocked until the learner edits the mapping"
            page.evaluate(
                "() => { const i = document.querySelector('.rtt-cell[data-eid^=\"cell:mapping:\"] input');"
                " i.focus(); i.value = '2'; i.dispatchEvent(new Event('input', {bubbles: true}));"
                " i.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true})); i.blur(); }"
            )
            page.wait_for_function(f"() => !({next_disabled})()", timeout=4000)

            page.evaluate(click_next)
            page.keyboard.press("ArrowRight")
            page.keyboard.press("ArrowRight")
            page.wait_for_function(f"{titled} 'Reveal more, chapter by chapter'", timeout=4000)
            page.wait_for_timeout(400)
            assert page.evaluate(next_disabled), "Next is blocked until the learner reaches chapter 4"
            rect = page.evaluate(
                "() => { const r = document.querySelector('.rtt-chapter-slider').getBoundingClientRect();"
                " return {x: r.x, y: r.y, w: r.width, h: r.height}; }"
            )
            page.mouse.click(rect["x"] + rect["w"] * 0.25, rect["y"] + rect["h"] / 2)
            page.wait_for_function(f"{reads} '4: Exploring temperaments'", timeout=6000)
            page.wait_for_function(f"() => !({next_disabled})()", timeout=4000)

            page.evaluate("() => document.querySelector('.rtt-tour-skip').click()")
            page.wait_for_function(f"{reads} '2: Mappings'", timeout=5000)
            assert not page.evaluate("() => !!document.querySelector('.rtt-tour-root')"), "skip closes the tour"
            assert not errors

    def test_active_cell_highlight_paints_only_with_an_active_cell(self, browser):
        with _page(browser) as (page, errors):
            highlighted = page.evaluate(
                "() => [...document.querySelectorAll('.rtt-gridval')]"
                ".filter(c => c.style.getPropertyValue('--rtt-hl')).length"
            )
            assert highlighted == 0, "no cell may carry the highlight before any cell is active"
            wrote = page.evaluate(
                "() => new Promise(resolve => {"
                " let count = 0;"
                " const obs = new MutationObserver(ms => ms.forEach(m => { if (m.attributeName === 'style') count++; }));"
                " document.querySelectorAll('.rtt-gridval').forEach(c => obs.observe(c, {attributes: true, attributeFilter: ['style']}));"
                " document.querySelector('.rtt-gridbody').dispatchEvent(new Event('scroll', {bubbles: true}));"
                " setTimeout(() => { obs.disconnect(); resolve(count); }, 90); })"
            )
            assert wrote == 0, f"a repaint wrote to {wrote} cells while nothing was active"
            page.hover(".rtt-gridval")
            page.wait_for_timeout(60)
            lit = page.evaluate(
                "() => [...document.querySelectorAll('.rtt-gridval')]"
                ".filter(c => c.style.getPropertyValue('--rtt-hl')).length"
            )
            assert lit > 0, "hovering a value cell must light its crosshair"
            assert not errors

    def test_arrow_key_moves_the_active_cell_and_highlights_it(self, browser):
        with _page(browser) as (page, errors):
            moved = page.evaluate(
                "() => { const cells = [...document.querySelectorAll('.rtt-app .rtt-cell.rtt-gridval')];"
                " if (cells.length < 2) return null;"
                " cells[0].dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));"
                " const first = document.querySelector('.rtt-gridval.rtt-active');"
                " document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true, cancelable: true}));"
                " const now = document.querySelector('.rtt-gridval.rtt-active');"
                " return {moved: now !== first, kbd: document.body.classList.contains('rtt-kbd'),"
                "         lit: now && now.style.getPropertyValue('--rtt-hl') === '1.000'}; }"
            )
            assert moved and moved["moved"], "ArrowDown must move the active cell to a new cell"
            assert moved["kbd"], "a keyboard move must put the grid in keyboard mode"
            assert moved["lit"], "the keyboard-moved active cell must be fully lit"
            assert not errors

    def test_moving_the_mouse_off_the_cells_hides_the_highlight_but_keyboard_resumes_from_it(self, browser):
        with _page(browser) as (page, errors):
            result = page.evaluate(
                "() => { const cells = [...document.querySelectorAll('.rtt-app .rtt-cell.rtt-gridval')];"
                " if (cells.length < 2) return null;"
                " const c = cells[0];"
                " const lit = () => [...document.querySelectorAll('.rtt-gridval')]"
                "   .filter(x => x.style.getPropertyValue('--rtt-hl')).length;"
                " c.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));"
                " const litOnHover = lit();"
                " document.body.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));"
                " const litAfterMove = lit();"
                " const activeGone = !document.querySelector('.rtt-gridval.rtt-active');"
                " const remembered = [...document.querySelectorAll('.rtt-gridval')].find(x => x.tabIndex === 0) === c;"
                " document.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowDown', bubbles: true, cancelable: true}));"
                " const afterKbd = document.querySelector('.rtt-gridval.rtt-active');"
                " const kbdCell = afterKbd, kbdLit = lit();"
                " document.body.dispatchEvent(new MouseEvent('mousemove', {bubbles: true}));"
                " const litAfterKbdMove = lit();"
                " const kbdRemembered = [...document.querySelectorAll('.rtt-gridval')].find(x => x.tabIndex === 0) === kbdCell;"
                " return {litOnHover, litAfterMove, activeGone, remembered,"
                "         moved: !!afterKbd && afterKbd !== c, resumedLit: kbdLit > 0,"
                "         litAfterKbdMove, kbdRemembered: !!kbdCell && kbdRemembered}; }"
            )
            assert result and result["litOnHover"] > 0, "hovering a value cell must light its crosshair"
            assert result["litAfterMove"] == 0, "moving the mouse off the cells must drop the hover highlight"
            assert result["activeGone"], "no cell may carry rtt-active once the mouse moves off"
            assert result["remembered"], "the left cell stays the roving-tabindex entry (remembered)"
            assert result["moved"], "a keyboard move must resume from the remembered cell, not the grid top"
            assert result["resumedLit"], "the keyboard-resumed active cell must be lit again"
            assert result["litAfterKbdMove"] == 0, "moving the mouse must also drop a KEYBOARD-set highlight"
            assert result["kbdRemembered"], "the keyboard cell stays remembered after the mouse moves off"
            assert not errors

    def test_freeze_syncs_the_frozen_header_to_horizontal_scroll(self, browser):
        with _page(browser, width=760, height=820) as (page, errors):
            synced = page.evaluate(
                "() => { const body = document.querySelector('.rtt-gridbody');"
                " if (body.scrollWidth <= body.clientWidth) return 'no-overflow';"
                " body.scrollLeft = 40; window.rttFreeze.update();"
                " return (document.querySelector('.rtt-column-head-inner') || {}).style.transform; }"
            )
            assert synced == "translateX(-40px)", f"frozen header did not track the scroll: {synced!r}"
            assert not errors

    def test_comma_pump_buttons_ride_the_comma_columns_float(self, browser):
        with _page(browser) as (page, errors):
            page.hover('.rtt-speaker[data-audio="vectors:commas"][data-idx="0"]')
            page.wait_for_timeout(150)
            float_el = page.evaluate(
                "() => { const f = document.querySelector('.rtt-speaker-float');"
                " return f && {on: f.classList.contains('rtt-speaker-float-on'),"
                "              pump: f.classList.contains('rtt-float-haspump'),"
                "              shown: getComputedStyle(f.querySelector('.rtt-pump-just')).display}; }"
            )
            assert float_el and float_el["on"], "hovering the comma column must float the speaker"
            assert float_el["pump"] and float_el["shown"] != "none", "a comma column's float offers the pump toggles"
            page.hover('.rtt-speaker[data-audio="quantities:primes"][data-idx="0"]')
            page.wait_for_timeout(150)
            assert not page.evaluate(
                "() => document.querySelector('.rtt-speaker-float').classList.contains('rtt-float-haspump')"
            ), "a prime column offers no pump"
            assert not errors

    def test_comma_pump_loops_toggle_flavors_and_die_on_mute(self, browser):
        with _page(browser) as (page, errors):
            page.hover('.rtt-speaker[data-audio="vectors:commas"][data-idx="0"]')
            page.wait_for_timeout(150)
            page.eval_on_selector('.rtt-pump-just', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:ji"
            lit = page.evaluate("() => document.querySelectorAll('.rtt-speaker[data-audio=\"vectors:commas\"].rtt-speaker-on').length")
            assert lit > 0, "the looping comma's column must stay lit"
            page.eval_on_selector('.rtt-score-modal .rtt-pump-tempered', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:t", "the modal that replaced the float swaps the loop's flavor"
            page.eval_on_selector('.rtt-score-modal .rtt-pump-tempered', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "a second click stops the loop"
            assert page.evaluate("() => document.querySelectorAll('.rtt-speaker-on').length") == 0
            page.eval_on_selector('.rtt-score-modal .rtt-pump-just', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:ji"
            page.eval_on_selector('[data-audio-control="mute"]', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "mute is the kill switch for a pump loop too"
            assert not errors

    def test_pump_sliders_render_their_ranges_and_the_engine_clamps_input(self, browser):
        with _page(browser) as (page, errors):
            assert page.evaluate("() => window.rttAudio.pumpConfig()") == {"size": 1, "type": "mixed", "tempo": 75}
            spans = page.evaluate(
                "() => [...document.querySelectorAll('.rtt-pump-slider')].map(s =>"
                " [s.getAttribute('aria-valuemin'), s.getAttribute('aria-valuemax'), s.getAttribute('aria-valuenow')])"
            )
            assert spans == [["1", "255", "75"], ["1", "4", "1"]], f"tempo slider then chord-size slider, with their ranges: {spans}"
            page.evaluate("() => { window.rttAudio.setPumpSize(3); window.rttAudio.setPumpTempo(999); }")
            assert page.evaluate("() => window.rttAudio.pumpConfig()") == {"size": 3, "type": "mixed", "tempo": 255}, \
                "the sliders' handlers feed these setters; the engine clamps tempo to its 1-255 span"
            page.evaluate("() => window.rttAudio.setPumpType('major')")
            assert page.evaluate("() => window.rttAudio.pumpConfig().type") == "major"
            page.evaluate("() => window.rttAudio.setPumpSize(2)")
            assert page.evaluate("() => window.rttAudio.pumpConfig().type") == "mixed", \
                "the type options are size-specific, so changing size resets the type to mixed"
            page.click(".rtt-hamburger")
            page.fill(".rtt-pump-tempo-input input", "110")
            page.press(".rtt-pump-tempo-input input", "Enter")
            page.wait_for_function("() => window.rttAudio.pumpConfig().tempo === 110", timeout=4000)
            page.wait_for_function(
                "() => document.querySelectorAll('.rtt-pump-slider')[0].getAttribute('aria-valuenow') === '110'",
                timeout=4000,
            )
            assert not errors, "typing a bpm steers the engine and the slider follows it"

    def test_pump_float_lights_only_the_hovered_button(self, browser):
        with _page(browser) as (page, errors):
            page.hover('.rtt-speaker[data-audio="vectors:commas"][data-idx="0"]')
            page.wait_for_timeout(150)
            page.hover('.rtt-speaker-float .rtt-pump-just')
            page.wait_for_timeout(100)
            shades = page.evaluate(
                "() => ['.rtt-float-play', '.rtt-pump-just', '.rtt-pump-tempered'].map(sel =>"
                " getComputedStyle(document.querySelector('.rtt-speaker-float ' + sel)).backgroundColor)"
            )
            assert shades[1] != shades[0] and shades[1] != shades[2], f"only the hovered pump button may light: {shades}"
            assert shades[0] == shades[2], f"the two unhovered buttons stay on the card surface: {shades}"
            box = page.locator(".rtt-speaker-float .rtt-pump-just").bounding_box()
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(400)
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:ji"
            assert page.evaluate(
                "() => document.body.classList.contains('rtt-score-open')"
            ), "a real pump click hands off from the float to the score modal"
            assert page.evaluate(
                "() => getComputedStyle(document.querySelector('.rtt-speaker-float')).display"
            ) == "none", "the modal replaces the float outright"
            assert not errors

    def test_space_pauses_and_resumes_the_last_clicked_pump(self, browser):
        with _page(browser) as (page, errors):
            page.hover('.rtt-speaker[data-audio="vectors:commas"][data-idx="0"]')
            page.wait_for_timeout(150)
            page.eval_on_selector('.rtt-pump-just', 'el => el.click()')
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:ji"
            page.keyboard.press("Space")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "Space pauses the pump instead of sounding the hovered cell on top"
            page.keyboard.press("Space")
            assert page.evaluate("() => window.rttAudio.pumpState()") == "0:ji", "Space again resumes the same loop"
            page.keyboard.press("Escape")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "Escape stops the running pump as it closes the score modal"
            page.keyboard.press("Escape")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None, "Escape never restarts it"
            assert not page.evaluate("() => window.rttAudio.pumpOwnsSpace()"), "closing the modal ends the pump session, so Space cannot resurrect it invisibly"
            page.keyboard.press("Space")
            assert page.evaluate("() => window.rttAudio.pumpState()") is None
            page.evaluate("() => window.rttAudio.pumpToggle('9', 'ji', '')")
            assert not errors


class TestAudioSettingsPersist:
    def test_a_waveform_choice_survives_a_reload(self, browser):
        with _page(browser) as (page, errors):
            assert page.evaluate("() => window.rttAudio.config().wave") == 0
            page.eval_on_selector('[data-audio-control="wave"]', "el => el.click()")
            assert page.evaluate("() => window.rttAudio.config().wave") == 1, "the click cycles the live waveform"
            page.wait_for_timeout(400)
            page.reload(wait_until="networkidle")
            page.wait_for_selector(".rtt-gridcontent", timeout=15000)
            page.wait_for_function(
                "() => window.rttAudio && window.rttAudio.config().wave === 1", timeout=5000
            )
            assert not errors

    def test_a_shared_link_restores_the_bank_and_pump_config(self, browser):
        token = _token(audio={"wave": 2, "mode": 1, "pump_tempo": 120, "muted": 1})
        with _page(browser, f"?state={token}") as (page, errors):
            page.wait_for_function(
                "() => window.rttAudio && window.rttAudio.config().wave === 2", timeout=5000
            )
            cfg = page.evaluate("() => window.rttAudio.config()")
            assert cfg["wave"] == 2 and cfg["mode"] == 1 and cfg["muted"] == 1
            assert page.evaluate("() => window.rttAudio.pumpConfig().tempo") == 120
            assert page.evaluate("() => document.body.classList.contains('rtt-audio-muted')")
            assert not errors

