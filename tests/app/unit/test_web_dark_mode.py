"""The dark-theme overlay (assets/rtt-dark.css + the dark option-box SVG vars).

The theme is a palette OVERLAY gated on the ``rtt-dark`` class on <body>: light mode is
the base and every dark rule is prefixed ``body.rtt-dark``, so with the class off the
overlay is inert. These tests assert the overlay is present and themes each surface,
text role and the theme-resistant marks — by checking the relevant *property is set*,
not its exact hue (the palette is tuned by eye, so pinning hexes would be brittle)."""

import pathlib
import re

import rtt.app.app as app
from rtt.app import building, marks, page_assets, render_html_tiles
from rtt.app import settings as show_settings
from rtt.app import tooltips


def _dark_sets(selector, prop):
    """True if some ``body.rtt-dark … <selector> … { … <prop>: … }`` rule exists — i.e. the
    overlay themes ``prop`` on a rule whose (possibly grouped) selector mentions ``selector``."""
    for m in re.finditer(r"(body\.rtt-dark[^{]*)\{([^}]*)\}", page_assets._CSS):
        sels, body = m.group(1), m.group(2)
        if selector in sels and re.search(rf"(^|;|\s){re.escape(prop)}\s*:", body):
            return True
    return False


def _dark_var_blocks():
    """The declaration bodies of every bare ``body.rtt-dark { … }`` block (the themed
    custom-property overrides), concatenated."""
    return " ".join(re.findall(r"body\.rtt-dark\s*\{([^}]*)\}", page_assets._CSS))


class TestWebDarkMode:
    def test_dark_overlay_is_gated_on_the_body_class(self):
        assert "body.rtt-dark" in page_assets._CSS, "the whole theme lives behind body.rtt-dark, so the default (light) render is untouched"

    def test_dark_theme_darkens_every_core_surface(self):
        for surface in (".rtt-app", ".rtt-rowband", ".rtt-rowfill", ".rtt-panelgroup",
                        ".rtt-block", ".rtt-show-group", ".rtt-show-tile"):
            assert _dark_sets(surface, "background"), surface

    def test_dark_theme_flips_text_light_on_every_text_role(self):
        assert _dark_sets(".rtt-drawer-inner", "color"), "the panel text rides .rtt-drawer-inner's colour; the grid's value/label/caption text # each carry their own, so each must be re-lit"
        for text in (".rtt-value", ".rtt-row-label", ".rtt-symbol", ".rtt-caption"):
            assert _dark_sets(text, "color"), text

    def test_dark_theme_relights_the_foreground_glyphs_that_inherit_their_colour(self):
        for glyph in (".rtt-generator-sign", ".rtt-drag-handle"):
            assert _dark_sets(glyph, "color"), (
                f"{glyph} is a bare glyph with no colour of its own — in light mode it inherits the "
                "cell's near-black; without a dark rule it stays dark-on-dark (the theme-coverage "
                "gate can't see an inherited colour, so pin it here)")

    def test_dark_theme_relights_the_editable_cell_inputs(self):
        assert _dark_sets(".rtt-cell-input-field", "background"), "an editable value/plain-text cell is a white q-input in light mode; dark must darken # its fill and re-light its typed text, or edited cells stay blinding white"
        assert _dark_sets(".rtt-cell-input-field", "color")
        assert _dark_sets(".rtt-plain-text-edit", "background")

    def test_dark_theme_retints_the_baked_in_marks_without_disturbing_the_pending_green(self):
        assert f'body.rtt-dark [fill="{marks.BR_COLOR}"]' in page_assets._CSS, "the EBK brackets bake BR_COLOR into their SVG fill; the overlay retints exactly that # value via an attribute rule (CSS beats the presentation attribute). A pending comma's # green marks (#2e9e3f) don't match it, so they stay green — assert nothing retints that fill"
        assert f'[fill="{marks.PENDING_COLOR}"]' not in page_assets._CSS

    def test_dark_theme_retints_stroke_drawn_marks_too(self):
        assert f'body.rtt-dark [stroke="{marks.BR_COLOR}"]' in page_assets._CSS, "some BR_COLOR marks are STROKE-drawn, not filled: the chart axes / zero baseline (and the # dummy tile's sample-chart axes). The fill attribute rule can't reach a stroke, so a parallel # stroke rule retints exactly that value — else those lines stay near-black on the dark pane"

    def test_dark_theme_overrides_the_themed_variables(self):
        allvars = _dark_var_blocks()
        for var in ("--c-gridline", "--cell-border", "--seam"):
            assert var + ":" in allvars, var

    def test_dark_stacked_cells_show_their_face_not_the_raw_input(self):
        css = page_assets._CSS
        unfocused = re.search(
            r"body\.rtt-dark \.rtt-cell-stacked \.rtt-cell-input-field \.q-field__native\s*\{([^}]*)\}", css)
        assert unfocused and "transparent" in unfocused.group(1)
        focused = re.search(
            r"body\.rtt-dark \.rtt-cell-stacked:focus-within \.rtt-cell-input-field \.q-field__native\s*\{([^}]*)\}", css)
        assert focused and "color:" in focused.group(1) and "#000" not in focused.group(1)

    def test_dark_mode_is_a_standalone_preference_not_a_show_setting(self):
        assert isinstance(page_assets._DARK_KEY, str) and page_assets._DARK_KEY != page_assets._STORE_KEY, "dark mode is a global VIEWING preference, deliberately kept OUT of the Show settings: it # persists under its own store key (separate from the serialized document), so it is untouched # by 'select all / none' and Reset — both of which act only on editor.settings"
        assert "dark_mode" not in show_settings.DEFAULTS

    def test_dark_mode_toggle_carries_hover_text(self):
        assert tooltips.CHROME_HELP["dark_mode"].strip(), "the toggle is app chrome (like select-all), so its help lives in CHROME_HELP, not SHOW_HELP"
        assert "dark_mode" not in tooltips.SHOW_HELP

    def test_light_wash_vars_keep_the_original_tints(self):
        for group, tint in page_assets._TINTS.items():
            assert f"--wash-{group}:{tint}" in page_assets._CSS

    def test_dark_theme_retints_the_colorization_washes(self):
        allvars = _dark_var_blocks()
        for var in ("--wash-base", "--wash-tuning", "--wash-temperament", "--wash-form"):
            assert var + ":" in allvars, var

    def test_boot_theme_bakes_a_stored_preference_so_no_round_trip_is_needed(self):
        assert "var p=true;" in page_assets.boot_theme_head(True), "a stored dark preference is baked into the boot script, so the first paint knows the mode # synchronously — no server round trip, no light flash"
        assert "var p=false;" in page_assets.boot_theme_head(False)

    def test_boot_theme_falls_back_to_the_os_preference_when_none_is_stored(self):
        boot = page_assets.boot_theme_head(None)
        assert "var p=null;" in boot, "with no stored preference the boot script must resolve the mode itself"
        assert "prefers-color-scheme: dark" in boot, "the unset case reads the OS preference synchronously (matchMedia) rather than waiting on the server"

    def test_boot_theme_paints_the_frame_before_anything_renders(self):
        boot = page_assets.boot_theme_head(True)
        assert "document.documentElement.style.background" in boot, "the boot script sets the page background on the very first synchronous frame, so dark never shows a white flash"
        assert page_assets._DARK_FRAME in boot and "'#fff'" in boot

    def test_boot_theme_hides_the_body_until_the_mode_is_applied(self):
        assert "body:not(.rtt-themed){visibility:hidden;}" in page_assets.boot_theme_head(None), "nothing is shown until the resolved theme adds .rtt-themed — 'don't render until you know which mode'"

    def test_seed_reports_the_os_preference_as_a_boolean(self):
        assert "emitEvent('rtt_seed_dark', dark())" in page_assets._SEED_DARK_JS, "the seed must report light AS WELL AS dark, so the server can reveal a light first-time page (not only reveal on dark)"

    def test_dark_mode_has_its_own_option_box_svgs(self):
        assert page_assets._CSS.count("data:image/svg") == 6, "the checkbox / option-box art is a baked SVG data-URI, so dark mode needs its own dark-box # variants (set via the --option-box-* properties under body.rtt-dark) — three more URIs"
        allvars = _dark_var_blocks()
        for var in ("--option-box-unchecked", "--option-box-checked", "--option-box-disabled"):
            assert var + ":url(" in allvars, var


