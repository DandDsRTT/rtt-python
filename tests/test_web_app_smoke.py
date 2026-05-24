"""Light smoke coverage for the NiceGUI layer.

The interaction logic lives in (and is tested via) rtt.web.editor; here we only
guard that the page module imports/wires cleanly and that input parsing matches
the original app's parseInt semantics. Rendering itself is verified in a browser.
"""

import re
import sys

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
    # matrices/vectors are bold-upright (weight only); maps are bold-italic (both).
    # the base ASCII letter renders in the UI serif, not relying on a maths font.
    assert app._math_html("𝐌") == '<span style="font-weight:700">M</span>'
    assert app._math_html("𝒕") == '<span style="font-weight:700;font-style:italic">t</span>'
    # a product styles each letter on its own (the comma column's 𝒕𝐂)
    assert app._math_html("𝒕𝐂") == ('<span style="font-weight:700;font-style:italic">t</span>'
                                      '<span style="font-weight:700">C</span>')
    # plain math-italic (no bold) — the counts' variables and some panel examples
    assert app._math_html("𝑑") == '<span style="font-style:italic">d</span>'
    # ordinary characters (an equivalence tail's " = " and operators) pass through
    assert app._math_html(" = 𝒈𝐌") == (' = <span style="font-weight:700;font-style:italic">g</span>'
                                         '<span style="font-weight:700">M</span>')


def test_ebk_marks_share_one_colour_and_map_one_to_one_to_their_cell():
    # every EBK mark is one SVG whose viewBox is the cell's own px box, so its
    # weight is a constant px count rather than a scaled stroke — that is what
    # keeps a 1-row and a many-row bracket the exact same thickness.
    marks = {
        "[": app._square_bracket(16, 16, "left"),
        "]2": app._square_bracket(16, 60, "right"),
        "<": app._angle_bracket(16, 16),
        "top": app._top_bracket(120, 9),
        "vbar": app._vbar(2, 60),
    }
    for svg in marks.values():
        assert svg.startswith("<svg") and f'fill="{app._BR_COLOR}"' in svg
        assert "stroke-width" not in svg  # weight is the 1:1 viewBox, not a scaling stroke
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
    # the stubbed box subcontrols: colorization is a colour swatch, tuning ranges an I-beam
    assert "background:#" in app._example_html("temperament_colorization")
    assert "background:#" in app._example_html("tuning_colorization")
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
