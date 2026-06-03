"""Light smoke coverage for the NiceGUI layer.

The interaction logic lives in (and is tested via) rtt.web.editor; here we only
guard that the page module imports/wires cleanly and that input parsing matches
the original app's parseInt semantics. Rendering itself is verified in a browser.
"""

import re
import sys
from pathlib import Path

import rtt.web.app as app
from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.layout import Line


def _bars(svg):
    """(y, height) of each chart bar in an SVG; the thin y-axis rect is excluded by width."""
    rects = re.findall(r'<rect x="[-\d.]+" y="([-\d.]+)" width="([\d.]+)" height="([-\d.]+)"', svg)
    return [(float(y), float(h)) for y, wdt, h in rects if float(wdt) > 1]


def test_app_module_exposes_entry_points():
    assert callable(app.index)
    assert callable(app.main)


def test_main_runs_server_with_reload_enabled(monkeypatch):
    captured = {}
    monkeypatch.setattr(sys, "argv", ["app.py"])
    monkeypatch.setattr(app.ui, "run", lambda **kwargs: captured.update(kwargs))
    app.main()
    # the 8137 default port + hot-reload on + no auto-open-browser contract, in one shot
    assert (captured["reload"], captured["port"], captured["show"]) == (True, 8137, False)


def test_main_sets_browser_tab_title_and_org_favicon(monkeypatch):
    # the browser tab reads "D&D's RTT App" and shows the DandDsRTT GitHub org avatar;
    # NiceGUI takes a remote URL for favicon verbatim, and github.com/<org>.png is the
    # canonical redirect to the org's current icon, so the tab always matches the org.
    captured = {}
    monkeypatch.setattr(sys, "argv", ["app.py"])
    monkeypatch.setattr(app.ui, "run", lambda **kwargs: captured.update(kwargs))
    app.main()
    assert captured["title"] == "D&D's RTT App"
    assert captured["favicon"] == "https://github.com/DandDsRTT.png"


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
    captured = {}
    monkeypatch.setattr(sys, "argv", ["app.py"])
    monkeypatch.setattr(app.ui, "run", lambda **kwargs: captured.update(kwargs))
    app.main()
    excludes = [e.strip() for e in captured["uvicorn_reload_excludes"].split(",")]
    for default in (".*", ".py[cod]", ".sw.*", "~*"):
        assert default in excludes
    for e in excludes:
        if Path(e).is_absolute():
            assert Path(e).is_dir(), f"absolute exclude {e!r} must be an existing dir (else Py3.14 glob crash)"
    worktrees = Path(app.__file__).resolve().parents[2] / ".claude" / "worktrees"
    assert (str(worktrees) in excludes) == worktrees.is_dir()


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
    config = Config("rtt.web.app:app", reload=True,
                    reload_excludes=excludes, reload_dirs=[str(repo)])  # must not raise on Py3.14
    file_filter = FileFilter(config)

    assert file_filter(worktrees / "wt1" / "rtt" / "web" / "app.py") is False  # agent edit: no reload
    assert file_filter(repo / "rtt" / "web" / "app.py") is True  # main-repo source edit: reloads


def test_parse_int_accepts_integers_and_rejects_partial_input():
    assert app._parse_int("5") == 5
    assert app._parse_int("-4") == -4
    assert app._parse_int("  3 ") == 3
    assert app._parse_int("") is None
    assert app._parse_int("-") is None
    assert app._parse_int("x") is None
    assert app._parse_int(None) is None


def test_ratio_parts_splits_fractions_and_passes_through_non_fractions():
    assert app._ratio_parts("3/2") == ("3", "2")  # rendered as a stacked fraction
    assert app._ratio_parts("2/1") == ("2", "1")
    assert app._ratio_parts("5") is None  # a bare integer is not a fraction
    assert app._ratio_parts("") is None


def test_cents_parts_splits_whole_and_fraction_for_decimal_alignment():
    assert app._cents_parts("1899.26") == ("1899", "26")  # big whole, small fraction
    assert app._cents_parts("-2.69") == ("-2", "69")
    assert app._cents_parts("0.00") == ("0", "00")
    assert app._cents_parts("5") == ("5", "")  # no fractional part