_COLOR_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


class TestTilePreviewsPaintThroughThemeTokens:
    """The settings-panel tile previews (the "tile features" dummy tile, the app-features example
    glyphs) must match the real tiles in BOTH themes. They render as HTML strings with inline
    styles, which no ``body.rtt-dark`` rule can reach — so a raw color hex there is frozen at its
    light value and goes illegible in dark mode. This gate forbids the whole class of that bug:
    every color must come from a themeable token (rtt.css :root, flipped in rtt-dark.css)."""

    def test_the_preview_builders_hold_no_raw_color_hex(self):
        for module in (render_html_tiles, building):
            source = pathlib.Path(module.__file__).read_text()
            leaked = sorted(set(_COLOR_HEX.findall(source)))
            assert not leaked, (
                f"{module.__name__} hardcodes color hex {leaked}. The tile previews must paint "
                "through the themeable CSS tokens (--fg, --fg-caption, --fg-icon, --cell-bg, "
                "--cell-border, --tile-border, --demo-tip-*, --demo-accent*) so rtt-dark.css re-lights "
                "them and the dummy tile keeps matching the real tiles in dark mode. Add a token to "
                "rtt.css :root (+ its dark override) instead of a literal hex here.")

    def test_the_preview_foreground_tokens_are_defined_and_flip_in_dark(self):
        for token in ("--fg", "--fg-caption", "--fg-icon"):
            assert f"{token}:" in page_assets._CSS, f"{token} must be defined for light mode"
            assert _dark_sets("", token) or (token + ":") in _dark_var_blocks(), (
                f"{token} must be overridden under body.rtt-dark so the preview text/icons re-light")
