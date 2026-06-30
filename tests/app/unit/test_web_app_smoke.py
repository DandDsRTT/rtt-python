"""Light smoke coverage for the NiceGUI layer.

The interaction logic lives in (and is tested via) rtt.app.editor; here we only
guard that the page module imports/wires cleanly and that input parsing matches
the original app's parseInt semantics. Rendering itself is verified in a browser.
"""

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import rtt.app.app as app
from rtt.app import (
    grid_tables,
    marks,
    page_assets,
    render_html,
    service,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_text,
    tooltips,
)
from rtt.app import settings as show_settings
from rtt.app._recon_handles import CellHandles, EntityHandles
from rtt.app.editor import Editor
from rtt.app.layout import Line
from rtt.app.reconciler import _Reconciler


class _FakeElement:
    """A stand-in for a ui element with just the .delete() drop() calls."""

    def __init__(self):
        self.deleted = False

    def delete(self):
        self.deleted = True


def _bars(svg):
    """(y, height) of each chart bar in an SVG; the thin y-axis rect is excluded by width."""
    rects = re.findall(r'<rect x="[-\d.]+" y="([-\d.]+)" width="([\d.]+)" height="([-\d.]+)"', svg)
    return [(float(y), float(height)) for y, wdt, height in rects if float(wdt) > 1]


def _capture_main_run(monkeypatch, argv=("app.py",), env=None):
    """Run main() with ui.run stubbed; return the kwargs it was called with.

    PORT/STORAGE_SECRET are cleared first so a stray hosting var in the ambient
    environment can't flip the launch mode under us; `env` then sets the vars the
    test is exercising.
    """
    captured = {}
    for var in ("PORT", "STORAGE_SECRET"):
        monkeypatch.delenv(var, raising=False)
    for key, value in (env or {}).items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(sys, "argv", list(argv))
    monkeypatch.setattr(app.ui, "run", lambda **kwargs: captured.update(kwargs))
    app.main()
    return captured


