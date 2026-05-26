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
    assert captured["reload"] is True  # hot-reload: edits are picked up without a manual restart
    assert captured["port"] == 8137  # default dev port when no argv override is given
    assert captured["show"] is False


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


def test_math_html_gives_each_maths_letter_explicit_weight_and_slant():
    # _math_html renders each maths letter as its base ASCII letter in the UI serif
    # with explicit CSS per its block — bold (weight), bold-italic (both), or italic;
    # plain ASCII passes through unstyled (the upright interval lists Y / C / T).
    assert app._math_html("𝐚") == '<span style="font-weight:700">a</span>'  # bold vector list
    assert app._math_html("𝒕") == '<span style="font-weight:700;font-style:italic">t</span>'  # bold-italic map
    assert app._math_html("𝑀") == '<span style="font-style:italic">M</span>'  # italic mapping
    assert app._math_html("𝟎") == '<span style="font-weight:700">0</span>'  # bold zero (the held-error vanishing)
    assert app._math_html("Y") == "Y"  # an upright list passes through, unstyled
    # a product styles each letter on its own (the comma column's 𝒕C: bold-italic map + upright basis)
    assert app._math_html("𝒕C") == '<span style="font-weight:700;font-style:italic">t</span>C'
    # ordinary characters (an equivalence tail's " = " and operators) pass through
    assert app._math_html(" = 𝒈𝑀") == (' = <span style="font-weight:700;font-style:italic">g</span>'
                                         '<span style="font-style:italic">M</span>')


