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


def _tour_step(title):
    for step in page_assets._TOUR_STEPS:
        if step["title"] == title:
            return step
    raise AssertionError(f"no tour step titled {title!r}")


def _tour_page(monkeypatch, store):
    monkeypatch.setattr(app, "_doc_store", lambda: store)
    page = app._Page.__new__(app._Page)
    page.editor = Editor()
    page.runtime = SimpleNamespace(
        chapter=show_settings.CHAPTER_DEFAULT,
        building=False,
        set_chapter=lambda v: setattr(page.runtime, "chapter", v),
    )
    page._tour_snapshot = None
    page.apply_chapter = lambda: None
    page.renderer = SimpleNamespace(render=lambda: None)
    return page


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


class TestWebAppSmoke3:
    def test_general_tile_equivalence_mixes_object_stylings(self):
        equiv = render_html._general_part_html("equivalences")
        assert 'font-style:italic">e</span>' in equiv
        assert ">G<" in equiv or equiv.rstrip().endswith("G")

    def test_interest_example_is_the_bold_interval_symbol(self):
        assert render_html._math_html("𝐢") in render_html._example_html("interest"), "the mockup labels each interval-of-interest 𝐢 (bold upright, like the vectors), so # the toggle's example shows that same glyph"

    def test_interval_ratios_example_is_81_80_as_a_stacked_fraction(self):
        example = render_html._example_html("interval_ratios")
        assert 'class="rtt-fraction"' in example
        assert '<span class="rtt-fraction-numerator">81</span>' in example
        assert '<span class="rtt-fraction-denominator">80</span>' in example
        assert "2.3.5" not in example
        assert "interval_ratios" not in render_html._EXAMPLE_TEXT

    def test_general_tile_covers_every_general_layer_exactly_once(self):
        general = [key for key, _label, _default in dict(show_settings.SHOW_GROUPS)["general"]]
        covered = [key for line in page_assets._GENERAL_TILE_LINES for key in line] + list(page_assets._TILE_IN_CELL_LAYERS)
        assert sorted(covered) == sorted(general)
        assert len(covered) == len(set(covered))
        for key in covered:
            assert render_html._general_part_html(key).strip(), f"empty tile part for {key}"

    def test_general_tile_rides_each_subcontrol_on_its_parents_line(self):
        lines = page_assets._GENERAL_TILE_LINES
        general_subs = {k: p for k, p in show_settings.SUBCONTROLS.items()
                        if k in [key for key, *_ in dict(show_settings.SHOW_GROUPS)["general"]]}
        assert general_subs
        for sub, parent in general_subs.items():
            assert any(sub in line and parent in line for line in lines), (sub, parent)

    def test_general_tile_seats_the_value_layers_inside_the_gridded_cell(self):
        value_line = next(line for line in page_assets._GENERAL_TILE_LINES if "gridded_values" in line)
        assert set(value_line) == {"gridded_values", "math_expressions", "quantities", "decimals",
                                   "drag_to_combine"}

    def test_general_tile_symbol_and_equivalence_read_as_one_equation(self):
        assert render_html._general_part_html("symbols") == render_html._math_html(render_html._TILE_SYMBOL), "the symbol part is the bold-italic n; the equivalence part is its defining-equation tail, # so the two joined read 𝒏 = 𝑒G (the symbol's equation), one source of truth with _TILE_*"
        assert render_html._general_part_html("symbols") + render_html._general_part_html("equivalences") \
            == render_html._math_html(render_html._TILE_SYMBOL + render_html._TILE_EQUIV)

    def test_general_tile_name_exposes_its_mnemonic_letter_as_a_separate_target(self):
        before, letter, after = render_html._tile_name_pieces()
        assert before + letter + after == render_html._TILE_NAME
        assert letter == "n"

    def test_general_tile_part_reads_black_when_on_grey_when_off_and_inert_under_an_off_parent(self):
        assert "cursor:pointer" in _css_rule(".rtt-tile-part"), "each clickable part of the dummy tile shows its toggle's state directly: black + full # opacity when on, grey + dimmed when off (the dim also fades the SVG samples, whose strokes # a color alone can't grey). Parts carry a pointer cursor; a value-cell part whose host cell # is off is inert (no click) until the cell is on. Mnemonics is an underline on the name letter"
        on = _css_rule(".rtt-part-on")
        assert "color:#000" in on and "opacity:1" in on
        off = _css_rule(".rtt-part-off")
        assert "color:#999" in off and "opacity:" in off
        assert "pointer-events:none" in _css_rule(".rtt-part-inert")
        mnem = _css_rule(".rtt-tile-mnem")
        assert "text-decoration:underline" in mnem and "text-decoration-color:#999" in mnem
        assert "text-decoration-color:#000" in _css_rule(".rtt-mnem-underline")

    def test_show_toggle_labels_wrap_long_names_onto_two_lines(self):
        rule = _css_rule(".rtt-show-item .q-checkbox__label")
        assert "white-space:pre-line" in rule
        assert "line-height:1" in rule

    def test_row_titles_stack_one_word_per_line_and_select_as_one_unit(self):
        rule = _css_rule(".rtt-row-label")
        assert "width:min-content" in rule, "min-content wraps the title at every space — one word per line — while the copied text # stays a single spaced line (a soft wrap carries no newline, an embedded \\n would)"
        assert "user-select:all" in rule, "any click — including a double-click — selects the whole title, so a copy grabs # 'superspace interval vectors' rather than one word or one line of it"
        assert "margin-left:auto" in rule and "text-align:right" in rule
        assert "white-space" not in rule

    def test_every_option_square_renders_at_one_uniform_size(self):
        assert spreadsheet_constants.OPTION_BOX_PX == 16, "The settings-panel checkboxes, the box-𝐋 diminuator / target-controls all-interval # checkboxes, and the tuning-ranges monotone/tradeoff radio boxes must all render as the # SAME square. Previously the in-grid control checkboxes were forced larger (font-size:40px # → an 18px box) than the settings (13.5px) and range (16px) boxes; now every q-checkbox box # and the range box are pinned to the one shared option-box size so they read identically"
        assert f"--option-box:{spreadsheet_constants.OPTION_BOX_PX}px" in page_assets._CSS
        box = "var(--option-box)"
        bg = _css_rule(".q-checkbox__bg")
        assert f"width:{box}" in bg and f"height:{box}" in bg
        inner = _css_rule(".q-checkbox__inner")
        assert f"width:{box}" in inner and f"height:{box}" in inner
        rangebox = _css_rule(".rtt-rangebox")
        assert f"width:{box}" in rangebox and f"height:{box}" in rangebox
        assert ".rtt-control-check .q-checkbox__inner" not in page_assets._CSS, "the per-control overrides that made the in-grid control checkboxes oversized are gone — # the universal rules above now size every box, so nothing re-diverges"
        assert ".rtt-control-check .q-checkbox__label" not in page_assets._CSS

    def test_option_box_renders_as_one_svg_for_zoom_stable_appearance(self):
        assert page_assets._CSS.count("data:image/svg") == 6, "The box + fill is ONE SVG background that scales as a coherent vector — square with an even # border at any zoom — instead of a CSS border + inset ::after fill, whose edges snap to the # device-pixel grid independently and distort the square / gap at fractional zooms (the reported # zoom-dependent jank). The checked SVG carries the black fill, the mixed master a grey fill, the # unchecked box only the outline; the tuning-ranges radio box reuses the same art. # the box art is one SVG per state, defined once as a :root custom property and referenced # everywhere (so the same vector backs the checkbox, the mixed master, and the range box)"
        bg = _css_rule(".q-checkbox__bg")
        assert "var(--option-box-unchecked)" in bg and "border:none" in bg
        assert "var(--option-box-checked)" in _css_rule('.q-checkbox[aria-checked="true"] .q-checkbox__bg')
        assert "var(--option-box-disabled)" in _css_rule(".rtt-show-mixed .q-checkbox__bg")
        assert "var(--option-box-unchecked)" in _css_rule(".rtt-rangebox")
        assert ".q-checkbox__bg::after" not in page_assets._CSS
        assert ".rtt-rangebox::after" not in page_assets._CSS

    def test_brace_is_one_filled_path_with_width_independent_end_curls(self):
        narrow, wide = marks.brace(44, 14), marks.brace(200, 14)
        for svg in (narrow, wide):
            assert svg.count("<path") == 1
            assert "stroke" not in svg, "filled, not stroked"
            assert f'fill="{marks.BR_COLOR}"' in svg
        assert 'viewBox="0 0 200.00 14.00"' in wide
        prefix = 0
        while narrow[prefix] == wide[prefix]:
            prefix += 1
        assert prefix > 40
        assert narrow != wide

    def test_curly_bracket_is_one_filled_ribbon_within_its_footprint(self):
        svg = marks.curly_bracket(16, 30)
        assert svg.startswith("<svg") and 'viewBox="0 0 16.00 30.00"' in svg
        assert svg.count("<path") == 1 and "stroke" not in svg
        assert f'fill="{marks.BR_COLOR}"' in svg
        pts = re.findall(r"(-?\d+\.\d+),(-?\d+\.\d+)", svg)
        xs, ys = [float(x) for x, _y in pts], [float(y) for _x, y in pts]
        assert 0 <= min(xs) and max(xs) <= 16
        assert 0 <= min(ys) and max(ys) <= 30

    def test_ebk_svg_routes_the_curly_open_brace_to_the_curly_bracket(self):
        from rtt.app.layout import CellBox
        cell_box = CellBox("bracket:tuning:generator_map:l", 0, 0, 16, 30, "bracket", text="{")
        assert marks.ebk_svg(cell_box) == marks.curly_bracket(16, 30), "not the square/angle renderer"

    def test_bar_chart_draws_one_scaled_bar_per_value_from_the_baseline(self):
        svg = render_html._bar_chart(272, 64, (0.0, 5.0, 10.0))
        assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
        bars = _bars(svg)
        assert len(bars) == 3
        assert bars[0][1] == 0.0
        assert bars[2][1] > bars[1][1] > 0

    def test_bar_chart_extends_its_axis_past_the_tallest_bar_for_a_top_gridline(self):
        svg = render_html._bar_chart(272, 64, (0.0, 5.0, 10.0))
        bar_tops = [y for y, ht in _bars(svg) if ht > 0]
        gridlines = [float(y) for y in re.findall(
            rf'<line x1="[\d.]+" y1="([\d.]+)"[^>]*stroke="{render_html._CHART_GRID}"', svg)]
        assert gridlines and bar_tops
        assert min(gridlines) < min(bar_tops)

    def test_bar_chart_straddles_a_shared_zero_baseline_for_signed_values(self):
        up, down = _bars(render_html._bar_chart(272, 64, (5.0, -5.0)))
        assert abs((up[0] + up[1]) - down[0]) < 0.01
        assert up[0] < down[0], "positive rises above the baseline, negative drops below it"

    def test_bar_chart_indicator_line_is_broken_by_its_power_labelled_mean_damage(self):
        svg = render_html._bar_chart(272, 64, (0.0, 10.0, 26.385), indicator=26.385, indicator_label="∞")
        assert svg.count(f'stroke="{render_html._CHART_INDICATOR}"') == 2, "the line is drawn in two segments (a stub left of the label, the rest to its right), # leaving the gap the label fills — not one unbroken rule"
        assert "⟪" in svg and "⟫" in svg and "∞" in svg
        assert 'font-weight="bold"' in svg
        plain = render_html._bar_chart(272, 64, (0.0, 10.0, 26.385))
        assert f'stroke="{render_html._CHART_INDICATOR}"' not in plain
        assert "⟪" not in plain

    def test_bar_chart_renders_numerically_flat_dust_without_dividing_by_zero(self):
        svg = render_html._bar_chart(272, 64, (1e-13, -2e-14, 3e-14))
        assert svg.startswith("<svg") and 'viewBox="0 0 272.00 64.00"' in svg
        bars = _bars(svg)
        assert len(bars) == 3
        assert all(abs(height) < 0.01 for _y, height in bars), "dust rests on the baseline, not blown up"

    def test_range_chart_draws_an_i_beam_with_min_max_labels_for_a_ranged_generator(self):
        svg = render_html._range_chart(92, 96, ((1200.0, 1200.0), (685.714, 720.0)))
        assert svg.startswith("<svg") and 'viewBox="0 0 92.00 96.00"' in svg
        assert "tuning ranges" not in svg
        for label in ("720.000", "685.714"):
            assert label in svg
        heights = [height for _y, height in _bars(svg)]
        assert max(heights) > 30

    def test_range_chart_ticks_the_live_tuning_within_a_generators_range(self):
        marks = sorted(y for y, height in _bars(render_html._range_chart(92, 96, ((685.714, 720.0),), (697.0,))) if height < 4)
        assert len(marks) == 3
        assert marks[0] < marks[1] < marks[2]
        plain = sorted(y for y, height in _bars(render_html._range_chart(92, 96, ((685.714, 720.0),))) if height < 4)
        assert len(plain) == 2

    def test_range_chart_draws_only_a_flat_cap_for_a_pinned_generator(self):
        svg = render_html._range_chart(92, 96, ((1200.0, 1200.0),))
        assert "1200.000" in svg
        heights = [height for _y, height in _bars(svg)]
        assert heights and max(heights) < 10

    def test_range_chart_shows_a_placeholder_and_no_i_beams_when_there_is_no_range(self):
        svg = render_html._range_chart(92, 96, ())
        assert "no range" in svg
        assert "<rect" not in svg

    def test_math_expression_html_stacks_two_lines_each_with_a_fitted_font(self):
        html = render_html._math_expression_html("1200 · log₂(3/2)\n= 701.96", 30)
        assert html.count("<div") == 3
        assert html.count("font-size:") == 2
        assert "1200 · log₂(3/2)" in html and "= 701.96" in html

    def test_math_expression_font_shrinks_for_longer_expressions(self):
        short = render_html._math_expression_html("1200 · log₂2\n= 1200.00", 30)
        long = render_html._math_expression_html("1200 · log₂(6/5)\n= 315.64", 30)
        assert _first_font(long) < _first_font(short)

    def test_fit_font_is_clamped_between_the_min_and_max(self):
        assert render_html._fit_font("x", 30) == render_html._EXPR_MAX_FONT
        assert render_html._fit_font("x" * 100, 30) == render_html._EXPR_MIN_FONT

    def test_math_expression_elides_a_giant_ratio_operand_instead_of_streaking(self):
        giant = spreadsheet_text._math_expr(
            spreadsheet_text._log_operand("2" * 80 + "/" + "3" * 60), 240000.0, show_value=True)
        html = render_html._math_expression_html(giant, 37)
        assert "1200 · log₂(…/…)" in html
        assert "2" * 80 not in html
        assert "= " in html
        assert _first_font(html) > render_html._EXPR_MIN_FONT

    def test_math_expression_elides_a_giant_bare_integer_operand_to_an_ellipsis(self):
        giant = spreadsheet_text._math_expr(
            spreadsheet_text._log_operand("2" * 80 + "/1"), 96000.0, show_value=True)
        html = render_html._math_expression_html(giant, 37)
        assert "1200 · log₂…" in html and "(…" not in html
        assert "2" * 80 not in html


