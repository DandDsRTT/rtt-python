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


def test_drop_purges_a_cell_from_every_handle_store():
    # A cell's state lives in exactly two records, both keyed by id: cells[id] (a CellHandles of every
    # cell-specific element handle + last-rendered value) and entities[id] (an EntityHandles of the
    # el + style/ring change-guard caches, shared with lines/washes). drop(eid) pops BOTH, so no handle
    # can leak to a deleted element, and a NEW handle is a new field on a record pop() already removes —
    # no parallel-dict sweep-list to forget (the old _handle_dicts footgun is gone by construction).
    rec = _Reconciler(Editor())
    rec.cells["scheme:primes"] = CellHandles()  # make_cell creates both records per cell in production
    rec.cells["scheme:primes"].chooser.scheme_button = "the-button"
    rec.entities["scheme:primes"] = EntityHandles(el=_FakeElement())
    rec.entities["scheme:primes"].styled = "left:0"
    rec.entities["scheme:primes"].ring_sig = (False, False)
    rec.drop("scheme:primes")
    assert "scheme:primes" not in rec.cells
    assert "scheme:primes" not in rec.entities
    assert rec.handles("scheme:primes").chooser.scheme_button is None  # null-object, not a leaked handle
    assert rec.entity("scheme:primes").el is None


def test_handles_sentinel_reads_none_but_refuses_writes():
    # rec.handles(id) returns a null-object for a non-live id so READS are safe (every field None).
    # That sentinel is SHARED, so a WRITE through it would silently corrupt every future miss — make
    # it raise instead, turning a latent bug into an immediate error. Real records stay writable.
    rec = _Reconciler(Editor())
    assert rec.handles("ghost").value.input is None
    with pytest.raises(AttributeError):
        rec.handles("ghost").value.input = "leak"
    rec.cells["live"] = CellHandles()
    rec.cells["live"].value.input = "ok"
    assert rec.handles("live").value.input == "ok"


def test_on_disconnect_cancels_the_pending_target_limit_commit():
    # _on_disconnect must reach the debounced target-limit commit at its REAL home and cancel it,
    # then end gestures. The commit moved to the tuning sub-controller in the editing split, and a
    # stale path (self.edits.target_limit_commit) was a crash on every disconnect — this pins it.
    calls = []
    page = app._Page.__new__(app._Page)
    page.edits = SimpleNamespace(
        tuning=SimpleNamespace(target_limit_commit=SimpleNamespace(cancel=lambda: calls.append("cancel")))
    )
    page.gestures = SimpleNamespace(end_gesture=lambda: calls.append("end"))
    app._Page._on_disconnect(page)
    assert calls == ["cancel", "end"]


def test_on_disconnect_with_no_pending_commit_just_ends_gestures():
    calls = []
    page = app._Page.__new__(app._Page)
    page.edits = SimpleNamespace(tuning=SimpleNamespace(target_limit_commit=None))
    page.gestures = SimpleNamespace(end_gesture=lambda: calls.append("end"))
    app._Page._on_disconnect(page)
    assert calls == ["end"]


def _bars(svg):
    """(y, height) of each chart bar in an SVG; the thin y-axis rect is excluded by width."""
    rects = re.findall(r'<rect x="[-\d.]+" y="([-\d.]+)" width="([\d.]+)" height="([-\d.]+)"', svg)
    return [(float(y), float(height)) for y, wdt, height in rects if float(wdt) > 1]


def test_app_module_exposes_entry_points():
    assert callable(app.index)
    assert callable(app.main)


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


def test_main_runs_server_with_reload_enabled(monkeypatch):
    captured = _capture_main_run(monkeypatch)
    # the 8137 default port + hot-reload on + no auto-open-browser contract, in one shot
    assert (captured["reload"], captured["port"], captured["show"]) == (True, 8137, False)


def test_main_sets_browser_tab_title_and_local_favicon(monkeypatch):
    # the browser tab reads "D&D's RTT App" and shows the DandDsRTT org avatar, served from a
    # LOCAL file vendored under assets/. It must NOT be a remote URL: NiceGUI registers
    # /favicon.ico -> get_favicon_response() for a non-local favicon, which raises ValueError on
    # any remote URL, so every hit on that route 500s (the production bug). A local file gates into
    # NiceGUI's FileResponse branch instead — see test_favicon_route_returns_200_for_local_file.
    from nicegui import helpers
    captured = _capture_main_run(monkeypatch)
    assert captured["title"] == "D&D's RTT App"
    favicon = captured["favicon"]
    assert not favicon.startswith(("http://", "https://"))  # NOT remote — that 500s /favicon.ico
    assert helpers.is_file(favicon)                          # a real local file NiceGUI will serve
    assert Path(favicon).name == "favicon.png" and Path(favicon).parent.name == "assets"


def test_favicon_route_returns_200_for_local_file(monkeypatch):
    # Regression for the production 500 on /favicon.ico. Drive NiceGUI's OWN route-registration
    # decision (the helpers.is_file gate in nicegui._startup) and the resulting handler through a
    # real request: main()'s local file takes the FileResponse branch and serves 200, whereas the
    # old remote URL falls to get_favicon_response(), which raises ValueError and 500s every hit.
    from nicegui import core, helpers
    from nicegui.favicon import get_favicon_response
    from starlette.applications import Starlette
    from starlette.responses import FileResponse
    from starlette.testclient import TestClient

    # the remote branch reads core.app.config.favicon (an init=False field, unset until ui.run); set
    # it for the duration and restore the prior state so the shared config isn't left polluted.
    sentinel = object()
    saved = getattr(core.app.config, "favicon", sentinel)

    def status_for(favicon):
        # mirror nicegui._startup exactly: pick the branch by is_file, off core.app.config.favicon
        core.app.config.favicon = favicon
        api = Starlette()
        if helpers.is_file(core.app.config.favicon):
            api.add_route("/favicon.ico", lambda _: FileResponse(core.app.config.favicon))
        else:
            api.add_route("/favicon.ico", lambda _: get_favicon_response())
        client = TestClient(api, raise_server_exceptions=False)
        return client.get("/favicon.ico").status_code

    try:
        assert status_for(_capture_main_run(monkeypatch)["favicon"]) == 200  # main()'s local file works
        assert status_for("https://github.com/DandDsRTT.png") == 500         # the old remote URL: the bug
    finally:
        if saved is sentinel:
            del core.app.config.favicon
        else:
            core.app.config.favicon = saved


def test_main_production_launch_when_platform_sets_port(monkeypatch):
    # A hosting platform (Render et al.) assigns the port via $PORT. main() then launches
    # for production: bind every interface (0.0.0.0) on that port, with the file-watching
    # reloader OFF — a deployed server has no editing session to watch, and the reloader's
    # multiprocessing worker would only fight the platform's process management — so no
    # uvicorn_reload_excludes are wired at all.
    captured = _capture_main_run(monkeypatch, env={"PORT": "10000"})
    assert (captured["reload"], captured["port"], captured["show"], captured["host"]) \
        == (False, 10000, False, "0.0.0.0")
    assert "uvicorn_reload_excludes" not in captured  # no reloader to exclude paths from


def test_main_takes_session_secret_from_env_with_a_local_fallback(monkeypatch):
    # the cookie-signing secret is overridable from the environment, so the deployed app
    # signs sessions with a strong platform-generated secret rather than the value baked
    # into this public repo; unset (local dev), it falls back to the module default.
    assert _capture_main_run(monkeypatch, env={"STORAGE_SECRET": "from-the-platform"})[
        "storage_secret"] == "from-the-platform"
    assert _capture_main_run(monkeypatch)["storage_secret"] == page_assets._STORAGE_SECRET


def test_main_passes_crash_safe_reload_excludes(monkeypatch):
    # main() wires _reload_excludes into ui.run. The user keeps this instance running to
    # use the app; agent worktrees live in .claude/worktrees/ inside the repo, so their
    # constant edits sit under the reload watcher's root and would refresh the user's
    # browser endlessly — main() excludes that subtree. NiceGUI's default ignore globs
    # must survive, and every ABSOLUTE entry must be an existing directory: uvicorn globs
    # any non-dir exclude relative to cwd, and on Python 3.14 pathlib raises
    # NotImplementedError for an absolute glob pattern, so an absolute path to a missing
    # dir would crash the server at startup. The worktrees subtree is therefore added
    # exactly when it exists (an existing dir uvicorn turns into an exclude_dir).
    captured = _capture_main_run(monkeypatch)
    excludes = [e.strip() for e in captured["uvicorn_reload_excludes"].split(",")]
    for default in (".*", ".py[cod]", ".sw.*", "~*"):
        assert default in excludes
    for e in excludes:
        if Path(e).is_absolute():
            assert Path(e).is_dir(), f"absolute exclude {e!r} must be an existing dir (else Py3.14 glob crash)"
    worktrees = Path(app.__file__).resolve().parents[2] / ".claude" / "worktrees"
    assert (str(worktrees) in excludes) == worktrees.is_dir()


def test_main_watches_assets_so_js_and_css_edits_hot_reload(monkeypatch):
    # uvicorn's reloader watches *.py ONLY by default, so an edit to audio.js / rtt.css would NOT
    # reload — the running instance keeps stale JS/CSS until some .py file happens to change (which is
    # how a JS-only audio fix silently failed to reach the user). main() widens the watch to the
    # assets so a JS / CSS edit hot-reloads on its own.
    captured = _capture_main_run(monkeypatch)
    # NiceGUI's ui.run does split_args(...).split(',') on this, so it MUST be a comma-STRING, not a
    # list (a list crashed the server at startup: 'list' object has no attribute 'split'). Splitting
    # it the way NiceGUI does both checks the patterns AND would catch a list (it'd have no .split).
    includes = [p.strip() for p in captured["uvicorn_reload_includes"].split(",")]
    for pat in ("*.py", "*.css", "*.js"):
        assert pat in includes, f"{pat} not watched for reload"


