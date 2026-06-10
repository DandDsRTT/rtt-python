"""The dark-theme overlay (assets/rtt-dark.css + the dark option-box SVG vars).

The theme is a palette OVERLAY gated on the ``rtt-dark`` class on <body>: light mode is
the base and every dark rule is prefixed ``body.rtt-dark``, so with the class off the
overlay is inert. These tests assert the overlay is present and themes each surface,
text role and the theme-resistant marks — by checking the relevant *property is set*,
not its exact hue (the palette is tuned by eye, so pinning hexes would be brittle)."""

import re

import rtt.web.app as app
from rtt.web import settings as show_settings
from rtt.web import tooltips


def _dark_sets(selector, prop):
    """True if some ``body.rtt-dark … <selector> … { … <prop>: … }`` rule exists — i.e. the
    overlay themes ``prop`` on a rule whose (possibly grouped) selector mentions ``selector``."""
    for m in re.finditer(r"(body\.rtt-dark[^{]*)\{([^}]*)\}", app._CSS):
        sels, body = m.group(1), m.group(2)
        if selector in sels and re.search(rf"(^|;|\s){re.escape(prop)}\s*:", body):
            return True
    return False


def _dark_var_blocks():
    """The declaration bodies of every bare ``body.rtt-dark { … }`` block (the themed
    custom-property overrides), concatenated."""
    return " ".join(re.findall(r"body\.rtt-dark\s*\{([^}]*)\}", app._CSS))


def test_dark_overlay_is_gated_on_the_body_class():
    # the whole theme lives behind body.rtt-dark, so the default (light) render is untouched
    assert "body.rtt-dark" in app._CSS


def test_dark_theme_darkens_every_core_surface():
    for surface in (".rtt-app", ".rtt-rowband", ".rtt-panelgroup",
                    ".rtt-block", ".rtt-show-group", ".rtt-show-tile"):
        assert _dark_sets(surface, "background"), surface


def test_dark_theme_flips_text_light_on_every_text_role():
    # the panel text rides .rtt-drawer-inner's colour; the grid's value/label/caption text
    # each carry their own, so each must be re-lit
    assert _dark_sets(".rtt-drawer-inner", "color")
    for text in (".rtt-value", ".rtt-rowlabel", ".rtt-symbol", ".rtt-caption"):
        assert _dark_sets(text, "color"), text


def test_dark_theme_relights_the_editable_cell_inputs():
    # an editable value/plain-text cell is a white q-input in light mode; dark must darken
    # its fill and re-light its typed text, or edited cells stay blinding white
    assert _dark_sets(".rtt-cellinput", "background")
    assert _dark_sets(".rtt-cellinput", "color")
    assert _dark_sets(".rtt-ptextedit", "background")


def test_dark_theme_retints_the_baked_in_marks_without_disturbing_the_pending_green():
    # the EBK brackets bake _BR_COLOR into their SVG fill; the overlay retints exactly that
    # value via an attribute rule (CSS beats the presentation attribute). A pending comma's
    # green marks (#388e3c) don't match it, so they stay green — assert nothing retints that fill.
    assert f'body.rtt-dark [fill="{app._BR_COLOR}"]' in app._CSS
    assert f'[fill="{app._PENDING_COLOR}"]' not in app._CSS


def test_dark_theme_retints_stroke_drawn_marks_too():
    # some _BR_COLOR marks are STROKE-drawn, not filled: the chart axes / zero baseline (and the
    # dummy tile's sample-chart axes). The fill attribute rule can't reach a stroke, so a parallel
    # stroke rule retints exactly that value — else those lines stay near-black on the dark pane.
    assert f'body.rtt-dark [stroke="{app._BR_COLOR}"]' in app._CSS


def test_dark_theme_overrides_the_themed_variables():
    # the colours already behind a custom property are retinted once, under body.rtt-dark, so
    # every consumer (gridlines, the cell/bracket rule, the frozen seam) follows for free
    allvars = _dark_var_blocks()
    for var in ("--c-gridline", "--cell-border", "--seam"):
        assert var + ":" in allvars, var


def test_dark_stacked_cells_show_their_face_not_the_raw_input():
    # the cents / ratio / generator-tuning / power cells overlay a formatted FACE on a transparent
    # input, revealing the raw text only on focus. The dark overlay must mirror that cascade: keep
    # the unfocused input transparent (else the face doubles over the raw text) and re-light it to a
    # legible NON-black colour on focus. Regression: one blanket .q-field__native rule lit the raw
    # text always AND lost to the light focus rule's #000 (black, illegible on the dark cell).
    css = app._CSS
    unfocused = re.search(
        r"body\.rtt-dark \.rtt-cell-stacked \.rtt-cellinput \.q-field__native\s*\{([^}]*)\}", css)
    assert unfocused and "transparent" in unfocused.group(1)
    focused = re.search(
        r"body\.rtt-dark \.rtt-cell-stacked:focus-within \.rtt-cellinput \.q-field__native\s*\{([^}]*)\}", css)
    assert focused and "color:" in focused.group(1) and "#000" not in focused.group(1)


def test_dark_mode_is_a_standalone_preference_not_a_show_setting():
    # dark mode is a global VIEWING preference, deliberately kept OUT of the Show settings: it
    # persists under its own store key (separate from the serialized document), so it is untouched
    # by "select all / none" and Reset — both of which act only on editor.settings.
    assert isinstance(app._DARK_KEY, str) and app._DARK_KEY != app._STORE_KEY
    assert "dark_mode" not in show_settings.DEFAULTS


def test_dark_mode_toggle_carries_hover_text():
    # the toggle is app chrome (like select-all), so its help lives in CHROME_HELP, not SHOW_HELP
    assert tooltips.CHROME_HELP["dark_mode"].strip()
    assert "dark_mode" not in tooltips.SHOW_HELP


def test_light_wash_vars_keep_the_original_tints():
    # the renderer emits each wash colour as var(--wash-<group>); :root defines each to its _TINTS
    # value, so light mode renders byte-identically and the legend swatch matches the grid band
    for group, tint in app._TINTS.items():
        assert f"--wash-{group}:{tint}" in app._CSS


def test_dark_theme_retints_the_colorization_washes():
    # Douglas: the colorization washes should be DARK in dark mode, not the light cyan/yellow/magenta.
    # The base + the three group tints are overridden under body.rtt-dark (the darken blend is kept,
    # so the subtractive green/blue/red overlaps survive).
    allvars = _dark_var_blocks()
    for var in ("--wash-base", "--wash-tuning", "--wash-temperament", "--wash-form"):
        assert var + ":" in allvars, var


def test_dark_mode_has_its_own_option_box_svgs():
    # the checkbox / option-box art is a baked SVG data-URI, so dark mode needs its own dark-box
    # variants (set via the --option-box-* properties under body.rtt-dark) — three more URIs
    assert app._CSS.count("data:image/svg") == 6  # 3 light + 3 dark, defined once each
    allvars = _dark_var_blocks()
    for var in ("--option-box-unchecked", "--option-box-checked", "--option-box-disabled"):
        assert var + ":url(" in allvars, var