class TestWebAppSmoke4:
    def test_math_expression_leaves_a_small_operand_intact(self):
        html = render_html._math_expression_html("1200 · log₂(3/2)\n= 701.96", 37)
        assert "1200 · log₂(3/2)" in html and "…" not in html

    def test_elided_expr_line_fits_its_cell_at_the_fitted_font(self):
        raw = "1200 · log₂(" + "2" * 100 + "/" + "3" * 100 + ")"
        elided = render_html._elide_expr_line(raw, 37)
        assert elided == "1200 · log₂(…/…)"
        assert len(elided) * render_html._EXPR_CHAR_W * render_html._fit_font(elided, 37) <= 37

    def test_plain_text_font_shrinks_to_fit_with_no_readability_floor(self):
        dense = render_html._plain_text_font("9.999 " * 40, 120)
        denser = render_html._plain_text_font("9.999 " * 80, 120)
        assert denser < dense < 5.0
        assert render_html._plain_text_font("1 0 0", 120) == spreadsheet_constants.PLAIN_TEXT_MAX_FONT
        assert render_html._plain_text_font("x" * 9, 30) <= spreadsheet_constants.PLAIN_TEXT_MAX_FONT

    def test_plain_text_font_is_glyph_aware_not_uniform_width(self):
        sparse = "0 0 0 0 0 0 0 0 0 0"
        dense = "0000000000000000000"
        assert len(sparse) == len(dense)
        assert render_html._plain_text_font(sparse, 40) > render_html._plain_text_font(dense, 40)

    def test_approach_radio_is_visible_iff_the_domain_has_nonprime_elements(self):
        from rtt.app.editor import Editor

        editor = Editor()
        assert render_html._approach_visible(editor) is False
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True, "BARBADOS over 2.3.13/5: 13/5 is a nonprime element, so the radio appears"
        assert render_html._approach_visible(editor) is True

    def test_target_chooser_default_limit_uses_the_nonstandard_basis(self):
        from rtt.app.editor import Editor
        editor = Editor()
        assert editor.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}") is True
        reconciler = _Reconciler(editor)
        assert reconciler._target_preset_values() == (16, "TILT")

    def test_target_chooser_resets_to_dash_when_the_domain_empties_the_target_set(self):
        from rtt.app.editor import Editor
        editor = Editor()
        assert editor.try_edit_mapping_text("5.7 [⟨1 0] ⟨0 1]}") is True
        editor.set_target_spec("5-TILT")
        assert editor.current_targets() == []
        assert _Reconciler(editor)._target_preset_values() == (None, None)

    def test_dense_prescaling_plain_text_fits_its_cell(self):
        s = show_settings.defaults()
        s.update(plain_text_values=True, weighting=True, alt_complexity=True)
        cells = {c.id: c for c in spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s,
                                                    tuning_scheme="TILT minimax-S").cells}
        for cell_id in ("plain_text:prescaling:primes", "plain_text:prescaling:targets"):
            c = cells[cell_id]
            assert render_html._plain_text_units(c.text) * render_html._plain_text_font(c.text, c.width) <= c.width, cell_id

    def test_units_fit_their_cell_for_long_alternative_complexity_annotations(self):
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
        assert shrunk, "no units cell shrank — the long-annotation fit never engaged"


