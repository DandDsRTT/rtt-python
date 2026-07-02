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
from _render_support import (
    _toggle,
    _enable,
    _pick_terminology,
    _terminology_opt_selected,
    _scheme_select,
    _op_classes,
    _cell_left,
    _part_classes,
    _row_classes,
    _marked,
    _approx_markers,
    _cell_child,
    _ratio_value,
    _wrap_classes,
    _ro_ratio_face,
    _click_glyph,
    _commit,
    _cell_text,
    _live,
    _live_assets,
    _GENERAL_KEY_BY_LABEL,
    _FEATURE_CELLS,
)


class TestFeatureRenderBranches:
    async def test_state_query_param_loads_a_shared_document(self, user: User) -> None:
        live = _live()
        document = Editor().serialize()
        document["settings"]["counts"] = not document["settings"]["counts"]
        token = _live_assets()._encode_state(document)
        await user.open(f"/?{_live_assets()._STATE_PARAM}={token}")
        stored = _live_assets()._doc_store()[_live_assets()._STORE_KEY]
        assert stored["settings"]["counts"] == document["settings"]["counts"]

    async def test_the_approach_radio_carries_its_caption_inside_the_subbox(self, user: User) -> None:
        ed = Editor()
        assert ed.try_edit_mapping_text("2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}")
        token = _live_assets()._encode_state(ed.serialize())
        await user.open(f"/?{_live_assets()._STATE_PARAM}={token}")
        await user.should_see(content="nonprime domain tuning approach")

    async def test_a_corrupt_state_query_param_falls_back_to_defaults(
        self, user: User, caplog
    ) -> None:
        with caplog.at_level(logging.CRITICAL, logger="rtt.app.app"):
            await user.open(f"/?{page_assets._STATE_PARAM}=not-a-real-token")
        await user.should_see("quantities")

    async def test_a_stacked_fraction_cell_publishes_its_value_uncorrupted(
        self, user: User
    ) -> None:
        document = Editor().serialize()
        document["settings"]["projection"] = True
        token = _live_assets()._encode_state(document)
        await user.open(f"/?{_live_assets()._STATE_PARAM}={token}")
        cell = next(iter(user.find(marker="cell:projection:2:1").elements))
        assert cell._props.get("data-value") == "1/4", (
            "the projection matrix's 1/4 entry renders as a stacked num-over-den pair whose textContent "
            "concatenates to '14'; data-value must carry the model value verbatim so the overlay reads 1/4"
        )

    _GENERAL_KEY_BY_LABEL = {
        label: key for key, label, _d in dict(show_settings.SHOW_GROUPS)["general"]
    }

    @pytest.mark.parametrize("label, cell_id", _FEATURE_CELLS)
    async def test_enabling_a_feature_renders_its_cell(
        self, user: User, label: str, cell_id: str
    ) -> None:
        await _enable(user, label)
        await user.should_see(marker=cell_id)

    async def test_guide_settings_box_carries_the_terminology_radio(self, user: User) -> None:
        await user.open("/")
        await user.should_see(content="guide settings")
        await user.should_see(content="terminology")
        assert _terminology_opt_selected(user, "dd")

    async def test_wiki_mode_swaps_grid_terms_to_wiki_live(self, user: User) -> None:
        await user.open("/")
        assert user.find(content="interval vectors").elements
        _pick_terminology(user, "wiki")
        await user.should_see(content="monzos")

    async def test_both_mode_shows_dd_terms_with_the_wiki_name_in_parentheses(
        self, user: User
    ) -> None:
        await user.open("/")
        _pick_terminology(user, "both")
        await user.should_see(content="interval vectors (monzos)")

    async def test_undo_of_a_terminology_change_restores_dd_terms(self, user: User) -> None:
        await user.open("/")
        _pick_terminology(user, "wiki")
        await user.should_see(content="monzos")
        user.find(marker="undo").click()
        await user.should_see(content="interval vectors")

    async def test_all_interval_scheme_dropdown_relabels_to_wiki_names_in_wiki_mode(
        self, user: User
    ) -> None:
        await user.open("/")
        user.find(marker="showpart:presets").click()
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        assert _scheme_select(user).options["minimax-S"] == "minimax-S"
        _pick_terminology(user, "wiki")
        assert _scheme_select(user).options["minimax-S"] == "TOP"

    async def test_enabling_math_expressions_renders_the_closed_form(self, user: User) -> None:
        await _enable(user, "math expressions")
        await user.should_see(content="log₂")

    async def test_enabling_generator_detempering_renders_the_column(self, user: User) -> None:
        await _enable(user, "generator detempering")
        await user.should_see(marker="header:detempering")

    async def test_generators_column_collapses_a_whole_ratio_but_keeps_its_approx_tilde(
        self, user: User
    ) -> None:
        await user.open("/")
        num, _den, collapsed = _ro_ratio_face(user, "quantities_generator:0")
        assert collapsed and num == "2"
        assert _approx_markers(user, "quantities_generator:0")
        _n, _d, generator_collapsed = _ro_ratio_face(user, "quantities_generator:1")
        assert not generator_collapsed and _approx_markers(user, "quantities_generator:1")
        _toggle(user, "symbols")
        num2, _d2, still = _ro_ratio_face(user, "quantities_generator:0")
        assert still and num2 == "2" and _approx_markers(user, "quantities_generator:0")

    async def test_detempering_column_collapses_a_whole_ratio_to_a_bare_integer(
        self, user: User
    ) -> None:
        await _enable(user, "generator detempering")
        await user.should_see(marker="detempering:0")
        num, _den, collapsed = _ro_ratio_face(user, "detempering:0")
        assert collapsed and num == "2"
        assert not _approx_markers(user, "detempering:0")
        _n, _d, fifth_collapsed = _ro_ratio_face(user, "detempering:1")
        assert not fifth_collapsed

    async def test_enabling_projection_renders_the_box(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="label:projection")
        await user.should_see(marker="cell:projection:2:1")

    async def test_projection_renders_the_projected_column_tiles(self, user: User) -> None:
        await _enable(user, "projection")
        _toggle(user, "generator detempering")
        await user.should_see(marker="cell:projection_detempering:1:2")
        assert _cell_text(user, "cell:projection_detempering:1:2") == "1/4"
        assert _marked(user, "cell:projection_detempering:1:2:numerator").text == "1"
        assert _marked(user, "cell:projection_detempering:1:2:denominator").text == "4"
        await user.should_see(marker="cell:projection_targets:0:0")

    async def test_projection_renders_the_embedding_and_its_choosers(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="projection").click()
        await user.should_see(marker="cell:embed:2:1")
        await user.should_see(marker="preset:projection")
        await user.should_see(marker="preset:projection:generators")
        assert _cell_child(user, "preset:projection").value == "1/4-comma", (
            "the default meantone (TILT minimax-U) IS quarter-comma — it holds 2/1 and 5/4 — so the choosers # read 1/4-comma and P/G fill in (the 5^(1/4) entries), NOT dashes"
        )
        assert _cell_text(user, "cell:projection:2:1") == "1/4"
        assert _cell_text(user, "cell:embed:2:1") == "1/4"
        _cell_child(user, "preset:projection").set_value("1/3-comma")
        await user.should_see(marker="cell:embed:2:1")
        assert _cell_text(user, "cell:projection:2:1") == "1/3"
        assert _cell_text(user, "cell:embed:2:1") == "1/3"
        assert _cell_child(user, "preset:projection:generators").value == "1/3-comma"
        assert _cell_child(user, "tuning:generator:1").value == "694.786"

    async def test_projection_choosers_show_a_dash_when_the_tuning_matches_no_named_projection(
        self,
        user: User,
    ) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="projection").click()
        await user.should_see(marker="preset:projection")
        assert "display-value" not in _cell_child(user, "preset:projection")._props
        _cell_child(user, "tuning:generator:1").set_value("690")
        await user.should_see(marker="preset:projection")
        assert _cell_child(user, "preset:projection")._props.get("display-value") == "-"
        assert _cell_child(user, "preset:projection:generators")._props.get("display-value") == "-"

    async def test_back_to_scheme_button_reverts_a_picked_projection(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="projection").click()
        await user.should_see(marker="scheme:primes")
        await user.should_see(marker="target:0")
        _cell_child(user, "preset:projection").set_value("1/3-comma")
        await user.should_not_see(marker="target:0")
        _click_glyph(user, "scheme:primes")
        await user.should_see(marker="target:0")
        assert _cell_child(user, "preset:projection").value == "1/4-comma"

    async def test_back_to_scheme_button_rides_the_projection_preset(
        self, user: User
    ) -> None:
        await _enable(user, "projection")
        await user.should_not_see(marker="scheme:primes")
        await user.should_not_see(marker="preset:projection")
        _toggle(user, "presets")
        await user.should_see(marker="preset:projection")
        await user.should_see(marker="scheme:primes")

    async def test_editing_the_unchanged_basis_retunes(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:1")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "cell:unchanged:0:1").set_value("1")
        _cell_child(user, "cell:unchanged:1:1").set_value("1")
        _cell_child(user, "cell:unchanged:2:1").set_value("-1")
        _commit(user, "cell:unchanged:2:1")
        assert _cell_child(user, "tuning:generator:1").value == "694.786"

    async def test_editing_the_unchanged_ratio_retunes(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="unchanged:1")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "unchanged:1").set_value("6/5")
        _commit(user, "unchanged:1")
        assert _cell_child(user, "tuning:generator:1").value == "694.786"

    async def test_editing_the_generator_embedding_retunes(self, user: User) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:generators")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "plain_text:projection:generators").set_value("{[1 0 0⟩[1/3 -1/3 1/3⟩]")
        _commit(user, "plain_text:projection:generators")
        assert _cell_child(user, "tuning:generator:1").value == "694.786"

    async def test_editing_the_projection_matrix_retunes(self, user: User) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:primes")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "plain_text:projection:primes").set_value(
            "[⟨1 4/3 4/3]⟨0 -1/3 -4/3]⟨0 1/3 4/3]⟩"
        )
        _commit(user, "plain_text:projection:primes")
        assert _cell_child(user, "tuning:generator:1").value == "694.786"

    async def test_clicking_reduce_folds_the_interval_into_one_equave(self, user: User) -> None:
        await user.open("/")
        assert "rtt-operation-disabled" not in _op_classes(user, "target:4:reduce")
        UserInteraction(user, set(user.find(marker="target:4:reduce").elements), None).trigger(
            "click"
        )
        assert _cell_child(user, "target:4").value == "5"
        assert "rtt-operation-disabled" in _op_classes(user, "target:4:reduce")

    async def test_clicking_reciprocate_flips_the_interval(self, user: User) -> None:
        await user.open("/")
        UserInteraction(user, set(user.find(marker="target:2:reciprocate").elements), None).trigger(
            "click"
        )
        assert _cell_child(user, "target:2").value == "2"

    async def test_clicking_reciprocate_on_a_comma_flips_its_sign(self, user: User) -> None:
        await user.open("/")
        assert _cell_child(user, "comma:0").value == "80"
        UserInteraction(user, set(user.find(marker="comma:0:reciprocate").elements), None).trigger(
            "click"
        )
        assert _cell_child(user, "comma:0").value == "81"

    async def test_editable_domain_basis_elements_get_the_buttons(self, user: User) -> None:
        await user.open("/")
        slider = next(iter(user.find(marker="chapterslider").elements))
        slider.set_value(show_settings.CHAPTER_STAR)
        _toggle(user, "optimization")
        _toggle(user, "nonstandard domain")
        await user.should_see(marker="prime:1:reduce")
        assert "rtt-operation-disabled" not in _op_classes(user, "prime:1:reduce")
        UserInteraction(user, set(user.find(marker="prime:1:reduce").elements), None).trigger(
            "click"
        )
        assert "rtt-operation-disabled" in _op_classes(user, "prime:1:reduce")


class TestProjectionPlainText:
    async def test_a_projection_plain_text_edit_is_unmolested_until_submit(
        self, user: User
    ) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:primes")
        _cell_child(user, "plain_text:projection:primes").set_value("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩")
        assert (
            "rtt-plain-text-error" not in _cell_child(user, "plain_text:projection:primes").classes
        )
        assert _cell_child(user, "tuning:generator:1").value == "696.578", "not retuned"
        _commit(user, "plain_text:projection:primes")
        await user.should_see("isn't a valid projection")
        assert "rtt-plain-text-error" in _cell_child(user, "plain_text:projection:primes").classes

    async def test_an_invalid_projection_plain_text_toasts_and_reddens(self, user: User) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:primes")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "plain_text:projection:primes").set_value("[⟨2 0 0]⟨0 1 0]⟨0 0 1]⟩")
        _commit(user, "plain_text:projection:primes")
        await user.should_see("isn't a valid projection")
        assert "rtt-plain-text-error" in _cell_child(user, "plain_text:projection:primes").classes
        assert _cell_child(user, "tuning:generator:1").value == "696.578"

    async def test_an_invalid_embedding_plain_text_toasts_and_reddens(self, user: User) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:generators")
        assert _cell_child(user, "tuning:generator:1").value == "696.578"
        _cell_child(user, "plain_text:projection:generators").set_value("{[0 0 0⟩[0 0 1/4⟩]")
        _commit(user, "plain_text:projection:generators")
        await user.should_see("isn't a valid embedding")
        assert (
            "rtt-plain-text-error" in _cell_child(user, "plain_text:projection:generators").classes
        )
        assert _cell_child(user, "tuning:generator:1").value == "696.578"

    async def test_an_unparseable_projection_plain_text_reddens_without_a_toast(
        self, user: User
    ) -> None:
        await _enable(user, "projection")
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:projection:primes")
        _cell_child(user, "plain_text:projection:primes").set_value("not a matrix")
        _commit(user, "plain_text:projection:primes")
        assert "rtt-plain-text-error" in _cell_child(user, "plain_text:projection:primes").classes
        assert _cell_child(user, "tuning:generator:1").value == "696.578"

    async def test_projection_renders_the_consolidated_v_and_scaling_factors(
        self, user: User
    ) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="label:scaling_factors")
        await user.should_see(marker="cell:scaling:u0")
        await user.should_see(marker="cell:unchanged:0:0")
        await user.should_see(marker="cell:mapped_unchanged:1:1")

    async def test_optimization_with_charts_renders_the_damage_indicator(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "charts")
        user.find(kind=ui.checkbox, content="optimization").click()
        await user.should_see(marker="chart:damage:targets")

    async def test_enabling_all_interval_renders_the_target_controls_checkbox(
        self, user: User
    ) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        await user.should_see(marker="control:all_interval")

    async def test_off_diagonal_pretransformer_edit_keeps_the_all_interval_weight_a_list(
        self, user: User
    ) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="cell:prescaling:primes:1:0")
        await user.should_see(marker="weight:target:0")
        _cell_child(user, "cell:prescaling:primes:1:0").set_value("0.3")
        await user.should_see(marker="weight:target:0")
        await user.should_not_see(marker="cell:weight:targets:0:0")

    async def test_dragging_a_target_onto_the_held_columns_gridline_moves_it_in(
        self, user: User
    ) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        await user.should_see(marker="grip:held:add")
        await user.should_not_see(marker="grip:held:0")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:held:add").elements), None).trigger(
            "drop.prevent"
        )
        await user.should_see(marker="grip:held:0")

    async def test_hovering_a_reorder_target_previews_the_move_then_reverts(
        self, user: User
    ) -> None:
        await user.open("/")
        x0, x2 = _cell_left(user, "target:0"), _cell_left(user, "target:2")
        assert x0 < x2
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger(
            "dragenter.prevent"
        )
        assert _cell_left(user, "target:0") > _cell_left(user, "target:2")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragend"
        )
        assert _cell_left(user, "target:0") == x0

    async def test_dropping_after_a_preview_commits_the_move(self, user: User) -> None:
        await user.open("/")
        x0 = _cell_left(user, "target:0")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger(
            "dragenter.prevent"
        )
        UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger(
            "drop.prevent"
        )
        assert _cell_left(user, "target:0") > _cell_left(user, "target:2")
        assert _cell_left(user, "target:0") != x0

    async def test_a_within_list_reorder_preview_rings_nothing(self, user: User) -> None:
        await user.open("/")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:targets:2").elements), None).trigger(
            "dragenter.prevent"
        )
        assert _cell_left(user, "target:0") > _cell_left(user, "target:2")
        assert "rtt-preview-change" not in _wrap_classes(user, "target:0")
        assert "rtt-preview-change" not in _wrap_classes(user, "target:1")

    async def test_dragging_across_lists_rings_the_changes_it_will_make(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        await user.should_see(marker="grip:held:add")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:held:add").elements), None).trigger(
            "dragenter.prevent"
        )
        assert "rtt-preview-change" in _wrap_classes(user, "held:0")
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragend"
        )
        await user.should_not_see(marker="held:0")

    async def test_editing_a_ratio_after_a_reorder_edits_the_column_it_heads(
        self, user: User
    ) -> None:
        await user.open("/")
        assert _ratio_value(user, "target:0") == "2"
        assert _ratio_value(user, "target:1") == "3"
        UserInteraction(user, set(user.find(marker="grip:targets:0").elements), None).trigger(
            "dragstart"
        )
        UserInteraction(user, set(user.find(marker="grip:targets:1").elements), None).trigger(
            "drop.prevent"
        )
        await user.should_see(marker="target:1")
        _cell_child(user, "target:1").set_value("9/8")
        _commit(user, "target:1")
        await user.should_see(marker="target:1")
        assert _ratio_value(user, "target:1") == "9/8"
        assert _ratio_value(user, "target:0") == "2"

    async def test_enabling_colorization_keeps_the_board_rendering(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="colorization").click()
        await user.should_see(marker="cell:mapping:0:0")

    async def test_edge_washes_also_render_into_the_frozen_panes(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="colorization").click()
        await user.should_see(marker="wash:temperament:counts:generators")
        await user.should_see(marker="wash:temperament:counts:generators#col")
        await user.should_see(marker="wash:temperament:mapping:quantities#row")

    async def test_settings_panel_renders_disclosure_nesting(
        self, user: User
    ) -> None:
        await user.open("/")
        for key in show_settings.GROUPING_PARENTS:
            assert "rtt-grouping-parent" in _row_classes(user, key)
            assert _marked(user, f"groupfold:{key}", required=False) is not None
        assert "rtt-nest-1" in _row_classes(user, "optimization")
        assert "rtt-grouping-parent" not in _row_classes(user, "counts")
        assert _marked(user, "groupfold:counts", required=False) is None

    async def test_dummy_tile_parts_reflect_and_drive_the_live_show_state(self, user: User) -> None:
        await user.open("/")
        user.find(marker="showpart:symbols").click()
        assert "rtt-part-on" in _part_classes(user, "names")
        assert "rtt-part-on" in _part_classes(user, "gridded_values")
        assert "rtt-part-off" in _part_classes(user, "symbols")
        assert "rtt-part-inert" not in _part_classes(user, "equivalences")
        assert "rtt-part-on" in _part_classes(user, "mnemonics")
        assert "rtt-mnem-underline" not in _part_classes(user, "mnemonics")
        user.find(marker="showpart:equivalences").click()
        assert "rtt-part-on" in _part_classes(user, "equivalences")
        assert "rtt-part-on" in _part_classes(user, "symbols")
        user.find(marker="showpart:gridded_values").click()
        assert "rtt-part-off" in _part_classes(user, "gridded_values")
        assert "rtt-part-inert" in _part_classes(user, "math_expressions")
        assert "rtt-part-inert" in _part_classes(user, "quantities")
        user.find(marker="showpart:gridded_values").click()
        user.find(marker="showpart:mnemonics").click()
        assert "rtt-mnem-underline" in _part_classes(user, "mnemonics")
        user.find(marker="showpart:names").click()
        assert "rtt-part-off" in _part_classes(user, "names")
        assert "rtt-mnem-underline" not in _part_classes(user, "mnemonics")
        assert "rtt-part-inert" not in _part_classes(user, "mnemonics")
        user.find(marker="showpart:mnemonics").click()
        assert "rtt-part-on" in _part_classes(user, "names")
        assert "rtt-mnem-underline" in _part_classes(user, "mnemonics")

    async def test_sliding_the_chapter_down_disables_the_advanced_layers_in_the_grid(
        self, user: User
    ) -> None:
        await user.open("/")
        slider = next(iter(user.find(marker="chapterslider").elements))
        slider.set_value(show_settings.CHAPTER_STAR)
        next(iter(user.find(marker="sectionall:general").elements)).set_value(True)
        next(iter(user.find(marker="sectionall:app features").elements)).set_value(True)
        await user.should_see(marker="units:mapping:primes")
        slider.set_value(2)
        await user.should_not_see(marker="units:mapping:primes")
        assert next(iter(user.find(marker="chapterreading").elements)).text == "2: Mappings"

    async def test_reset_returns_to_the_simple_chapter_two_beginning(self, user: User) -> None:
        await user.open("/")
        slider = next(iter(user.find(marker="chapterslider").elements))
        slider.set_value(show_settings.CHAPTER_STAR)
        assert slider.value == show_settings.CHAPTER_STAR
        user.find(marker="reset").click()
        assert slider.value == show_settings.CHAPTER_MIN, "reset returns to the simple chapter-2 # beginning the tour starts from, not the fuller chapter-4 view"
        assert next(iter(user.find(marker="chapterreading").elements)).text == "2: Mappings"

    async def test_toggling_gridded_values_off_at_runtime_removes_the_grid_value_cells(
        self, user: User
    ) -> None:
        await user.open("/")
        await user.should_see(marker="prime:0")
        await user.should_see(marker="target:0")
        user.find(marker="showpart:gridded_values").click()
        await user.should_not_see(marker="prime:0")
        await user.should_not_see(marker="target:0")
        user.find(marker="showpart:gridded_values").click()
        await user.should_see(marker="prime:0")

    async def test_quantities_off_at_runtime_does_not_strand_a_tilde_on_blanked_generator_ratios(
        self, user: User
    ) -> None:
        await user.open("/")
        assert _approx_markers(user, "generator:0")
        assert _approx_markers(user, "quantities_generator:0")
        user.find(marker="showpart:quantities").click()
        assert not _approx_markers(user, "generator:0")
        assert not _approx_markers(user, "quantities_generator:0")
        user.find(marker="showpart:quantities").click()
        assert _approx_markers(user, "generator:0")