def test_reload_excludes_omits_worktrees_when_missing(tmp_path):
    # When the agent-worktrees subtree doesn't exist, main() must NOT hand uvicorn an
    # absolute path for it: uvicorn globs any exclude that isn't an existing dir relative
    # to cwd, and on Python 3.14 pathlib raises NotImplementedError for an absolute glob
    # pattern — which crashed the server at startup. With no worktrees there's nothing to
    # skip, so only NiceGUI's default ignore globs remain.
    missing = tmp_path / ".claude" / "worktrees"  # never created
    excludes = [e.strip() for e in app._reload_excludes(missing).split(",")]
    assert str(missing) not in excludes
    for default in (".*", ".py[cod]", ".sw.*", "~*"):
        assert default in excludes


def test_reload_excludes_filter_skips_worktrees_but_reloads_source(tmp_path):
    # Exercise the excludes through uvicorn's REAL reload pipeline (not a monkeypatched
    # ui.run): build a fake repo whose .claude/worktrees/ holds an agent worktree, run the
    # helper's output the way NiceGUI does (comma-split + strip, then append sys.prefix),
    # and hand it to the actual uvicorn Config + FileFilter. Constructing the Config is the
    # Python 3.14 crash site (it globs each exclude) — it must NOT raise — and the filter
    # must drop a change under the worktree while still reloading on a main-source edit.
    from uvicorn.config import Config
    from uvicorn.supervisors.watchfilesreload import FileFilter

    repo = tmp_path
    worktrees = repo / ".claude" / "worktrees"
    (worktrees / "wt1" / "rtt" / "web").mkdir(parents=True)
    (repo / "rtt" / "web").mkdir(parents=True)

    excludes = [e.strip() for e in app._reload_excludes(worktrees).split(",")] + [sys.prefix]
    config = Config("rtt.app.app:app", reload=True, reload_includes=["*.py", "*.css", "*.js"],
                    reload_excludes=excludes, reload_dirs=[str(repo)])  # must not raise on Py3.14
    file_filter = FileFilter(config)

    # a .py OR an asset (audio.js / rtt.css) edit reloads from the main repo but is skipped under a worktree
    assert file_filter(worktrees / "wt1" / "rtt" / "web" / "app.py") is False    # agent .py edit: no reload
    assert file_filter(repo / "rtt" / "web" / "app.py") is True                  # main .py edit: reloads
    assert file_filter(worktrees / "wt1" / "rtt" / "web" / "audio.js") is False  # agent JS edit: no reload
    assert file_filter(repo / "rtt" / "web" / "audio.js") is True                # main JS edit: reloads


def test_parse_int_accepts_integers_and_rejects_partial_input():
    assert render_html._parse_int("5") == 5
    assert render_html._parse_int("-4") == -4
    assert render_html._parse_int("  3 ") == 3
    assert render_html._parse_int("") is None
    assert render_html._parse_int("-") is None
    assert render_html._parse_int("x") is None
    assert render_html._parse_int(None) is None


def test_ratio_parts_splits_fractions_and_passes_through_non_fractions():
    assert render_html._ratio_parts("3/2") == ("3", "2")  # rendered as a stacked fraction
    assert render_html._ratio_parts("2/1") == ("2", "1")
    assert render_html._ratio_parts("5") is None  # a bare integer is not a fraction
    assert render_html._ratio_parts("") is None


def test_cents_parts_splits_whole_and_fraction_for_decimal_alignment():
    assert render_html._cents_parts("1899.26") == ("1899", "26")  # big whole, small fraction
    assert render_html._cents_parts("-2.69") == ("-2", "69")
    assert render_html._cents_parts("0.00") == ("0", "00")
    assert render_html._cents_parts("5") == ("5", "")  # no fractional part


def test_power_parts_annotates_infinity_as_max():
    # ∞ carries a small "(max)" below it (it IS the max-norm / minimax power), stacked like a
    # cents value's decimal; a numeric power (2, 1) shows bare, with no annotation
    assert render_html._power_parts("∞") == ("∞", "(max)")
    assert render_html._power_parts("2") == ("2", "")
    assert render_html._power_parts("1") == ("1", "")


def test_underline_html_wraps_only_the_marked_spans():
    # no spans -> plain text (the caption with mnemonics off)
    assert render_html._underline_html("tuning map", ()) == "tuning map"
    # a leading one-letter span -> just that letter underlined (the symbol mnemonic)
    assert render_html._underline_html("tuning map", ((0, 1),)) == "<u>t</u>uning map"
    # a span mid-string keeps the surrounding text intact
    assert render_html._underline_html("(temperament) mapping", ((14, 1),)) == "(temperament) <u>m</u>apping"
    # a descender letter (g/j/p/q/y) is tagged so only its underline drops below the
    # tail; non-descenders keep the normal snug underline
    assert render_html._underline_html("just tuning map", ((0, 1),)) == '<u class="rtt-desc">j</u>ust tuning map'


def test_math_html_maps_each_block_to_its_weight_and_slant():
    # each maths letter renders as its base ASCII letter carrying the weight/slant of its
    # Unicode block — bold (vector lists), bold-italic (maps/generators), or italic
    # (mappings) — set via inline CSS, rather than its literal styled markup.
    bold, bold_italic, italic = (True, False), (True, True), (False, True)
    for glyph, base, (want_bold, want_italic) in [
        ("𝐚", "a", bold), ("𝟎", "0", bold),                 # bold vector list / held-error zero
        ("𝒕", "t", bold_italic), ("𝒈", "g", bold_italic),   # bold-italic map / generator
        ("𝑀", "M", italic),                                  # italic mapping
    ]:
        html = render_html._math_html(glyph)
        assert f">{base}</span>" in html, glyph
        assert ("font-weight:700" in html) is want_bold, glyph
        assert ("font-style:italic" in html) is want_italic, glyph
    assert render_html._math_html("Y") == "Y"  # an upright list passes through, unstyled


def test_math_html_styles_products_per_letter_and_honours_the_subscript_sentinels():
    # a product styles each letter on its own (the comma column's 𝒕C: bold-italic map +
    # upright basis; an equivalence tail's 𝒈𝑀); ordinary characters pass through
    assert render_html._math_html("𝒕C") == render_html._math_html("𝒕") + "C"
    assert render_html._math_html(" = 𝒈𝑀") == " = " + render_html._math_html("𝒈") + render_html._math_html("𝑀")
    # NORM_SUB forces an italic subscript (the complexity row's trailing q); SUB is a PLAIN
    # subscript where only the math-italic 𝑞 slants (the dual(q) mean damage: "dual" upright)
    assert render_html._math_html(grid_tables.NORM_SUB_OPEN + "q" + grid_tables.NORM_SUB_CLOSE) == \
        '<sub style="font-style:italic">q</sub>'
    plain = render_html._math_html(grid_tables.SUB_OPEN + "dual(𝑞)" + grid_tables.SUB_CLOSE)
    assert plain.startswith("<sub>dual(") and plain.endswith(")</sub>") and "font-style:italic" in plain