def test_underline_html_wraps_only_the_marked_spans():
    # no spans -> plain text (the caption with mnemonics off)
    assert app._underline_html("tuning map", ()) == "tuning map"
    # a leading one-letter span -> just that letter underlined (the symbol mnemonic)
    assert app._underline_html("tuning map", ((0, 1),)) == "<u>t</u>uning map"
    # a span mid-string keeps the surrounding text intact
    assert app._underline_html("(temperament) mapping", ((14, 1),)) == "(temperament) <u>m</u>apping"
    # a descender letter (g/j/p/q/y) is tagged so only its underline drops below the
    # tail; non-descenders keep the normal snug underline
    assert app._underline_html("just tuning map", ((0, 1),)) == '<u class="rtt-desc">j</u>ust tuning map'


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
        html = app._math_html(glyph)
        assert f">{base}</span>" in html, glyph
        assert ("font-weight:700" in html) is want_bold, glyph
        assert ("font-style:italic" in html) is want_italic, glyph
    assert app._math_html("Y") == "Y"  # an upright list passes through, unstyled


def test_math_html_styles_products_per_letter_and_honours_the_subscript_sentinels():
    # a product styles each letter on its own (the comma column's 𝒕C: bold-italic map +
    # upright basis; an equivalence tail's 𝒈𝑀); ordinary characters pass through
    assert app._math_html("𝒕C") == app._math_html("𝒕") + "C"
    assert app._math_html(" = 𝒈𝑀") == " = " + app._math_html("𝒈") + app._math_html("𝑀")
    # NORM_SUB forces an italic subscript (the complexity row's trailing q); SUB is a PLAIN
    # subscript where only the math-italic 𝑞 slants (the dual(q) objective: "dual" upright)
    assert app._math_html(spreadsheet.NORM_SUB_OPEN + "q" + spreadsheet.NORM_SUB_CLOSE) == \
        '<sub style="font-style:italic">q</sub>'
    plain = app._math_html(spreadsheet.SUB_OPEN + "dual(𝑞)" + spreadsheet.SUB_CLOSE)
    assert plain.startswith("<sub>dual(") and plain.endswith(")</sub>") and "font-style:italic" in plain


def test_ebk_marks_share_one_colour_and_map_one_to_one_to_their_cell():
    # every EBK mark is one SVG whose viewBox is the cell's own px box, so its
    # weight is a constant px count rather than a scaled stroke — that is what
    # keeps a 1-row and a many-row bracket the exact same thickness.
    marks = {
        "[": app._square_bracket(16, 16, "left"),
        "]2": app._square_bracket(16, 60, "right"),
        "<": app._angle_bracket(16, 16),
        "top": app._top_bracket(120, 9),
        "angle": app._angle_foot(14, 7),  # the raw-vector column's ket foot (a down-chevron)
        "vbar": app._vbar(2, 60),
    }
    for svg in marks.values():
        assert svg.startswith("<svg") and f'fill="{app._BR_COLOR}"' in svg
        assert "stroke-width" not in svg  # weight is the 1:1 viewBox, not a scaling stroke
    assert marks["angle"].count("<path") == 1 and "stroke" not in marks["angle"]  # one filled chevron
    # the down-chevron foot fits inside its oblong like every other mark — its whole
    # footprint (stroke included) stays within the 7px-tall box, never overshooting
    import re
    ys = [float(y) for _x, y in re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", app._angle_foot(14, 7))]
    assert 0 <= min(ys) and max(ys) <= 7
    def _viewbox(svg):
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg)
        return float(m.group(1)), float(m.group(2))
    assert _viewbox(marks["["]) == (16, 16)
    assert _viewbox(marks["]2"]) == (16, 60)  # 1 row vs many: same generator, viewBox == the cell box


def test_units_html_bolds_variables_but_not_cents_oct_or_slash():
    # the variable symbols (g, p, b, the placeholder 1, with subscripts) are bold; the
    # units of interval size — the cent sign ¢ and the spelled-out "oct" (octaves) — and
    # the "/" separator stay un-bold, consistently in the per-box line and the units
    # row/col. A per-box line also keeps "units:" in the serif label face.
    # a per-box line keeps "units:" in the serif label face and bolds its variables
    assert app._units_html("units: g/p") == '<span class="rtt-units-pre">units: </span><b>g</b>/<b>p</b>'
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
        html = app._units_html(text)
        for v in bolded:
            assert f"<b>{v}</b>" in html, (text, v)
        for u in bare:
            assert u in html and f"<b>{u}</b>" not in html, (text, u)