class TestGuidedTour:
    def test_tour_steps_are_well_formed_and_assets_wired(self):
        assert page_assets._TOUR_STEPS, "no tour steps defined"
        for step in page_assets._TOUR_STEPS:
            assert step["title"] and step["body"], f"empty copy: {step}"
            selection = step["selector"]
            assert isinstance(selection, str)
            assert selection == "" or selection[0] in ".[", f"selector should be a real CSS selector # (class or attribute), not a test-only .mark(), got {selection!r}"
        assert page_assets._TOUR_JS.strip(), "tour.js not loaded"
        assert ".rtt-tour-card" in page_assets._CSS, "tour.css not folded into the page stylesheet"
        assert "tour" in tooltips.CHROME_HELP

    def test_first_run_opens_at_the_default_chapter(self):
        assert app._initial_chapter({}) == show_settings.CHAPTER_DEFAULT, (
            "a genuinely-new browser opens at the default chapter, not the minimum")
        assert app._initial_chapter({page_assets._STORE_KEY: "saved"}) == show_settings.CHAPTER_DEFAULT, (
            "a saved document with no explicit chapter still opens at the default chapter")
        assert app._initial_chapter({page_assets._CHAPTER_KEY: 7}) == 7, (
            "an explicit chapter choice is honored across visits")

    def test_tour_copy_is_plain_words_never_math_symbols(self):
        for step in page_assets._TOUR_STEPS:
            for ch in step["title"] + step["body"]:
                assert not (0x1D400 <= ord(ch) <= 0x1D7FF), (
                    f"the tour teaches in plain words, not the grid's math italics (𝑀 etc.) which a "
                    f"newcomer can't read: {ch!r} in {step['title']!r}")

    def test_mapping_step_frames_the_whole_mapping_in_plain_words(self):
        from rtt.app import ids
        step = _tour_step("The mapping")
        assert step["selector"].startswith(".rtt-cell") and "cell:mapping:" in step["selector"]
        assert step.get("region") is True, "the spotlight frames the WHOLE mapping matrix, not one cell"
        assert ids.mapping_cell("0", 0).startswith("cell:mapping:"), "the selector must match a real # mapping cell id, not a test-only .mark()"
        assert "generator" in step["body"] and "prime" in step["body"]

    def test_tour_arms_mapping_demos_itself_so_the_grid_lesson_stays_hop_free(self):
        titles = [step["title"] for step in page_assets._TOUR_STEPS]
        assert "Switch on mapping demos" not in titles, "the tour arms mapping demos itself (tour_begin) # so the early grid lesson never detours into the settings panel to flip it on"
        assert "mapping demos" in _tour_step("App features")["body"].lower(), "the panel step still names # mapping demos so the learner sees where the switch that drew the animations lives"

    def test_tempering_out_step_frames_the_whole_comma_for_the_hover_demo(self):
        from rtt.app import ids
        step = _tour_step("Tempering out")
        assert step.get("interact") is True, "the concept is taught by doing: tour.js drops the scrim's # pointer-events so the learner's hover reaches the comma and the mapping demo animates"
        assert step["selector"].startswith(".rtt-cell") and "cell:comma:" in step["selector"]
        assert step.get("region") is True, "the spotlight frames the WHOLE comma basis, not one cell"
        assert step.get("gate") == "demo", "Next stays blocked until the learner actually hovers and the # demo draws — teaching by doing, not clicking past"
        assert ids.comma_cell("0", 0).startswith("cell:comma:"), "the selector must match a real comma # cell id, not a test-only .mark()"
        assert "temper" in step["body"].lower() and "vanish" in step["body"].lower()
        assert "[0 0]" in step["body"], "the payoff is the comma mapping to the all-zeros generator-count # vector the guide writes [0 0]"

    def test_try_an_edit_step_is_restored_and_hands_on(self):
        step = _tour_step("Try an edit")
        assert step.get("interact") is True and "cell:mapping:" in step["selector"], "the learner # edits a real mapping cell and watches the grid recompute — restored from the old tour"
        assert step.get("gate") == "edited", "Next stays blocked until the mapping actually changes"
        assert "recompute" in step["body"].lower() and "undo" in step["body"].lower()

    def test_learner_raises_the_chapter_themselves(self):
        step = _tour_step("Reveal more, chapter by chapter")
        assert step["selector"] == ".rtt-chapter-group" and step.get("open") is True
        assert step.get("interact") is True, "the learner drives the real chapter slider up themselves — # an interact step so the drag reaches the control"
        assert step.get("gate") == "chapter4", "Next stays blocked until they actually reach chapter 4"
        assert "4" in step["body"] and "tuning" in step["body"].lower()

    def test_gated_steps_block_next_until_the_learner_acts(self):
        js = page_assets._TOUR_JS
        assert "armGate" in js and "next.disabled" in js, "an interact step disables Next until its gate # is met, so the tour blocks progress until the learner does the thing"
        gated = {step["title"]: step["gate"] for step in page_assets._TOUR_STEPS if step.get("gate")}
        assert gated == {"Tempering out": "demo", "Try an edit": "edited",
                         "Reveal more, chapter by chapter": "chapter4"}, gated
        for title in gated:
            assert _tour_step(title).get("interact") is True, "only interact steps are gated"

    def test_reshaping_and_undo_and_panel_steps_survive_the_rewrite(self):
        for title in ("Reshaping the grid", "Undo, reset & share", "Tile features", "App features"):
            step = _tour_step(title)
            assert step["title"] and step["body"], f"good onboarding step {title!r} must stay in the tour"

    def test_tour_visits_the_grid_before_the_panel_with_a_single_pane_switch(self):
        opens = [i for i, step in enumerate(page_assets._TOUR_STEPS) if step.get("open")]
        assert opens, "the settings-panel steps open the drawer"
        assert opens == list(range(opens[0], len(page_assets._TOUR_STEPS) - 1)), "every drawer step is # contiguous at the end — the grid lesson finishes first, then the panel, one switch, no hopping"

    def test_landing_step_closes_the_tour_and_points_back_to_reset_and_replay(self):
        step = _tour_step("Explore from here")
        assert step is page_assets._TOUR_STEPS[-1], "explore is the final step"
        assert "reset" in step["body"].lower()

    def test_tour_bridges_begin_skip_and_complete(self):
        js = page_assets._TOUR_JS
        assert 'emit("rtt_tour_begin")' in js, "start() snapshots the learner's work and resets to ch2"
        assert '"rtt_tour_skip"' in js and '"rtt_tour_complete"' in js, "both exits restore the sandbox — # skip lands at ch2, complete at the full app"
        assert "rtt_tour_home" not in js

    def test_skip_lands_at_ch2_and_complete_at_the_full_app(self):
        js = page_assets._TOUR_JS
        assert 'stop(false)' in js, "reaching the end completes rather than aborts"
        assert 'abort === false ? "rtt_tour_complete" : "rtt_tour_skip"' in js, "an abort (skip/Escape) # returns to ch2; the end completes to the full app — both restore the learner's own work"

    def test_tour_owns_the_arrow_keys_gated_and_the_grid_yields_them(self):
        tour_js, active_js = page_assets._TOUR_JS, page_assets._ACTIVECELL_JS
        assert "gateSatisfied(step.gate)" in tour_js and "ArrowRight" in tour_js, "ArrowRight advances # only when the step's gate is satisfied, exactly like the Next button"
        assert "rtt-tour-running" in active_js, "the grid's active-cell arrow-roam yields to the tour so # a single arrow press never both advances the tour AND moves the grid cursor"

    def test_tour_region_step_frames_every_matched_cell_not_just_the_first(self):
        js = page_assets._TOUR_JS
        assert "step.region" in js and "querySelectorAll" in js, "a region step unions every matched # cell into one spotlight so the whole matrix is framed"
        region_steps = [s for s in page_assets._TOUR_STEPS if s.get("region")]
        assert region_steps, "the mapping and comma steps frame their whole matrix"
        for step in region_steps:
            assert step["selector"].startswith(".rtt-cell["), "a region step targets a family of cells"

    def test_tour_silences_the_apps_incidental_hover_affordances_while_running(self):
        js = page_assets._TOUR_JS
        assert 'classList.add("rtt-tour-running")' in js, "start() flags the body while the tour runs"
        assert 'classList.remove("rtt-tour-running")' in js, "stop() clears the flag"
        css = page_assets._CSS
        for surface in (".rtt-zoom-overlay", ".q-tooltip", ".rtt-zoom-help", ".rtt-guide-card"):
            assert f"body.rtt-tour-running {surface}" in css, f"the tour hides {surface} so the # tempering hover shows only the tour's own card, spotlight and mapping-demo overlay"

    def test_a_brand_new_browser_still_opens_at_the_default_chapter(self):
        assert show_settings.CHAPTER_MIN < show_settings.CHAPTER_DEFAULT
        assert app._initial_chapter({}) == show_settings.CHAPTER_DEFAULT, "first-run for a genuinely-new # browser is unchanged at chapter 4 (#204); it is the tour and Reset that drive the ch2 beginning"

    def test_tour_begin_teaches_from_a_clean_chapter_two_default_with_the_demo_armed(self, monkeypatch):
        page = _tour_page(monkeypatch, {})
        page.editor.set_show("units", True)
        app._Page.tour_begin(page)
        assert page.runtime.chapter == show_settings.CHAPTER_MIN
        assert page.editor.settings["mapping_demos"] is True, "the demo is armed so the hover step works # without a settings detour"
        assert page.editor.settings["units"] is False, "the tour teaches on a clean default (the 81/80 # lesson and the edit step land on a throwaway), so no step points at a feature already on"
        assert page.editor.settings["tuning"] is False and page.editor.settings["interest"] is False, "chapter 2 is the simplest grid"

    def test_tour_is_a_sandbox_restoring_the_learners_work_when_they_leave(self, monkeypatch):
        page = _tour_page(monkeypatch, {})
        page.editor.set_show("optimization", True)
        app._Page.tour_begin(page)
        assert page.editor.settings["optimization"] is False, "the tour teaches on the clean default"
        app._Page.tour_exit(page, show_settings.CHAPTER_DEFAULT)
        assert page.editor.settings["optimization"] is True, "leaving the tour restores the learner's own # work — the reset was only a sandbox for the lesson, never a real edit to their document"
        assert page.editor.settings["mapping_demos"] is False, "and the tour's armed demo is put back the # way the learner had it"
        assert page.runtime.chapter == show_settings.CHAPTER_DEFAULT, "completing lands at the full app; # skip (tour_exit with CHAPTER_MIN) would land at the simple chapter-2 start instead"

    def test_tour_begin_persists_the_chapter_two_start_like_a_reset(self, monkeypatch):
        store: dict = {}
        page = _tour_page(monkeypatch, store)
        app._Page.tour_begin(page)
        assert store[page_assets._CHAPTER_KEY] == show_settings.CHAPTER_MIN, "chapter 2 is now a real # resting state (Reset lands there too), so the tour's clean start persists it like any chapter"

    def test_raising_the_chapter_re_reveals_the_default_layers_lowering_hides_them(self, monkeypatch):
        page = _tour_page(monkeypatch, {})
        app._Page.on_chapter_change(page, show_settings.CHAPTER_MIN)
        assert page.editor.settings["tuning"] is False, "lowering to chapter 2 hides the advanced layers"
        app._Page.on_chapter_change(page, show_settings.CHAPTER_DEFAULT)
        assert page.editor.settings["tuning"] is True, "the chapter slider is non-lossy: raising it re-reveals # the default layers, so the grid fills back in as you ramp up from the chapter-2 beginning"

    def test_tour_autostart_is_desktop_first_but_replay_is_always_available(self):
        js = page_assets._TOUR_JS
        assert "AUTOSTART_MIN_WIDTH" in js and "wideEnough" in js
        autostart = js.split("config.autostart", 1)[1].split("{", 1)[0]
        assert "!seen()" in autostart and "wideEnough()" in autostart, "autostart is gated on width (alongside # any other autostart guards)"
        assert "window.rttTour.start = start" in js, "the ? replay button (start) stays available at any width"

    def test_tour_exposes_forget_to_clear_the_seen_flag(self):
        js = page_assets._TOUR_JS
        assert "function forget()" in js and "removeItem(SEEN_KEY)" in js
        assert "window.rttTour.forget = forget" in js

    def test_reset_returns_to_chapter_two_and_clears_the_tour_seen_flag(self, monkeypatch):
        calls: list = []
        store: dict = {}
        monkeypatch.setattr(app, "_doc_store", lambda: store)
        monkeypatch.setattr(app.ui, "run_javascript", lambda js, *a, **k: calls.append(js))
        page = _tour_page(monkeypatch, store)
        page.edits = SimpleNamespace(act=lambda fn: fn())
        app._Page.reset_everything(page)
        assert page.runtime.chapter == show_settings.CHAPTER_MIN, "Reset returns to the simple chapter-2 # beginning"
        assert any("rttTour" in js and "forget" in js for js in calls), "Reset also clears rttTourSeen # (window.rttTour.forget) so it genuinely restores the first-run onboarding, not just the grid"