def test_ebk_marks_share_one_colour_and_map_one_to_one_to_their_cell():
    # every EBK mark is one SVG whose viewBox is the cell's own px box, so its
    # weight is a constant px count rather than a scaled stroke — that is what
    # keeps a 1-row and a many-row bracket the exact same thickness.
    mark_svgs = {
        "[": marks.square_bracket(16, 16, "left"),
        "]2": marks.square_bracket(16, 60, "right"),
        "<": marks.angle_bracket(16, 16),
        "top": marks.top_bracket(120, 9),
        "angle": marks.angle_foot(14, 7),  # the raw-vector column's ket foot (a down-chevron)
        "vbar": marks.vbar(2, 60),
    }
    for svg in mark_svgs.values():
        assert svg.startswith("<svg") and f'fill="{marks.BR_COLOR}"' in svg
        assert "stroke-width" not in svg  # weight is the 1:1 viewBox, not a scaling stroke
    assert mark_svgs["angle"].count("<path") == 1 and "stroke" not in mark_svgs["angle"]  # one filled chevron
    # the down-chevron foot fits inside its oblong like every other mark — its whole
    # footprint (stroke included) stays within the 7px-tall box, never overshooting
    import re
    ys = [float(y) for _x, y in re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", marks.angle_foot(14, 7))]
    assert 0 <= min(ys) and max(ys) <= 7
    def _viewbox(svg):
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        return float(m.group(1)), float(m.group(2))
    assert _viewbox(mark_svgs["["]) == (16, 16)
    assert _viewbox(mark_svgs["]2"]) == (16, 60)  # 1 row vs many: same generator, viewBox == the cell box


def test_units_html_bolds_variables_but_not_cents_oct_or_slash():
    # the variable symbols (g, p, b, the placeholder 1, with subscripts) are bold; the
    # units of interval size — the cent sign ¢ and the spelled-out "oct" (octaves) — and
    # the "/" separator stay un-bold, consistently in the per-box line and the units
    # row/col. A per-box line also keeps "units:" in the serif label face.
    # a per-box line keeps "units:" in the serif label face and bolds its variables
    assert render_html._units_html("units: g/p") == '<span class="rtt-units-pre">units: </span><b>g</b>/<b>p</b>'
    # the bolding rule token by token: each variable (with subscript) is wrapped in <b>; the
    # size units ¢ and "oct" and the "/" separator appear but never bold. Covers the per-box
    # "units: …" line and the bare domain-unit coordinate labels alike.
    for text, bolded, bare in [
        ("units: ¢/g", ["g"], ["¢", "/"]),
        ("units: oct/p", ["p"], ["oct", "/"]),
        ("units: ¢", [], ["¢"]),
        ("g₁/", ["g₁"], ["/"]),
        ("/p₁", ["p₁"], ["/"]),
        ("/1", ["1"], ["/"]),     # the "1" placeholder is a variable, so bold
        ("oct/", [], ["oct", "/"]),
    ]:
        html = render_html._units_html(text)
        for v in bolded:
            assert f"<b>{v}</b>" in html, (text, v)
        for u in bare:
            assert u in html and f"<b>{u}</b>" not in html, (text, u)


def test_line_style_centres_the_rule_on_its_coordinate():
    # a gridline's W-px border grows off one edge of its zero-size box, so the renderer
    # offsets the box by half the width to seat the rule centred on its coordinate -- the
    # toggle-node / cell-column centre -- rather than leaning a full width off to one side
    half = spreadsheet_constants.LINE_W / 2
    # the rule is positioned by transform:translate (so a reflow shift rides the compositor); the box is
    # anchored at left:0;top:0 and translated to (centred coordinate, start), its LENGTH on height/width
    v = render_html._line_style(Line("trunk:x", "v", 100, 50, 200))
    assert f"transform:translate({100 - half}px,50px)" in v  # centred on x=100 (not flush), seated at y=50
    assert "height:200px" in v and "left:0; top:0" in v       # the length runs unchanged; box anchored at origin
    height = render_html._line_style(Line("h:x", "h", 60, 10, 300))
    assert f"transform:translate(10px,{60 - half}px)" in height    # seated at x=10, centred on y=60
    assert "width:300px" in height and "left:0; top:0" in height


def test_line_style_dots_a_collapsed_bands_rule_and_restores_it_when_open():
    # a collapsed row/column converges to one rule, drawn dotted as a placeholder. The dots
    # are a repeating gradient painted through a transparent border (so the zero-size box
    # doesn't resize as a band folds), swept along the rule's length. The border colour and
    # background are emitted every update, so re-expanding restores the solid grey rule.
    v_dotted = render_html._line_style(Line("trunk:x", "v", 100, 0, 50, dotted=True))
    assert "border-left-color:transparent" in v_dotted and "repeating-linear-gradient(to bottom," in v_dotted
    # painted over the border box -- the box has no width of its own, only the border, so
    # without this the gradient fills the zero-width content box and the dots never show
    assert "border-box" in v_dotted
    v_solid = render_html._line_style(Line("trunk:x", "v", 100, 0, 50))
    assert "border-left-color:var(--c-gridline)" in v_solid and "background:none" in v_solid
    h_dotted = render_html._line_style(Line("h:x", "h", 60, 0, 50, dotted=True))
    assert "border-top-color:transparent" in h_dotted and "repeating-linear-gradient(to right," in h_dotted
    h_solid = render_html._line_style(Line("h:x", "h", 60, 0, 50))
    assert "border-top-color:var(--c-gridline)" in h_solid and "background:none" in h_solid
    # the dots are sparse: the transparent gap runs well past the dot's far edge (a LINE_W
    # dot then a gap several times wider), unlike CSS `dotted`'s ~one-width packing
    assert f"transparent {spreadsheet_constants.LINE_W}px {render_html._DOT_PITCH}px" in v_dotted
    assert render_html._DOT_PITCH >= 3 * spreadsheet_constants.LINE_W


def test_shared_axis_gridlines_render_two_pixels_thick():
    # the shared coordinate axes (.rtt-line, the rules the cells sit on, threading the
    # gaps between tiles) are the board's gridlines; doubled from 1px to 2px so they read
    # clearly. Both orientations carry the same #e0e0e0 weight.
    assert spreadsheet_constants.LINE_W == 2
    assert f"--line-w:{spreadsheet_constants.LINE_W}px" in page_assets._CSS  # the gridline weight, set in :root
    assert "--c-gridline:#e0e0e0" in page_assets._CSS  # the gridline colour, set in :root so dark mode can retint it
    assert "border-left:var(--line-w) solid var(--c-gridline)" in page_assets._CSS  # the vertical gridlines
    assert "border-top:var(--line-w) solid var(--c-gridline)" in page_assets._CSS   # the horizontal gridlines


def test_colfill_bounce_layer_sits_behind_the_scroller_carries_no_zindex_and_hugs_the_body_inset():
    fill = _css_rule(".rtt-colfill")
    assert "z-index" not in fill
    assert "pointer-events:none" in fill
    assert "left:var(--pad)" in fill and "bottom:0" in fill


def test_colfill_is_visible_on_desktop_so_the_top_bounce_bridge_shows_and_hidden_only_on_touch():
    # desktop keeps its bounce and pins scrollTop at 0 through it, so the bridge shows only by being
    # visible at rest (no scroll signal marks the bounce, hence no scrollTop<0 overpull gate); touch
    # removes the bounce, so the bridge never bares and is hidden there to kill the iOS late-sync echo.
    assert "visibility:hidden" not in _css_rule(".rtt-colfill")
    assert ".rtt-app.rtt-overpull-y" not in page_assets._CSS
    assert "rtt-overpull-y" not in page_assets._FREEZE_JS
    touch = re.search(r"@media \(hover: none\) and \(pointer: coarse\) \{(.*?\.rtt-colfill[^}]*\})\s*\}",
                      page_assets._CSS, re.S)
    assert touch and re.search(r"\.rtt-colfill\s*\{[^}]*visibility:hidden", touch.group(1))


def test_rowfill_mirrors_colfill_for_the_sticky_row_bands_top_overpull_gap():
    # the row band is position:sticky, so a top overpull slides it down and opens a gap below the fixed
    # corner that bares the body's rules through the frozen-left edge. rowfill is the left twin of
    # colfill: a fixed grey strip behind the body at the frozen-column inset, carrying the same seam.
    fill = _css_rule(".rtt-rowfill")
    assert "left:var(--pad)" in fill and "bottom:0" in fill
    assert "background:#c0c0c0" in fill
    assert "box-shadow:1px 0 0 var(--seam-x,transparent)" in fill
    assert "z-index" not in fill  # behind the body, like colfill, so the row band covers it at rest
    # the seam lights with the row band's, on a horizontal scroll
    assert ".rtt-app.rtt-scrolled-x .rtt-rowfill" in page_assets._CSS


def test_touch_devices_damp_the_overscroll_bounce_so_the_grid_does_not_rubber_band():
    # the bounce-zone gridline echo and the collapse-all/row-toggle float are both artifacts of the
    # elastic overscroll; on touch devices we remove the bounce so neither can occur. It must be
    # overscroll-behavior:none (contain only stops chaining, keeping the bounce), and scoped to a
    # coarse-pointer/no-hover device so desktop keeps its bounce and the colfill/rowfill bridges.
    assert "@media (hover: none) and (pointer: coarse)" in page_assets._CSS
    touch = re.search(r"@media \(hover: none\) and \(pointer: coarse\) \{(.*?\})\s*\}", page_assets._CSS, re.S)
    assert touch and ".rtt-gridbody" in touch.group(1) and "overscroll-behavior:none" in touch.group(1)


def test_only_full_height_seam_reaching_column_rules_are_twinned_in_the_colfill_not_centre_stubs():
    lay = Editor().layout()
    fy = lay.freeze_y
    twinned = {ln.id for ln in lay.lines if ln.orientation == "v" and ln.start <= fy and ln.length > fy}
    assert {"v:gen:0", "v:prime:0", "v:comma:0", "v:target:0"} <= twinned
    assert "trunk:gens" not in twinned


def _css_rule(selector):
    """The declaration body of the first `selector { ... }` block in the page CSS."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", page_assets._CSS)
    assert m, f"no CSS rule for {selector}"
    return m.group(1)


def test_temperament_divider_headers_read_as_centred_grey_rules_inset_like_the_items():
    # the rank/limit divider rows read as section headers, not choices: a centred grey label
    # flanked by rules (the lines are CSS now, not the old ── dashes baked into the label text).
    # The label flex-centres its text in grey (#777); the divider keeps the items' horizontal
    # padding rather than running to the popup's literal edges, so its flex:1 ::before/::after
    # lines stop the same 8px in from each edge as the item text.
    label = _css_rule(".rtt-select-popup .q-item.disabled .q-item__label")
    assert "justify-content:center" in label   # centred text
    assert "color:#777" in label                # grey, lighter than the items' black
    # the divider does NOT zero its padding -> its rules align with the item text, not the edges
    assert "padding-left:0" not in page_assets._CSS
    assert ".q-item.disabled .q-item__label::before" in page_assets._CSS  # the flanking rules...
    assert "border-top:1px solid #777" in page_assets._CSS                # ...are grey lines


def test_sidebar_hugs_its_content_as_a_fixed_left_column():
    # The chrome + settings drawer share .rtt-panelgroup, the app's fixed left sidebar (flex:none, and
    # no position:sticky — the page never scrolls). Under the shell's align-items:flex-start it HUGS
    # its content height rather than stretching its grey down the window: the chrome's title tab when
    # the drawer is collapsed, the settings panel's height when open. The drawer animates its height
    # (grid-template-rows 0fr->1fr) so a collapsed drawer contributes no height (sidebar = the tab).
    rule = _css_rule(".rtt-panelgroup")
    assert "flex:none" in rule                # fixed width; doesn't grow/shrink with the grid
    assert "position:sticky" not in rule      # no page scroll to pin against
    drawer = _css_rule(".rtt-drawer")
    assert "grid-template-rows:0fr" in drawer  # collapsed -> zero height, so the sidebar hugs the chrome
    assert "align-self:flex-start" in drawer   # ...and the panelgroup doesn't stretch it back open


def test_opening_widens_the_single_sidebar_so_the_tab_becomes_the_pane():
    # One sidebar that WIDENS from the closed tab to the open pane (a single transitioned width), so
    # the collapsed sidebar becomes the expanded one rather than one panel replacing another. The
    # chrome stacks over the settings drawer (column), and only the width animates.
    pg = _css_rule(".rtt-panelgroup")
    assert "flex-direction:column" in pg                  # chrome stacked over the settings drawer
    assert "width:var(--tab-w)" in pg                     # closed: the narrow tab
    assert "transition:width" in pg                       # ...animated...
    assert "width:var(--panel-w)" in _css_rule(".rtt-panelgroup.rtt-open")  # ...to the full pane


def test_the_chrome_pins_the_hamburger_and_swings_the_title_upright():
    # The chrome is ONE hamburger + ONE title that morph in place (no second copy swapped in). The
    # hamburger is absolutely pinned, so opening never reflows it out from under the cursor; the title
    # swings via an animated transform from a quarter-turn (down the closed tab) to upright (across the
    # open bar).
    assert "position:absolute" in _css_rule(".rtt-hamburger")   # pinned — never reflows on open/close
    title = _css_rule(".rtt-sidetitle")
    assert "position:absolute" in title
    assert "rotate(90deg)" in title                             # closed: turned a quarter-turn down the tab
    assert "transition" in title and "transform" in title       # ...and the swing is animated
    assert "rotate(0deg)" in _css_rule(".rtt-panelgroup.rtt-open .rtt-sidetitle")  # open: upright


def _z(selector):
    m = re.search(r"z-index:(\d+)", _css_rule(selector))
    assert m, f"no z-index in {selector}"
    return int(m.group(1))


def test_titles_freeze_outside_or_sticky_within_the_body_scroller():
    # The frozen titles sit so the body's scrollbars stop at them. The row band freezes by
    # position:sticky to the left of the body scroller; the column-title strip and the corner sit
    # OUTSIDE the scroller (position:absolute on the pane), so the body's vertical scrollbar starts
    # below the strip. They stack above the body, the corner above both edges.
    assert "position:sticky" in _css_rule(".rtt-rowband") and "left:0" in _css_rule(".rtt-rowband")
    assert "position:absolute" in _css_rule(".rtt-colhead")  # the strip is lifted out of the scroller
    assert "position:absolute" in _css_rule(".rtt-corner")   # ...as is the corner (frozen both)
    assert _z(".rtt-cell") < _z(".rtt-colhead") < _z(".rtt-rowband") < _z(".rtt-corner")


def test_grid_body_reserves_its_grey_margin_as_scroll_padding():
    # the body fills to the pane's right/bottom EDGES so its scrollbars sit flush there (no grey
    # stranded outside them). The _PAD grey margin past the gridlines must survive scrolling to the
    # end, though: a margin from merely sizing the pane larger than the board vanishes once the board
    # overflows and the body scrolls (the board's far edge reaches the flush pane edge at max scroll).
    # So the body reserves the right/bottom margin as PADDING — it rides in the scrollable content and
    # shows past the last gridline even at the scroll extreme, while the scrollbars stay flush. No
    # top/left padding: those margins are structural (the body is already inset _PAD from the pane
    # there, outside the scroller).
    rule = _css_rule(".rtt-gridbody")
    assert "padding:0 var(--pad) var(--pad) 0" in rule  # top:0 right:PAD bottom:PAD left:0
    assert f"--pad:{page_assets._PAD}px" in page_assets._CSS  # the grey-margin width, set in :root


def test_shell_fixes_the_app_to_the_window_framed_by_a_white_margin():
    # The shell is position:fixed at a 6px inset from every window edge, so the app fills the window
    # exactly and the page itself never scrolls (the grid scrolls inside its own pane instead). The
    # 6px of white body around the fixed shell frames the whole app — the white margin that stays
    # put even while the grid scrolls, since nothing scrolls over it.
    rule = _css_rule(".rtt-shell")
    assert "position:fixed" in rule
    for edge in ("top:6px", "left:6px", "right:6px", "bottom:6px"):
        assert edge in rule, edge


def test_settings_pane_stacks_a_frozen_header_over_a_scrolling_body():
    # The settings panel can outrun the screen, so — like the grid pane's frozen column titles over
    # its scrolling body — the pane freezes its header and scrolls the toggle groups under it. The
    # drawer-inner is a flex column that hugs its content (no max-height of its own).
    inner = _css_rule(".rtt-drawer-inner")
    assert "display:flex" in inner and "flex-direction:column" in inner
    # the settings content is inset from the top by the SAME _PAD the grid pane insets its column-
    # header band, so the settings frozen header lines up with the main app's header (not 12px above)
    assert "padding-top:var(--pad)" in inner
    # the header (select-all/none + the show/example titles) never shrinks or scrolls...
    assert "flex:none" in _css_rule(".rtt-show-frozen")
    # ...and the groups sit in a body that sizes to its OWN content (flex:none, NOT flex:1) and scrolls
    # (overflow-y:auto) only past a max-height set in render() to (window − inset − header). Sizing to
    # its own content — rather than the flex remainder — stops a sub-pixel rounding popping a spurious
    # scrollbar when the panel fits; render() sets the cap (asserted in test_web_render).
    body = _css_rule(".rtt-show-scroll")
    assert "flex:none" in body and "overflow-y:auto" in body
    assert "flex:1" not in body  # NOT the flex-fill hug that rounded a hair short and scrolled


def test_settings_frozen_seam_sits_below_the_header_not_inside_it():
    # the darker-grey rule moves from between select-all/none and the show/example titles to
    # BELOW both — it becomes the header's bottom edge, the frozen/scrolling seam, exactly as the
    # column band's seam divides the frozen titles from the scrolling grid. select-all/none, now
    # the header's first line, no longer carries the rule (nor the spacing that set it apart).
    assert "border-bottom:1px solid #c4c4c4" in _css_rule(".rtt-show-frozen")
    assert "border-bottom" not in _css_rule(".rtt-show-all")


def test_row_band_wrapper_passes_clicks_through_and_the_strip_clips():
    # the row band rides a full-height .rtt-band wrapper that lets clicks fall through to the body
    # (pointer-events:none); the sticky inner re-enables them and is opaque #c0c0c0, so the body is
    # hidden behind the row titles as it scrolls under them. The column strip clips its translated
    # inner (overflow:hidden) so titles scrolled off the left don't spill over the corner / sidebar.
    assert "pointer-events:none" in _css_rule(".rtt-band")
    assert "pointer-events:auto" in page_assets._CSS  # the row band inner re-enables clicks
    assert "overflow:hidden" in _css_rule(".rtt-colhead")


def test_grid_scrolls_in_its_own_body_pane_not_the_page():
    # the grid scrolls inside .rtt-gridbody (overflow:auto) — its own pane, within the grid region
    # .rtt-app. .rtt-app hugs the grid (flex:0 1 auto — shrinks to the room left of the sidebar
    # rather than filling it) and only clips (overflow:hidden), hosting the absolutely-placed frozen
    # regions; the page never scrolls. So a grid bigger than the pane scrolls in the body, scrollbars
    # bounded there, right of the sidebar.
    assert "overflow:auto" in _css_rule(".rtt-gridbody")             # the grid's own scroller
    app_rule = _css_rule(".rtt-app")
    assert "overflow:hidden" in app_rule and "position:relative" in app_rule  # the region, not the scroller
    assert "flex:0 1 auto" in app_rule and "min-width:0" in app_rule  # hugs the grid, shrinks to the pane


def test_panes_hug_their_content_and_cap_at_the_window():
    # both panes size to their content (under the shell's align-items:flex-start) so their grey
    # backdrops don't stretch into empty space — white body shows beyond the shorter one. Each caps
    # at the window before scrolling internally: the grid pane via max-width/max-height (flex-shrinking
    # to the room left of the sidebar), the settings pane via the drawer-inner's max-height.
    assert "align-items:flex-start" in _css_rule(".rtt-shell")
    app_rule = _css_rule(".rtt-app")
    assert "max-width:100%" in app_rule and "max-height:100%" in app_rule


def test_seam_appears_only_when_the_body_is_scrolled():
    # each frozen region's body-facing edge is seamless at rest and takes a 1px grey seam only once the
    # body is scrolled on that axis (.rtt-app gains rtt-scrolled-x/y, see _FREEZE_JS). Drawn as a drop
    # SHADOW, not a border: a 1px transparent border would reserve a 1px strip at rest that shows the
    # grey pane THROUGH the colour washes as a thin line (the frozen edge-wash copies clip to the
    # content box, inside the border). A shadow reserves no layout, so the frozen content + its wash
    # copies sit flush to the seam with no rest-state gap; a per-axis custom property carries the
    # colour, transparent until that axis scrolls (so revealing it still shifts nothing).
    css = page_assets._CSS
    colhead, rowband = _css_rule(".rtt-colhead"), _css_rule(".rtt-rowband")
    assert "box-shadow:0 1px 0 var(--seam-y" in colhead  # column-strip seam (below the strip)
    assert "border-bottom" not in colhead                # NOT a layout-reserving border
    assert "box-shadow:1px 0 0 var(--seam-x" in rowband  # row-band seam (right of the band)
    assert "border-right" not in rowband
    assert ".rtt-app.rtt-scrolled-y .rtt-colhead" in css and "--seam-y:var(--seam)" in css
    assert ".rtt-app.rtt-scrolled-x .rtt-rowband" in css and "--seam-x:var(--seam)" in css
    assert f"--seam:{page_assets._SEAM}" in css  # the seam colour, set in :root


def test_block_panes_routes_a_wash_into_every_frozen_pane_its_rect_crosses():
    # A grey tile sits inside both seams, so it renders into the body alone. A colour wash, though,
    # overhangs its tile by WASH_PAD-PAD, so a top-row / left-column wash spills PAST the seam — and
    # must render into the frozen strip/band it spills into as well, or the column strip clips that
    # spill (the body scroller stops at the seam) and the row band paints over it. Like a gridline
    # crossing the seam, the wash routes into the body plus every frozen pane it reaches.
    from rtt.app.layout import Block
    fx, fy = 144.0, 68.0
    inside = Block("b", 200, 200, 50, 50)            # clears both seams
    over_top = Block("b", 200, 62, 50, 64)           # spills above freeze_y
    over_left = Block("b", 138, 200, 50, 50)         # spills left of freeze_x
    over_corner = Block("b", 138, 62, 50, 64)        # spills past both, into the corner
    assert render_html._block_panes(inside, fx, fy) == ("body",)
    assert render_html._block_panes(over_top, fx, fy) == ("body", "col")
    assert render_html._block_panes(over_left, fx, fy) == ("body", "row")
    assert render_html._block_panes(over_corner, fx, fy) == ("body", "col", "row", "corner")


def test_frozen_wash_copies_show_only_at_rest_dropping_once_the_body_scrolls():
    # The top/left-edge washes also render into the frozen column strip / row band so their colour
    # fills the inter-title gap at rest. That copy only belongs unscrolled: once the body scrolls on
    # an axis the first row/column has left the seam, so the strip would stain the gap with a stale
    # colour over the wrong tiles. So it drops when .rtt-app gains rtt-scrolled-x/y — paired with the
    # seam toggle on the same axis (column strip on y, row band on x; the base hides with its colour).
    css = page_assets._CSS
    for sel in (".rtt-app.rtt-scrolled-y .rtt-colhead .rtt-wash",
                ".rtt-app.rtt-scrolled-y .rtt-colhead .rtt-washbase",
                ".rtt-app.rtt-scrolled-x .rtt-rowband .rtt-wash",
                ".rtt-app.rtt-scrolled-x .rtt-rowband .rtt-washbase"):
        assert sel in css
    m = re.search(r"rtt-scrolled-y \.rtt-colhead \.rtt-wash[\s\S]*?\{([^}]*)\}", css)
    assert m and "display:none" in m.group(1)  # the copies are dropped, not merely restyled


def test_freeze_script_syncs_the_column_strip_and_toggles_the_seam_on_body_scroll():
    # the freeze SYNC is a capture-phase scroll listener over .rtt-gridbody (the body scroller). It
    # translateX-syncs the column-title strip to the body's horizontal scroll (the one thing CSS
    # can't do for a strip lifted out of the scroller) and toggles rtt-scrolled-x/y on .rtt-app from
    # the body's scroll offset to reveal the seams. It never moves the row titles — position:sticky
    # does that — so there is no bobble. (A second pass reserves scrollbar space; see the next test.)
    js = page_assets._FREEZE_JS
    assert ".rtt-gridbody" in js                                # listens to the body scroller
    assert "scrollTop" in js and "scrollLeft" in js             # reads its scroll offset
    assert ".rtt-colhead-inner" in js and "translateX" in js    # syncs the strip horizontally
    assert ".rtt-colfill-inner" in js
    assert "rtt-scrolled-x" in js and "rtt-scrolled-y" in js    # toggles the seams
    assert "addEventListener('scroll'" in js
    assert "ResizeObserver" not in js and "scroll-timeline" not in js  # no fixed-box machinery
    # Only the VERTICAL twin offset is clamped non-negative. iOS WebKit reports scrollTop negative
    # through a top overscroll (desktop holds it at 0), so clamping keeps the colfill twins put to
    # bridge the bared strip; the horizontal axis must track raw scroll so the twins stay glued under
    # their columns — clamping X ghosts a second set of verticals on a left overscroll.
    assert "Math.max(0, b.scrollTop)" in js
    assert "-b.scrollLeft" in js
    assert "Math.max(0, b.scrollLeft)" not in js


def test_freeze_script_reserves_a_scrollbar_so_one_bar_never_forces_a_second():
    # The body scroller fills the pane, which HUGS the grid with only a _PAD margin — narrower than a
    # scrollbar. So a scrollbar on one axis used to eat into the perpendicular margin and tip a SECOND,
    # spurious scrollbar onto the other axis (the reported bug: a vertical scrollbar forcing a needless
    # horizontal one). rttFreeze.fit removes the coupling: it reads the pane's published base size
    # (data-base-w/-h), detects which axis the window caps, then (a) grows the pane by a scrollbar's
    # width on the axis PERPENDICULAR to a needed scrollbar — borrowing the surrounding white margin so
    # the bar sits in reserved space and the grid never reflows — and (b) drops that side's scroll-
    # padding, so even when the pane is already maxed (no room to grow) the gridlines themselves still
    # fit. It runs off resize/boot (and a render/sidebar nudge), never the scroll path — no scroll-time
    # work, no bobble — and uses no ResizeObserver / scroll-timeline.
    js = page_assets._FREEZE_JS
    assert "fit" in js                                          # the reservation pass
    assert "data-base" in js or "baseW" in js                  # reads the pane's published base size
    assert "paddingRight" in js and "paddingBottom" in js      # drops the cross-axis margin if maxed
    assert "offsetWidth" in js and "clientWidth" in js         # measures the live scrollbar width
    assert "ResizeObserver" not in js and "scroll-timeline" not in js  # still no fixed-box machinery


def test_tooltip_dismiss_script_drops_hover_help_before_a_reflow():
    # A Quasar tooltip shows on its anchor's mouseenter and hides on the matching mouseleave; when the
    # anchor is removed or reflowed out from under a stationary cursor no mouseleave ever fires, so the
    # tooltip is stranded. The dismiss script is capture-phase listeners that synthesize that mouseleave
    # before the reflow: from the pressed node on pointerdown (a click presses the anchor), and from the
    # hovered element on keydown / wheel (a keyboard commit or wheel-step reflows with no pointerdown,
    # so the at-risk tooltip is on whatever the cursor rests on — dropped only when one is showing).
    js = page_assets._TOOLTIP_DISMISS_JS
    assert "__rttTipDismiss" in js                                  # guarded so it installs only once
    assert "addEventListener('pointerdown'" in js and ", true)" in js  # capture phase, before the click
    assert "keydown" in js and "wheel" in js                        # the pointerdown-free reflow triggers too
    assert ":hover" in js and ".q-tooltip" in js                    # drop the HOVERED tooltip, only when showing
    assert "mouseleave" in js and "dispatchEvent" in js            # synthesizes the event Quasar hides on
    assert "parentElement" in js                                   # walks up to reach the tooltip's anchor
    assert "blur" not in js  # never blur — that would trip the editable cells' blur-commit handlers


def test_every_show_toggle_has_a_non_empty_example():
    # every Show layer must have a sample render: the "general" layers as parts of the dummy tile
    # (_general_part_html), every OTHER group's toggles in the example column (_example_html) — the
    # "specific tiles & controls" grid layers and the "interface" app-wide behaviours alike. No layer
    # may be missing its sample — except the pure grouping parents (temperament / form / tuning),
    # which carry no grid layer of their own and so deliberately render a blank example cell.
    for group_name, items in show_settings.SHOW_GROUPS:
        for key, _l, _d in items:
            if group_name == "general":
                assert render_html._general_part_html(key).strip(), f"no tile sample for {key}"
            elif key in show_settings.GROUPING_PARENTS:
                assert render_html._example_html(key) == "", f"grouping parent {key} should have a blank example"
            else:
                assert render_html._example_html(key).strip(), f"no example for {key}"


def test_interface_behaviours_are_the_visual_settings_box_toggles_default_on_ch2():
    # the three app-wide interaction behaviours (animations / preview highlighting / tooltips) are
    # the visual-settings box's icon toggles (alongside dark mode), pulled out of the show/example
    # list since they are generic app settings, not RTT layers; each ships ON, is live (not greyed),
    # reveals at chapter 2, and is a flat top-level on/off with no sub-controls.
    keys = ("animations", "preview_highlighting", "tooltips")
    assert [k for k, *_ in show_settings.VISUAL_TOGGLES] == list(keys)
    grouped = {k for _, items in show_settings.SHOW_GROUPS for k, *_ in items}
    for key in keys:
        assert key not in grouped  # no longer a show/example row
        assert show_settings.DEFAULTS[key] is True
        assert key in show_settings.IMPLEMENTED
        assert show_settings.CHAPTER[key] == 2
        assert show_settings.reveal_chapter(key) == 2
        assert key not in show_settings.SUBCONTROLS


def test_example_html_renders_each_specific_groups_special_sample_kind():
    # the "specific tiles & controls" group's graphical samples carry their own markup: the
    # colorization swatches are wash-coloured chips stamped with their driving matrix (𝑀 mapping,
    # 𝐺 generator embedding, 𝐹 form), audio a speaker glyph, tuning ranges the min/max I-beam SVG.
    for key, letter, group in (("temperament_colorization", "𝑀", "temperament"),
                               ("tuning_colorization", "𝐺", "tuning"),
                               ("form_colorization", "𝐹", "form")):
        html = render_html._example_html(key)
        assert f"--wash-{group}" in html         # the swatch rides the group's wash variable (so it
        assert render_html._math_html(letter) in html    # retints with the grid in dark mode)...stamped with its matrix letter
    assert "<svg" in render_html._example_html("tuning_ranges")  # the min/max I-beam


def test_audio_bank_leads_with_a_mute_kill_switch_defaulting_to_on():
    # the bank's first control is mute: it doubles as the kill switch (its engine fn stops all
    # audio) and the engage gate (muting is what blocks a clicked cell from sounding). Audio now
    # starts ON (unmuted), so the bank shows the plain (volume_up) glyph; muting shows the slash.
    assert [ctrl for ctrl, *_ in page_assets._AUDIO_BANK] == ["mute", "wave", "mode", "hold", "root"]
    assert page_assets._AUDIO_BANK[0][2] == "toggleMute"               # wired to the engine's mute/kill
    mute_up, mute_off = page_assets._AUDIO_GLYPHS["mute"]
    assert "volume_up" in mute_up and "volume_off" in mute_off  # speaker / speaker-with-slash
    assert page_assets._AUDIO_BANK[0][1] == mute_up                    # default unmuted → the plain glyph shows


def test_general_tile_renders_its_special_samples():
    # the dummy tile's graphical / styled samples: the value cell is an EBK-framed box (hand-drawn
    # SVG marks + a bordered cell) the closed form and value sit inside; the symbol is the styled
    # bold-italic n; the presets field looks like a real dropdown ("(presets)" + a caret); charts a
    # sparkline (the shared render).
    assert "<svg" in render_html._general_part_html("gridded_values")   # the EBK frame marks...
    assert "border" in render_html._general_part_html("gridded_values")  # ...around a bordered value box
    assert "log" in render_html._general_part_html("math_expressions")  # 1200·log₂(3/2)
    # the "=" belongs to the math EXPRESSION, not the numeric value (so it shows only with the form)
    assert "=" in render_html._general_part_html("math_expressions")
    # the value is the bare number — no "=" in its VISIBLE text (the stacked face carries "=" only
    # inside HTML attributes like class=, never as a displayed glyph)
    assert "=" not in re.sub(r"<[^>]+>", "", render_html._general_part_html("quantities"))
    assert 'font-style:italic">n</span>' in render_html._general_part_html("symbols")  # the styled 𝒏
    # the units sample reads "units: ¢/p" — the "units:" prefix (as on a real tile) and a unit
    # naming what it is (cents per prime), the variable p bold like real units
    units = render_html._general_part_html("units")
    assert "units: " in units and "¢" in units and "<b>p</b>" in units
    assert "(presets)" in render_html._general_part_html("presets")       # the placeholder...
    assert "arrow_drop_down" in render_html._general_part_html("presets")  # ...and the dropdown caret
    chart = render_html._general_part_html("charts")
    assert "<svg" in chart                  # the sparkline...
    assert render_html._CHART_GRID in chart         # ...with at least one grey horizontal tick line
    assert "<svg" in render_html._tile_fold_html()  # the decorative top-left fold toggle (a boxed chevron)


def test_general_tile_value_is_the_grids_stacked_three_decimal_face():
    # a gridded cents value appears in the real grid as the whole integer part big over a
    # three-decimal .fraction stacked BENEATH it (the grid's .rtt-stacked-main / -sub classes), not
    # as a flat inline number. The dummy tile reads like a live cell: 701 over .955 (the pure fifth,
    # 3 dp). The whole part and its decimals are SEPARATE click targets (quantities / decimals), so
    # the .fraction can be toggled on its own.
    assert render_html._TILE_VALUE == "701.955"                           # 3 dp, the grid's cents precision
    whole = render_html._general_part_html("quantities")
    assert 'class="rtt-stacked-main">701<' in whole              # the big whole part, its own target
    assert ".955" not in whole and "rtt-stacked-sub" not in whole  # the fraction is NOT here…
    frac = render_html._general_part_html("decimals")
    assert 'class="rtt-stacked-sub">.955<' in frac               # …it is the decimals part below


def test_dummy_tile_chart_rides_the_themeable_mark_colors():
    # the sample sparkline's bars + axes must ride the shared mark colour (BR_COLOR) and its
    # gridlines the shared chart-grid colour — the same tokens the real chart and the EBK frame
    # use — so the dark overlay's attribute rules retint them. A hardcoded pure black would be
    # invisible on the dark pane (the bug: bars/axes that stay black in dark mode).
    chart = render_html._example_chart()
    assert marks.BR_COLOR in chart and render_html._CHART_GRID in chart
    assert "#000" not in chart


def test_general_tile_equivalence_mixes_object_stylings():
    # the equivalence 𝒏 = 𝑒G shows styling variety: an italic scalar e and an upright (matrix) G,
    # distinct from the bold-italic map 𝒏 — so the equation reads as a mix of mathematical objects.
    equiv = render_html._general_part_html("equivalences")
    assert 'font-style:italic">e</span>' in equiv  # the italic scalar e (not bold-italic)
    assert ">G<" in equiv or equiv.rstrip().endswith("G")  # the upright G, unstyled


def test_interest_example_is_the_bold_interval_symbol():
    # the mockup labels each interval-of-interest 𝐢 (bold upright, like the vectors), so
    # the toggle's example shows that same glyph
    assert render_html._math_html("𝐢") in render_html._example_html("interest")


def test_general_tile_covers_every_general_layer_exactly_once():
    # the "general" group is rendered as a single clickable dummy tile (the alternative to a
    # column of checkboxes); _GENERAL_TILE_LINES lays most layers out in tile order, and two more
    # (header_symbols, cell_units) ride INSIDE the value cell (_TILE_IN_CELL_LAYERS) rather than on
    # a line of their own. Together they must account for EVERY general toggle exactly once — a new
    # general layer can't slip in without earning a place (and a click target) in the tile.
    general = [key for key, _label, _default in dict(show_settings.SHOW_GROUPS)["general"]]
    covered = [key for line in page_assets._GENERAL_TILE_LINES for key in line] + list(page_assets._TILE_IN_CELL_LAYERS)
    assert sorted(covered) == sorted(general)
    assert len(covered) == len(set(covered))  # no layer placed twice
    for key in covered:  # every covered part renders a non-empty sample (the builder uses this)
        assert render_html._general_part_html(key).strip(), f"empty tile part for {key}"


def test_general_tile_rides_each_subcontrol_on_its_parents_line():
    # a sub-control refines its parent layer, so in the tile it shares that layer's line rather
    # than getting a line of its own: equivalences extends the symbol (𝒏 = 𝑒G), mnemonics
    # underlines the name. Every general sub-control must sit on a line WITH its parent.
    lines = page_assets._GENERAL_TILE_LINES
    general_subs = {k: p for k, p in show_settings.SUBCONTROLS.items()
                    if k in [key for key, *_ in dict(show_settings.SHOW_GROUPS)["general"]]}
    assert general_subs  # guard the test itself: there are general sub-controls to check
    for sub, parent in general_subs.items():
        assert any(sub in line and parent in line for line in lines), (sub, parent)


def test_general_tile_seats_the_value_layers_inside_the_gridded_cell():
    # the value, its closed form and the gridded box are NOT separate tile rows: on a real tile
    # the value and math expression live inside the boxed cell, so the three ride one line. The
    # drag-to-combine grip also rides this line (in a slot left of the row label, like the grid).
    value_line = next(line for line in page_assets._GENERAL_TILE_LINES if "gridded_values" in line)
    assert set(value_line) == {"gridded_values", "math_expressions", "quantities", "decimals",
                               "drag_to_combine"}


def test_general_tile_symbol_and_equivalence_read_as_one_equation():
    # the symbol part is the bold-italic n; the equivalence part is its defining-equation tail,
    # so the two joined read 𝒏 = 𝑒G (the symbol's equation), one source of truth with _TILE_*.
    assert render_html._general_part_html("symbols") == render_html._math_html(render_html._TILE_SYMBOL)
    assert render_html._general_part_html("symbols") + render_html._general_part_html("equivalences") \
        == render_html._math_html(render_html._TILE_SYMBOL + render_html._TILE_EQUIV)


def test_general_tile_name_exposes_its_mnemonic_letter_as_a_separate_target():
    # the name word is split at its symbol-spelling letter so that letter (the mnemonics target)
    # is distinct from the rest of the word (names); the three pieces rejoin to exactly the name.
    before, letter, after = render_html._tile_name_pieces()
    assert before + letter + after == render_html._TILE_NAME
    assert letter == "n"  # the letter the symbol 𝒏 spells, underlined for mnemonics


def test_general_tile_part_reads_black_when_on_grey_when_off_and_inert_under_an_off_parent():
    # each clickable part of the dummy tile shows its toggle's state directly: black + full
    # opacity when on, grey + dimmed when off (the dim also fades the SVG samples, whose strokes
    # a color alone can't grey). Parts carry a pointer cursor; a value-cell part whose host cell
    # is off is inert (no click) until the cell is on. Mnemonics is an underline on the name letter.
    assert "cursor:pointer" in _css_rule(".rtt-tile-part")
    on = _css_rule(".rtt-part-on")
    assert "color:#000" in on and "opacity:1" in on
    off = _css_rule(".rtt-part-off")
    assert "color:#999" in off and "opacity:" in off
    assert "pointer-events:none" in _css_rule(".rtt-part-inert")
    # the mnemonic underline is ALWAYS drawn so the toggle reads as a toggle: grey (like any
    # disabled part) when off, black when on — the colour, not the underline's presence, flips.
    mnem = _css_rule(".rtt-tile-mnem")
    assert "text-decoration:underline" in mnem and "text-decoration-color:#999" in mnem
    assert "text-decoration-color:#000" in _css_rule(".rtt-mnem-underline")


def test_show_toggle_labels_wrap_long_names_onto_two_lines():
    # most toggle labels are short and fit the narrow label column on one line, but "other
    # intervals of interest" needs two — the label honours its embedded newline (pre-line)
    # instead of clipping/overflowing as nowrap would. Its line-height is pinned tight
    # (1) so the two wrapped lines sit almost touching, not spaced like neighbouring rows.
    rule = _css_rule(".rtt-show-item .q-checkbox__label")
    assert "white-space:pre-line" in rule
    assert "line-height:1" in rule


def test_every_option_square_renders_at_one_uniform_size():
    # The settings-panel checkboxes, the box-𝐋 diminuator / target-controls all-interval
    # checkboxes, and the tuning-ranges monotone/tradeoff radio boxes must all render as the
    # SAME square. Previously the in-grid control checkboxes were forced larger (font-size:40px
    # → an 18px box) than the settings (13.5px) and range (16px) boxes; now every q-checkbox box
    # and the range box are pinned to the one shared option-box size so they read identically.
    assert spreadsheet_constants.OPTION_BOX_PX == 16
    assert f"--option-box:{spreadsheet_constants.OPTION_BOX_PX}px" in page_assets._CSS  # the one shared size, set in :root
    box = "var(--option-box)"
    bg = _css_rule(".q-checkbox__bg")
    assert f"width:{box}" in bg and f"height:{box}" in bg  # the visible bordered square
    inner = _css_rule(".q-checkbox__inner")
    assert f"width:{box}" in inner and f"height:{box}" in inner  # ...and its box model
    rangebox = _css_rule(".rtt-rangebox")
    assert f"width:{box}" in rangebox and f"height:{box}" in rangebox
    # the per-control overrides that made the in-grid control checkboxes oversized are gone —
    # the universal rules above now size every box, so nothing re-diverges
    assert ".rtt-control-check .q-checkbox__inner" not in page_assets._CSS
    assert ".rtt-control-check .q-checkbox__label" not in page_assets._CSS


def test_option_box_renders_as_one_svg_for_zoom_stable_appearance():
    # The box + fill is ONE SVG background that scales as a coherent vector — square with an even
    # border at any zoom — instead of a CSS border + inset ::after fill, whose edges snap to the
    # device-pixel grid independently and distort the square / gap at fractional zooms (the reported
    # zoom-dependent jank). The checked SVG carries the black fill, the mixed master a grey fill, the
    # unchecked box only the outline; the tuning-ranges radio box reuses the same art.
    # the box art is one SVG per state, defined once as a :root custom property and referenced
    # everywhere (so the same vector backs the checkbox, the mixed master, and the range box)
    assert page_assets._CSS.count("data:image/svg") == 6  # unchecked / checked / disabled, each a light + dark variant
    bg = _css_rule(".q-checkbox__bg")
    assert "var(--option-box-unchecked)" in bg and "border:none" in bg
    assert "var(--option-box-checked)" in _css_rule('.q-checkbox[aria-checked="true"] .q-checkbox__bg')
    assert "var(--option-box-disabled)" in _css_rule(".rtt-show-mixed .q-checkbox__bg")
    assert "var(--option-box-unchecked)" in _css_rule(".rtt-rangebox")
    # the per-edge CSS fill is gone for both the checkbox and the range box
    assert ".q-checkbox__bg::after" not in page_assets._CSS
    assert ".rtt-rangebox::after" not in page_assets._CSS


def test_brace_is_one_filled_path_with_width_independent_end_curls():
    # the brace is ONE filled variable-width ribbon computed from the width — no
    # composite pieces (so no seams/overshoot). Only the arm length tracks the
    # width; the end-curls/cusp are fixed px shapes identical at any width.
    narrow, wide = marks.brace(44, 14), marks.brace(200, 14)
    for svg in (narrow, wide):
        assert svg.count("<path") == 1  # a single shape
        assert "stroke" not in svg  # filled, not stroked
        assert f'fill="{marks.BR_COLOR}"' in svg  # the one shared bracket colour
    assert 'viewBox="0 0 200.00 14.00"' in wide
    prefix = 0  # the left end-curl is laid down before any arm, so the two paths...
    while narrow[prefix] == wide[prefix]:
        prefix += 1
    assert prefix > 40  # ...agree coordinate-for-coordinate over the curl...
    assert narrow != wide  # ...then diverge once the arm length differs


def test_curly_bracket_is_one_filled_ribbon_within_its_footprint():
    # the generator tuning map's { is a vertical calligraphic brace (the matrix brace
    # turned a quarter-turn): one filled ribbon, no stroke, staying inside its oblong
    svg = marks.curly_bracket(16, 30)
    assert svg.startswith("<svg") and 'viewBox="0 0 16.00 30.00"' in svg
    assert svg.count("<path") == 1 and "stroke" not in svg
    assert f'fill="{marks.BR_COLOR}"' in svg
    pts = re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", svg)
    xs, ys = [float(x) for x, _y in pts], [float(y) for _x, y in pts]
    assert 0 <= min(xs) and max(xs) <= 16  # within the bracket-gutter width
    assert 0 <= min(ys) and max(ys) <= 30  # and the cell height


def test_ebk_svg_routes_the_curly_open_brace_to_the_curly_bracket():
    from rtt.app.layout import CellBox
    cb = CellBox("bracket:tuning:genmap:l", 0, 0, 16, 30, "bracket", text="{")
    assert marks.ebk_svg(cb) == marks.curly_bracket(16, 30)  # not the square/angle renderer


def test_bar_chart_draws_one_scaled_bar_per_value_from_the_baseline():
    svg = render_html._bar_chart(272, 64, (0.0, 5.0, 10.0))  # all positive (damage-like)
    assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
    bars = _bars(svg)
    assert len(bars) == 3  # one bar per value
    assert bars[0][1] == 0.0  # the zero value draws no bar height
    assert bars[2][1] > bars[1][1] > 0  # a taller bar for the larger value


def test_bar_chart_extends_its_axis_past_the_tallest_bar_for_a_top_gridline():
    # standard chart practice: the value axis runs one nice step past the data so a
    # gridline always sits ABOVE the tallest bar (the bar must never reach the top edge)
    svg = render_html._bar_chart(272, 64, (0.0, 5.0, 10.0))
    bar_tops = [y for y, ht in _bars(svg) if ht > 0]  # the drawn bars' top edges
    gridlines = [float(y) for y in re.findall(
        rf'<line x1="[\d.]+" y1="([\d.]+)"[^>]*stroke="{render_html._CHART_GRID}"', svg)]
    assert gridlines and bar_tops
    assert min(gridlines) < min(bar_tops)  # the top gridline is above the tallest bar


def test_bar_chart_straddles_a_shared_zero_baseline_for_signed_values():
    up, down = _bars(render_html._bar_chart(272, 64, (5.0, -5.0)))  # signed (retuning-like)
    # the positive bar's bottom meets the negative bar's top at the common zero line
    assert abs((up[0] + up[1]) - down[0]) < 0.01
    assert up[0] < down[0]  # positive rises above the baseline, negative drops below it


def test_bar_chart_indicator_line_is_broken_by_its_power_labelled_mean_damage():
    # the minimized-damage indicator: a solid grey line BROKEN by its ⟪𝐝⟫ label (the label
    # sits in a gap in the line), the scheme's Lp power as the subscript
    svg = render_html._bar_chart(272, 64, (0.0, 10.0, 26.385), indicator=26.385, indicator_label="∞")
    # the line is drawn in two segments (a stub left of the label, the rest to its right),
    # leaving the gap the label fills — not one unbroken rule
    assert svg.count(f'stroke="{render_html._CHART_INDICATOR}"') == 2
    # the label reads ⟪𝐝⟫ with the power (∞) as a subscript, the 𝐝 bold
    assert "⟪" in svg and "⟫" in svg and "∞" in svg
    assert 'font-weight="bold"' in svg
    # ...and a plain chart (no indicator) draws no such line or label
    plain = render_html._bar_chart(272, 64, (0.0, 10.0, 26.385))
    assert f'stroke="{render_html._CHART_INDICATOR}"' not in plain
    assert "⟪" not in plain


def test_bar_chart_renders_numerically_flat_dust_without_dividing_by_zero():
    # a retuning that is "made to vanish" (held/comma intervals) cancels to floating-point
    # dust (~1e-13), not exact zero. That all-but-zero range slips past the exact-equal tick
    # guard yet collapses to a single value once the ticks are rounded — which zeroed the
    # axis span and crashed the chart's y-scaling with ZeroDivisionError (hit by clicking
    # optimize with charts on). Numerically-flat data must render flat, not raise.
    svg = render_html._bar_chart(272, 64, (1e-13, -2e-14, 3e-14))  # must not raise
    assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
    bars = _bars(svg)
    assert len(bars) == 3  # one (flat) bar per value
    assert all(abs(height) < 0.01 for _y, height in bars)  # dust rests on the baseline, not blown up


def test_range_chart_draws_an_i_beam_with_min_max_labels_for_a_ranged_generator():
    # the generator tuning-ranges chart: a tall I-beam (stem + two caps) for a generator
    # with a range, the max/min cents labelled at its top/bottom caps. The "tuning ranges"
    # title is a boxtitle above the chart now, not drawn inside this SVG.
    svg = render_html._range_chart(92, 96, ((1200.0, 1200.0), (685.714, 720.0)))
    assert svg.startswith("<svg") and 'viewBox="0 0 92.00 96.00"' in svg
    assert "tuning ranges" not in svg  # the title moved out to a boxtitle
    for label in ("720.000", "685.714"):  # the fifth's max (top cap) and min (bottom cap), 3dp like the grid
        assert label in svg
    heights = [height for _y, height in _bars(svg)]
    assert max(heights) > 30  # the ranged generator's I-beam stem spans the plot area


def test_range_chart_ticks_the_live_tuning_within_a_generators_range():
    # the live generator tuning is marked as a horizontal tick between the min/max caps,
    # at its proportional position within the range (here ~2/3 of the way down)
    marks = sorted(y for y, height in _bars(render_html._range_chart(92, 96, ((685.714, 720.0),), (697.0,))) if height < 4)
    assert len(marks) == 3  # max cap (top), live-tuning tick (interior), min cap (bottom)
    assert marks[0] < marks[1] < marks[2]  # the tick sits strictly between the two bounds
    # with no live tuning supplied (the bare helper), only the two range caps are drawn
    plain = sorted(y for y, height in _bars(render_html._range_chart(92, 96, ((685.714, 720.0),))) if height < 4)
    assert len(plain) == 2


def test_range_chart_draws_only_a_flat_cap_for_a_pinned_generator():
    # the period is pinned (octave held pure), so its [min, max] is a point — drawn as a
    # single flat cap with one value label, not a misleading full-height range bar
    svg = render_html._range_chart(92, 96, ((1200.0, 1200.0),))
    assert "1200.000" in svg
    heights = [height for _y, height in _bars(svg)]
    assert heights and max(heights) < 10  # only a flat cap, no tall range stem


def test_range_chart_shows_a_placeholder_and_no_i_beams_when_there_is_no_range():
    # the diamond-monotone range can be empty (no monotone tuning); show a placeholder
    svg = render_html._range_chart(92, 96, ())
    assert "no range" in svg  # the placeholder text
    assert "<rect" not in svg  # no I-beams drawn


def _first_font(html):
    return float(html.split("font-size:")[1].split("px")[0])


def test_mathexpr_html_stacks_two_lines_each_with_a_fitted_font():
    html = render_html._mathexpr_html("1200 · log₂(3/2)\n= 701.96", 30)
    # a wrapper plus one div per line, each carrying its own inline font-size
    assert html.count("<div") == 3
    assert html.count("font-size:") == 2
    assert "1200 · log₂(3/2)" in html and "= 701.96" in html


def test_mathexpr_font_shrinks_for_longer_expressions():
    short = render_html._mathexpr_html("1200 · log₂2\n= 1200.00", 30)  # short prime-map expression
    long = render_html._mathexpr_html("1200 · log₂(6/5)\n= 315.64", 30)  # longer target-ratio one
    assert _first_font(long) < _first_font(short)  # the longer line is scaled down to fit


def test_fit_font_is_clamped_between_the_min_and_max():
    assert render_html._fit_font("x", 30) == render_html._EXPR_MAX_FONT  # a tiny line caps at the max
    assert render_html._fit_font("x" * 100, 30) == render_html._EXPR_MIN_FONT  # a huge line floors at the min


def test_mathexpr_elides_a_giant_ratio_operand_instead_of_streaking():
    # a target / comma can be an astronomically large ratio; rendered literally,
    # "1200 · log₂(N/D)" streaks clear across the page. When the line can't fit even at the
    # minimum font, the operand is elided to "(…/…)" so it stays in its cell — the exact size
    # still shows on the "= cents" line below. Built through the real _math_expr/_log_operand so
    # the elision keys off the same "log₂" literal the renderer receives.
    giant = spreadsheet_text._math_expr(
        spreadsheet_text._log_operand("2" * 80 + "/" + "3" * 60), 240000.0, show_value=True)
    html = render_html._mathexpr_html(giant, 37)
    assert "1200 · log₂(…/…)" in html      # the giant ratio is elided, its ratio shape kept
    assert "2" * 80 not in html            # the huge numerator is gone
    assert "= " in html                    # the cents value line is untouched
    assert _first_font(html) > render_html._EXPR_MIN_FONT  # the elided line now genuinely fits (off the floor)


def test_mathexpr_elides_a_giant_bare_integer_operand_to_an_ellipsis():
    # a whole-number target (denominator 1) has a bare operand, no parens; a giant one elides to a
    # lone "…", matching the un-parenthesised form a small one (log₂65536) takes.
    giant = spreadsheet_text._math_expr(
        spreadsheet_text._log_operand("2" * 80 + "/1"), 96000.0, show_value=True)
    html = render_html._mathexpr_html(giant, 37)
    assert "1200 · log₂…" in html and "(…" not in html
    assert "2" * 80 not in html


def test_mathexpr_leaves_a_small_operand_intact():
    # an operand that fits at the minimum font is never elided — no spurious "…"
    html = render_html._mathexpr_html("1200 · log₂(3/2)\n= 701.96", 37)
    assert "1200 · log₂(3/2)" in html and "…" not in html


def test_elided_expr_line_fits_its_cell_at_the_fitted_font():
    # the elided line is chosen so it fits the cell at the font the renderer then picks for it,
    # using the same glyph-width estimate _fit_font uses — i.e. the elision actually resolves the
    # overflow rather than merely shortening it.
    raw = "1200 · log₂(" + "2" * 100 + "/" + "3" * 100 + ")"
    elided = render_html._elide_expr_line(raw, 37)
    assert elided == "1200 · log₂(…/…)"
    assert len(elided) * render_html._EXPR_CHAR_W * render_html._fit_font(elided, 37) <= 37


def test_plain_text_font_shrinks_to_fit_with_no_readability_floor():
    # the plain-text contract is fit-on-ONE-line, so the sizer has NO readability floor:
    # the denser the value the smaller the font (a prescaling ket-matrix at a high prime
    # limit shrinks well past any legible floor), while a short value grows to the cap.
    dense = render_html._plain_text_font("9.999 " * 40, 120)    # ~240 chars in a narrow box
    denser = render_html._plain_text_font("9.999 " * 80, 120)   # twice as long → smaller still
    assert denser < dense < 5.0                     # keeps shrinking past the old 5px floor
    assert render_html._plain_text_font("1 0 0", 120) == spreadsheet_constants.PLAIN_TEXT_MAX_FONT  # short value hits the cap
    assert render_html._plain_text_font("x" * 9, 30) <= spreadsheet_constants.PLAIN_TEXT_MAX_FONT   # never exceeds the cap


def test_plain_text_font_is_glyph_aware_not_uniform_width():
    # width is summed from real per-glyph widths, not length×constant: a punctuation/space-
    # heavy value (narrow glyphs) fits a bigger font than a digit-dense value of the SAME
    # length, so a sparse string like a prescaling ket-matrix uses the room it actually has.
    sparse = "0 0 0 0 0 0 0 0 0 0"   # zeros split by (narrow) spaces
    dense = "0000000000000000000"    # all (wide) digits, identical length
    assert len(sparse) == len(dense)
    assert render_html._plain_text_font(sparse, 40) > render_html._plain_text_font(dense, 40)


def test_approach_radio_is_visible_iff_the_domain_has_nonprime_elements():
    # the chapter-9 nonstandard-domain-approach radio (prime-based / nonprime-based / neutral)
    # is hidden when the loaded basis is all primes (the approach trait is meaningless there),
    # visible when the basis carries any non-prime element. The visibility predicate the radio
    # binds to is exposed for test coverage so the gating is checkable without driving NiceGUI.
    from rtt.app.editor import Editor

    editor = Editor()  # 2.3.5 standard prime limit — no nonprimes
    assert render_html._approach_visible(editor) is False
    # BARBADOS over 2.3.13/5: 13/5 is a nonprime element, so the radio appears
    assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
    assert render_html._approach_visible(editor) is True


def test_target_chooser_default_limit_uses_the_nonstandard_basis():
    # the chooser's default limit derives from the loaded temperament's domain basis: on
    # Barbados (2.3.13/5) the next prime past 13 is 17, so TILT defaults to 16 — not the 6
    # a standard-prime reading (2.3.5: next prime past 5 is 7) would give
    from rtt.app.editor import Editor
    editor = Editor()
    assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
    rec = _Reconciler(editor)
    assert rec._target_preset_values() == (16, "TILT")


def test_target_chooser_resets_to_dash_when_the_domain_empties_the_target_set():
    from rtt.app.editor import Editor
    editor = Editor()
    assert editor.try_edit_mapping_text("5.7 [⟨1 0] ⟨0 1]}") is True
    editor.set_target_spec("5-TILT")
    assert editor.current_targets() == []
    assert _Reconciler(editor)._target_preset_values() == (None, None)


def test_dense_prescaling_plain_text_fits_its_cell():
    # the reported overflow: the complexity-prescaler and prescaled-target-list tiles hold
    # the densest plain text (a d×k ket-matrix linearised onto one line). Each must fit its
    # cell width at the sizer's font — no spill off the tile's right edge. The estimated
    # width (glyph-aware, calibrated >= the real render) fitting guarantees the render fits.
    s = show_settings.defaults()
    s.update(plain_text_values=True, weighting=True, alt_complexity=True)
    # the prescaling row is gated on alternative complexity (or an all-interval scheme); turning it
    # on reveals the row without changing the prescaler values (the prescaler is slope-independent)
    cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                tuning_scheme="TILT minimax-S").cells}
    for cid in ("plain_text:prescaling:primes", "plain_text:prescaling:targets"):
        c = cells[cid]
        assert render_html._plain_text_units(c.text) * render_html._plain_text_font(c.text, c.width) <= c.width, cid


def test_units_fit_their_cell_for_long_alternative_complexity_annotations():
    # the units column / per-cell units carry the live scheme's annotated unit — ¢(E-sopfr-S)/,
    # (E-sopfr-C) — far longer than the old ¢/ or (C)/. Each must fit its cell width at the fitted
    # font, never spilling the tile (the reported "units spill the units col" bug). The 0.5 char
    # estimate overshoots the units sans (Corbel ≈0.42 em), so an estimate-fit guarantees the
    # render fits.
    s = show_settings.defaults()
    s.update(units=True, domain_units=True, weighting=True)
    cells = spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                              tuning_scheme="TILT minimax-E-sopfr-S").cells
    shrunk = False
    for c in cells:
        if c.kind == "units":
            font = render_html._units_font(c.text, c.width, page_assets._UNITS_MAX_FONT)
            assert len(c.text) * render_html._EXPR_CHAR_W * font <= c.width, f"units {c.id}={c.text!r}"
            shrunk = shrunk or font < page_assets._UNITS_MAX_FONT
        if c.unit:
            font = render_html._units_font(c.unit, c.width, page_assets._CELLUNIT_MAX_FONT)
            assert len(c.unit) * render_html._EXPR_CHAR_W * font <= c.width, f"cellunit {c.id}={c.unit!r}"
    # the long annotation actually triggered a shrink (the fit engaged — not a trivial pass)
    assert shrunk, "no units cell shrank — the long-annotation fit never engaged"


def test_tour_steps_are_well_formed_and_assets_wired():
    # the guided-tour steps drive the client engine (assets/tour.js); each must carry the copy the
    # card renders, and a non-empty selector must look like a CSS selector (a region class), never a
    # NiceGUI .mark() name (which is test-only and never reaches the DOM the tour queries).
    assert page_assets._TOUR_STEPS, "no tour steps defined"
    for step in page_assets._TOUR_STEPS:
        assert step["title"] and step["body"], f"empty copy: {step}"
        sel = step["sel"]
        assert isinstance(sel, str)
        assert sel == "" or sel.startswith("."), f"selector should be a class, got {sel!r}"
    # the engine + styles are bundled the same way the other assets are
    assert page_assets._TOUR_JS.strip(), "tour.js not loaded"
    assert ".rtt-tour-card" in page_assets._CSS, "tour.css not folded into the page stylesheet"
    # the corner replay button has its hover help
    assert "tour" in tooltips.CHROME_HELP


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


def test_reconciler_callback_protocol_matches_marked_methods_exactly():
    # The ReconcilerCallbacks Protocol is the single declared contract of what the reconciler may
    # call. It must name EXACTLY the @cb_method-marked entry points across the four controllers:
    # a rename or dropped mark leaves a declared callback unprovided; an unmapped marked method
    # leaves a control wired to nothing. Either drift fails here loudly.
    from rtt.app.reconciler import required_callback_names

    declared = set(required_callback_names())
    marked = _marked_callback_names()
    assert declared == marked, {
        "declared_only": sorted(declared - marked),
        "marked_only": sorted(marked - declared),
    }
    # a private helper must never be marked — only frontend entry points are callbacks
    assert not any(n.startswith("_") for n in marked)


def test_bind_callbacks_binds_every_declared_callback():
    from types import SimpleNamespace

    from rtt.app.editing import EditController
    from rtt.app.gestures import GestureController
    from rtt.app.reconciler import (
        ReconcilerCallbacks,
        bind_callbacks,
        required_callback_names,
    )

    gestures = GestureController(SimpleNamespace(), None)
    runtime = SimpleNamespace(building=False)
    edits = EditController(SimpleNamespace(), SimpleNamespace(), gestures, None, runtime)

    cb = bind_callbacks(
        edits,
        edits.vectors,
        edits.tuning,
        edits.controls,
        gestures,
        gestures.combine,
        gestures.hover,
    )
    assert isinstance(cb, ReconcilerCallbacks)
    for name in required_callback_names():
        assert getattr(cb, name)._rtt_cb is True


def test_bind_callbacks_fails_loudly_on_a_missing_callback():
    from rtt.app.reconciler import bind_callbacks, required_callback_names

    class _PartialSource:
        pass

    source = _PartialSource()
    victim = next(iter(required_callback_names()))
    for name in required_callback_names():
        if name != victim:
            setattr(source, name, _cb_stub())

    with pytest.raises(RuntimeError, match=victim):
        bind_callbacks(source)


def test_bind_callbacks_fails_loudly_on_a_duplicate_provider():
    from types import SimpleNamespace

    from rtt.app.reconciler import bind_callbacks, required_callback_names

    full = SimpleNamespace(**{name: _cb_stub() for name in required_callback_names()})
    clash = next(iter(required_callback_names()))
    extra = SimpleNamespace(**{clash: _cb_stub()})

    with pytest.raises(RuntimeError, match="multiple"):
        bind_callbacks(full, extra)


def _cb_stub():
    def stub(*_a, **_k):
        return None

    stub._rtt_cb = True
    return stub
