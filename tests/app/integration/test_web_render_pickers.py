import asyncio
import copy
import logging
import re
import sys
from fractions import Fraction
from types import SimpleNamespace
import nicegui.ui as ui
import pytest
from nicegui import core
from nicegui.element_filter import ElementFilter
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction
from rtt.app import app as web_app
from rtt.app import rendering as web_rendering
from rtt.app import _editing_tuning, page_assets, service, spreadsheet, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.editor import Editor
from _render_support import _enable, _cell_child, _wrap_classes, _click_glyph


class TestSubpickersBuild:
    async def test_subpickers_build_and_derive_their_value_from_state(self, user: User) -> None:
        await _enable(user, "presets")
        et0 = _cell_child(user, "etpick:0")
        cp0 = _cell_child(user, "commapick:0")
        assert isinstance(et0, ui.select) and isinstance(cp0, ui.select)
        assert et0.value is None, "default meantone: its canonical rows aren't single ETs, so the ET picker shows the '-' prompt; # its comma (4 -4 1) IS the syntonic comma (up to sign), so the comma picker matches it"
        assert cp0.value == "81/80"

    async def test_picking_two_ets_builds_the_temperament_and_syncs_the_chooser(self, user: User) -> None:
        await _enable(user, "presets")
        _cell_child(user, "etpick:0").set_value("12")
        _cell_child(user, "etpick:1").set_value("19")
        assert _cell_child(user, "etpick:0").value == "12"
        assert _cell_child(user, "etpick:1").value == "19"
        assert _cell_child(user, "preset:temperament").value == "5:Meantone"

    async def test_picking_a_dependent_et_is_rejected_and_reverts(self, user: User) -> None:
        await _enable(user, "presets")
        _cell_child(user, "etpick:0").set_value("12")
        _cell_child(user, "etpick:1").set_value("19")
        _cell_child(user, "etpick:1").set_value("12")
        assert _cell_child(user, "etpick:1").value == "19"

    async def test_picking_a_comma_replaces_the_column_and_syncs(self, user: User) -> None:
        await _enable(user, "presets")
        _cell_child(user, "commapick:0").set_value("128/125")
        assert _cell_child(user, "commapick:0").value == "128/125"
        assert _cell_child(user, "preset:temperament").value == "5:Augmented"

    async def test_a_draft_comma_picker_adds_the_chosen_comma(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="cell:mapping:1:0")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="commapick:draft")
        _cell_child(user, "commapick:draft").set_value("128/125")
        await user.should_not_see(marker="cell:mapping:1:0")
        await user.should_not_see(marker="commapick:draft")

    async def test_a_draft_et_picker_adds_a_generator(self, user: User) -> None:
        await _enable(user, "presets")
        _click_glyph(user, "map_plus")
        await user.should_see(marker="etpick:draft")
        _cell_child(user, "etpick:draft").set_value("22")
        await user.should_see(marker="cell:mapping:2:0")
        await user.should_not_see(marker="etpick:draft")

    async def test_hovering_an_et_picker_option_previews_replacing_the_row(self, user: User) -> None:
        await _enable(user, "presets")
        et0 = _cell_child(user, "etpick:0")
        wrap = set(user.find(marker="etpick:0").elements)
        idx = list(et0.options).index("12")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")

    async def test_hovering_a_comma_picker_option_previews_replacing_the_column(self, user: User) -> None:
        await _enable(user, "presets")
        cp0 = _cell_child(user, "commapick:0")
        wrap = set(user.find(marker="commapick:0").elements)
        idx = list(cp0.options).index("128/125")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")

    async def test_hovering_a_draft_comma_picker_populates_the_green_column(self, user: User) -> None:
        await _enable(user, "presets")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="commapick:draft")
        dp = _cell_child(user, "commapick:draft")
        wrap = set(user.find(marker="commapick:draft").elements)
        idx = list(dp.options).index("128/125")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert _cell_child(user, "cell:comma:0:1").value == "7"
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:comma:0:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:1")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert _cell_child(user, "cell:comma:0:1").value == ""

    async def test_et_picker_offers_every_uniform_map_through_72(self, user: User) -> None:
        await _enable(user, "presets")
        options = list(_cell_child(user, "etpick:0").options)
        ints = sorted(int(v) for v in options if v.isdigit())
        assert [n for n in range(1, 73) if n not in ints] == []
        assert "17c" in options
        assert max(ints) >= 311 and len(options) >= 300