def test_line_style_centres_the_rule_on_its_coordinate():
    # a gridline's W-px border grows off one edge of its zero-size box, so the renderer
    # offsets the box by half the width to seat the rule centred on its coordinate -- the
    # toggle-node / cell-column centre -- rather than leaning a full width off to one side
    half = spreadsheet.LINE_W / 2
    v = app._line_style(Line("trunk:x", "v", 100, 50, 200))
    assert f"left:{100 - half}px" in v  # centred on x=100, not flush at 100
    assert "top:50px" in v and "height:200px" in v  # the length runs unchanged
    h = app._line_style(Line("h:x", "h", 60, 10, 300))
    assert f"top:{60 - half}px" in h  # centred on y=60
    assert "left:10px" in h and "width:300px" in h


def test_line_style_dots_a_collapsed_bands_rule_and_restores_it_when_open():
    # a collapsed row/column converges to one rule, drawn dotted as a placeholder. The dots
    # are a repeating gradient painted through a transparent border (so the zero-size box
    # doesn't resize as a band folds), swept along the rule's length. The border colour and
    # background are emitted every update, so re-expanding restores the solid grey rule.
    v_dotted = app._line_style(Line("trunk:x", "v", 100, 0, 50, dotted=True))
    assert "border-left-color:transparent" in v_dotted and "repeating-linear-gradient(to bottom," in v_dotted
    # painted over the border box -- the box has no width of its own, only the border, so
    # without this the gradient fills the zero-width content box and the dots never show
    assert "border-box" in v_dotted
    v_solid = app._line_style(Line("trunk:x", "v", 100, 0, 50))
    assert "border-left-color:#e0e0e0" in v_solid and "background:none" in v_solid
    h_dotted = app._line_style(Line("h:x", "h", 60, 0, 50, dotted=True))
    assert "border-top-color:transparent" in h_dotted and "repeating-linear-gradient(to right," in h_dotted
    h_solid = app._line_style(Line("h:x", "h", 60, 0, 50))
    assert "border-top-color:#e0e0e0" in h_solid and "background:none" in h_solid
    # the dots are sparse: the transparent gap runs well past the dot's far edge (a LINE_W
    # dot then a gap several times wider), unlike CSS `dotted`'s ~one-width packing
    assert f"transparent {spreadsheet.LINE_W}px {app._DOT_PITCH}px" in v_dotted
    assert app._DOT_PITCH >= 3 * spreadsheet.LINE_W


def test_shared_axis_gridlines_render_two_pixels_thick():
    # the shared coordinate axes (.rtt-line, the rules the cells sit on, threading the
    # gaps between tiles) are the board's gridlines; doubled from 1px to 2px so they read
    # clearly. Both orientations carry the same #e0e0e0 weight.
    assert spreadsheet.LINE_W == 2
    assert f"--line-w:{spreadsheet.LINE_W}px" in app._CSS  # the gridline weight, set in :root
    assert "border-left:var(--line-w) solid #e0e0e0" in app._CSS  # the vertical gridlines
    assert "border-top:var(--line-w) solid #e0e0e0" in app._CSS   # the horizontal gridlines


