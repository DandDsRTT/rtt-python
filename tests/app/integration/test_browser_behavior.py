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
            instance = driver.chromium.launch(channel="chrome")
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
    document = editor.serialize()
    document["settings"].update({k: v for k, v in settings.items() if k != "mapping_text"})
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
        with _page(browser) as (page, errors):
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
        token = _token(mapping_text="2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}", mapping_demos=True,
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
                " if (!num) return null; const box = num.closest('.rtt-fraction-edit'); num.focus();"
                " num.dispatchEvent(new KeyboardEvent('keydown', {key: '/', bubbles: true, cancelable: true}));"
                " const den = box.querySelector('.rtt-fraction-denominator-input input');"
                " return {mode: box.dataset.fracmode, denFocused: document.activeElement === den}; }"
            )
            assert opened == {"mode": "ratio", "denFocused": True}
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

    def test_tour_ramps_from_the_simplest_chapter_through_tempering_and_back_home(self, browser):
        reads = "() => (document.querySelector('.rtt-chapter-reading') || {}).textContent === "
        has_interest = "() => !!document.querySelector('[data-eid=\"header:interest\"]')"
        demos_on = "() => document.body.classList.contains('rtt-mapping-demos')"
        with _page(browser) as (page, errors):
            assert page.evaluate(has_interest), "the default-chapter home shows intervals of interest"
            page.evaluate("() => { window.rttTour.stop(); window.rttTour.start(); }")
            page.wait_for_function(f"{reads} '2: Mappings'", timeout=6000)
            assert not page.evaluate(has_interest), "the chapter-2 tour view hides intervals of interest"
            assert page.evaluate(demos_on), "the tempering demo is armed for the hover step"

            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(150)
            page.keyboard.press("ArrowRight")
            page.wait_for_timeout(200)
            page.evaluate(
                "() => { const c = document.querySelector('[data-eid^=\"cell:comma:\"]');"
                " c.dispatchEvent(new MouseEvent('mouseover', {bubbles: true})); }"
            )
            page.wait_for_timeout(200)
            assert _overlay_texts(page) is not None, "hovering the comma mid-tour animates the mapping demo"
            mapped = page.evaluate(
                "() => [...document.querySelectorAll('[data-eid^=\"cell:mapped_comma:\"]')]"
                ".map(c => (c.getAttribute('data-value') || c.textContent).trim())"
            )
            assert any(v == "0" for v in mapped) and all(v in ("", "0") for v in mapped), (
                f"the comma vanishes — every mapped-comma generator count is zero: {mapped}"
            )

            page.keyboard.press("Escape")
            page.wait_for_function(f"{reads} '4: Exploring temperaments'", timeout=6000)
            assert page.evaluate(has_interest), "skipping out lands at the default-chapter home, interest back"
            assert not page.evaluate(demos_on), "the tour's temporary demo is reverted at the home"
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