def test_ebk_marks_share_one_colour_and_map_one_to_one_to_their_cell():
    # every EBK mark is one SVG whose viewBox is the cell's own px box, so its
    # weight is a constant px count rather than a scaled stroke — that is what
    # keeps a 1-row and a many-row bracket the exact same thickness.
    marks = {
        "[": app._square_bracket(16, 16, "left"),
        "]2": app._square_bracket(16, 60, "right"),
        "<": app._angle_bracket(16, 16),
        "top": app._top_bracket(120, 9),
        "angle": app._angle_foot(14, 7),  # the raw-monzo column's ket foot (a down-chevron)
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
    assert 'viewBox="0 0 16.00 16.00"' in marks["["]
    assert 'viewBox="0 0 16.00 60.00"' in marks["]2"]  # 1 row vs many: same generator


def test_units_html_bolds_variables_but_not_cents_or_slash():
    # the variable symbols (g, p, the placeholder 1, with subscripts) are bold; the cent
    # sign ¢ and the "/" separator stay un-bold — consistently in the per-box line and the
    # units row/col. A per-box line also keeps "units:" in the serif label face.
    per_box = app._units_html("units: g/p")
    assert per_box == '<span class="rtt-units-pre">units: </span><b>g</b>/<b>p</b>'
    assert app._units_html("units: ¢/g") == '<span class="rtt-units-pre">units: </span>¢/<b>g</b>'
    assert app._units_html("units: ¢") == '<span class="rtt-units-pre">units: </span>¢'
    # bare domain-units coordinate labels: variables bold, ¢ and / plain, the "1" placeholder bold
    assert app._units_html("g₁/") == "<b>g₁</b>/"
    assert app._units_html("/p₁") == "/<b>p₁</b>"
    assert app._units_html("¢/") == "¢/"
    assert app._units_html("/1") == "/<b>1</b>"


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


def test_shared_axis_gridlines_render_two_pixels_thick():
    # the shared coordinate axes (.rtt-line, the rules the cells sit on, threading the
    # gaps between tiles) are the board's gridlines; doubled from 1px to 2px so they read
    # clearly. Both orientations carry the same #e0e0e0 weight.
    assert "border-left:2px solid #e0e0e0" in app._CSS  # the vertical gridlines
    assert "border-top:2px solid #e0e0e0" in app._CSS   # the horizontal gridlines


def _css_rule(selector):
    """The declaration body of the first `selector { ... }` block in the page CSS."""
    m = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", app._CSS)
    assert m, f"no CSS rule for {selector}"
    return m.group(1)


def test_left_rail_height_tracks_the_settings_drawer_not_the_taller_grid():
    # The app-title rail and the settings drawer share .rtt-panelgroup; the rail (no
    # align-self) stretches to that group's height. The group must hug its content
    # (align-self:flex-start) so its height — and the rail's — tracks the drawer, i.e. the
    # open settings panel. With align-self:stretch the group instead grew to the shell's
    # tallest child, so a grid taller than the settings dragged the rail down to the grid's
    # full height rather than matching the panel beside it.
    rule = _css_rule(".rtt-panelgroup")
    assert "align-self:flex-start" in rule
    assert "stretch" not in rule  # never re-stretch to the shell (the grid) height


def test_only_the_body_pane_scrolls_so_the_scrollbar_sits_by_the_body():
    # the four panes are DISJOINT; only the body pane scrolls (overflow:auto), so its scrollbar
    # is the only one and sits beside/below the body — never alongside the frozen title strips,
    # which clip (overflow:hidden). The frame itself clips so nothing leaks past the viewport.
    assert "overflow:auto" in _css_rule(".rtt-bodyscroll")
    assert "overflow:hidden" in _css_rule(".rtt-colhead")
    assert "overflow:hidden" in _css_rule(".rtt-rowhead")
    assert "overflow:hidden" in _css_rule(".rtt-frame")


def test_column_title_strip_bleeds_into_the_right_margin_so_an_overhanging_title_shows():
    # Column titles overhang their content-hugging columns, centred on the gridline (a title
    # wider than its column spills into the gaps/margins; the column is never widened to seat
    # it — see spreadsheet col_w). The RIGHTMOST column's title (e.g. the narrow intervals-of-
    # interest column's "other intervals\nof interest") overhangs the board's right CONTENT edge
    # into the frame's _PAD margin. So the colhead strip must extend that far — right:-_PAD —
    # so its overflow:hidden clips at the FRAME edge, not the grid's content edge; otherwise the
    # title's tail is cut (the split-pane rebuild regressed this by clipping at right:0). The
    # left edge stays clipped at the corner (the frozen row labels) via the inline left:freeze_x.
    assert f"right:-{app._PAD}px" in _css_rule(".rtt-colhead")


def test_shell_is_viewport_bounded_so_the_body_pane_scrolls_internally():
    # the rail+app shell sits in a flex-column (.nicegui-content, align-items:flex-start), so
    # it would otherwise take the grid's full content width and push the HORIZONTAL scroll onto
    # the page — letting the frozen row titles scroll off. Capped to the viewport (max-width)
    # with min-width:0 it stays put and the body pane scrolls the grid within it instead.
    rule = _css_rule(".rtt-shell")
    assert "min-width:0" in rule
    assert "max-width:100%" in rule


def test_title_strips_track_the_body_scroll_on_the_compositor():
    # jank-free pinning: the body publishes named scroll timelines, hoisted to the grid so the
    # sibling strips can read them; each strip-inner rides one and is translated to the body's
    # max scroll (--rtt-maxx/maxy) — a compositor scroll-driven animation, no per-frame JS.
    css = app._CSS
    assert "scroll-timeline-name: --rtt-tlx, --rtt-tly" in css
    assert "timeline-scope: --rtt-tlx, --rtt-tly" in css
    assert "animation-timeline: --rtt-tlx" in css and "animation-timeline: --rtt-tly" in css
    assert "var(--rtt-maxx" in css and "var(--rtt-maxy" in css


def test_seam_and_scrollbar_appear_only_while_scrolled():
    # the seam edges are transparent at rest and take the grey only when the body is scrolled on
    # that axis; the scrollbar thumb is invisible at rest and colours only while scrolling. So
    # neither shows merely because a row/col was added — only when the user actually scrolls.
    css = app._CSS
    assert "border-bottom:1px solid transparent" in css  # column-title seam, hidden at rest
    assert "border-right:1px solid transparent" in css   # row-title seam, hidden at rest
    assert ".rtt-frame.rtt-scrolled-y .rtt-colhead" in css and f"border-bottom-color:{app._SEAM}" in css
    assert ".rtt-frame.rtt-scrolled-x .rtt-rowhead" in css and f"border-right-color:{app._SEAM}" in css
    assert "scrollbar-color:transparent transparent" in css  # invisible scrollbar at rest
    assert ".rtt-frame.rtt-scrolling .rtt-bodyscroll" in css  # coloured only while scrolling


def test_freeze_sync_keeps_blank_space_and_gates_the_chrome_on_scroll():
    # the support script keeps the body's max scroll current via a ResizeObserver (never on
    # scroll); pads the board with a screenful of blank so the body is ALWAYS scrollable (adding
    # a row/col never newly triggers a scrollbar); toggles the seam/scrollbar classes on scroll;
    # and, only without scroll-driven animations, syncs the strips from the scroll listener.
    js = app._FREEZE_JS
    assert "--rtt-maxx" in js and "--rtt-maxy" in js
    assert "ResizeObserver" in js
    assert "paddingRight" in js and "paddingBottom" in js  # the always-present blank space
    assert "rtt-scrolled-x" in js and "rtt-scrolled-y" in js  # seam gating
    assert "rtt-scrolling" in js  # scrollbar gating
    assert "animation-timeline" in js  # the support gate guarding the fallback sync
    assert "scrollLeft" in js and "scrollTop" in js


def test_every_show_toggle_has_a_non_empty_example():
    # the panel's "example" column illustrates each toggle (per the mockup's Show
    # legend), so no toggle may be missing its sample render
    keys = [key for _g, items in show_settings.SHOW_GROUPS for key, _l, _d in items]
    for key in keys:
        assert app._example_html(key).strip(), f"no example for {key}"


def test_example_html_renders_each_special_sample_kind():
    # plain glyph/text samples come through as text; the graphical ones carry their
    # own markup — the EBK gridded mark and the chart are SVGs, the mnemonic sample
    # underlines its symbol letters, the preselect sample shows the chooser caret
    assert "log" in app._example_html("math_expressions")  # log₂3
    # the symbols sample is the bold-italic tuning-map covector, styled (not a raw glyph)
    assert 'font-style:italic">t</span>' in app._example_html("symbols")
    assert "<svg" in app._example_html("gridded_values")  # the ⟨12 19 24] EBK mini-mark
    assert "<svg" in app._example_html("charts")  # the little sparkline
    assert "<u>" in app._example_html("mnemonics")  # underlined mnemonic letters
    assert "▼" in app._example_html("preselects")  # the dropdown caret
    # the colorization subcontrols preview a swatch of their actual wash colour (one
    # source of truth with _TINTS), stamped with the fundamental matrix that drives it:
    # 𝑀 (mapping) for temperament, 𝐺 (generator embedding) for tuning, 𝐹 (form) for form
    for key, letter, group in (("temperament_colorization", "𝑀", "temperament"),
                               ("tuning_colorization", "𝐺", "tuning"),
                               ("form_colorization", "𝐹", "form")):
        html = app._example_html(key)
        assert app._TINTS[group] in html        # the swatch is the real wash colour...
        assert app._math_html(letter) in html   # ...stamped with its matrix letter
    assert "<svg" in app._example_html("tuning_ranges")  # the min/max I-beam


def test_interest_example_is_the_bold_interval_symbol():
    # the mockup labels each interval-of-interest 𝐢 (bold upright, like the vectors), so
    # the toggle's example shows that same glyph
    assert app._math_html("𝐢") in app._example_html("interest")


def test_show_toggle_labels_wrap_long_names_onto_two_lines():
    # most toggle labels are short and fit the narrow label column on one line, but "other
    # intervals of interest" needs two — the label honours its embedded newline (pre-line)
    # instead of clipping/overflowing as nowrap would. Its line-height is pinned tight
    # (1) so the two wrapped lines sit almost touching, not spaced like neighbouring rows.
    rule = _css_rule(".rtt-show-item .q-checkbox__label")
    assert "white-space:pre-line" in rule
    assert "line-height:1" in rule


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


def test_range_chart_draws_a_titled_i_beam_with_min_max_labels_for_a_ranged_generator():
    # the generator tuning-ranges chart: a tall I-beam (stem + two caps) for a generator
    # with a range, the max/min cents labelled at its top/bottom caps
    svg = app._range_chart(92, 96, ((1200.0, 1200.0), (685.714, 720.0)))
    assert svg.startswith("<svg") and 'viewBox="0 0 92.00 96.00"' in svg
    assert "tuning ranges" in svg  # the chart title, per the mockup
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
    assert "tuning ranges" in svg
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


def test_dense_prescaling_plain_text_fits_its_cell():
    # the reported overflow: the complexity-prescaler and prescaled-target-list tiles hold
    # the densest plain text (a d×k ket-matrix linearised onto one line). Each must fit its
    # real cell width at the sizer's font — no spill off the tile's right edge.
    s = show_settings.defaults()
    s.update(plain_text_values=True, weighting=True)
    cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s).cells}
    for cid in ("ptext:prescaling:primes", "ptext:prescaling:targets"):
        c = cells[cid]
        assert len(c.text) * 0.58 * app._ptext_font(c.text, c.w) <= c.w, cid
