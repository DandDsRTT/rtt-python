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
from _render_support import _toggle, _enable, _cell_child, _ratio_value, _wrap_classes, _click_glyph, _commit, _cell_text, _ro_value, _target_preset


class TestImproperMapping:
    async def test_mapping_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await user.open("/")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        cell = _cell_child(user, "cell:mapping:1:2")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("7")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        UserInteraction(user, {cell}, None).trigger("blur")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"

    async def test_an_improper_mapping_commit_toasts_and_reverts_the_cells(self, user: User) -> None:
        await user.open("/")
        for p, v in zip(range(3), ("1", "1", "0")):
            _cell_child(user, f"cell:mapping:1:{p}").set_value(v)
        _commit(user, "cell:mapping:1:2")
        await user.should_see(page_assets._INVALID_TEMPERAMENT)
        assert [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)] == ["0", "1", "4"]
        assert _cell_text(user, "cell:mapped:1:6") == "4"

    async def test_an_improper_mapping_preview_rings_nothing_and_does_not_toast(self, user: User) -> None:
        await user.open("/")
        UserInteraction(user, {_cell_child(user, "cell:mapping:1:0")}, None).trigger("focus")
        _cell_child(user, "cell:mapping:1:0").set_value("1")
        _cell_child(user, "cell:mapping:1:1").set_value("1")
        cell = _cell_child(user, "cell:mapping:1:2")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("0")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "4"

    async def test_a_mapping_row_draft_commit_materializes_a_new_generator_row(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="cell:mapping:2:0")
        _click_glyph(user, "gen_plus")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes
        for p, v in zip(range(3), ("0", "0", "1")):
            _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
        _commit(user, "cell:mapping:2:2")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-pending" not in _cell_child(user, "cell:mapping:2:0")._classes
        await user.should_not_see(marker="comma_minus:0")

    async def test_a_comma_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await user.open("/")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        cell = _cell_child(user, "cell:comma:0:0")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("8")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        UserInteraction(user, {cell}, None).trigger("blur")
        await user.should_see(marker="cell:comma:0:0")
        assert _cell_child(user, "cell:comma:0:0").value == "8"

    async def test_an_improper_comma_commit_toasts_and_reverts_the_cells(self, user: User) -> None:
        await user.open("/")
        for p, v in zip(range(3), ("0", "0", "1")):
            _cell_child(user, f"cell:comma:{p}:0").set_value(v)
        _commit(user, "cell:comma:2:0")
        await user.should_see(page_assets._INVALID_TEMPERAMENT)
        assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["4", "-4", "1"]

    async def test_an_improper_comma_preview_rings_nothing_and_does_not_toast(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:comma:0:0").set_value("0")
        _cell_child(user, "cell:comma:1:0").set_value("0")
        cell = _cell_child(user, "cell:comma:2:0")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("1")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")
        assert "rtt-preview-remove" not in _wrap_classes(user, "cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "4"

    async def test_a_comma_draft_commit_materializes_a_new_comma_column(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        await user.should_see(marker="cell:comma:0:1")
        assert "rtt-pending" in _cell_child(user, "cell:comma:0:1")._classes
        for p, v in zip(range(3), ("7", "0", "-3")):
            _cell_child(user, f"cell:comma:{p}:1").set_value(v)
        _commit(user, "cell:comma:2:1")
        await user.should_see(marker="comma_minus:1")
        assert "rtt-pending" not in _cell_child(user, "cell:comma:0:1")._classes

    async def test_an_invalid_unchanged_basis_reverts_silently(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:1")
        before = _cell_child(user, "tuning:gen:1").value
        for p, v in zip(range(3), ("0", "0", "0")):
            _cell_child(user, f"cell:unchanged:{p}:1").set_value(v)
        _commit(user, "cell:unchanged:2:1")
        await user.should_see(marker="tuning:gen:1")
        assert _cell_child(user, "tuning:gen:1").value == before
        await user.should_not_see("Not a valid")

    async def test_an_unchanged_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:1")
        before = _cell_child(user, "tuning:gen:1").value
        cell = _cell_child(user, "cell:unchanged:2:1")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("-1")
        assert _cell_child(user, "tuning:gen:1").value == before, "not retuned — no commit on the keystroke"

    async def test_an_interest_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "interest_plus")
        for p, v in zip(range(3), ("-1", "1", "0")):
            _cell_child(user, f"cell:interest:{p}:0").set_value(v)
        _commit(user, "cell:interest:2:0")
        await user.should_see(marker="interest:0")
        assert _ratio_value(user, "interest:0") == "3/2"
        cell = _cell_child(user, "cell:interest:0:0")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("-2")
        assert _ratio_value(user, "interest:0") == "3/2"

    async def test_any_integer_interest_vector_is_accepted_on_commit(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "interest_plus")
        for p, v in zip(range(3), ("5", "-3", "2")):
            _cell_child(user, f"cell:interest:{p}:0").set_value(v)
        _commit(user, "cell:interest:2:0")
        await user.should_see(marker="interest:0")
        assert [_cell_child(user, f"cell:interest:{p}:0").value for p in range(3)] == ["5", "-3", "2"]

    async def test_an_interest_draft_commit_materializes_a_new_interest_column(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="interest:0")
        _click_glyph(user, "interest_plus")
        await user.should_see(marker="cell:interest:0:0")
        assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes
        for p, v in zip(range(3), ("-1", "1", "0")):
            _cell_child(user, f"cell:interest:{p}:0").set_value(v)
        _commit(user, "cell:interest:2:0")
        await user.should_see(marker="interest:0")
        assert "rtt-pending" not in _cell_child(user, "cell:interest:0:0")._classes

    async def test_a_held_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        for p, v in zip(range(3), ("-1", "1", "0")):
            _cell_child(user, f"cell:held:{p}:0").set_value(v)
        _commit(user, "cell:held:2:0")
        await user.should_see(marker="held:0")
        assert _cell_child(user, "tuning:gen:1").value == "701.955"
        cell = _cell_child(user, "cell:held:0:0")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("-2")
        assert _cell_child(user, "tuning:gen:1").value == "701.955"

    async def test_a_held_draft_commit_materializes_a_new_held_column(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        await user.should_see(marker="cell:held:0:0")
        assert "rtt-pending" in _cell_child(user, "cell:held:0:0")._classes
        for p, v in zip(range(3), ("-1", "1", "0")):
            _cell_child(user, f"cell:held:{p}:0").set_value(v)
        _commit(user, "cell:held:2:0")
        await user.should_see(marker="held:0")
        assert "rtt-pending" not in _cell_child(user, "cell:held:0:0")._classes

    async def test_a_target_keystroke_preview_does_not_commit_until_blur(self, user: User) -> None:
        await user.open("/")
        assert _cell_child(user, "cell:vector:targets:0:0").value == "1"
        cell = _cell_child(user, "cell:vector:targets:0:0")
        UserInteraction(user, {cell}, None).trigger("focus")
        cell.set_value("2")
        assert _cell_child(user, "cell:vector:targets:1:1").value == "1"
        UserInteraction(user, {cell}, None).trigger("blur")
        await user.should_see(marker="cell:vector:targets:0:0")
        assert _cell_child(user, "cell:vector:targets:0:0").value == "2"

    async def test_a_target_cell_edit_commits_through_the_reversed_id_shape(self, user: User) -> None:
        await user.open("/")
        cell = _cell_child(user, "cell:vector:targets:0:1")
        cell.set_value("1")
        _commit(user, "cell:vector:targets:0:1")
        await user.should_see(marker="cell:vector:targets:0:1")
        assert _cell_child(user, "cell:vector:targets:0:1").value == "1"

    async def test_a_target_draft_commit_materializes_a_new_target_column(self, user: User) -> None:
        k = len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, Editor().state.domain_basis))
        await user.open("/")
        _click_glyph(user, "target_plus")
        await user.should_see(marker=f"cell:vector:targets:{k}:0")
        assert "rtt-pending" in _cell_child(user, f"cell:vector:targets:{k}:0")._classes
        for p, v in zip(range(3), ("-1", "1", "0")):
            _cell_child(user, f"cell:vector:targets:{k}:{p}").set_value(v)
        _commit(user, f"cell:vector:targets:{k}:2")
        await user.should_see(marker=f"target:{k}")
        assert "rtt-pending" not in _cell_child(user, f"cell:vector:targets:{k}:0")._classes

    async def test_an_interest_draft_keystroke_preview_does_not_materialize_early(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "interest_plus")
        await user.should_see(marker="cell:interest:0:0")
        first = _cell_child(user, "cell:interest:0:0")
        UserInteraction(user, {first}, None).trigger("focus")
        first.set_value("-1")
        assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes
        await user.should_not_see(marker="interest:0")

    async def test_a_mapping_draft_keystroke_preview_rings_nothing_from_the_value(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "gen_plus")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")
        first = _cell_child(user, "cell:mapping:2:0")
        UserInteraction(user, {first}, None).trigger("focus")
        first.set_value("0")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:comma:0:0")
        assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes

    async def test_the_mapping_matrix_is_inert_when_temperament_tiles_are_off(self, user: User) -> None:
        await user.open("/")
        assert user.find(marker="cell:mapping:0:0").elements
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        user.find(kind=ui.checkbox, content="temperament tiles").click()
        await user.should_not_see(marker="cell:mapping:0:0")
        user.find(kind=ui.checkbox, content="temperament tiles").click()
        await user.should_see(marker="cell:mapping:0:0")
        assert _cell_text(user, "cell:mapped:1:6") == "4"

    async def test_an_unfocused_grid_rings_no_cells(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        await user.should_see(marker="cell:mapped:1:6")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapped:1:6")

    async def test_wheeling_a_generator_tuning_rings_the_cells_it_moves(self, user: User) -> None:
        await user.open("/")
        cell = set(user.find(marker="tuning:gen:0").elements)
        UserInteraction(user, cell, None).trigger("mouseenter")
        UserInteraction(user, cell, None).trigger("wheel.prevent", {"deltaY": -1})
        await user.should_see(marker="retune:target:0")
        assert "rtt-preview-change" in _wrap_classes(user, "retune:target:0")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:gen:0")
        UserInteraction(user, cell, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:0")

    async def test_hovering_a_generator_tuning_sign_previews_reversing_it(self, user: User) -> None:
        await user.open("/")
        sign = set(user.find(marker="gensign:1").elements)
        UserInteraction(user, sign, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")
        UserInteraction(user, sign, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")

    async def test_hovering_a_temperament_option_previews_loading_it(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        await user.should_see(marker="preset:temperament")
        wrap = set(user.find(marker="preset:temperament").elements)
        idx = list(presets.temperament_options()).index("5:Porcupine")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:2")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:2")

    async def test_hovering_a_tuning_scheme_option_previews_reselecting(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        await user.should_see(marker="preset:tuning")
        before = _ro_value(user, "weight:target:1")
        wrap = set(user.find(marker="preset:tuning").elements)
        idx = list(presets.tuning_scheme_options(False, False, True)).index("minimax-S")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") != before
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") == before

    async def test_hovering_a_prescaler_option_previews_reselecting(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        _toggle(user, "alternative complexity")
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        await user.should_see(marker="preset:prescaler")
        before = _ro_value(user, "weight:target:1")
        wrap = set(user.find(marker="preset:prescaler").elements)
        idx = list(presets.prescaler_options(True)).index("identity")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") != before
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") == before

    async def test_hovering_a_complexity_option_previews_reselecting(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        _toggle(user, "alternative complexity")
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        await user.should_see(marker="control:complexity")
        before = _ro_value(user, "weight:target:1")
        wrap = set(user.find(marker="control:complexity").elements)
        idx = list(service.COMPLEXITY_DISPLAYS).index("sopfr")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") != before
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") == before


class TestHoveringForm:
    async def test_hovering_a_weight_slope_option_previews_reselecting(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        await user.should_see(marker="control:slope")
        before = _ro_value(user, "weight:target:1")
        wrap = set(user.find(marker="control:slope").elements)
        idx = list(service.WEIGHT_SLOPES).index("simplicity-weight")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        assert _ro_value(user, "weight:target:1") == before
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")

    async def test_hovering_a_locked_weight_slope_shows_no_preview(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        _toggle(user, "all-interval")
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="control:slope")
        wrap = set(user.find(marker="control:slope").elements)
        idx = list(service.WEIGHT_SLOPES).index("complexity-weight")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")

    async def test_hovering_the_form_canonical_option_previews_canonicalizing(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "equivalences")
        _toggle(user, "form")
        _toggle(user, "form controls")
        await user.should_see(marker="formchooser:mapping")
        await user.should_not_see(marker="cell:canon:0:2")
        wrap = set(user.find(marker="formchooser:mapping").elements)
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": 1})
        await user.should_see(marker="cell:mapping:0:2")
        assert _cell_child(user, "cell:mapping:0:2").value == "-4"
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:2"), "ringed amber vs the pre-hover grid"
        await user.should_not_see(marker="cell:canon:0:2")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        await user.should_see(marker="cell:mapping:0:2")
        assert _cell_child(user, "cell:mapping:0:2").value == "0"
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:2")

    async def test_choosing_the_form_canonical_option_commits_canonicalizing(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "form")
        _toggle(user, "form controls")
        await user.should_see(marker="formchooser:mapping")
        wrap = set(user.find(marker="formchooser:mapping").elements)
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": 1})
        _cell_child(user, "formchooser:mapping").set_value("canonical")
        await user.should_see(marker="cell:mapping:0:2")
        assert _cell_child(user, "cell:mapping:0:2").value == "-4"
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:2")
        user.find(marker="undo").click()
        await user.should_see(marker="cell:mapping:0:2")
        assert _cell_child(user, "cell:mapping:0:2").value == "0"

    async def test_hovering_a_form_away_from_canonical_leaves_the_canon_tile_gated_on_form_tiles(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "equivalences")
        _toggle(user, "form")
        _toggle(user, "form controls")
        await user.should_see(marker="formchooser:mapping")
        _cell_child(user, "formchooser:mapping").set_value("canonical")
        await user.should_see(marker="cell:mapping:0:2")
        await user.should_not_see(marker="cell:canon:0:2")
        wrap = set(user.find(marker="formchooser:mapping").elements)
        eq_idx = 1 + list(service.MAPPING_FORM_KEYS).index("equave-reduced")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": eq_idx})
        await user.should_not_see(marker="cell:canon:0:2")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:0:2")
        assert _cell_child(user, "cell:mapping:0:2").value == "0"
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:0:2")
        await user.should_not_see(marker="cell:canon:0:2")

    def test_option_hover_delegation_cancels_the_settle_timer_on_pointerdown(self) -> None:
        js = "".join(web_app._OPTION_HOVER_DELEGATION.split())
        assert "addEventListener('pointerdown'" in js, "the delegation must cancel its timer on a press"
        assert "clearTimeout(timer);" in js and ";},true)" in js, \
            "pointerdown must clearTimeout(timer) in the capture phase"
        assert "lastCid=null;lastIdx=null;},true)" in js, \
            "pointerdown must reset the dedupe so each popup session's first hover fires"

    async def test_hovering_a_target_family_reddens_the_rows_it_drops(self, user: User) -> None:
        from rtt.app import presets
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        before = _ro_value(user, "retune:target:1")
        wrap = set(user.find(marker="preset:target").elements)
        idx = list(presets.TARGET_SETS).index("OLD")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-remove" in _wrap_classes(user, "retune:target:1")
        await user.should_see(marker="retune:target:1")
        assert _ro_value(user, "retune:target:1") == before
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:1")

    async def test_hovering_a_same_count_target_family_rings_the_moved_rows_amber(self, user: User) -> None:
        from rtt.app import presets
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        num, _sel = _target_preset(user)
        num.set_value("5")
        await user.should_see(marker="retune:target:1")
        before = _ro_value(user, "retune:target:1")
        wrap = set(user.find(marker="preset:target").elements)
        idx = list(presets.TARGET_SETS).index("OLD")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-change" in _wrap_classes(user, "retune:target:1")
        assert "rtt-preview-remove" not in _wrap_classes(user, "retune:target:1")
        assert _ro_value(user, "retune:target:1") != before
        _num, sel = _target_preset(user)
        assert sel.value == "TILT", "chooser held steady, not flipped"
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-change" not in _wrap_classes(user, "retune:target:1")
        assert _ro_value(user, "retune:target:1") == before

    async def test_hovering_the_generator_minus_previews_the_dual_rank_change(self, user: User) -> None:
        await user.open("/")
        button = set(user.find(marker="gen_minus").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "tuning:gen:1")
        assert "rtt-preview-remove" in _wrap_classes(user, "cell:mapping:1:0")
        await user.should_see(marker="tuning:gen:1")
        assert "rtt-preview-change" in _wrap_classes(user, "cell:comma:0:0")
        await user.should_see(marker="cell:comma:0:1")
        assert "rtt-pending" in _wrap_classes(user, "cell:comma:0:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:gen:1")
        await user.should_not_see(marker="cell:comma:0:1")

    async def test_hovering_a_column_minus_reddens_the_removed_column(self, user: User) -> None:
        await user.open("/")
        button = set(user.find(marker="minus").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "prime:2")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:prime:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "prime:2")

    async def test_clicking_a_per_element_domain_minus_removes_that_element(self, user: User) -> None:
        await _enable(user, "nonstandard domain")
        await user.should_see(marker="element_minus:0")
        await user.should_see(marker="element_minus:2")
        await user.should_see(marker="prime:2")
        _click_glyph(user, "element_minus:1")
        await user.should_not_see(marker="prime:2")
        await user.should_not_see(marker="element_minus:2")

    async def test_clicking_the_mapping_plus_opens_a_green_draft_row_to_fill_in(self, user: User) -> None:
        await user.open("/")
        await user.should_not_see(marker="cell:mapping:2:0")
        _click_glyph(user, "gen_plus")
        await user.should_see(marker="cell:mapping:2:0")
        await user.should_see(marker="gen:pending")
        assert "rtt-pending" in _cell_child(user, "cell:mapping:2:0")._classes
        assert _cell_child(user, "cell:mapping:2:0").value == ""
        for p, v in zip(range(3), ("0", "0", "1")):
            _cell_child(user, f"cell:mapping:2:{p}").set_value(v)
        _commit(user, "cell:mapping:2:2")
        await user.should_see(marker="cell:mapping:2:0")
        assert "rtt-pending" not in _cell_child(user, "cell:mapping:2:0")._classes
        assert [_cell_child(user, f"cell:mapping:2:{p}").value for p in range(3)] == ["0", "0", "1"]

    async def test_hovering_a_temperament_of_a_different_dimensionality_reflows_the_grid(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        await user.should_see(marker="preset:temperament")
        await user.should_not_see(marker="prime:3")
        wrap = set(user.find(marker="preset:temperament").elements)
        seven = next(k for k in presets.temperament_options() if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS)
        idx = list(presets.temperament_options()).index(seven)
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        await user.should_see(marker="prime:3")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        await user.should_not_see(marker="prime:3")

    async def test_hovering_a_lower_limit_temperament_keeps_the_dropped_column_red(self, user: User) -> None:
        from rtt.app import presets
        await user.open("/")
        _toggle(user, "presets")
        await user.should_see(marker="preset:temperament")
        seven = next(k for k in presets.temperament_options()
                     if k.startswith("7:") and k in presets.TEMPERAMENT_COMMAS
                     and len(presets.TEMPERAMENT_COMMAS[k]) == 2)
        _cell_child(user, "preset:temperament").set_value(seven)
        await user.should_see(marker="prime:3")
        wrap = set(user.find(marker="preset:temperament").elements)
        five = next(k for k in presets.temperament_options()
                    if k.startswith("5:") and k in presets.TEMPERAMENT_COMMAS)
        idx = list(presets.temperament_options()).index(five)
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": idx})
        assert "rtt-preview-remove" in _wrap_classes(user, "prime:3")
        await user.should_see(marker="prime:3")
        UserInteraction(user, wrap, None).trigger("opthover", {"detail": -1})
        assert "rtt-preview-remove" not in _wrap_classes(user, "prime:3")

    async def test_hovering_the_replace_diminuator_checkbox_previews_its_reweighting(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        await user.should_see(marker="control:diminuator")
        button = set(user.find(marker="control:diminuator").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:2")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:2")

    async def test_hovering_undo_rings_what_reverting_the_last_edit_changes(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="tuning:target:1")
        button = set(user.find(marker="undo").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")

    async def test_hovering_redo_rings_what_redoing_the_undone_edit_changes(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        user.find(marker="undo").click()
        await user.should_see(marker="tuning:target:1")
        button = set(user.find(marker="redo").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")

    async def test_hovering_reset_rings_everything_snapping_back_to_defaults(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="tuning:target:1")
        button = set(user.find(marker="reset").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" in _wrap_classes(user, "tuning:target:1")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:1")

    async def test_a_disabled_history_button_shows_no_preview(self, user: User) -> None:
        await user.open("/")
        button = set(user.find(marker="undo").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-change" not in _wrap_classes(user, "tuning:target:4")
        assert "rtt-preview-remove" not in _wrap_classes(user, "tuning:target:4")
        UserInteraction(user, button, None).trigger("mouseleave")
