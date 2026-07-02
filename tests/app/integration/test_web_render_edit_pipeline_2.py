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
from _render_support import _toggle, _enable, _wrap, _marked, _cell_child, _wrap_classes, _click_glyph, _commit, _stacked_face, _ro_stacked_face, _target_preset, _preset_tooltip_text, _radio_selected, _radio_enabled


class TestChoosers:
    async def test_temperament_divider_rows_render_as_disabled_options(self, user: User) -> None:
        await _enable(user, "presets")
        select = _cell_child(user, "preset:temperament")
        option_by_value = dict(zip(select._values, select._props["options"]))
        assert option_by_value["hdr:2:5"]["disable"] is True
        assert option_by_value["hdr:3:13"]["disable"] is True
        assert "disable" not in option_by_value["13:Marvel"]

    async def test_temperament_chooser_omits_the_offlist_prompt_from_its_list(self, user: User) -> None:
        await _enable(user, "presets")
        select = _cell_child(user, "preset:temperament")
        assert "" not in select._values
        assert "-" not in select._labels

    async def test_temperament_chooser_shows_the_prompt_as_a_placeholder_when_no_preset_matches(self, user: User) -> None:
        await _enable(user, "presets")
        assert "display-value" not in _cell_child(user, "preset:temperament")._props
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="preset:temperament")
        assert _cell_child(user, "preset:temperament")._props.get("display-value") == "-"

    async def test_tuning_chooser_shows_the_prompt_as_a_placeholder_when_off_list(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        assert "display-value" not in _cell_child(user, "preset:tuning")._props
        _cell_child(user, "optimization:power").set_value("2")
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"

    async def test_tuning_chooser_shows_the_prompt_when_the_generator_tuning_is_overridden(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        both = ("preset:tuning", "preset:tuning:generators")
        assert all("display-value" not in _cell_child(user, cell_id)._props for cell_id in both)
        _cell_child(user, "tuning:generator:1").set_value("700.000")
        await user.should_see(marker="preset:tuning")
        assert all(_cell_child(user, cell_id)._props.get("display-value") == "-" for cell_id in both)

    async def test_picking_a_scheme_clears_the_manual_tuning_and_retunes(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        seed = _cell_child(user, "tuning:generator:1").value
        _cell_child(user, "tuning:generator:1").set_value("700.000")
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"
        _cell_child(user, "preset:tuning").set_value("minimax-U")
        await user.should_see(marker="preset:tuning")
        assert "display-value" not in _cell_child(user, "preset:tuning")._props
        assert _cell_child(user, "tuning:generator:1").value == seed

    async def test_prescaler_chooser_shows_the_prompt_when_a_diagonal_is_overridden(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "presets")
        await user.should_see(marker="preset:prescaler")
        assert "display-value" not in _cell_child(user, "preset:prescaler")._props
        _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
        await user.should_see(marker="preset:prescaler")
        assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"

    async def test_pretransform_mode_relabels_the_prescaler_help_live(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "presets")
        await user.should_see(marker="preset:prescaler")
        guide = next(iter(user.find(marker="caption:prescaling:primes").elements))
        assert "prescaler" in guide._props.get("data-guide-text", "")
        assert "pretransformer" not in guide._props.get("data-guide-text", "")
        assert "prescaler" in _preset_tooltip_text(user, "preset:prescaler")
        _cell_child(user, "cell:prescaling:primes:1:0").set_value("0.3")
        await user.should_see(marker="preset:prescaler")
        assert "pretransformer" in guide._props.get("data-guide-text", "")
        assert "prescaler" not in guide._props.get("data-guide-text", "")
        assert "pretransformer" in _preset_tooltip_text(user, "preset:prescaler")

    async def test_picking_a_prescaler_clears_a_manual_diagonal_override(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "presets")
        await user.should_see(marker="cell:prescaling:primes:1:1")
        seed = _cell_child(user, "cell:prescaling:primes:1:1").value
        _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
        await user.should_see(marker="preset:prescaler")
        assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"
        _cell_child(user, "preset:prescaler").set_value("log-prime")
        await user.should_see(marker="preset:prescaler")
        assert "display-value" not in _cell_child(user, "preset:prescaler")._props
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == seed

    async def test_editing_the_prescaler_wipes_then_restores_the_complexity_chooser(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "presets")
        await user.should_see(marker="control:complexity")
        assert _cell_child(user, "control:complexity").value == "lp (log-product)"
        _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
        await user.should_see(marker="control:complexity")
        assert _cell_child(user, "preset:prescaler")._props.get("display-value") == "-"
        assert _cell_child(user, "control:complexity").value == "custom"
        _cell_child(user, "preset:prescaler").set_value("log-prime")
        await user.should_see(marker="control:complexity")
        assert _cell_child(user, "control:complexity").value == "lp (log-product)", "complexity recovers"

    async def test_target_chooser_shows_the_prompt_when_an_interval_is_overridden(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="cell:vector:targets:0:0")
        num, selection = _target_preset(user)
        assert "display-value" not in selection._props
        assert num.value not in (None, "-")
        _cell_child(user, "cell:vector:targets:0:0").set_value("3")
        _commit(user, "cell:vector:targets:0:0")
        await user.should_see(marker="preset:target")
        num, selection = _target_preset(user)
        assert selection._props.get("display-value") == "-"
        assert num.value == "-"

    async def test_selecting_a_target_family_clears_an_interval_override(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="cell:vector:targets:0:0")
        original = _cell_child(user, "cell:vector:targets:0:0").value
        _cell_child(user, "cell:vector:targets:0:0").set_value("3")
        _commit(user, "cell:vector:targets:0:0")
        await user.should_see(marker="preset:target")
        _, selection = _target_preset(user)
        assert selection._props.get("display-value") == "-"
        selection.set_value("TILT")
        await user.should_see(marker="cell:vector:targets:0:0")
        _, selection = _target_preset(user)
        assert "display-value" not in selection._props
        assert _cell_child(user, "cell:vector:targets:0:0").value == original

    async def test_weighting_complexity_chooser_is_disabled_when_lp_only(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        await user.should_see(marker="control:complexity")
        chooser = _cell_child(user, "control:complexity")
        assert not chooser.enabled
        assert chooser.value == "lp (log-product)"
        assert "rtt-caption-disabled" in _cell_child(user, "caption:complexity")._classes

    async def test_alt_complexity_enables_and_widens_the_complexity_chooser(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        await user.should_see(marker="control:complexity")
        assert not _cell_child(user, "control:complexity").enabled
        assert list(_cell_child(user, "control:complexity").options) == ["lp (log-product)"]
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="control:complexity")
        widened = _cell_child(user, "control:complexity")
        assert widened.enabled
        assert set(widened.options) == set(service.COMPLEXITY_DISPLAYS.values()) | {"custom"}
        assert widened.value == "lp (log-product)"

    async def test_typing_the_q_field_drives_the_complexity_norm(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="control:dual")
        assert _cell_child(user, "control:q").value == "1"
        assert _marked(user, "control:dual:main").text == "∞"
        _cell_child(user, "control:q").set_value("2")
        await user.should_see(marker="control:dual")
        assert _cell_child(user, "control:q").value == "2"
        assert _marked(user, "control:dual:main").text == "2"

    async def test_q_norm_power_is_read_only_until_alt_complexity(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(marker="control:slope:simplicity-weight").click()
        await user.should_see(marker="control:q")
        assert "rtt-cell-input" not in _wrap_classes(user, "control:q")
        assert _marked(user, "control:q:main").text == "1"
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="control:q")
        assert "rtt-cell-input" in _wrap_classes(user, "control:q")
        assert _cell_child(user, "control:q").value == "1"

    async def test_weight_slope_chooser_mirrors_a_scheme_change(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _toggle(user, "presets")
        await user.should_see(marker="control:slope")
        await user.should_see(marker="preset:tuning")
        before = _radio_selected(user, "control:slope", service.WEIGHT_SLOPES)
        _cell_child(user, "preset:tuning").set_value("minimax-C")
        await user.should_see(marker="control:slope")
        assert _radio_selected(user, "control:slope", service.WEIGHT_SLOPES) != before

    async def test_changing_the_weight_slope_renames_the_established_scheme_chooser(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        await user.should_see(marker="control:slope")
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning").value == "minimax-U"
        user.find(marker="control:slope:complexity-weight").click()
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning").value == "minimax-C", "tracked the slope, not '-'"
        user.find(marker="control:slope:simplicity-weight").click()
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning").value == "minimax-S"

    async def test_custom_weights_toggle_makes_the_weight_row_editable_and_retunes(self, user: User) -> None:
        await user.open("/")
        slider = next(iter(user.find(marker="chapterslider").elements))
        slider.set_value(show_settings.CHAPTER_STAR)
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="custom weights").click()
        await user.should_see(marker="weight:target:0")
        assert "rtt-cell-input" in _wrap_classes(user, "weight:target:0")
        assert not _radio_enabled(user, "control:slope")
        _cell_child(user, "weight:target:0").set_value("3")
        await user.should_see(marker="weight:target:0")
        assert _cell_child(user, "weight:target:0").value == service.cents(3.0)

    async def test_custom_weights_stays_checkable_under_all_interval_so_select_all_works(self, user: User) -> None:
        def box(key):
            return next(iter(user.find(marker=f"showbox:{key}").elements))
        await user.open("/")
        slider = next(iter(user.find(marker="chapterslider").elements))
        slider.set_value(show_settings.CHAPTER_STAR)
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        assert "disable" not in box("all_interval")._props and "disable" not in box("custom_weights")._props
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        assert "disable" not in box("custom_weights")._props, "custom weights is NOT greyed under all-interval"
        user.find(kind=ui.checkbox, content="custom weights").click()
        assert box("custom_weights").value is True

    async def test_all_interval_greys_and_locks_the_weight_slope_chooser(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        await user.should_see(marker="control:slope")
        assert _radio_enabled(user, "control:slope")
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="control:slope")
        assert not _radio_enabled(user, "control:slope"), \
            "locking fades the whole radio sub-box — including the 'damage weight slope' caption riding inside it"
        assert _radio_selected(user, "control:slope", service.WEIGHT_SLOPES) == "simplicity-weight"

    async def test_range_mode_selector_highlights_the_live_mode(self, user: User) -> None:
        await _enable(user, "tuning ranges")
        await user.should_see(marker="rangemode:tuning:generators")
        wrap = next(iter(user.find(marker="rangemode:tuning:generators").elements))
        on = [c for c in wrap.default_slot.children if "rtt-range-option-on" in c._classes]
        assert len(on) == 1

    async def test_optimization_renders_the_mean_damage_and_power(self, user: User) -> None:
        await _enable(user, "optimization")
        for marker in ("optimization:mean_damage", "optimization:mean_damage:symbol",
                       "optimization:power", "optimization:power:symbol", "optimization:power:caption"):
            await user.should_see(marker=marker)
        await user.should_not_see(marker="optimization:button")

    async def test_minimax_power_stacks_a_max_annotation_below_infinity(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        main, sub = _stacked_face(user, "optimization:power")
        assert (main.text, sub.text) == ("∞", "(max)")
        _cell_child(user, "optimization:power").set_value("2")
        main, sub = _stacked_face(user, "optimization:power")
        assert (main.text, sub.text) == ("2", "")

    async def test_all_interval_renders_the_locked_power_as_a_read_only_value(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")
        edit_main, edit_sub = _stacked_face(user, "optimization:power")
        assert (edit_main.text, edit_sub.text) == ("∞", "(max)")
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="optimization:power")
        assert "rtt-cell-input" not in _wrap_classes(user, "optimization:power")
        main, sub = _ro_stacked_face(user, "optimization:power")
        assert (main.text, sub.text) == ("∞", "(max)")
        _cell_child(user, "control:all_interval").set_value(False)
        await user.should_see(marker="optimization:power")
        assert "rtt-cell-input" in _wrap_classes(user, "optimization:power")

    async def test_mean_damage_help_tracks_the_all_interval_mode(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()

        def help_text() -> str:
            return _wrap(user, "optimization:mean_damage")._props.get("data-zoomhelp", "")

        assert "⟪𝐝⟫ₚ" in help_text()
        assert "retuning magnitude" not in help_text().lower()

        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)

        assert "retuning magnitude" in help_text().lower()
        assert "⟪𝐝⟫ₚ" not in help_text()

    async def test_all_interval_disables_the_target_chooser_and_falls_back_to_dash(self, user: User) -> None:
        await _enable(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        num, selection = _target_preset(user)
        assert selection.enabled and "display-value" not in selection._props
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="preset:target")
        num, selection = _target_preset(user)
        assert not selection.enabled and not num.enabled
        assert selection._props.get("display-value") == "-" and num.value == "-"
        _cell_child(user, "control:all_interval").set_value(False)
        await user.should_see(marker="preset:target")
        num, selection = _target_preset(user)
        assert selection.enabled and "display-value" not in selection._props

    async def test_hovering_the_all_interval_checkbox_previews_collapsing_to_the_primes(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        await user.should_see(marker="control:all_interval")
        button = set(user.find(marker="control:all_interval").elements)
        UserInteraction(user, button, None).trigger("mouseenter")
        assert "rtt-preview-remove" in _wrap_classes(user, "target:2")
        assert "rtt-preview-change" in _wrap_classes(user, "weight:target:1")
        await user.should_see(marker="target:2")
        UserInteraction(user, button, None).trigger("mouseleave")
        assert "rtt-preview-remove" not in _wrap_classes(user, "target:2")
        assert "rtt-preview-change" not in _wrap_classes(user, "weight:target:1")


class TestHeldAndInterestCommit:
    async def test_optimization_renders_the_held_column_and_its_add_control(self, user: User) -> None:
        await _enable(user, "optimization")
        await user.should_see(marker="header:held")
        await user.should_see(marker="held_plus")

    async def test_a_held_interval_retunes_the_grid_immediately(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        _toggle(user, "optimization")
        assert _cell_child(user, "preset:tuning").value == "minimax-U"
        assert _cell_child(user, "tuning:generator:1").value != "701.955"
        _click_glyph(user, "held_plus")
        await user.should_see(marker="cell:held:0:0")
        _cell_child(user, "cell:held:0:0").set_value("-1")
        _cell_child(user, "cell:held:1:0").set_value("1")
        _cell_child(user, "cell:held:2:0").set_value("0")
        _commit(user, "cell:held:2:0")
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "cell:held:0:0").value == "-1"
        assert _cell_child(user, "tuning:generator:1").value == "701.955"
        assert _cell_child(user, "preset:tuning")._props.get("display-value") == "-"

    async def test_adding_an_interval_of_interest_commits_when_filled(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "interest_plus")
        await user.should_see(marker="cell:interest:0:0")
        assert "rtt-pending" in _cell_child(user, "cell:interest:0:0")._classes
        _cell_child(user, "cell:interest:0:0").set_value("-1")
        _cell_child(user, "cell:interest:1:0").set_value("1")
        _cell_child(user, "cell:interest:2:0").set_value("0")
        _commit(user, "cell:interest:2:0")
        await user.should_see(marker="interest:0")
        assert _cell_child(user, "cell:interest:0:0").value == "-1"

    async def test_adding_a_target_commits_when_filled(self, user: User) -> None:
        k = len(service.target_interval_set(service.DEFAULT_TARGET_SPEC, Editor().state.domain_basis))
        await user.open("/")
        _click_glyph(user, "target_plus")
        await user.should_see(marker=f"cell:vector:targets:{k}:0")
        assert "rtt-pending" in _cell_child(user, f"cell:vector:targets:{k}:0")._classes
        _cell_child(user, f"cell:vector:targets:{k}:0").set_value("-1")
        _cell_child(user, f"cell:vector:targets:{k}:1").set_value("1")
        _cell_child(user, f"cell:vector:targets:{k}:2").set_value("0")
        _commit(user, f"cell:vector:targets:{k}:2")
        await user.should_see(marker=f"target:{k}")
        assert _cell_child(user, f"cell:vector:targets:{k}:0").value == "-1"
