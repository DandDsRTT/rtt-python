"""Every colour that renders on a themed surface must have a dark-mode disposition.

Dark mode is a palette overlay: light rules in rtt.css carry literal greys, and rtt-dark.css
restates each on a ``body.rtt-dark`` rule (or retints a shared custom property). A colour that is
hardcoded with no such counterpart shows through wrong in dark mode — the exact class of bug that
left the mapping demo (a #fff baked into an SVG the overlay can't reach) and the generator +/- sign
dark-on-dark. This gate scans the shipped stylesheets and client JS for that class so it cannot
regress: a raw colour literal in a themed CSS property whose selector has no dark override, a light
``:root`` colour token with no dark redefinition, or a raw colour literal in an asset script (which
a ``body.rtt-dark`` selector can never override). Genuinely theme-neutral cases — self-contained
dark cards, error/focus accents, drop shadows — are enumerated in
``theme_checks.INTENTIONALLY_THEME_NEUTRAL`` with a reason, so each is an explicit, reviewed choice
rather than an oversight."""

from pathlib import Path

from rtt.app import page_assets
from tools import theme_checks

_ASSETS = Path(page_assets.__file__).parent / "assets"


class TestThemeCoverage:
    def test_no_untethemed_colour_literal_in_the_stylesheets(self):
        light = (_ASSETS / "rtt.css").read_text()
        dark = (_ASSETS / "rtt-dark.css").read_text()
        gaps = theme_checks.css_theme_gaps(light, dark)
        assert gaps == [], (
            "each colour below renders in dark mode with no dark counterpart — add a body.rtt-dark "
            "override (or retint the shared token), or record it in "
            "theme_checks.INTENTIONALLY_THEME_NEUTRAL with a reason:\n  " + "\n  ".join(gaps)
        )

    def test_client_js_routes_every_colour_through_a_themed_var(self):
        hits = theme_checks.js_colour_literals(sorted(_ASSETS.glob("*.js")))
        assert hits == [], (
            "a script sets a raw colour a body.rtt-dark selector can't reach; route it through a "
            "themed var (e.g. var(--cell-bg)) so it inverts with the theme:\n  " + "\n  ".join(hits)
        )
