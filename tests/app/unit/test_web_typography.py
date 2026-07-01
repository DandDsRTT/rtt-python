"""WP10 typography: one type scale, one char-width model, one subscript treatment."""

import re
from pathlib import Path

from rtt.app import (
    char_metrics,
    page_assets,
    render_html,
    render_html_glyphs,
    spreadsheet_constants,
    spreadsheet_text,
)


def _css_rule(selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", page_assets._CSS)
    assert match, f"no CSS rule for {selector}"
    return match.group(1)


class TestTypeScale:
    def test_the_scale_values_are_pinned(self):
        assert spreadsheet_constants.SYMBOL_FONT == 15
        assert spreadsheet_constants.CAPTION_FONT == 9
        assert spreadsheet_constants.CELL_FONT == 17
        assert spreadsheet_constants.STACKED_MAIN_FONT == 10
        assert spreadsheet_constants.STACKED_SUB_FONT == 7
        assert spreadsheet_constants.RANGE_FONT == 7
        assert spreadsheet_constants.SUB_FONT_PCT == 70

    def test_every_font_size_reads_the_one_scale(self):
        assert page_assets._CELL_FONT is spreadsheet_constants.CELL_FONT
        assert page_assets._STACKED_MAIN_FONT is spreadsheet_constants.STACKED_MAIN_FONT
        assert render_html._RANGE_FONT is spreadsheet_constants.RANGE_FONT

    def test_the_css_vars_carry_the_scale_to_the_stylesheet(self):
        for var, size in (
            ("--symbol-font", spreadsheet_constants.SYMBOL_FONT),
            ("--caption-font", spreadsheet_constants.CAPTION_FONT),
            ("--cell-font", spreadsheet_constants.CELL_FONT),
            ("--stacked-main-font", spreadsheet_constants.STACKED_MAIN_FONT),
            ("--stacked-sub-font", spreadsheet_constants.STACKED_SUB_FONT),
        ):
            assert f"{var}:{size}px" in page_assets._CSS
        assert f"--sub-font-pct:{spreadsheet_constants.SUB_FONT_PCT}%" in page_assets._CSS

    def test_the_type_scale_faces_read_the_vars_not_literals(self):
        assert "font-size:var(--symbol-font)" in _css_rule(".rtt-symbol")
        assert "font-size:var(--caption-font)" in _css_rule(".rtt-caption")
        assert "font-size:var(--stacked-main-font)" in _css_rule(".rtt-stacked-main")
        assert "font-size:var(--stacked-sub-font)" in _css_rule(".rtt-stacked-sub")


class TestCharWidthModel:
    def test_the_estimators_share_one_glyph_table(self):
        assert render_html._PLAIN_TEXT_GLYPH_EM is char_metrics.GLYPH_EM
        assert render_html._PLAIN_TEXT_DEFAULT_EM is char_metrics.DEFAULT_EM
        assert render_html._EXPR_CHAR_W is char_metrics.EXPR_EM

    def test_the_caption_estimator_reads_the_shared_caption_em(self):
        width, font = 100.0, float(spreadsheet_constants.CAPTION_FONT)
        expected = max(1, int((width - 4) / (font * char_metrics.CAPTION_EM)))
        assert spreadsheet_text._chars_per_line(width, font) == expected

    def test_the_chart_indicator_reads_the_shared_label_em(self):
        assert char_metrics.CHART_LABEL_EM == 0.62
        source = Path(render_html_glyphs.__file__).read_text(encoding="utf-8")
        assert "char_metrics.CHART_LABEL_EM" in source
        assert "0.62" not in source

    def test_emittable_is_exactly_the_glyph_table(self):
        assert char_metrics.EMITTABLE == frozenset(char_metrics.GLYPH_EM)

    def test_every_glyph_a_value_face_can_emit_has_a_width(self):
        brackets = "⟨][{"
        alphabet = set("0123456789 ./-" + brackets + spreadsheet_constants.DASH)
        missing = alphabet - char_metrics.EMITTABLE
        assert not missing, f"no em-width for {sorted(missing)}; they would fall to DEFAULT_EM and risk a spill"


def _first_substring_rule(selector):
    for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", page_assets._CSS):
        sels, body = match.group(1), match.group(2)
        if selector in sels and "@media" not in sels:
            return body
    return None


class TestSubscriptTreatment:
    def test_one_rule_gives_every_value_symbol_unit_subscript_the_same_optics(self):
        body = _css_rule(
            ".rtt-matrix-label sub, .rtt-symbol sub, .rtt-count sub, .rtt-units sub, .rtt-cell-unit sub"
        )
        assert "font-size:var(--sub-font-pct)" in body
        assert "vertical-align:sub" in body
        assert "line-height:0" in body

    def test_the_subscript_rule_does_not_shadow_the_unit_colour_lookups(self):
        for selector in (".rtt-cell-unit", ".rtt-units"):
            body = _first_substring_rule(selector)
            assert body is not None and "color:" in body, (
                f"a substring lookup for {selector} must land on its colour rule first — the shared "
                f"subscript rule (which also names {selector} sub) must sit AFTER it in the sheet, or "
                f"the accessibility contrast test reads a colourless body"
            )