def _css_rule(selector):
    """The declaration body of the first `selector { ... }` block in the page CSS."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", page_assets._CSS)
    assert m, f"no CSS rule for {selector}"
    return m.group(1)


def _z(selector):
    m = re.search(r"z-index:(\d+)", _css_rule(selector))
    assert m, f"no z-index in {selector}"
    return int(m.group(1))


def _first_font(html):
    return float(html.split("font-size:")[1].split("px")[0])


def _marked_callback_names():
    from rtt.app._editing_tuning import _TuningEdits
    from rtt.app._editing_vectors import _VectorEdits
    from rtt.app.editing import EditController, _ControlEdits
    from rtt.app.gestures import GestureController, _GestureCombine, _GestureHover

    return {
        name
        for cls in (
            EditController,
            _ControlEdits,
            _VectorEdits,
            _TuningEdits,
            GestureController,
            _GestureCombine,
            _GestureHover,
        )
        for name in dir(cls)
        if getattr(getattr(cls, name, None), "_rtt_cb", False)
    }


def _cb_stub():
    def stub(*_a, **_k):
        return None

    stub._rtt_cb = True
    return stub


class TestWebAppSmoke1:
    def test_drop_purges_a_cell_from_every_handle_store(self):
        reconciler = _Reconciler(Editor())
        reconciler.cells["scheme:primes"] = CellHandles()
        reconciler.cells["scheme:primes"].chooser.scheme_button = "the-button"
        reconciler.entities["scheme:primes"] = EntityHandles(element=_FakeElement())
        reconciler.entities["scheme:primes"].styled = "left:0"
        reconciler.entities["scheme:primes"].ring_sig = (False, False)
        reconciler.drop("scheme:primes")
        assert "scheme:primes" not in reconciler.cells
        assert "scheme:primes" not in reconciler.entities
        assert reconciler.handles("scheme:primes").chooser.scheme_button is None, "null-object, not a leaked handle"
        assert reconciler.entity("scheme:primes").element is None

    def test_handles_sentinel_reads_none_but_refuses_writes(self):
        reconciler = _Reconciler(Editor())
        assert reconciler.handles("ghost").value.input is None
        with pytest.raises(AttributeError):
            reconciler.handles("ghost").value.input = "leak"
        reconciler.cells["live"] = CellHandles()
        reconciler.cells["live"].value.input = "ok"
        assert reconciler.handles("live").value.input == "ok"

    def test_on_disconnect_cancels_the_pending_target_limit_commit(self):
        calls = []
        page = app._Page.__new__(app._Page)
        page.edits = SimpleNamespace(
            tuning=SimpleNamespace(target_limit_commit=SimpleNamespace(cancel=lambda: calls.append("cancel")))
        )
        page.gestures = SimpleNamespace(end_gesture=lambda: calls.append("end"))
        app._Page._on_disconnect(page)
        assert calls == ["cancel", "end"]

    def test_on_disconnect_with_no_pending_commit_just_ends_gestures(self):
        calls = []
        page = app._Page.__new__(app._Page)
        page.edits = SimpleNamespace(tuning=SimpleNamespace(target_limit_commit=None))
        page.gestures = SimpleNamespace(end_gesture=lambda: calls.append("end"))
        app._Page._on_disconnect(page)
        assert calls == ["end"]

    def test_app_module_exposes_entry_points(self):
        assert callable(app.index)
        assert callable(app.main)

    def test_main_runs_server_with_reload_enabled(self, monkeypatch):
        captured = _capture_main_run(monkeypatch)
        assert (captured["reload"], captured["port"], captured["show"]) == (True, 8137, False)

    def test_main_sets_browser_tab_title_and_local_favicon(self, monkeypatch):
        from nicegui import helpers
        captured = _capture_main_run(monkeypatch)
        assert captured["title"] == "D&D's RTT App"
        favicon = captured["favicon"]
        assert not favicon.startswith(("http://", "https://")), "NOT remote — that 500s /favicon.ico"
        assert helpers.is_file(favicon)
        assert Path(favicon).name == "favicon.png" and Path(favicon).parent.name == "assets"

    def test_favicon_route_returns_200_for_local_file(self, monkeypatch):
        from nicegui import core, helpers
        from nicegui.favicon import get_favicon_response
        from starlette.applications import Starlette
        from starlette.responses import FileResponse
        from starlette.testclient import TestClient

        sentinel = object()
        saved = getattr(core.app.config, "favicon", sentinel)

        def status_for(favicon):
            core.app.config.favicon = favicon
            api = Starlette()
            if helpers.is_file(core.app.config.favicon):
                api.add_route("/favicon.ico", lambda _: FileResponse(core.app.config.favicon))
            else:
                api.add_route("/favicon.ico", lambda _: get_favicon_response())
            client = TestClient(api, raise_server_exceptions=False)
            return client.get("/favicon.ico").status_code

        try:
            assert status_for(_capture_main_run(monkeypatch)["favicon"]) == 200
            assert status_for("https://github.com/DandDsRTT.png") == 500, "the old remote URL: the bug"
        finally:
            if saved is sentinel:
                del core.app.config.favicon
            else:
                core.app.config.favicon = saved

    def test_main_production_launch_when_platform_sets_port(self, monkeypatch):
        captured = _capture_main_run(monkeypatch, env={"PORT": "10000"})
        assert (captured["reload"], captured["port"], captured["show"], captured["host"]) \
            == (False, 10000, False, "0.0.0.0")
        assert "uvicorn_reload_excludes" not in captured

    def test_main_takes_session_secret_from_env_with_a_local_fallback(self, monkeypatch):
        assert _capture_main_run(monkeypatch, env={"STORAGE_SECRET": "from-the-platform"})[
            "storage_secret"] == "from-the-platform"
        assert _capture_main_run(monkeypatch)["storage_secret"] == page_assets._STORAGE_SECRET

    def test_main_passes_crash_safe_reload_excludes(self, monkeypatch):
        captured = _capture_main_run(monkeypatch)
        excludes = [e.strip() for e in captured["uvicorn_reload_excludes"].split(",")]
        for default in (".*", ".py[cod]", ".sw.*", "~*"):
            assert default in excludes
        for e in excludes:
            if Path(e).is_absolute():
                assert Path(e).is_dir(), f"absolute exclude {e!r} must be an existing dir (else Py3.14 glob crash)"
        worktrees = Path(app.__file__).resolve().parents[2] / ".claude" / "worktrees"
        assert (str(worktrees) in excludes) == worktrees.is_dir()

    def test_main_watches_assets_so_js_and_css_edits_hot_reload(self, monkeypatch):
        captured = _capture_main_run(monkeypatch)
        includes = [p.strip() for p in captured["uvicorn_reload_includes"].split(",")]
        for pat in ("*.py", "*.css", "*.js"):
            assert pat in includes, f"{pat} not watched for reload"

    def test_reload_excludes_omits_worktrees_when_missing(self, tmp_path):
        missing = tmp_path / ".claude" / "worktrees"
        excludes = [e.strip() for e in app._reload_excludes(missing).split(",")]
        assert str(missing) not in excludes
        for default in (".*", ".py[cod]", ".sw.*", "~*"):
            assert default in excludes

    def test_reload_excludes_filter_skips_worktrees_but_reloads_source(self, tmp_path):
        from uvicorn.config import Config
        from uvicorn.supervisors.watchfilesreload import FileFilter

        repo = tmp_path
        worktrees = repo / ".claude" / "worktrees"
        (worktrees / "wt1" / "rtt" / "web").mkdir(parents=True)
        (repo / "rtt" / "web").mkdir(parents=True)

        excludes = [e.strip() for e in app._reload_excludes(worktrees).split(",")] + [sys.prefix]
        config = Config("rtt.app.app:app", reload=True, reload_includes=["*.py", "*.css", "*.js"],
                        reload_excludes=excludes, reload_dirs=[str(repo)])
        file_filter = FileFilter(config)

        assert file_filter(worktrees / "wt1" / "rtt" / "web" / "app.py") is False
        assert file_filter(repo / "rtt" / "web" / "app.py") is True
        assert file_filter(worktrees / "wt1" / "rtt" / "web" / "audio.js") is False
        assert file_filter(repo / "rtt" / "web" / "audio.js") is True

    def test_parse_int_accepts_integers_and_rejects_partial_input(self):
        assert render_html._parse_int("5") == 5
        assert render_html._parse_int("-4") == -4
        assert render_html._parse_int("  3 ") == 3
        assert render_html._parse_int("") is None
        assert render_html._parse_int("-") is None
        assert render_html._parse_int("x") is None
        assert render_html._parse_int(None) is None

    def test_ratio_parts_splits_fractions_and_passes_through_non_fractions(self):
        assert render_html._ratio_parts("3/2") == ("3", "2")
        assert render_html._ratio_parts("2/1") == ("2", "1")
        assert render_html._ratio_parts("5") is None, "a bare integer is not a fraction"
        assert render_html._ratio_parts("") is None

    def test_cents_parts_splits_whole_and_fraction_for_decimal_alignment(self):
        assert render_html._cents_parts("1899.26") == ("1899", "26")
        assert render_html._cents_parts("-2.69") == ("-2", "69")
        assert render_html._cents_parts("0.00") == ("0", "00")
        assert render_html._cents_parts("5") == ("5", "")

    def test_power_parts_annotates_infinity_as_max(self):
        assert render_html._power_parts("∞") == ("∞", "(max)")
        assert render_html._power_parts("2") == ("2", "")
        assert render_html._power_parts("1") == ("1", "")

    def test_underline_html_wraps_only_the_marked_spans(self):
        assert render_html._underline_html("tuning map", ()) == "tuning map"
        assert render_html._underline_html("tuning map", ((0, 1),)) == "<u>t</u>uning map"
        assert render_html._underline_html("(temperament) mapping", ((14, 1),)) == "(temperament) <u>m</u>apping"
        assert render_html._underline_html("just tuning map", ((0, 1),)) == '<u class="rtt-desc">j</u>ust tuning map', "a descender letter (g/j/p/q/y) is tagged so only its underline drops below the # tail; non-descenders keep the normal snug underline"

    def test_math_html_maps_each_block_to_its_weight_and_slant(self):
        bold, bold_italic, italic = (True, False), (True, True), (False, True)
        for glyph, base, (want_bold, want_italic) in [
            ("𝐚", "a", bold), ("𝟎", "0", bold),
            ("𝒕", "t", bold_italic), ("𝒈", "g", bold_italic),
            ("𝑀", "M", italic),
        ]:
            html = render_html._math_html(glyph)
            assert f">{base}</span>" in html, glyph
            assert ("font-weight:700" in html) is want_bold, glyph
            assert ("font-style:italic" in html) is want_italic, glyph
        assert render_html._math_html("Y") == "Y"

    def test_math_html_styles_products_per_letter_and_honours_the_subscript_sentinels(self):
        assert render_html._math_html("𝒕C") == render_html._math_html("𝒕") + "C"
        assert render_html._math_html(" = 𝒈𝑀") == " = " + render_html._math_html("𝒈") + render_html._math_html("𝑀")
        assert render_html._math_html(grid_tables.NORM_SUB_OPEN + "q" + grid_tables.NORM_SUB_CLOSE) == \
            '<sub style="font-style:italic">q</sub>'
        plain = render_html._math_html(grid_tables.SUB_OPEN + "dual(𝑞)" + grid_tables.SUB_CLOSE)
        assert plain.startswith("<sub>dual(") and plain.endswith(")</sub>") and "font-style:italic" in plain

    def test_ebk_marks_share_one_colour_and_map_one_to_one_to_their_cell(self):
        mark_svgs = {
            "[": marks.square_bracket(16, 16, "left"),
            "]2": marks.square_bracket(16, 60, "right"),
            "<": marks.angle_bracket(16, 16),
            "top": marks.top_bracket(120, 9),
            "angle": marks.angle_foot(14, 7),
            "vbar": marks.vbar(2, 60),
        }
        for svg in mark_svgs.values():
            assert svg.startswith("<svg") and f'fill="{marks.BR_COLOR}"' in svg
            assert "stroke-width" not in svg, "weight is the 1:1 viewBox, not a scaling stroke"
        assert mark_svgs["angle"].count("<path") == 1 and "stroke" not in mark_svgs["angle"]
        import re
        ys = [float(y) for _x, y in re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", marks.angle_foot(14, 7))]
        assert 0 <= min(ys) and max(ys) <= 7
        def _viewbox(svg):
            m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
            return float(m.group(1)), float(m.group(2))
        assert _viewbox(mark_svgs["["]) == (16, 16)
        assert _viewbox(mark_svgs["]2"]) == (16, 60), "1 row vs many: same generator, viewBox == the cell box"

    def test_units_html_bolds_variables_but_not_cents_oct_or_slash(self):
        assert render_html._units_html("units: g/p") == '<span class="rtt-units-pre">units: </span><b>g</b>/<b>p</b>', "the variable symbols (g, p, b, the placeholder 1, with subscripts) are bold; the # units of interval size — the cent sign ¢ and the spelled-out 'oct' (octaves) — and # the '/' separator stay un-bold, consistently in the per-box line and the units # row/col. A per-box line also keeps 'units:' in the serif label face. # a per-box line keeps 'units:' in the serif label face and bolds its variables"
        for text, bolded, bare in [
            ("units: ¢/g", ["g"], ["¢", "/"]),
            ("units: oct/p", ["p"], ["oct", "/"]),
            ("units: ¢", [], ["¢"]),
            ("g₁/", ["g₁"], ["/"]),
            ("/p₁", ["p₁"], ["/"]),
            ("/1", ["1"], ["/"]),
            ("oct/", [], ["oct", "/"]),
        ]:
            html = render_html._units_html(text)
            for v in bolded:
                assert f"<b>{v}</b>" in html, (text, v)
            for u in bare:
                assert u in html and f"<b>{u}</b>" not in html, (text, u)

    def test_line_style_centres_the_rule_on_its_coordinate(self):
        half = spreadsheet_constants.LINE_WIDTH / 2
        v = render_html._line_style(Line("trunk:x", "v", 100, 50, 200))
        assert f"transform:translate({100 - half}px,50px)" in v
        assert "height:200px" in v and "left:0; top:0" in v
        height = render_html._line_style(Line("h:x", "h", 60, 10, 300))
        assert f"transform:translate(10px,{60 - half}px)" in height
        assert "width:300px" in height and "left:0; top:0" in height

    def test_line_style_dots_a_collapsed_bands_rule_and_restores_it_when_open(self):
        v_dotted = render_html._line_style(Line("trunk:x", "v", 100, 0, 50, dotted=True))
        assert "border-left-color:transparent" in v_dotted and "repeating-linear-gradient(to bottom," in v_dotted
        assert "border-box" in v_dotted, "painted over the border box -- the box has no width of its own, only the border, so # without this the gradient fills the zero-width content box and the dots never show"
        v_solid = render_html._line_style(Line("trunk:x", "v", 100, 0, 50))
        assert "border-left-color:var(--c-gridline)" in v_solid and "background:none" in v_solid
        h_dotted = render_html._line_style(Line("h:x", "h", 60, 0, 50, dotted=True))
        assert "border-top-color:transparent" in h_dotted and "repeating-linear-gradient(to right," in h_dotted
        h_solid = render_html._line_style(Line("h:x", "h", 60, 0, 50))
        assert "border-top-color:var(--c-gridline)" in h_solid and "background:none" in h_solid
        assert f"transparent {spreadsheet_constants.LINE_WIDTH}px {render_html._DOT_PITCH}px" in v_dotted
        assert render_html._DOT_PITCH >= 3 * spreadsheet_constants.LINE_WIDTH

    def test_shared_axis_gridlines_render_two_pixels_thick(self):
        assert spreadsheet_constants.LINE_WIDTH == 2, "the shared coordinate axes (.rtt-line, the rules the cells sit on, threading the # gaps between tiles) are the board's gridlines; doubled from 1px to 2px so they read # clearly. Both orientations carry the same #e0e0e0 weight"
        assert f"--line-w:{spreadsheet_constants.LINE_WIDTH}px" in page_assets._CSS
        assert "--c-gridline:#e0e0e0" in page_assets._CSS, "the gridline colour, set in :root so dark mode can retint it"
        assert "border-left:var(--line-w) solid var(--c-gridline)" in page_assets._CSS
        assert "border-top:var(--line-w) solid var(--c-gridline)" in page_assets._CSS

    def test_columnfill_bounce_layer_sits_behind_the_scroller_carries_no_zindex_and_hugs_the_body_inset(self):
        fill = _css_rule(".rtt-column-fill")
        assert "z-index" not in fill
        assert "pointer-events:none" in fill
        assert "left:var(--pad)" in fill and "bottom:0" in fill

    def test_columnfill_is_visible_on_desktop_so_the_top_bounce_bridge_shows_and_hidden_only_on_touch(self):
        assert "visibility:hidden" not in _css_rule(".rtt-column-fill"), "desktop keeps its bounce and pins scrollTop at 0 through it, so the bridge shows only by being # visible at rest (no scroll signal marks the bounce, hence no scrollTop<0 overpull gate); touch # removes the bounce, so the bridge never bares and is hidden there to kill the iOS late-sync echo"
        assert ".rtt-app.rtt-overpull-y" not in page_assets._CSS
        assert "rtt-overpull-y" not in page_assets._FREEZE_JS
        touch = re.search(r"@media \(hover: none\) and \(pointer: coarse\) \{(.*?\.rtt-column-fill[^}]*\})\s*\}",
                          page_assets._CSS, re.S)
        assert touch and re.search(r"\.rtt-column-fill\s*\{[^}]*visibility:hidden", touch.group(1))


class TestWebAppSmoke2:
    def test_rowfill_mirrors_columnfill_for_the_sticky_row_bands_top_overpull_gap(self):
        fill = _css_rule(".rtt-rowfill")
        assert "left:var(--pad)" in fill and "bottom:0" in fill
        assert "background:#c0c0c0" in fill
        assert "box-shadow:1px 0 0 var(--seam-x,transparent)" in fill
        assert "z-index" not in fill, "behind the body, like columnfill, so the row band covers it at rest"
        assert ".rtt-app.rtt-scrolled-x .rtt-rowfill" in page_assets._CSS

    def test_touch_devices_damp_the_overscroll_bounce_so_the_grid_does_not_rubber_band(self):
        assert "@media (hover: none) and (pointer: coarse)" in page_assets._CSS, "the bounce-zone gridline echo and the collapse-all/row-toggle float are both artifacts of the # elastic overscroll; on touch devices we remove the bounce so neither can occur. It must be # overscroll-behavior:none (contain only stops chaining, keeping the bounce), and scoped to a # coarse-pointer/no-hover device so desktop keeps its bounce and the columnfill/rowfill bridges"
        touch = re.search(r"@media \(hover: none\) and \(pointer: coarse\) \{(.*?\})\s*\}", page_assets._CSS, re.S)
        assert touch and ".rtt-gridbody" in touch.group(1) and "overscroll-behavior:none" in touch.group(1)

    def test_only_full_height_seam_reaching_column_rules_are_twinned_in_the_columnfill_not_centre_stubs(self):
        layout = Editor().layout()
        fy = layout.freeze_y
        twinned = {line.id for line in layout.lines if line.orientation == "v" and line.start <= fy and line.length > fy}
        assert {"v:generator:0", "v:prime:0", "v:comma:0", "v:target:0"} <= twinned
        assert "trunk:generators" not in twinned

    def test_temperament_divider_headers_read_as_centred_grey_rules_inset_like_the_items(self):
        label = _css_rule(".rtt-select-popup .q-item.disabled .q-item__label")
        assert "justify-content:center" in label
        assert "color:#777" in label
        assert "padding-left:0" not in page_assets._CSS, "the divider does NOT zero its padding -> its rules align with the item text, not the edges"
        assert ".q-item.disabled .q-item__label::before" in page_assets._CSS
        assert "border-top:1px solid #777" in page_assets._CSS

    def test_sidebar_hugs_its_content_as_a_fixed_left_column(self):
        rule = _css_rule(".rtt-panelgroup")
        assert "flex:none" in rule
        assert "position:sticky" not in rule
        drawer = _css_rule(".rtt-drawer")
        assert "grid-template-rows:0fr" in drawer, "collapsed -> zero height, so the sidebar hugs the chrome"
        assert "align-self:flex-start" in drawer

    def test_opening_widens_the_single_sidebar_so_the_tab_becomes_the_pane(self):
        pg = _css_rule(".rtt-panelgroup")
        assert "flex-direction:column" in pg
        assert "width:var(--tab-w)" in pg
        assert "transition:width" in pg
        assert "width:var(--panel-w)" in _css_rule(".rtt-panelgroup.rtt-open")

    def test_the_chrome_pins_the_hamburger_and_swings_the_title_upright(self):
        assert "position:absolute" in _css_rule(".rtt-hamburger"), "The chrome is ONE hamburger + ONE title that morph in place (no second copy swapped in). The # hamburger is absolutely pinned, so opening never reflows it out from under the cursor; the title # swings via an animated transform from a quarter-turn (down the closed tab) to upright (across the # open bar)"
        title = _css_rule(".rtt-sidetitle")
        assert "position:absolute" in title
        assert "rotate(90deg)" in title
        assert "transition" in title and "transform" in title
        assert "rotate(0deg)" in _css_rule(".rtt-panelgroup.rtt-open .rtt-sidetitle")

    def test_titles_freeze_outside_or_sticky_within_the_body_scroller(self):
        assert "position:sticky" in _css_rule(".rtt-rowband") and "left:0" in _css_rule(".rtt-rowband"), "The frozen titles sit so the body's scrollbars stop at them. The row band freezes by # position:sticky to the left of the body scroller; the column-title strip and the corner sit # OUTSIDE the scroller (position:absolute on the pane), so the body's vertical scrollbar starts # below the strip. They stack above the body, the corner above both edges"
        assert "position:absolute" in _css_rule(".rtt-column-head")
        assert "position:absolute" in _css_rule(".rtt-corner")
        assert _z(".rtt-cell") < _z(".rtt-column-head") < _z(".rtt-rowband") < _z(".rtt-corner")

    def test_grid_body_reserves_its_grey_margin_as_scroll_padding(self):
        rule = _css_rule(".rtt-gridbody")
        assert "padding:0 var(--pad) var(--pad) 0" in rule
        assert f"--pad:{page_assets._PAD}px" in page_assets._CSS

    def test_shell_fixes_the_app_to_the_window_framed_by_a_white_margin(self):
        rule = _css_rule(".rtt-shell")
        assert "position:fixed" in rule
        for edge in ("top:6px", "left:6px", "right:6px", "bottom:6px"):
            assert edge in rule, edge

    def test_settings_pane_stacks_a_frozen_header_over_a_scrolling_body(self):
        inner = _css_rule(".rtt-drawer-inner")
        assert "display:flex" in inner and "flex-direction:column" in inner
        assert "padding-top:var(--pad)" in inner, "the settings content is inset from the top by the SAME _PAD the grid pane insets its column- # header band, so the settings frozen header lines up with the main app's header (not 12px above)"
        assert "flex:none" in _css_rule(".rtt-show-frozen")
        body = _css_rule(".rtt-show-scroll")
        assert "flex:none" in body and "overflow-y:auto" in body
        assert "flex:1" not in body, "NOT the flex-fill hug that rounded a hair short and scrolled"

    def test_settings_frozen_seam_sits_below_the_header_not_inside_it(self):
        assert "border-bottom:1px solid #c4c4c4" in _css_rule(".rtt-show-frozen")
        assert "border-bottom" not in _css_rule(".rtt-show-all")

    def test_row_band_wrapper_passes_clicks_through_and_the_strip_clips(self):
        assert "pointer-events:none" in _css_rule(".rtt-band"), "the row band rides a full-height .rtt-band wrapper that lets clicks fall through to the body # (pointer-events:none); the sticky inner re-enables them and is opaque #c0c0c0, so the body is # hidden behind the row titles as it scrolls under them. The column strip clips its translated # inner (overflow:hidden) so titles scrolled off the left don't spill over the corner / sidebar"
        assert "pointer-events:auto" in page_assets._CSS
        assert "overflow:hidden" in _css_rule(".rtt-column-head")

    def test_grid_scrolls_in_its_own_body_pane_not_the_page(self):
        assert "overflow:auto" in _css_rule(".rtt-gridbody"), "the grid scrolls inside .rtt-gridbody (overflow:auto) — its own pane, within the grid region # .rtt-app. .rtt-app hugs the grid (flex:0 1 auto — shrinks to the room left of the sidebar # rather than filling it) and only clips (overflow:hidden), hosting the absolutely-placed frozen # regions; the page never scrolls. So a grid bigger than the pane scrolls in the body, scrollbars # bounded there, right of the sidebar"
        app_rule = _css_rule(".rtt-app")
        assert "overflow:hidden" in app_rule and "position:relative" in app_rule, "the region, not the scroller"
        assert "flex:0 1 auto" in app_rule and "min-width:0" in app_rule

    def test_panes_hug_their_content_and_cap_at_the_window(self):
        assert "align-items:flex-start" in _css_rule(".rtt-shell"), "both panes size to their content (under the shell's align-items:flex-start) so their grey # backdrops don't stretch into empty space — white body shows beyond the shorter one. Each caps # at the window before scrolling internally: the grid pane via max-width/max-height (flex-shrinking # to the room left of the sidebar), the settings pane via the drawer-inner's max-height"
        app_rule = _css_rule(".rtt-app")
        assert "max-width:100%" in app_rule and "max-height:100%" in app_rule

    def test_seam_appears_only_when_the_body_is_scrolled(self):
        css = page_assets._CSS
        columnhead, rowband = _css_rule(".rtt-column-head"), _css_rule(".rtt-rowband")
        assert "box-shadow:0 1px 0 var(--seam-y" in columnhead
        assert "border-bottom" not in columnhead, "NOT a layout-reserving border"
        assert "box-shadow:1px 0 0 var(--seam-x" in rowband
        assert "border-right" not in rowband
        assert ".rtt-app.rtt-scrolled-y .rtt-column-head" in css and "--seam-y:var(--seam)" in css
        assert ".rtt-app.rtt-scrolled-x .rtt-rowband" in css and "--seam-x:var(--seam)" in css
        assert f"--seam:{page_assets._SEAM}" in css

    def test_block_panes_routes_a_wash_into_every_frozen_pane_its_rect_crosses(self):
        from rtt.app.layout import Block
        fx, fy = 144.0, 68.0
        inside = Block("b", 200, 200, 50, 50)
        over_top = Block("b", 200, 62, 50, 64)
        over_left = Block("b", 138, 200, 50, 50)
        over_corner = Block("b", 138, 62, 50, 64)
        assert render_html._block_panes(inside, fx, fy) == ("body",)
        assert render_html._block_panes(over_top, fx, fy) == ("body", "col")
        assert render_html._block_panes(over_left, fx, fy) == ("body", "row")
        assert render_html._block_panes(over_corner, fx, fy) == ("body", "col", "row", "corner")

    def test_frozen_wash_copies_show_only_at_rest_dropping_once_the_body_scrolls(self):
        css = page_assets._CSS
        for selection in (".rtt-app.rtt-scrolled-y .rtt-column-head .rtt-wash",
                    ".rtt-app.rtt-scrolled-y .rtt-column-head .rtt-washbase",
                    ".rtt-app.rtt-scrolled-x .rtt-rowband .rtt-wash",
                    ".rtt-app.rtt-scrolled-x .rtt-rowband .rtt-washbase"):
            assert selection in css
        m = re.search(r"rtt-scrolled-y \.rtt-column-head \.rtt-wash[\s\S]*?\{([^}]*)\}", css)
        assert m and "display:none" in m.group(1), "the copies are dropped, not merely restyled"

    def test_freeze_script_syncs_the_column_strip_and_toggles_the_seam_on_body_scroll(self):
        js = page_assets._FREEZE_JS
        assert ".rtt-gridbody" in js
        assert "scrollTop" in js and "scrollLeft" in js
        assert ".rtt-column-head-inner" in js and "translateX" in js
        assert ".rtt-column-fill-inner" in js
        assert "rtt-scrolled-x" in js and "rtt-scrolled-y" in js
        assert "addEventListener('scroll'" in js
        assert "ResizeObserver" not in js and "scroll-timeline" not in js
        assert "Math.max(0, b.scrollTop)" in js, "Only the VERTICAL twin offset is clamped non-negative. iOS WebKit reports scrollTop negative # through a top overscroll (desktop holds it at 0), so clamping keeps the columnfill twins put to # bridge the bared strip; the horizontal axis must track raw scroll so the twins stay glued under # their columns — clamping X ghosts a second set of verticals on a left overscroll"
        assert "-b.scrollLeft" in js
        assert "Math.max(0, b.scrollLeft)" not in js

    def test_frozen_strips_are_promoted_to_a_layer_only_while_scrolling(self):
        assert "will-change" not in _css_rule(".rtt-column-head-inner"), "no PERMANENT compositor layer: a constant will-change keeps the frozen strip on its own GPU # layer at rest, which a browser page-zoom re-rasters out of sync with the body (the column # titles trail the grid). Promotion is confined to active scroll instead"
        assert "will-change" not in _css_rule(".rtt-column-fill-inner")
        scrolling = _css_rule(".rtt-app.rtt-scrolling .rtt-column-head-inner,\n.rtt-app.rtt-scrolling .rtt-column-fill-inner")
        assert "will-change:transform" in scrolling
        js = page_assets._FREEZE_JS
        assert "rtt-scrolling" in js
        assert "classList.add('rtt-scrolling')" in js and "remove('rtt-scrolling')" in js
        assert "setTimeout" in js, "cleared a short idle after the last scroll, not on every frame"

    def test_zoom_freezes_animations_for_a_beat_so_the_grid_rescales_as_one(self):
        assert "--t:0s" in _css_rule("body.rtt-zoom-freeze"), "rtt-zoom-freeze zeroes the transition var like rtt-no-anim, but as its OWN class so a zoom # snaps the grid without disturbing the user's animations toggle"
        js = page_assets._FREEZE_JS
        assert "addEventListener('keydown'" in js and "addEventListener('wheel'" in js, "armed on the zoom GESTURE (Ctrl/Cmd +/-/0 keydown, Ctrl+wheel) — which fires BEFORE the browser # rescales — not on the resize after, by when the staggered frame is already painted. A View-menu zoom # has no such pre-paint signal and is deliberately not covered"
        assert "ctrlKey" in js and "metaKey" in js
        assert "rtt-zoom-freeze" in js
        assert "classList.add('rtt-zoom-freeze')" in js and "remove('rtt-zoom-freeze')" in js
        assert "setTimeout" in js, "held a beat past the last gesture, then removed to restore the animations toggle"

    def test_freeze_script_reserves_a_scrollbar_so_one_bar_never_forces_a_second(self):
        js = page_assets._FREEZE_JS
        assert "fit" in js
        assert "data-base" in js or "baseW" in js
        assert "paddingRight" in js and "paddingBottom" in js, "drops the cross-axis margin if maxed"
        assert "offsetWidth" in js and "clientWidth" in js
        assert "ResizeObserver" not in js and "scroll-timeline" not in js

    def test_tooltip_dismiss_script_drops_hover_help_before_a_reflow(self):
        js = page_assets._TOOLTIP_DISMISS_JS
        assert "__rttTipDismiss" in js, "guarded so it installs only once"
        assert "addEventListener('pointerdown'" in js and ", true)" in js
        assert "keydown" in js and "wheel" in js
        assert ":hover" in js and ".q-tooltip" in js
        assert "mouseleave" in js and "dispatchEvent" in js
        assert "parentElement" in js
        assert "blur" not in js

    def test_every_show_toggle_has_a_non_empty_example(self):
        for group_name, items in show_settings.SHOW_GROUPS:
            for key, _l, _d in items:
                if group_name == "general":
                    assert render_html._general_part_html(key).strip(), f"no tile sample for {key}"
                elif key in show_settings.GROUPING_PARENTS:
                    assert render_html._example_html(key) == "", f"grouping parent {key} should have a blank example"
                else:
                    assert render_html._example_html(key).strip(), f"no example for {key}"

    def test_interface_behaviours_are_the_visual_settings_box_toggles_default_on_ch2(self):
        keys = ("animations", "preview_highlighting", "tooltips")
        assert [k for k, *_ in show_settings.VISUAL_TOGGLES] == list(keys)
        grouped = {k for _, items in show_settings.SHOW_GROUPS for k, *_ in items}
        for key in keys:
            assert key not in grouped
            assert show_settings.DEFAULTS[key] is True
            assert key in show_settings.IMPLEMENTED
            assert show_settings.CHAPTER[key] == 2
            assert show_settings.reveal_chapter(key) == 2
            assert key not in show_settings.SUBCONTROLS

    def test_example_html_renders_each_specific_groups_special_sample_kind(self):
        for key, letter, group in (("temperament_colorization", "𝑀", "temperament"),
                                   ("tuning_colorization", "𝐺", "tuning"),
                                   ("form_colorization", "𝐹", "form")):
            html = render_html._example_html(key)
            assert f"--wash-{group}" in html, "the swatch rides the group's wash variable (so it"
            assert render_html._math_html(letter) in html
        assert "<svg" in render_html._example_html("tuning_ranges")

    def test_audio_bank_leads_with_a_mute_kill_switch_defaulting_to_on(self):
        assert [control for control, *_ in page_assets._AUDIO_BANK] == ["mute", "wave", "mode", "hold", "root"], "the bank's first control is mute: it doubles as the kill switch (its engine fn stops all # audio) and the engage gate (muting is what blocks a clicked cell from sounding). Audio now # starts ON (unmuted), so the bank shows the plain (volume_up) glyph; muting shows the slash"
        assert page_assets._AUDIO_BANK[0][2] == "toggleMute"
        mute_up, mute_off = page_assets._AUDIO_GLYPHS["mute"]
        assert "volume_up" in mute_up and "volume_off" in mute_off
        assert page_assets._AUDIO_BANK[0][1] == mute_up

    def test_general_tile_renders_its_special_samples(self):
        assert "<svg" in render_html._general_part_html("gridded_values")
        assert "border" in render_html._general_part_html("gridded_values")
        assert "log" in render_html._general_part_html("math_expressions")
        assert "=" in render_html._general_part_html("math_expressions"), "the '=' belongs to the math EXPRESSION, not the numeric value (so it shows only with the form)"
        assert "=" not in re.sub(r"<[^>]+>", "", render_html._general_part_html("quantities"))
        assert 'font-style:italic">n</span>' in render_html._general_part_html("symbols")
        units = render_html._general_part_html("units")
        assert "units: " in units and "¢" in units and "<b>p</b>" in units
        assert "(presets)" in render_html._general_part_html("presets")
        assert "arrow_drop_down" in render_html._general_part_html("presets")
        chart = render_html._general_part_html("charts")
        assert "<svg" in chart
        assert render_html._CHART_GRID in chart
        assert "<svg" in render_html._tile_fold_html()

    def test_general_tile_value_is_the_grids_stacked_three_decimal_face(self):
        assert render_html._TILE_VALUE == "701.955", "a gridded cents value appears in the real grid as the whole integer part big over a # three-decimal .fraction stacked BENEATH it (the grid's .rtt-stacked-main / -sub classes), not # as a flat inline number. The dummy tile reads like a live cell: 701 over .955 (the pure fifth, # 3 dp). The whole part and its decimals are SEPARATE click targets (quantities / decimals), so # the .fraction can be toggled on its own"
        whole = render_html._general_part_html("quantities")
        assert 'class="rtt-stacked-main">701<' in whole
        assert ".955" not in whole and "rtt-stacked-sub" not in whole, "the fraction is NOT here…"
        frac = render_html._general_part_html("decimals")
        assert 'class="rtt-stacked-sub">.955<' in frac

    def test_dummy_tile_chart_rides_the_themeable_mark_colors(self):
        chart = render_html._example_chart()
        assert marks.BR_COLOR in chart and render_html._CHART_GRID in chart
        assert "#000" not in chart
