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
from _render_support import _toggle, _enable, _cell_child, _ratio_value, _wrap_classes, _click_glyph, _commit, _cell_text, _target_preset, _escape_target


class TestEditPreviewRipple:
    async def test_editing_a_cell_previews_the_ripple_then_commits_on_blur(self, user: User) -> None:
        await user.open("/")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        source = _cell_child(user, "cell:mapping:1:2")
        UserInteraction(user, {source}, None).trigger("focus")
        source.set_value("7")
        await user.should_see(marker="cell:mapped:1:6")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")
        assert _cell_text(user, "cell:mapped:1:6") == "4", "...and the edit is NOT applied yet (preview only)"
        UserInteraction(user, {source}, None).trigger("blur")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")

    async def test_repeated_edits_keep_previewing(self, user: User) -> None:
        await user.open("/")
        source = _cell_child(user, "cell:mapping:1:2")
        UserInteraction(user, {source}, None).trigger("focus")
        source.set_value("7")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6")
        UserInteraction(user, {source}, None).trigger("blur")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")
        source = _cell_child(user, "cell:mapping:1:2")
        UserInteraction(user, {source}, None).trigger("focus")
        source.set_value("9")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapped:1:6"), \
            "the live preview must keep working on later edits, not only the first"
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        UserInteraction(user, {source}, None).trigger("blur")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "9"

    async def test_opening_a_comma_draft_previews_the_rank_drop_on_the_mapping(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="cell:comma:0:1")
        await user.should_see(marker="cell:mapping:1:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:2")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:2")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0"), "the survivor is not red"
        _click_glyph(user, "comma_minus:pending")
        await user.should_see(marker="cell:mapping:1:0")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:1:0")

    async def test_opening_a_mapping_row_draft_previews_the_dropped_comma(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "generator_plus")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")
        _click_glyph(user, "map_minus:pending")
        await user.should_see(marker="cell:comma:0:0")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")

    async def test_a_fresh_comma_draft_wires_escape_to_the_drafts_cancel_button(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="comma:pending")
        assert _escape_target(user, "comma:pending") == "comma_minus:pending"
        assert _escape_target(user, "cell:comma:0:1") == "comma_minus:pending"

    async def test_a_fresh_mapping_row_draft_wires_escape_to_the_drafts_cancel_button(self, 
        user: User,
    ) -> None:
        await user.open("/")
        _click_glyph(user, "generator_plus")
        await user.should_see(marker="cell:mapping:2:0")
        assert _escape_target(user, "cell:mapping:2:0") == "map_minus:pending"

    async def test_hovering_a_comma_minus_previews_the_born_generator(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="cell:mapping:2:0")
        button = set(user.find(marker="comma_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-pending" in _wrap_classes(user, "cell:mapping:2:0")
        assert [_cell_text(user, f"cell:mapping:2:{p}") for p in range(3)] == ["0", "0", "1"], "the op is known, so the born generator's coords are COMPUTED and shown: dropping the syntonic # comma un-tempers to JI, whose third generator is prime 5 → ⟨0 0 1]"
        assert _cell_text(user, "cell:mapped:2:0") != ""
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapped_comma:2:0")
        assert "rtt-pending" not in _wrap_classes(user, "cell:mapped_comma:2:0")
        UserInteraction(user, button, None).trigger("mouseleave")
        await user.should_not_see(marker="cell:mapping:2:0")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")

    async def test_hovering_a_mapping_minus_previews_the_born_comma(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="cell:comma:0:1")
        button = set(user.find(marker="map_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        await user.should_see(marker="cell:comma:0:1")
        assert "rtt-pending" in _wrap_classes(user, "cell:comma:0:1")
        assert "rtt-pending" in _wrap_classes(user, "comma:pending"), "its quantities-row ratio face (a read-only commaratio showing the COMPUTED ratio) greens too — # rings its wrap like every sibling value cell down the column, not just the vector/derived rows"
        assert [_cell_text(user, f"cell:comma:{p}:1") for p in range(3)] == ["0", "-4", "1"], "the born comma's coords are COMPUTED and shown (dropping meantone's generator un-tempers to the # rank-1 ET whose extra comma is [0 -4 1⟩)"
        assert _cell_text(user, "cell:mapped_comma:1:1") == "0"
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:0:0")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:comma:0:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapped_comma:0:1")
        assert "rtt-pending" not in _wrap_classes(user, "cell:mapped_comma:0:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        await user.should_not_see(marker="cell:comma:0:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0")

    async def test_hovering_a_mapping_minus_in_projection_dooms_the_last_unchanged_interval(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:1")
        button = set(user.find(marker="map_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:unchanged:0:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:unchanged:0:0")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:unchanged:0:1")

    async def test_hovering_a_comma_minus_in_projection_births_an_unchanged_interval(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:1")
        await user.should_not_see(marker="cell:unchanged:0:2")
        button = set(user.find(marker="comma_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        await user.should_see(marker="cell:unchanged:0:2")
        assert "rtt-pending" in _wrap_classes(user, "cell:unchanged:0:2")
        UserInteraction(user, button, None).trigger("mouseleave")
        await user.should_not_see(marker="cell:unchanged:0:2")

    async def test_blurring_an_incomplete_draft_cell_keeps_the_other_typed_cells(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="cell:comma:0:1")
        _cell_child(user, "cell:comma:0:1").set_value("7")
        UserInteraction(user, {_cell_child(user, "cell:comma:0:1")}, None).trigger("blur")
        await user.should_see(marker="cell:comma:0:1")
        assert _cell_child(user, "cell:comma:0:1").value == "7"

    async def test_hovering_a_non_last_comma_minus_reds_that_comma_not_the_last(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        for p, v in zip(range(3), ("7", "0", "-3")):
            _cell_child(user, f"cell:comma:{p}:1").set_value(v)
        _commit(user, "cell:comma:2:1")
        await user.should_see(marker="comma_minus:1")
        button = set(user.find(marker="comma_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "comma:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:comma:0:0")

    async def test_hovering_a_non_last_mapping_row_minus_reds_that_row_not_the_last(self, user: User) -> None:
        await user.open("/")
        button = set(user.find(marker="map_minus:0").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:0:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "generator:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "tuning:generator:0")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:1:0")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapping:0:0")

    async def test_adding_a_mapping_row_previews_the_rank_raise_while_the_draft_is_green(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "generator_plus")
        await user.should_see(marker="cell:mapping:2:0")
        for p, v in zip(range(2), ("0", "0")):
            _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
        last = _cell_child(user, "cell:mapping:2:2")
        UserInteraction(user, {last}, None).trigger("focus")
        last.set_value("1")
        await user.should_see(marker="cell:comma:0:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0"), "the comma it un-tempers → red"
        assert "rtt-preview-remove" in _wrap_classes(user, "comma:0")
        assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes
        UserInteraction(user, {last}, None).trigger("blur")
        await user.should_see(marker="cell:mapping:2:0")
        await user.should_not_see(marker="comma_minus:0")

    async def test_typing_a_target_limit_rings_the_rows_it_moves(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        num.set_value("9")
        await user.should_see(marker="retune:target:8")
        assert "rtt-preview-change" in _wrap_classes(user, "retune:target:8")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:generator:0")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")
        UserInteraction(user, {num}, None).trigger("blur")
        assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:8")

    async def test_scrolling_the_target_limit_down_reddens_the_dropped_target_rows(self, 
            user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 100)
        await _enable(user, "presets")
        await user.should_see(marker="retune:target:7")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": 100})
        num, _sel = _target_preset(user)
        assert int(num.value) == 5
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")
        assert "rtt-preview-remove" in _wrap_classes(user, "target:7")
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")

    async def test_typing_the_target_limit_down_reddens_the_dropped_target_rows(self, 
            user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 100)
        await _enable(user, "presets")
        await user.should_see(marker="retune:target:7")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        UserInteraction(user, {num}, None).trigger("keyup", "5")
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")
        assert "rtt-preview-remove" in _wrap_classes(user, "target:7")
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")

    async def test_the_typed_target_limit_preview_rides_keyup_not_input(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        num, _sel = _target_preset(user)
        listeners = list(num._event_listeners.values())
        types = {listener.type for listener in listeners}
        assert "keyup" in types, f"typed-limit preview must ride keyup; got {sorted(types)}"
        assert "input" not in types, "native `input` never fires on a QInput — the preview must not rely on it"
        keyup = next(listener for listener in listeners if listener.type == "keyup")
        assert keyup.js_handler and "target.value" in keyup.js_handler, \
            f"keyup must emit the live target.value via a js_handler; got {keyup.js_handler!r}"

    async def test_the_dropped_target_red_preview_clears_when_the_limit_field_is_left(self, 
            user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 100)
        await _enable(user, "presets")
        await user.should_see(marker="retune:target:7")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": 100})
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:7")
        UserInteraction(user, {num}, None).trigger("blur")
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:7")

    async def test_the_target_remove_preview_diffs_the_on_screen_grid_not_the_focus_snapshot(self, 
            user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 0.01)
        await _enable(user, "presets")
        await user.should_see(marker="retune:target:7")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        num.set_value("8")
        await user.should_see(marker="retune:target:9")
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 100)
        UserInteraction(user, {num}, None).trigger("keyup", "6")
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:8"), \
            "a preview after a focused commit must diff the on-screen (8-TILT) grid, not the focus snapshot"
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:9")
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:6")

    async def test_scrolling_the_target_limit_up_reddens_no_target_rows(self, user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 100)
        await _enable(user, "presets")
        await user.should_see(marker="retune:target:7")
        num, _sel = _target_preset(user)
        UserInteraction(user, {num}, None).trigger("focus")
        UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": -100})
        num, _sel = _target_preset(user)
        assert int(num.value) == 7
        for index in range(8):
            assert "rtt-preview-remove" not in _wrap_classes(user, f"retune:target:{index}")

    async def test_an_invalid_target_limit_stays_reddened_through_the_edit_preview_gesture(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        _num, selection = _target_preset(user)
        selection.set_value("OLD")
        await user.should_see(marker="preset:target")
        num, _sel = _target_preset(user)
        assert "rtt-limit-error" in num._classes
        UserInteraction(user, {num}, None).trigger("focus")
        UserInteraction(user, {num}, None).trigger("blur")
        num, _sel = _target_preset(user)
        assert "rtt-limit-error" in num._classes

    async def test_switching_the_family_to_old_over_an_even_limit_toasts(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        _num, selection = _target_preset(user)
        selection.set_value("OLD")
        await user.should_see("needs an odd limit")
        num, _sel = _target_preset(user)
        assert "rtt-limit-error" in num._classes

    async def test_relabeling_a_domain_element_clears_the_edit_preview_on_commit(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "nonstandard domain")
        await user.should_see(marker="prime:1")
        inp = _cell_child(user, "prime:1")
        UserInteraction(user, {inp}, None).trigger("focus")
        inp.set_value("7")
        assert "rtt-preview-change" in _wrap_classes(user, "just:prime:1")
        UserInteraction(user, {inp}, None).trigger("blur")
        await user.should_see(marker="just:prime:1")
        assert _cell_child(user, "prime:1").value == "7"
        assert "rtt-preview-change" not in _wrap_classes(user, "just:prime:1")

    async def test_relabeling_a_domain_element_across_a_kind_change_clears_on_blur(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "nonstandard domain")
        await user.should_see(marker="prime:1")
        inp = _cell_child(user, "prime:1")
        UserInteraction(user, {inp}, None).trigger("focus")
        inp.set_value("9/7")
        assert "rtt-preview-change" in _wrap_classes(user, "just:prime:1")
        UserInteraction(user, {inp}, None).trigger("blur")
        await user.should_see(marker="just:prime:1")
        assert _ratio_value(user, "prime:1") == "9/7"
        assert "rtt-preview-change" not in _wrap_classes(user, "just:prime:1"), \
            "the kind-change relabel left the amber ring stuck after commit"

    async def test_committing_a_ratio_clears_the_edit_preview(self, user: User) -> None:
        await user.open("/")
        await user.should_see(marker="comma:0")
        inp = _cell_child(user, "comma:0")
        UserInteraction(user, {inp}, None).trigger("focus")
        inp.set_value("25/24")
        UserInteraction(user, {inp}, None).trigger("blur")
        await user.should_see(marker="cell:comma:0:0")
        assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]
        for p in range(3):
            assert "rtt-preview-change" not in _wrap_classes(user, f"cell:comma:{p}:0")

    async def test_an_unrelated_render_does_not_strand_a_control_hovers_red_ring(self, user: User) -> None:
        await user.open("/")
        button = set(user.find(marker="generator_minus").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "tuning:generator:1")
        _toggle(user, "counts")
        await user.should_see(marker="tuning:generator:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:generator:1"), "...its red was stripped, not orphaned"
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:generator:1")

    async def test_selecting_a_temperament_clears_a_prior_shrink_hovers_red(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        await user.should_see(marker="preset:temperament")
        sevens = [k for k in presets.temperament_options()
                  if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS
                  and len(presets.TEMPERAMENT_COMMAS[k]) == 2]
        _cell_child(user, "preset:temperament").set_value(sevens[0])
        await user.should_see(marker="prime:3")
        wrap = set(user.find(marker="preset:temperament").elements)
        five = next(k for k in presets.temperament_options()
                    if k.startswith("5:") and k in presets.TEMPERAMENT_COMMAS)
        index = list(presets.temperament_options()).index(five)
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": index})
        assert "rtt-preview-remove" in _wrap_classes(user, "prime:3")
        other7 = next(k for k in sevens if k != sevens[0])
        _cell_child(user, "preset:temperament").set_value(other7)
        await user.should_see(marker="prime:3")
        assert "rtt-preview-remove" not in _wrap_classes(user, "prime:3")


class TestPreviewClearing:
    async def test_completing_a_held_interval_draft_clears_the_rings_without_blur(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        await user.should_see(marker="cell:held:0:0")
        inp = _cell_child(user, "cell:held:0:0")
        UserInteraction(user, {inp}, None).trigger("focus")
        _cell_child(user, "cell:held:1:0").set_value("1")
        _cell_child(user, "cell:held:2:0").set_value("0")
        wrap = set(user.find(marker="cell:held:0:0").elements)
        UserInteraction(user, wrap, None).trigger("wheel", {"deltaY": 100})
        await user.should_see(marker="held:0")
        assert _ratio_value(user, "held:0") == "3/2"
        for p in range(3):
            assert "rtt-preview-change" not in _wrap_classes(user, f"cell:held:{p}:0"), \
                "the held interval commit left its rings stranded (no blur ever fires on this path)"
        assert "rtt-preview-change" not in _wrap_classes(user, "held:0")

    async def test_clicking_reset_after_hovering_it_clears_the_preview(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "tuning:generator:1").set_value("700.000")
        await user.should_see(marker="reset")
        button = set(user.find(marker="reset").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:generator:1")
        user.find(marker="reset").click()
        await user.should_see(marker="tuning:generator:1")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:generator:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:generator:1")

    async def test_selecting_an_established_projection_clears_the_chooser_preview(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="projection").click()
        await user.should_see(marker="preset:projection")
        selection = _cell_child(user, "preset:projection")
        wrap = set(user.find(marker="preset:projection").elements)
        index = list(selection.options).index("1/3-comma")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": index})
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:generator:1")
        selection.set_value("1/3-comma")
        await user.should_see(marker="preset:projection")
        assert _cell_child(user, "tuning:generator:1").value == "694.786"
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:generator:1"), \
            "the projection pick left its hover rings stranded after the commit"

    async def test_a_stale_opthover_after_popup_hide_is_dropped(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        await user.should_see(marker="preset:tuning")
        selection = _cell_child(user, "preset:tuning")
        wrap = set(user.find(marker="preset:tuning").elements)
        index = list(presets.tuning_scheme_options(False, False, True)).index("minimax-S")
        UserInteraction(user, {selection}, None).trigger("popupShow")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": index})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        UserInteraction(user, {selection}, None).trigger("popupHide")
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": index})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1"), \
            "a stale opthover after popup-hide re-armed the preview (the stranded-ring race)"
        UserInteraction(user, {selection}, None).trigger("popupShow")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": index})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")

    async def test_a_control_hover_preserves_an_open_draft(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="comma:pending")
        UserInteraction(user, {_cell_child(user, "comma:pending")}, None).trigger("blur")
        button = set(user.find(marker="minus").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        UserInteraction(user, button, None).trigger("mouseleave")
        _toggle(user, "counts")
        await user.should_see(marker="comma:pending")
        assert "rtt-pending" in _wrap_classes(user, "comma:pending")
        await user.should_see(marker="cell:comma:0:1")

    async def test_generator_sign_hover_hands_the_wheel_preview_back(self, user: User) -> None:
        await user.open("/")
        cell = set(user.find(marker="tuning:generator:0").elements)
        UserInteraction(user, cell, None).trigger("mouseenter")
        sign = set(user.find(marker="generator_sign:0").elements)
        UserInteraction(user, sign, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:0")
        UserInteraction(user, sign, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:0")
        UserInteraction(user, cell, None).trigger("wheel.prevent", {"deltaY": -1})
        await user.should_see(marker="retune:target:0")
        assert "rtt-preview-change" in _wrap_classes(user, "retune:target:0"), \
            "the sign-hover detour lost the wheel gesture — the notch rang nothing"
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:generator:0")
        UserInteraction(user, cell, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:0")

    async def test_added_cells_are_withheld_until_the_reflow_settles_but_the_cold_paint_and_drafts_are_not(self, 
            user: User) -> None:
        await user.open("/")
        assert "rtt-withhold" not in _wrap_classes(user, "cell:mapping:0:0")
        _toggle(user, "presets")
        await user.should_see(marker="preset:tuning")
        assert "rtt-withhold" in _wrap_classes(user, "preset:tuning")
        _click_glyph(user, "interest_plus")
        await user.should_see(marker="cell:interest:0:0")
        assert "rtt-cell-input" in _wrap_classes(user, "cell:interest:0:0")
        assert "rtt-withhold" not in _wrap_classes(user, "cell:interest:0:0"), "...appears at once, not withheld"

    async def test_hovering_a_nonstandard_approach_option_previews_setting_it(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "plain text values")
        _cell_child(user, "plain_text:mapping:primes").set_value("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        await user.should_see(marker="approach")
        prime_opt = set(user.find(marker="approach-prime-based").elements)
        UserInteraction(user, prime_opt, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:prime:0")
        UserInteraction(user, set(user.find(marker="approach").elements), None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:prime:0")
