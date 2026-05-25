"""Light smoke coverage for the NiceGUI layer.

The interaction logic lives in (and is tested via) rtt.web.editor; here we only
guard that the page module imports/wires cleanly and that input parsing matches
the original app's parseInt semantics. Rendering itself is verified in a browser.
"""

import re
import sys
from pathlib import Path

import rtt.web.app as app
from rtt.web import settings as show_settings


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
    # source of truth with _TINTS); tuning ranges previews an I-beam
    assert app._TINTS["temperament"] in app._example_html("temperament_colorization")
    assert app._TINTS["tuning"] in app._example_html("tuning_colorization")
    assert "<svg" in app._example_html("tuning_ranges")  # the min/max I-beam


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


def test_bar_chart_straddles_a_shared_zero_baseline_for_signed_values():
    up, down = _bars(app._bar_chart(272, 64, (5.0, -5.0)))  # signed (retuning-like)
    # the positive bar's bottom meets the negative bar's top at the common zero line
    assert abs((up[0] + up[1]) - down[0]) < 0.01
    assert up[0] < down[0]  # positive rises above the baseline, negative drops below it


def test_range_chart_draws_a_titled_i_beam_with_min_max_labels_for_a_ranged_generator():
    # the generator tuning-ranges chart: a tall I-beam (stem + two caps) for a generator
    # with a range, the max/min cents labelled at its top/bottom caps
    svg = app._range_chart(92, 96, ((1200.0, 1200.0), (685.714, 720.0)))
    assert svg.startswith("<svg") and 'viewBox="0 0 92.00 96.00"' in svg
    assert "tuning ranges" in svg  # the chart title, per the mockup
    for label in ("720.00", "685.71"):  # the fifth's max (top cap) and min (bottom cap)
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
    assert "1200.00" in svg
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
