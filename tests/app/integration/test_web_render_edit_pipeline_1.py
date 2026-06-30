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
from _render_support import _toggle, _enable, _marked, _cell_child, _dec_mode, _frac_inputs, _ratio_value, _wrap_classes, _click_glyph, _commit, _cell_text, _stacked_face, _ro_stacked_face, _dec_inputs, _generator_tuning_face, _ratio_face, _target_preset


class TestCellEditPipeline:
    async def test_single_option_tuning_chooser_is_a_disabled_dropdown(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        await user.should_see(marker="preset:tuning")
        tuning = _cell_child(user, "preset:tuning")
        assert not tuning.enabled
        assert tuning.value == "minimax-U"
        assert "rtt-caption-disabled" in _cell_child(user, "block:preset:tuning:label")._classes

    async def test_checking_all_interval_drops_the_T_prefix_from_the_scheme_chooser(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "presets")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        assert _cell_child(user, "preset:tuning").options["minimax-S"] == "T minimax-S"
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="preset:tuning")
        assert _cell_child(user, "preset:tuning").options["minimax-S"] == "minimax-S"

    async def test_editing_a_mapping_cell_updates_the_mapped_list(self, user: User) -> None:
        await user.open("/")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"

    async def test_editing_a_generator_tuning_cell_applies_an_override(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "tuning:generator:1").set_value("700.000")
        await user.should_see(marker="tuning:generator:1")
        assert _cell_child(user, "tuning:generator:1").value == "700.000"

    async def test_scrolling_a_generator_tuning_cell_nudges_it_by_a_thousandth_cent(self, user: User) -> None:
        await user.open("/")
        before = float(_cell_child(user, "tuning:generator:1").value)
        user.find(marker="tuning:generator:1").trigger("wheel.prevent", {"deltaY": -100})
        await user.should_see(marker="tuning:generator:1")
        assert round(float(_cell_child(user, "tuning:generator:1").value) - before, 3) == 0.001
        user.find(marker="tuning:generator:1").trigger("wheel.prevent", {"deltaY": 100})
        await user.should_see(marker="tuning:generator:1")
        assert round(float(_cell_child(user, "tuning:generator:1").value) - before, 3) == 0.0

    async def test_scrolling_an_integer_cell_steps_it_by_one(self, user: User) -> None:
        await user.open("/")
        before = int(_cell_child(user, "cell:mapping:1:2").value)
        user.find(marker="cell:mapping:1:2").trigger("wheel", {"deltaY": -100})
        await user.should_see(marker="cell:mapping:0:0")
        assert int(_cell_child(user, "cell:mapping:1:2").value) == before + 1
        user.find(marker="cell:mapping:1:2").trigger("wheel", {"deltaY": 100})
        await user.should_see(marker="cell:mapping:0:0")
        assert int(_cell_child(user, "cell:mapping:1:2").value) == before

    async def test_the_integer_wheel_step_is_generic_over_cell_kinds(self, user: User) -> None:
        await user.open("/")
        before = int(_cell_child(user, "cell:comma:0:0").value)
        user.find(marker="cell:comma:0:0").trigger("wheel", {"deltaY": -50})
        await user.should_see(marker="cell:comma:0:0")
        assert int(_cell_child(user, "cell:comma:0:0").value) == before + 1

    async def test_scrolling_the_optimization_power_steps_a_finite_power_and_leaves_infinity(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="optimization:power")
        assert _cell_child(user, "optimization:power").value == "∞"
        user.find(marker="optimization:power").trigger("wheel", {"deltaY": -100})
        await user.should_see(marker="optimization:power")
        assert _cell_child(user, "optimization:power").value == "∞", "unchanged — you type ∞, not scroll to it"
        _cell_child(user, "optimization:power").set_value("2")
        await user.should_see(marker="optimization:power")
        user.find(marker="optimization:power").trigger("wheel", {"deltaY": -100})
        await user.should_see(marker="optimization:power")
        assert _cell_child(user, "optimization:power").value == "3"

    async def test_scrolling_a_prescaler_weight_nudges_it_by_a_thousandth(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="cell:prescaling:primes:1:1")
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"
        user.find(marker="cell:prescaling:primes:1:1").trigger("wheel", {"deltaY": -100})
        await user.should_see(marker="cell:prescaling:primes:1:1")
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.586"
        user.find(marker="cell:prescaling:primes:1:1").trigger("wheel", {"deltaY": 100})
        await user.should_see(marker="cell:prescaling:primes:1:1")
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"

    async def test_scrolling_the_target_limit_steps_then_commits(self, user: User, monkeypatch) -> None:
        monkeypatch.setattr(_editing_tuning, "_TARGET_LIMIT_DEBOUNCE", 0)
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")
        num, _sel = _target_preset(user)
        before = int(num.value)
        UserInteraction(user, {num}, None).trigger("wheel", {"deltaY": -100})
        num, _sel = _target_preset(user)
        assert int(num.value) == before + 1
        await asyncio.sleep(0.05)
        num, _sel = _target_preset(user)
        assert int(num.value) == before + 1, "committed, not reverted"

    async def test_clicking_the_sign_flips_the_generator_and_its_mapping_row(self, user: User) -> None:
        await user.open("/")
        before = float(_cell_child(user, "tuning:generator:1").value)
        assert before > 0
        assert _cell_child(user, "cell:mapping:1:2").value == "4"
        sign_lbl, _, _ = _generator_tuning_face(user, "tuning:generator:1")
        UserInteraction(user, {sign_lbl}, None).click()
        await user.should_see(marker="tuning:generator:1")
        assert float(_cell_child(user, "tuning:generator:1").value) == -before
        sign_lbl, _, _ = _generator_tuning_face(user, "tuning:generator:1")
        assert sign_lbl.text == "−"
        assert _cell_child(user, "cell:mapping:1:2").value == "-4"

    async def test_editing_a_target_cell_overrides_the_set(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:vector:targets:0:0").set_value("2")
        _commit(user, "cell:vector:targets:0:0")
        await user.should_see(marker="cell:vector:targets:0:0")
        assert _cell_child(user, "cell:vector:targets:0:0").value == "2"

    async def test_editing_a_comma_ratio_updates_the_basis(self, user: User) -> None:
        await user.open("/")
        assert _ratio_value(user, "comma:0") == "80/81"
        _cell_child(user, "comma:0").set_value("25/24")
        _commit(user, "comma:0")
        await user.should_see(marker="cell:comma:0:0")
        assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["-3", "-1", "2"]
        assert _ratio_value(user, "comma:0") == "25/24"

    async def test_an_out_of_limit_comma_ratio_toasts_and_reverts(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "comma:0").set_value("82/81")
        _commit(user, "comma:0")
        await user.should_see("outside the 2.3.5 domain")
        assert _ratio_value(user, "comma:0") == "80/81", "reverted, not left showing the bad 82/81"
        assert [_cell_child(user, f"cell:comma:{p}:0").value for p in range(3)] == ["4", "-4", "1"]

    async def test_an_unparseable_comma_ratio_toasts_that_its_invalid(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "comma:0").set_value("12three")
        _commit(user, "comma:0")
        await user.should_see("not a valid ratio")
        assert _ratio_value(user, "comma:0") == "80/81"

    async def test_editing_a_target_ratio_overrides_the_set(self, user: User) -> None:
        await user.open("/")
        assert _ratio_value(user, "target:0") == "2"
        _cell_child(user, "target:0").set_value("5/4")
        _commit(user, "target:0")
        await user.should_see(marker="target:0")
        assert _ratio_value(user, "target:0") == "5/4"

    async def test_editing_a_held_ratio_updates_the_interval(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        _cell_child(user, "cell:held:0:0").set_value("-1")
        _cell_child(user, "cell:held:1:0").set_value("1")
        _cell_child(user, "cell:held:2:0").set_value("0")
        _commit(user, "cell:held:2:0")
        await user.should_see(marker="held:0")
        _cell_child(user, "held:0").set_value("5/4")
        _commit(user, "held:0")
        await user.should_see(marker="cell:held:0:0")
        assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-2", "0", "1"]

    async def test_editing_an_interest_ratio_updates_the_interval(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "interest_plus")
        _cell_child(user, "cell:interest:0:0").set_value("1")
        _cell_child(user, "cell:interest:1:0").set_value("1")
        _cell_child(user, "cell:interest:2:0").set_value("-1")
        _commit(user, "cell:interest:2:0")
        await user.should_see(marker="interest:0")
        _cell_child(user, "interest:0").set_value("5/4")
        _commit(user, "interest:0")
        await user.should_see(marker="cell:interest:0:0")
        assert [_cell_child(user, f"cell:interest:{p}:0").value for p in range(3)] == ["-2", "0", "1"]

    async def test_typing_a_ratio_into_a_pending_draft_fills_it(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        await user.should_see(marker="held:pending")
        assert "rtt-pending" in _wrap_classes(user, "held:pending")
        assert _ratio_value(user, "held:pending") == "?/?", "pre-filled, so you edit '?/?' not a blank box"
        _cell_child(user, "held:pending").set_value("3/2")
        _commit(user, "held:pending")
        await user.should_see(marker="held:0")
        assert _ratio_value(user, "held:0") == "3/2"
        assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["-1", "1", "0"]

    async def test_typing_a_bare_integer_into_a_pending_draft_fills_it(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "optimization")
        _click_glyph(user, "held_plus")
        await user.should_see(marker="held:pending")
        num, den = _frac_inputs(user, "held:pending")
        assert (num.value, den.value) == ("?", "?")
        num.set_value("2")
        _commit(user, "held:pending")
        await user.should_see(marker="held:0")
        assert _ratio_value(user, "held:0") == "2", "committed the bare integer, not '2/?'"
        assert [_cell_child(user, f"cell:held:{p}:0").value for p in range(3)] == ["1", "0", "0"]

    async def test_clicking_a_non_last_comma_minus_un_tempers_that_comma(self, user: User) -> None:
        await user.open("/")
        _click_glyph(user, "comma_plus")
        _cell_child(user, "cell:comma:0:1").set_value("7")
        _cell_child(user, "cell:comma:1:1").set_value("0")
        _cell_child(user, "cell:comma:2:1").set_value("-3")
        _commit(user, "cell:comma:2:1")
        await user.should_see(marker="comma_minus:1")
        two = service.from_comma_basis(((4, -4, 1), (7, 0, -3)))
        drop0, drop_last = service.remove_comma(two, 0), service.remove_comma(two, -1)
        keep0, keep_last = service.comma_ratios(drop0.comma_basis)[0], service.comma_ratios(drop_last.comma_basis)[0]
        assert keep0 != keep_last, "dropping the first vs the last genuinely differ"
        _click_glyph(user, "comma_minus:0")
        await user.should_not_see(marker="comma_minus:0")
        assert _ratio_value(user, "comma:1") == keep0, "the index-0 removal rendered, NOT the last-comma one"

    def test_ratio_font_shrinks_a_long_fraction_to_fit_its_square(self) -> None:
        import math

        from rtt.app.render_html import _ratio_font
        from rtt.app.render_html import _RATIO_DIGIT_EM, _RATIO_MAX_FONT, _RATIO_PAD
        cell = spreadsheet_constants.COLUMN_WIDTH
        assert _ratio_font("2", "1", cell) == _RATIO_MAX_FONT
        assert _ratio_font("128", "125", cell) == _RATIO_MAX_FONT
        overflow = math.floor((cell - _RATIO_PAD) / (_RATIO_DIGIT_EM * _RATIO_MAX_FONT)) + 1
        for num, den in [("9" * overflow, "1"), ("1", "9" * overflow), ("9" * (overflow + 2), "1")]:
            font = _ratio_font(num, den, cell)
            assert font < _RATIO_MAX_FONT
            longest = max(len(num), len(den))
            assert longest * _RATIO_DIGIT_EM * font + _RATIO_PAD <= cell + 1e-9
        widths = [_ratio_font("9" * n, "1", cell) for n in range(1, 9)]
        assert widths == sorted(widths, reverse=True)

    async def test_a_long_ratio_face_shrinks_to_fit_its_cell(self, user: User) -> None:
        await user.open("/")
        num, den = _ratio_face(user, "target:0")
        assert (num.value, den.value) == ("2", "")
        assert "font-size" in num._style, "the fraction field must carry a fitted font size"
        big = float(num._style["font-size"].rstrip("px"))
        _cell_child(user, "target:0").set_value("65536/1")
        _commit(user, "target:0")
        await user.should_see(marker="target:0")
        num, den = _ratio_face(user, "target:0")
        assert num.value == "65536"
        small = float(num._style["font-size"].rstrip("px"))
        assert small < big
        assert num._style["font-size"] == den._style["font-size"]

    async def test_decimals_off_shrinks_a_long_integer_to_fit_its_cell(self, user: User) -> None:
        cell_font = float(page_assets._CELL_FONT)
        await user.open("/")
        main_on, sub_on = _ro_stacked_face(user, "tuning:prime:0")
        assert (main_on.text, sub_on.text) == ("1200", ".000")
        _toggle(user, "decimals")
        long_main, long_sub = _ro_stacked_face(user, "tuning:prime:0")
        assert (long_main.text, long_sub.text) == ("1200", "")
        assert float(long_main._style["font-size"].rstrip("px")) < cell_font, \
            "a 4-digit value must shrink below the full cell font so it fits its box"
        short_main, short_sub = _ro_stacked_face(user, "retune:prime:0")
        assert (short_main.text, short_sub.text) == ("0", "")
        assert float(short_main._style["font-size"].rstrip("px")) == cell_font
        generator_whole, _ = _dec_inputs(user, "tuning:generator:1")
        assert len(str(generator_whole.value)) == 3
        generator_box = _marked(user, "tuning:generator:1:editbox")
        assert float(generator_box._style["--dec-whole-font"].rstrip("px")) < cell_font, \
            "a signed 3-digit generator must shrink below the full cell font to clear its sign + box edge"

    async def test_typing_the_prescaler_plain_text_overrides_the_scheme(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:prescaling:primes")
        _cell_child(user, "plain_text:prescaling:primes").set_value("[⟨1 0 0] ⟨0 4 0] ⟨0 0 2.322]⟩")
        await user.should_see(marker="cell:prescaling:primes:1:1")
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "4"

    async def test_unparseable_prescaler_plain_text_reddens_the_box(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        _toggle(user, "plain text values")
        await user.should_see(marker="plain_text:prescaling:primes")
        _cell_child(user, "plain_text:prescaling:primes").set_value("[⟨1 0.5 0] ⟨0 1 0] ⟨0 0 1]⟩")
        classes = _cell_child(user, "plain_text:prescaling:primes").classes
        assert "rtt-plain-text-error" in classes
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "1.585"

    async def test_editing_a_prescaler_diagonal_cell_overrides_the_scheme(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="cell:prescaling:primes:1:1")
        _cell_child(user, "cell:prescaling:primes:1:1").set_value("4.0")
        await user.should_see(marker="cell:prescaling:primes:1:1")
        assert _cell_child(user, "cell:prescaling:primes:1:1").value == "4", "the typed value rode the override back to the diagonal cell on re-render (it would # otherwise have reverted to the scheme's 1.585), and the off-diagonal '0' stays read-only"
        await user.should_see(marker="cell:prescaling:primes:0:1")

    async def test_editable_prescaler_cell_renders_a_stacked_cents_face(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="cell:prescaling:primes:1:1")
        value = _cell_child(user, "cell:prescaling:primes:1:1").value
        whole_in, frac_in = _dec_inputs(user, "cell:prescaling:primes:1:1")
        assert "." not in whole_in.value
        assert frac_in.value and "." not in frac_in.value
        assert f"{whole_in.value}.{frac_in.value}" == value
        assert _dec_mode(user, "cell:prescaling:primes:1:1") == "dec"


class TestValueDisplayAndUndo:
    async def test_a_bare_integer_value_fills_the_cell_not_the_reduced_whole_part_size(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        _cell_child(user, "control:slope").set_value("simplicity-weight")
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        await user.should_see(marker="cell:prescaling:primes:0:1")
        zero_main, _ = _ro_stacked_face(user, "cell:prescaling:primes:0:1")
        assert zero_main.text == "0"
        assert "rtt-stacked-solo" in zero_main._classes
        assert _dec_mode(user, "cell:prescaling:primes:1:1") == "dec", "the diagonal log₂3 = 1.585 keeps the stacked whole-over-.fraction view (dec mode, not solo)"
        assert _dec_mode(user, "cell:prescaling:primes:0:0") == "int"

    async def test_a_finite_power_fills_the_cell_when_re_synced_from_infinity(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        main, sub = _stacked_face(user, "optimization:power")
        assert (main.text, sub.text) == ("∞", "(max)")
        assert "rtt-stacked-solo" not in main._classes
        _cell_child(user, "optimization:power").set_value("2")
        await user.should_see(marker="optimization:power")
        main, sub = _stacked_face(user, "optimization:power")
        assert (main.text, sub.text) == ("2", "")
        assert "rtt-stacked-solo" in main._classes

    async def test_undo_button_reverts_a_mapping_edit(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        user.find(marker="undo").click()
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "4"

    async def test_target_chooser_renders_in_the_expanded_target_interval_list(self, user: User) -> None:
        await _enable(user, "presets")
        await user.should_see(marker="preset:target")

    async def test_chooser_popups_open_wide_enough_for_one_line_entries(self, user: User) -> None:
        await _enable(user, "presets")
        _toggle(user, "optimization")
        _toggle(user, "weighting")
        for cell_id in ("preset:temperament", "preset:tuning"):
            style = _cell_child(user, cell_id)._props["popup-content-style"]
            assert "width:max-content" in style, f"{cell_id}: {style}"
            assert style.startswith("min-width:"), f"{cell_id}: {style}"
