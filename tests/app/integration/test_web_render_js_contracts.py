"""Render-level DOM contracts the client JS depends on (WP9 finding 7).

The in-process User plugin renders the Python element tree but never runs the asset
JS, so it can't click the busy scrim or drive a fraction edit. What it CAN pin is the
app-side half of the contract: that the reconciler keeps stamping the hook classes the
JS queries (`.rtt-fraction-edit` and its numerator/denominator inputs; `.rtt-decimal-edit`
and its whole/fraction inputs), that the busy scrim the settings-click handler arms is
present, and that the settings render the checkbox controls that handler catches. If a
reconciler or NiceGUI change drops one of these, a JS selector would silently miss in
production — here it fails CI instead.

The Quasar-internal half — the `.q-*` runtime classes, the `input` descendant of a
q-input, the dropdown teleport target — only exists in the live browser (the User tree
carries our `.classes()`, not Quasar's runtime classes), so it is covered by the opt-in
browser smoke, not here.
"""

import nicegui.ui as ui
from nicegui.element_filter import ElementFilter
from nicegui.testing import User

from rtt.app import page_assets


def _by_class(user: User, css_class: str) -> list:
    with user._client:
        return [e for e in ElementFilter() if css_class in getattr(e, "_classes", [])]


class TestClientJsDomContracts:
    async def test_editable_fraction_cell_carries_the_selectors_fraction_js_queries(self, user: User) -> None:
        await user.open("/")
        editbox = next(iter(user.find(marker="comma:0:editbox").elements))
        assert "rtt-fraction-edit" in editbox._classes
        num = next(iter(user.find(marker="comma:0:numerator").elements))
        den = next(iter(user.find(marker="comma:0:denominator").elements))
        assert "rtt-fraction-numerator-input" in num._classes
        assert "rtt-fraction-denominator-input" in den._classes

    async def test_editable_decimal_cell_carries_the_selectors_decimal_js_queries(self, user: User) -> None:
        await user.open("/")
        editbox = next(iter(user.find(marker="tuning:generator:1:editbox").elements))
        assert "rtt-decimal-edit" in editbox._classes
        whole = next(iter(user.find(marker="tuning:generator:1:whole").elements))
        frac = next(iter(user.find(marker="tuning:generator:1:fraction").elements))
        assert "rtt-decimal-whole-input" in whole._classes
        assert "rtt-decimal-fraction-input" in frac._classes

    async def test_busy_scrim_and_its_arm_targets_are_present(self, user: User) -> None:
        await user.open("/")
        assert _by_class(user, "rtt-busy"), "the scrim rttBusy.arm() reveals must render"
        with user._client:
            assert list(ElementFilter(kind=ui.checkbox)), "settings render the checkboxes the arm handler catches"
        busy_js = page_assets._BUSY_JS
        assert "window.rttBusy" in busy_js and ".arm()" in busy_js
        assert ".q-checkbox" in busy_js and ".rtt-range-option" in busy_js
