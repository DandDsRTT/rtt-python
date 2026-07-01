import re

from rtt.app import marks, page_assets, spreadsheet_constants

CSS = page_assets._CSS

_GRADIENT_REUSED_ANCHORS = frozenset({"#31373f", "#2c323a"})


def _rule_bodies():
    return re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


class TestDarkPaletteTokens:
    def test_every_dark_anchor_is_defined_once_as_a_custom_property(self):
        for name, value in page_assets._DARK_PALETTE_VARS:
            assert f"{name}:{value}" in CSS, f"{name} must be emitted onto body.rtt-dark"

    def test_dark_anchor_values_are_single_sourced_not_re_typed_raw(self):
        body = _rule_bodies()
        for name, value in page_assets._DARK_PALETTE_VARS:
            expected = 2 if value in _GRADIENT_REUSED_ANCHORS else 1
            assert body.count(value) == expected, (
                f"{value} ({name}) leaks {body.count(value)} raw copies into rule bodies; "
                "it must live only in its --dark-* definition (the scheme-button 3-D bevel "
                "gradients are the sole sanctioned reuse)"
            )

    def test_option_box_svg_constants_feed_the_same_dark_tokens(self):
        for constant, name in (
            (page_assets._DARK_CELL, "--dark-cell"),
            (page_assets._DARK_MARK, "--dark-mark"),
            (page_assets._DARK_TEXT, "--dark-text"),
            (page_assets._DARK_MUTED, "--dark-muted"),
        ):
            assert f"{name}:{constant}" in CSS, name


class TestPythonRoutedTokens:
    def test_wash_tints_are_generated_from_the_tints_dict(self):
        for group, tint in page_assets._TINTS.items():
            assert f"--wash-{group}:{tint}" in CSS, group

    def test_ebk_mark_is_sourced_from_the_marks_bracket_colour(self):
        assert f"--ebk-mark:{marks.BR_COLOR}" in CSS
        assert "color:var(--ebk-mark)" in CSS, "the transpose mark ink rides the token"

    def test_preset_height_token_mirrors_the_layout_constant(self):
        assert f"--preset-h:{spreadsheet_constants.PRESET_HEIGHT}px" in CSS

    def test_transpose_pending_reuses_the_pending_accent(self):
        assert ".rtt-transpose.rtt-pending { color:var(--pending-color); }" in CSS


class TestSharedCssTokens:
    def test_tile_border_token_replaces_every_raw_grey_border(self):
        body = _rule_bodies()
        assert "--tile-border:#8a8a8a" in CSS
        assert "border:1px solid #8a8a8a" not in body
        assert body.count("border:1px solid var(--tile-border)") == 6

    def test_highlight_ring_and_wash_are_single_sourced(self):
        body = _rule_bodies()
        assert "--hl-ring-w:2px" in CSS and "--hl-wash:14%" in CSS
        assert "inset 0 0 0 1.5px" not in body, (
            "the drifted keyframe ring width is unified via --hl-ring-w"
        )
        assert body.count("box-shadow:inset 0 0 0 var(--hl-ring-w)") == 13
        assert body.count("var(--hl-wash), transparent)") == 13

    def test_settings_bank_squares_use_the_option_box_token(self):
        body = _rule_bodies()
        assert "repeat(2, var(--option-box))" in body
        assert "repeat(3, var(--option-box))" in body

    def test_show_panel_grid_metrics_are_tokenised(self):
        body = _rule_bodies()
        assert "--show-col1:160px" in CSS and "--show-row-h:26px" in CSS
        assert body.count("var(--show-col1) 1fr") == 2
        assert body.count("min-height:var(--show-row-h)") == 2

    def test_preset_height_token_drives_the_preset_chooser_rules(self):
        body = _rule_bodies()
        assert "height:var(--preset-h)" in body


class TestCssDeduplication:
    def test_the_duplicate_disabled_target_block_is_gone(self):
        body = _rule_bodies()
        assert (
            body.count(
                ".rtt-preset-number.q-field--disabled .q-field__control { background:#d6d6d6"
            )
            == 1
        )

    def test_the_redundant_scheme_idle_hover_restatement_is_gone(self):
        assert ".rtt-scheme-button-idle:hover" not in CSS


class TestConstantSingleSourcing:
    def test_optimization_padding_has_one_literal_source(self):
        c = spreadsheet_constants
        assert c.OPTIMIZATION_PADDING == 8
        assert (
            c.OPTIMIZATION_PADDING_T
            == c.OPTIMIZATION_PADDING_B
            == c.OPTIMIZATION_PADDING_L
            == c.OPTIMIZATION_PADDING_R
            == c.OPTIMIZATION_PADDING
        )

    def test_box_gap_is_named(self):
        assert spreadsheet_constants.BOX_GAP == 8


class TestRecessedInsetBox:
    def test_inset_box_is_a_two_tier_token_darker_than_its_surface(self):
        body = _rule_bodies()
        assert "--inset-box:#d4d4d4" in CSS, "the light recessed inset well"
        assert "--inset-box:#21262d" in CSS, "the dark recessed inset well"
        assert "#e8e8e8" not in body, "the old near-tile inset grey is retired"
        assert body.count("background:var(--inset-box)") == 2

    def test_dark_inset_background_comes_from_the_token_not_a_separate_rule(self):
        assert (
            "body.rtt-dark .rtt-tile-complexity-box { border-color:var(--dark-tile-border); }"
            in CSS
        ), "the dark inset rule keeps only its border; the fill rides --inset-box"


class TestSpeakerFlashSymmetry:
    def test_dark_mode_drops_the_column_hover_dim_light_omits(self):
        assert ".rtt-speaker-dim::after" not in CSS
        assert ".rtt-speaker-hover::after" not in CSS

    def test_the_sounding_flash_still_fires_in_both_themes(self):
        assert ".rtt-speaker-on::after" in CSS
        assert "body.rtt-dark .rtt-speaker-on::after" in CSS
