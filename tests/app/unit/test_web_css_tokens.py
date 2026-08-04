import re

from rtt.app import page_assets, spreadsheet_constants

CSS = page_assets._CSS

_GRADIENT_REUSED_ANCHORS = frozenset()


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
                "it must live only in its --dark-* definition"
            )

    def test_option_checkbox_svg_constants_feed_the_same_dark_tokens(self):
        for constant, name in (
            (page_assets._DARK_CELL, "--dark-cell"),
            (page_assets._DARK_MARK, "--dark-mark"),
            (page_assets._DARK_TEXT, "--dark-text"),
            (page_assets._DARK_MUTED, "--dark-muted"),
        ):
            assert f"{name}:{constant}" in CSS, name


class TestPythonRoutedTokens:
    def test_tile_tints_are_generated_from_the_tints_dict(self):
        for group, tint in page_assets._TINTS.items():
            assert f"--tile-{group}:{tint}" in CSS, group

    def test_tile_pair_tokens_are_the_darken_min_of_their_two_tints(self):
        assert page_assets._TILE_PAIRS == {
            "form-temperament": "#d8a4a4",
            "form-tuning": "#a4a4d8",
            "temperament-tuning": "#a4d8a4",
        }, "a two-group tile is tinted its two singles pre-combined by darken (per-channel min)"
        for key, tint in page_assets._TILE_PAIRS.items():
            assert f"--tile-{key}:{tint}" in CSS, key

    def test_preset_height_token_mirrors_the_layout_constant(self):
        assert f"--preset-h:{spreadsheet_constants.PRESET_HEIGHT}px" in CSS


class TestSharedCssTokens:
    def test_tile_border_token_replaces_every_raw_grey_border(self):
        body = _rule_bodies()
        assert "--tile-border:#8a8a8a" in CSS
        assert "border:1px solid #8a8a8a" not in body
        assert body.count("border:1px solid var(--tile-border)") == 9

    def test_highlight_ring_and_wash_are_single_sourced(self):
        body = _rule_bodies()
        assert "--hl-ring-w:2px" in CSS and "--hl-wash:14%" in CSS
        assert "inset 0 0 0 1.5px" not in body, (
            "the drifted keyframe ring width is unified via --hl-ring-w"
        )
        assert body.count("box-shadow:inset 0 0 0 var(--hl-ring-w)") == 13
        assert body.count("var(--hl-wash), transparent)") == 13

    def test_settings_bank_squares_use_the_settings_icon_token(self):
        body = _rule_bodies()
        assert "repeat(2, var(--settings-icon))" in body
        assert "repeat(3, var(--settings-icon))" in body

    def test_the_settings_icon_is_its_own_token_and_outgrows_the_shared_checkbox(self):
        assert spreadsheet_constants.SETTINGS_ICON_PX > spreadsheet_constants.OPTION_CHECKBOX_PX

    def test_show_panel_grid_metrics_are_tokenised(self):
        body = _rule_bodies()
        assert "--show-row-h:26px" in CSS
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

    def test_scheme_button_is_flat_like_canonicalize_and_guards_its_disabled_state(self):
        assert "rtt-scheme-button-idle" not in CSS, "the 3-D idle class is gone; disabled now rides Quasar's .disabled"
        assert ".rtt-scheme-button:hover:not(.disabled)" in CSS and ".rtt-scheme-button:active:not(.disabled)" in CSS, \
            "hover/press are guarded so a disabled ✕ neither responds nor flashes"
        assert ".rtt-scheme-button.disabled" in CSS
        assert ".rtt-scheme-button { width:100% !important" in CSS and "background:var(--cell-bg)" in CSS, "flat tokened face, no 3-D gradient"


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

    def test_panel_gap_is_named(self):
        assert spreadsheet_constants.PANEL_GAP == 8


class TestRecessedInsetPanel:
    def test_inset_panel_is_a_two_tier_token_darker_than_its_surface(self):
        body = _rule_bodies()
        assert "--inset-panel:#d4d4d4" in CSS, "the light recessed inset well"
        assert "--inset-panel:#21262d" in CSS, "the dark recessed inset well"
        assert "#e8e8e8" not in body, "the old near-tile inset grey is retired"
        assert body.count("background:var(--inset-panel)") == 4

    def test_dark_inset_background_comes_from_the_token_not_a_separate_rule(self):
        assert (
            "body.rtt-dark .rtt-tile-complexity-panel { border-color:var(--dark-tile-border); }"
            in CSS
        ), "the dark inset rule keeps only its border; the fill rides --inset-panel"


class TestGripOrientationAndSize:
    def test_column_axis_grips_lie_landscape_and_row_axis_grips_stand_portrait(self):
        assert (
            ".rtt-subcolumn-grip .rtt-grip, .rtt-column-grip .rtt-grip,\n"
            ".rtt-column-handle .rtt-grip, .rtt-derived-mark .rtt-grip { transform:rotate(90deg); }"
        ) in CSS, "a handle for a COLUMN lies wider than tall; the native drag_indicator glyph is portrait, so every column-axis grip rotates"
        assert ".rtt-row-grip .rtt-grip { transform:rotate(90deg)" not in CSS, "a handle for a ROW stands taller than wide — the glyph's native orientation, unrotated"

    def test_every_grip_shares_the_one_drag_handle_size(self):
        assert ".rtt-grip { font-size:15px" not in CSS, "no grip rides a smaller face than the others"
        assert ".rtt-drag-handle .rtt-grip, .rtt-derived-mark .rtt-grip { font-size:18px" in CSS


class TestSpeakerFlashSymmetry:
    def test_dark_mode_drops_the_column_hover_dim_light_omits(self):
        assert ".rtt-speaker-dim::after" not in CSS
        assert ".rtt-speaker-hover::after" not in CSS

    def test_the_sounding_flash_still_fires_in_both_themes(self):
        assert ".rtt-speaker-on::after" in CSS
        assert "body.rtt-dark .rtt-speaker-on::after" in CSS
