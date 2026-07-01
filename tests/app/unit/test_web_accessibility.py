"""WP3 accessibility: the page honours the OS motion/theme preferences, meets AA
text contrast, and adapts its fixed left rail on narrow viewports.

These assert the shipped CSS/JS rather than a live browser (rendering is covered by
the render suite and the browser-smoke probe). The contrast tests pull the actual
colour out of the rule and compute the WCAG ratio, so they encode the *requirement*
(>= 4.5:1) — not a brittle hex — and fail if a later edit lightens the text back."""

import re

from rtt.app.page_assets import _CSS, _SEED_DARK_JS, _TOUR_JS


def _relative_luminance(hex_color):
    digits = hex_color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(d * 2 for d in digits)
    channels = []
    for pair in (digits[0:2], digits[2:4], digits[4:6]):
        c = int(pair, 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg, bg):
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def _rule_body(css, selector):
    """The declaration body of the first rule whose selector text contains ``selector``,
    skipping ``@media`` group openers (their body is nested braces, not declarations)."""
    for match in re.finditer(r"([^{}]*)\{([^{}]*)\}", css):
        sels, body = match.group(1), match.group(2)
        if selector in sels and "@media" not in sels:
            return body
    return None


def _prop(css, selector, prop):
    body = _rule_body(css, selector)
    assert body is not None, f"no rule for {selector}"
    found = re.search(rf"(?:^|;|\s){prop}\s*:\s*([^;]+)", body)
    return found.group(1).strip() if found else None


def _media_blocks(css, query):
    """The concatenated inner text of every ``@media`` block opened by ``query`` (there may be more
    than one block for the same query in different sections of the sheet)."""
    out = []
    for start in [m.start() for m in re.finditer(re.escape(query), css)]:
        brace = css.index("{", start)
        depth, i = 1, brace + 1
        while depth and i < len(css):
            depth += 1 if css[i] == "{" else -1 if css[i] == "}" else 0
            i += 1
        out.append(css[brace + 1 : i - 1])
    return "\n".join(out)


class TestReducedMotion:
    def test_reduce_motion_zeroes_the_transition_var(self):
        block = _media_blocks(_CSS, "@media (prefers-reduced-motion: reduce)")
        assert re.search(r":root\s*\{[^}]*--t\s*:\s*0s", block), (
            "reduce-motion must zero the shared --t kill-switch so every var(--t) slide/fade/rotate "
            "(including the wordmark's rotate) snaps instantly"
        )

    def test_tour_autostart_is_suppressed_under_reduced_motion(self):
        assert "prefers-reduced-motion" in _TOUR_JS, (
            "the auto-running first-load tour (with its moving spotlight) must not start itself when "
            "the OS asks to reduce motion; the ? replay button still works"
        )
        assert re.search(r"config\.autostart[^\n{]*reduceMotion", _TOUR_JS), (
            "the autostart condition itself must be gated on the reduce-motion check"
        )


class TestContrast:
    LIGHT_TILE = "#e0e0e0"
    LIGHT_PANE = "#c0c0c0"
    DARK_BOX = "#31373f"

    def test_cell_unit_text_meets_aa_on_the_grid_tile(self):
        color = _prop(_CSS, ".rtt-cell-unit", "color")
        assert _contrast(color, self.LIGHT_TILE) >= 4.5, color

    def test_disabled_caption_meets_aa_on_the_grid_pane(self):
        color = _prop(_CSS, ".rtt-caption.rtt-caption-disabled", "color")
        assert _contrast(color, self.LIGHT_PANE) >= 4.5, color

    def test_dark_disabled_caption_meets_aa_on_the_dark_box(self):
        color = _prop(_CSS, "body.rtt-dark .rtt-caption.rtt-caption-disabled", "color")
        assert _contrast(color, self.DARK_BOX) >= 4.5, color

    def test_the_dummy_tile_unit_sample_matches_the_real_cell_unit(self):
        from rtt.app import building

        source = (building.__file__).replace(".pyc", ".py")
        with open(source, encoding="utf-8") as handle:
            assert "#555" not in handle.read(), (
                "the Show-panel sample unit must track the real .rtt-cell-unit contrast fix, not keep "
                "the old #555"
            )


class TestResponsiveRail:
    def test_narrow_viewport_collapses_the_wordmark_rail(self):
        block = _media_blocks(_CSS, "@media (max-width: 600px)")
        assert re.search(r"--tab-w\s*:\s*\d", block), (
            "below the breakpoint the closed sidebar tab must narrow so the grid pane reclaims the width"
        )
        assert "rtt-sidetitle" in block, (
            "the rotated wordmark is dropped in the collapsed state on phones so it stops eating grid width"
        )


class TestTouchAffordances:
    def test_ratio_operations_surface_on_focus_under_a_coarse_pointer(self):
        block = _media_blocks(_CSS, "@media (hover: none) and (pointer: coarse)")
        reveal = re.search(
            r"\.rtt-fraction-cell:focus-within\s+\.rtt-ratio-operation\s*\{([^}]*)\}", block
        )
        assert reveal and "opacity:1" in reveal.group(1).replace(" ", ""), (
            "touch users have no hover, so a tap that focuses a ratio cell must reveal its "
            "reduce/reciprocate operations"
        )


class TestColorSchemeSeed:
    def test_dark_is_seeded_from_the_os_preference(self):
        assert "prefers-color-scheme: dark" in _SEED_DARK_JS
        assert "rtt_seed_dark" in _SEED_DARK_JS