def _css_rule(selector):
    """The declaration body of the first `selector { ... }` block in the page CSS."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", app._CSS)
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
    assert "padding-left:0" not in app._CSS
    assert ".q-item.disabled .q-item__label::before" in app._CSS  # the flanking rules...
    assert "border-top:1px solid #777" in app._CSS                # ...are grey lines


def test_sidebar_hugs_its_content_as_a_fixed_left_column():
    # The rail + settings drawer share .rtt-panelgroup, the app's fixed left sidebar (flex:none, and
    # no position:sticky — the page never scrolls). Under the shell's align-items:flex-start it HUGS
    # its content height rather than stretching its grey down the window: the rail's title tab when
    # the drawer is collapsed, the settings panel's height when open. The drawer animates its height
    # (grid-template-rows 0fr->1fr) so a collapsed drawer contributes no height (sidebar = rail tab).
    rule = _css_rule(".rtt-panelgroup")
    assert "flex:none" in rule                # fixed width; doesn't grow/shrink with the grid
    assert "position:sticky" not in rule      # no page scroll to pin against
    drawer = _css_rule(".rtt-drawer")
    assert "grid-template-rows:0fr" in drawer  # collapsed -> zero height, so the sidebar hugs the rail
    assert "align-self:flex-start" in drawer   # ...and the panelgroup doesn't stretch it back open


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
    assert f"--pad:{app._PAD}px" in app._CSS  # the grey-margin width, set in :root


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
    assert "pointer-events:auto" in app._CSS  # the row band inner re-enables clicks
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
    # each frozen region's body-facing edge is transparent until the body is scrolled on that axis,
    # when .rtt-app gains rtt-scrolled-x/y (see _FREEZE_JS) and the edge takes the grey seam; the
    # border is always 1px so revealing it shifts nothing.
    css = app._CSS
    assert "border-bottom:1px solid transparent" in css  # column-strip seam, hidden at rest
    assert "border-right:1px solid transparent" in css   # row-band seam, hidden at rest
    assert ".rtt-app.rtt-scrolled-y .rtt-colhead" in css and "border-bottom-color:var(--seam)" in css
    assert ".rtt-app.rtt-scrolled-x .rtt-rowband" in css and "border-right-color:var(--seam)" in css
    assert f"--seam:{app._SEAM}" in css  # the seam colour, set in :root


def test_freeze_script_syncs_the_column_strip_and_toggles_the_seam_on_body_scroll():
    # the only JS is a capture-phase scroll listener over .rtt-gridbody (the body scroller). It
    # translateX-syncs the column-title strip to the body's horizontal scroll (the one thing CSS
    # can't do for a strip lifted out of the scroller) and toggles rtt-scrolled-x/y on .rtt-app from
    # the body's scroll offset to reveal the seams. It never moves the row titles — position:sticky
    # does that — so there is no bobble.
    js = app._FREEZE_JS
    assert ".rtt-gridbody" in js                                # listens to the body scroller
    assert "scrollTop" in js and "scrollLeft" in js             # reads its scroll offset
    assert ".rtt-colhead-inner" in js and "translateX" in js    # syncs the strip horizontally
    assert "rtt-scrolled-x" in js and "rtt-scrolled-y" in js    # toggles the seams
    assert "addEventListener('scroll'" in js
    assert "ResizeObserver" not in js and "scroll-timeline" not in js  # no fixed-box machinery


def test_every_show_toggle_has_a_non_empty_example():
    # every Show layer must have a sample render: the "specific boxes & controls" toggles in the
    # example column (_example_html), the "general" layers as parts of the dummy tile
    # (_general_part_html). No layer may be missing its sample.
    groups = dict(show_settings.SHOW_GROUPS)
    for key, _l, _d in groups["general"]:
        assert app._general_part_html(key).strip(), f"no tile sample for {key}"
    for key, _l, _d in groups["specific boxes & controls"]:
        assert app._example_html(key).strip(), f"no example for {key}"


def test_example_html_renders_each_specific_groups_special_sample_kind():
    # the "specific boxes & controls" group's graphical samples carry their own markup: the
    # colorization swatches are wash-coloured chips stamped with their driving matrix (𝑀 mapping,
    # 𝐺 generator embedding, 𝐹 form), audio a speaker glyph, tuning ranges the min/max I-beam SVG.
    for key, letter, group in (("temperament_colorization", "𝑀", "temperament"),
                               ("tuning_colorization", "𝐺", "tuning"),
                               ("form_colorization", "𝐹", "form")):
        html = app._example_html(key)
        assert app._TINTS[group] in html        # the swatch is the real wash colour...
        assert app._math_html(letter) in html   # ...stamped with its matrix letter
    assert "volume_up" in app._example_html("audio")     # the speaker glyph
    assert "<svg" in app._example_html("tuning_ranges")  # the min/max I-beam


def test_general_tile_renders_its_special_samples():
    # the dummy tile's graphical / styled samples: the value cell is an EBK-framed box (hand-drawn
    # SVG marks + a bordered cell) the closed form and value sit inside; the symbol is the styled
    # bold-italic n; the presets field looks like a real dropdown ("(presets)" + a caret); charts a
    # sparkline (the shared render).
    assert "<svg" in app._general_part_html("gridded_values")   # the EBK frame marks...
    assert "border" in app._general_part_html("gridded_values")  # ...around a bordered value box
    assert "log" in app._general_part_html("math_expressions")  # 1200·log₂(3/2)
    # the "=" belongs to the math EXPRESSION, not the numeric value (so it shows only with the form)
    assert "=" in app._general_part_html("math_expressions")
    assert "=" not in app._general_part_html("quantities")      # the value is the bare number
    assert 'font-style:italic">n</span>' in app._general_part_html("symbols")  # the styled 𝒏
    # the units sample reads "units: ¢/p" — the "units:" prefix (as on a real tile) and a unit
    # naming what it is (cents per prime), the variable p bold like real units
    units = app._general_part_html("units")
    assert "units: " in units and "¢" in units and "<b>p</b>" in units
    assert "(presets)" in app._general_part_html("presets")       # the placeholder...
    assert "arrow_drop_down" in app._general_part_html("presets")  # ...and the dropdown caret
    chart = app._general_part_html("charts")
    assert "<svg" in chart                  # the sparkline...
    assert "#bbb" in chart                  # ...with at least one grey horizontal tick line
    assert "<svg" in app._tile_fold_html()  # the decorative top-left fold toggle (a boxed chevron)


def test_general_tile_equivalence_mixes_object_stylings():
    # the equivalence 𝒏 = 𝑒G shows styling variety: an italic scalar e and an upright (matrix) G,
    # distinct from the bold-italic map 𝒏 — so the equation reads as a mix of mathematical objects.
    equiv = app._general_part_html("equivalences")
    assert 'font-style:italic">e</span>' in equiv  # the italic scalar e (not bold-italic)
    assert ">G<" in equiv or equiv.rstrip().endswith("G")  # the upright G, unstyled


def test_interest_example_is_the_bold_interval_symbol():
    # the mockup labels each interval-of-interest 𝐢 (bold upright, like the vectors), so
    # the toggle's example shows that same glyph
    assert app._math_html("𝐢") in app._example_html("interest")


def test_general_tile_covers_every_general_layer_exactly_once():
    # the "general" group is rendered as a single clickable dummy tile (the alternative to a
    # column of checkboxes); _GENERAL_TILE_LINES lays the layers out in tile order, so it must
    # account for EVERY general toggle exactly once — a new general layer can't slip in without
    # earning a place (and a click target) in the tile.
    general = [key for key, _label, _default in dict(show_settings.SHOW_GROUPS)["general"]]
    placed = [key for line in app._GENERAL_TILE_LINES for key in line]
    assert sorted(placed) == sorted(general)
    assert len(placed) == len(set(placed))  # no layer placed twice
    for key in placed:  # every placed part renders a non-empty sample (the builder uses this)
        assert app._general_part_html(key).strip(), f"empty tile part for {key}"


def test_general_tile_rides_each_subcontrol_on_its_parents_line():
    # a sub-control refines its parent layer, so in the tile it shares that layer's line rather
    # than getting a line of its own: equivalences extends the symbol (𝒏 = 𝑒G), mnemonics
    # underlines the name. Every general sub-control must sit on a line WITH its parent.
    lines = app._GENERAL_TILE_LINES
    general_subs = {k: p for k, p in show_settings.SUBCONTROLS.items()
                    if k in [key for key, *_ in dict(show_settings.SHOW_GROUPS)["general"]]}
    assert general_subs  # guard the test itself: there are general sub-controls to check
    for sub, parent in general_subs.items():
        assert any(sub in line and parent in line for line in lines), (sub, parent)


def test_general_tile_seats_the_value_layers_inside_the_gridded_cell():
    # the value, its closed form and the gridded box are NOT separate tile rows: on a real tile
    # the value and math expression live inside the boxed cell, so the three ride one line.
    value_line = next(line for line in app._GENERAL_TILE_LINES if "gridded_values" in line)
    assert set(value_line) == {"gridded_values", "math_expressions", "quantities"}


def test_general_tile_symbol_and_equivalence_read_as_one_equation():
    # the symbol part is the bold-italic n; the equivalence part is its defining-equation tail,
    # so the two joined read 𝒏 = 𝑒G (the symbol's equation), one source of truth with _TILE_*.
    assert app._general_part_html("symbols") == app._math_html(app._TILE_SYMBOL)
    assert app._general_part_html("symbols") + app._general_part_html("equivalences") \
        == app._math_html(app._TILE_SYMBOL + app._TILE_EQUIV)


def test_general_tile_name_exposes_its_mnemonic_letter_as_a_separate_target():
    # the name word is split at its symbol-spelling letter so that letter (the mnemonics target)
    # is distinct from the rest of the word (names); the three pieces rejoin to exactly the name.
    before, letter, after = app._tile_name_pieces()
    assert before + letter + after == app._TILE_NAME
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
    assert spreadsheet.OPTION_BOX_PX == 16
    assert f"--option-box:{spreadsheet.OPTION_BOX_PX}px" in app._CSS  # the one shared size, set in :root
    box = "var(--option-box)"
    bg = _css_rule(".q-checkbox__bg")
    assert f"width:{box}" in bg and f"height:{box}" in bg  # the visible bordered square
    inner = _css_rule(".q-checkbox__inner")
    assert f"width:{box}" in inner and f"height:{box}" in inner  # ...and its box model
    rangebox = _css_rule(".rtt-rangebox")
    assert f"width:{box}" in rangebox and f"height:{box}" in rangebox
    # the per-control overrides that made the in-grid control checkboxes oversized are gone —
    # the universal rules above now size every box, so nothing re-diverges
    assert ".rtt-control-check .q-checkbox__inner" not in app._CSS
    assert ".rtt-control-check .q-checkbox__label" not in app._CSS


def test_option_box_renders_as_one_svg_for_zoom_stable_appearance():
    # The box + fill is ONE SVG background that scales as a coherent vector — square with an even
    # border at any zoom — instead of a CSS border + inset ::after fill, whose edges snap to the
    # device-pixel grid independently and distort the square / gap at fractional zooms (the reported
    # zoom-dependent jank). The checked SVG carries the black fill, the mixed master a grey fill, the
    # unchecked box only the outline; the tuning-ranges radio box reuses the same art.
    # the box art is one SVG per state, defined once as a :root custom property and referenced
    # everywhere (so the same vector backs the checkbox, the mixed master, and the range box)
    assert app._CSS.count("data:image/svg") == 3  # unchecked / checked / disabled, defined once each
    bg = _css_rule(".q-checkbox__bg")
    assert "var(--option-box-unchecked)" in bg and "border:none" in bg
    assert "var(--option-box-checked)" in _css_rule('.q-checkbox[aria-checked="true"] .q-checkbox__bg')
    assert "var(--option-box-disabled)" in _css_rule(".rtt-show-mixed .q-checkbox__bg")
    assert "var(--option-box-unchecked)" in _css_rule(".rtt-rangebox")
    # the per-edge CSS fill is gone for both the checkbox and the range box
    assert ".q-checkbox__bg::after" not in app._CSS
    assert ".rtt-rangebox::after" not in app._CSS


def test_brace_is_one_filled_path_with_width_independent_end_curls():
    # the brace is ONE filled variable-width ribbon computed from the width — no
    # composite pieces (so no seams/overshoot). Only the arm length tracks the
    # width; the end-curls/cusp are fixed px shapes identical at any width.
    narrow, wide = app._brace(44, 14), app._brace(200, 14)
    for svg in (narrow, wide):
        assert svg.count("<path") == 1  # a single shape
        assert "stroke" not in svg  # filled, not stroked
        assert f'fill="{app._BR_COLOR}"' in svg  # the one shared bracket colour
    assert 'viewBox="0 0 200.00 14.00"' in wide
    prefix = 0  # the left end-curl is laid down before any arm, so the two paths...
    while narrow[prefix] == wide[prefix]:
        prefix += 1
    assert prefix > 40  # ...agree coordinate-for-coordinate over the curl...
    assert narrow != wide  # ...then diverge once the arm length differs


def test_curly_bracket_is_one_filled_ribbon_within_its_footprint():
    # the generator tuning map's { is a vertical calligraphic brace (the matrix brace
    # turned a quarter-turn): one filled ribbon, no stroke, staying inside its oblong
    svg = app._curly_bracket(16, 30)
    assert svg.startswith("<svg") and 'viewBox="0 0 16.00 30.00"' in svg
    assert svg.count("<path") == 1 and "stroke" not in svg
    assert f'fill="{app._BR_COLOR}"' in svg
    pts = re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", svg)
    xs, ys = [float(x) for x, _y in pts], [float(y) for _x, y in pts]
    assert 0 <= min(xs) and max(xs) <= 16  # within the bracket-gutter width
    assert 0 <= min(ys) and max(ys) <= 30  # and the cell height


def test_ebk_svg_routes_the_curly_open_brace_to_the_curly_bracket():
    from rtt.web.layout import CellBox
    cb = CellBox("bracket:tuning:genmap:l", 0, 0, 16, 30, "bracket", text="{")
    assert app._ebk_svg(cb) == app._curly_bracket(16, 30)  # not the square/angle renderer


def test_bar_chart_draws_one_scaled_bar_per_value_from_the_baseline():
    svg = app._bar_chart(272, 64, (0.0, 5.0, 10.0))  # all positive (damage-like)
    assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
    bars = _bars(svg)
    assert len(bars) == 3  # one bar per value
    assert bars[0][1] == 0.0  # the zero value draws no bar height
    assert bars[2][1] > bars[1][1] > 0  # a taller bar for the larger value


def test_bar_chart_extends_its_axis_past_the_tallest_bar_for_a_top_gridline():
    # standard chart practice: the value axis runs one nice step past the data so a
    # gridline always sits ABOVE the tallest bar (the bar must never reach the top edge)
    svg = app._bar_chart(272, 64, (0.0, 5.0, 10.0))
    bar_tops = [y for y, ht in _bars(svg) if ht > 0]  # the drawn bars' top edges
    gridlines = [float(y) for y in re.findall(
        rf'<line x1="[\d.]+" y1="([\d.]+)"[^>]*stroke="{app._CHART_GRID}"', svg)]
    assert gridlines and bar_tops
    assert min(gridlines) < min(bar_tops)  # the top gridline is above the tallest bar


def test_bar_chart_straddles_a_shared_zero_baseline_for_signed_values():
    up, down = _bars(app._bar_chart(272, 64, (5.0, -5.0)))  # signed (retuning-like)
    # the positive bar's bottom meets the negative bar's top at the common zero line
    assert abs((up[0] + up[1]) - down[0]) < 0.01
    assert up[0] < down[0]  # positive rises above the baseline, negative drops below it


def test_bar_chart_indicator_line_is_broken_by_its_power_labelled_objective():
    # the minimized-damage indicator: a solid grey line BROKEN by its ⟪𝐝⟫ label (the label
    # sits in a gap in the line), the scheme's Lp power as the subscript
    svg = app._bar_chart(272, 64, (0.0, 10.0, 26.385), indicator=26.385, indicator_label="∞")
    # the line is drawn in two segments (a stub left of the label, the rest to its right),
    # leaving the gap the label fills — not one unbroken rule
    assert svg.count(f'stroke="{app._CHART_INDICATOR}"') == 2
    # the label reads ⟪𝐝⟫ with the power (∞) as a subscript, the 𝐝 bold
    assert "⟪" in svg and "⟫" in svg and "∞" in svg
    assert 'font-weight="bold"' in svg
    # ...and a plain chart (no indicator) draws no such line or label
    plain = app._bar_chart(272, 64, (0.0, 10.0, 26.385))
    assert f'stroke="{app._CHART_INDICATOR}"' not in plain
    assert "⟪" not in plain


def test_bar_chart_renders_numerically_flat_dust_without_dividing_by_zero():
    # a retuning that is "made to vanish" (held/comma intervals) cancels to floating-point
    # dust (~1e-13), not exact zero. That all-but-zero range slips past the exact-equal tick
    # guard yet collapses to a single value once the ticks are rounded — which zeroed the
    # axis span and crashed the chart's y-scaling with ZeroDivisionError (hit by clicking
    # optimize with charts on). Numerically-flat data must render flat, not raise.
    svg = app._bar_chart(272, 64, (1e-13, -2e-14, 3e-14))  # must not raise
    assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
    bars = _bars(svg)
    assert len(bars) == 3  # one (flat) bar per value
    assert all(abs(h) < 0.01 for _y, h in bars)  # dust rests on the baseline, not blown up


def test_range_chart_draws_an_i_beam_with_min_max_labels_for_a_ranged_generator():
    # the generator tuning-ranges chart: a tall I-beam (stem + two caps) for a generator
    # with a range, the max/min cents labelled at its top/bottom caps. The "tuning ranges"
    # title is a boxtitle above the chart now, not drawn inside this SVG.
    svg = app._range_chart(92, 96, ((1200.0, 1200.0), (685.714, 720.0)))
    assert svg.startswith("<svg") and 'viewBox="0 0 92.00 96.00"' in svg
    assert "tuning ranges" not in svg  # the title moved out to a boxtitle
    for label in ("720.000", "685.714"):  # the fifth's max (top cap) and min (bottom cap), 3dp like the grid
        assert label in svg
    heights = [h for _y, h in _bars(svg)]
    assert max(heights) > 30  # the ranged generator's I-beam stem spans the plot area


def test_range_chart_ticks_the_live_tuning_within_a_generators_range():
    # the live generator tuning is marked as a horizontal tick between the min/max caps,
    # at its proportional position within the range (here ~2/3 of the way down)
    marks = sorted(y for y, h in _bars(app._range_chart(92, 96, ((685.714, 720.0),), (697.0,))) if h < 4)
    assert len(marks) == 3  # max cap (top), live-tuning tick (interior), min cap (bottom)
    assert marks[0] < marks[1] < marks[2]  # the tick sits strictly between the two bounds
    # with no live tuning supplied (the bare helper), only the two range caps are drawn
    plain = sorted(y for y, h in _bars(app._range_chart(92, 96, ((685.714, 720.0),))) if h < 4)
    assert len(plain) == 2


def test_range_chart_draws_only_a_flat_cap_for_a_pinned_generator():
    # the period is pinned (octave held pure), so its [min, max] is a point — drawn as a
    # single flat cap with one value label, not a misleading full-height range bar
    svg = app._range_chart(92, 96, ((1200.0, 1200.0),))
    assert "1200.000" in svg
    heights = [h for _y, h in _bars(svg)]
    assert heights and max(heights) < 10  # only a flat cap, no tall range stem


def test_range_chart_shows_a_placeholder_and_no_i_beams_when_there_is_no_range():
    # the diamond-monotone range can be empty (no monotone tuning); show a placeholder
    svg = app._range_chart(92, 96, ())
    assert "no range" in svg  # the placeholder text
    assert "<rect" not in svg  # no I-beams drawn


def _first_font(html):
    return float(html.split("font-size:")[1].split("px")[0])


def test_mathexpr_html_stacks_two_lines_each_with_a_fitted_font():
    html = app._mathexpr_html("1200 · log₂(3/2)\n= 701.96", 30)
    # a wrapper plus one div per line, each carrying its own inline font-size
    assert html.count("<div") == 3
    assert html.count("font-size:") == 2
    assert "1200 · log₂(3/2)" in html and "= 701.96" in html


def test_mathexpr_font_shrinks_for_longer_expressions():
    short = app._mathexpr_html("1200 · log₂2\n= 1200.00", 30)  # short prime-map expression
    long = app._mathexpr_html("1200 · log₂(6/5)\n= 315.64", 30)  # longer target-ratio one
    assert _first_font(long) < _first_font(short)  # the longer line is scaled down to fit


def test_fit_font_is_clamped_between_the_min_and_max():
    assert app._fit_font("x", 30) == app._EXPR_MAX_FONT  # a tiny line caps at the max
    assert app._fit_font("x" * 100, 30) == app._EXPR_MIN_FONT  # a huge line floors at the min


def test_plain_text_font_shrinks_to_fit_with_no_readability_floor():
    # the plain-text contract is fit-on-ONE-line, so the sizer has NO readability floor:
    # the denser the value the smaller the font (a prescaling ket-matrix at a high prime
    # limit shrinks well past any legible floor), while a short value grows to the cap.
    dense = app._ptext_font("9.999 " * 40, 120)    # ~240 chars in a narrow box
    denser = app._ptext_font("9.999 " * 80, 120)   # twice as long → smaller still
    assert denser < dense < 5.0                     # keeps shrinking past the old 5px floor
    assert app._ptext_font("1 0 0", 120) == spreadsheet.PTEXT_MAX_FONT  # short value hits the cap
    assert app._ptext_font("x" * 9, 30) <= spreadsheet.PTEXT_MAX_FONT   # never exceeds the cap


def test_plain_text_font_is_glyph_aware_not_uniform_width():
    # width is summed from real per-glyph widths, not length×constant: a punctuation/space-
    # heavy value (narrow glyphs) fits a bigger font than a digit-dense value of the SAME
    # length, so a sparse string like a prescaling ket-matrix uses the room it actually has.
    sparse = "0 0 0 0 0 0 0 0 0 0"   # zeros split by (narrow) spaces
    dense = "0000000000000000000"    # all (wide) digits, identical length
    assert len(sparse) == len(dense)
    assert app._ptext_font(sparse, 40) > app._ptext_font(dense, 40)


def test_dense_prescaling_plain_text_fits_its_cell():
    # the reported overflow: the complexity-prescaler and prescaled-target-list tiles hold
    # the densest plain text (a d×k ket-matrix linearised onto one line). Each must fit its
    # cell width at the sizer's font — no spill off the tile's right edge. The estimated
    # width (glyph-aware, calibrated >= the real render) fitting guarantees the render fits.
    s = show_settings.defaults()
    s.update(plain_text_values=True, weighting=True)
    cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s).cells}
    for cid in ("ptext:prescaling:primes", "ptext:prescaling:targets"):
        c = cells[cid]
        assert app._ptext_units(c.text) * app._ptext_font(c.text, c.w) <= c.w, cid