class TestReconcilerProtocol:
    def test_reconciler_callback_protocol_matches_marked_methods_exactly(self):
        from rtt.app.reconciler import required_callback_names

        declared = set(required_callback_names())
        marked = _marked_callback_names()
        assert declared == marked, {
            "declared_only": sorted(declared - marked),
            "marked_only": sorted(marked - declared),
        }
        assert not any(n.startswith("_") for n in marked), "a private helper must never be marked — only frontend entry points are callbacks"

    def test_bind_callbacks_binds_every_declared_callback(self):
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

        cell_box = bind_callbacks(
            edits,
            edits.vectors,
            edits.tuning,
            edits.controls,
            gestures,
            gestures.combine,
            gestures.hover,
        )
        assert isinstance(cell_box, ReconcilerCallbacks)
        for name in required_callback_names():
            assert getattr(cell_box, name)._rtt_cb is True

    def test_bind_callbacks_fails_loudly_on_a_missing_callback(self):
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

    def test_bind_callbacks_fails_loudly_on_a_duplicate_provider(self):
        from types import SimpleNamespace

        from rtt.app.reconciler import bind_callbacks, required_callback_names

        full = SimpleNamespace(**{name: _cb_stub() for name in required_callback_names()})
        clash = next(iter(required_callback_names()))
        extra = SimpleNamespace(**{clash: _cb_stub()})

        with pytest.raises(RuntimeError, match="multiple"):
            bind_callbacks(full, extra)
