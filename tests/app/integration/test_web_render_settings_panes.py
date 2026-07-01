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
from _render_support import _toggle, _enable, _cell_child, _wrap_classes, _commit, _cell_text, _live, _live_assets, _ENABLE_HTML_CELLS, _DEFAULT_HTML_CELLS


class TestSettingsAndPanes:
    async def test_select_all_turns_on_every_implemented_feature(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="select all / none").click()
        await user.should_see(marker="chart:retune:targets")

    async def test_reset_restores_settings_expand_collapse_and_values(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        _toggle(user, "charts")
        await user.should_see(marker="chart:retune:targets")
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        user.find(marker="reset").click()
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "4"
        await user.should_not_see(marker="chart:retune:targets")

    async def test_undo_button_reverts_a_settings_change(self, user: User) -> None:
        await user.open("/")
        _toggle(user, "charts")
        await user.should_see(marker="chart:retune:targets")
        user.find(marker="undo").click()
        await user.should_see(marker="cell:mapping:0:0")
        await user.should_not_see(marker="chart:retune:targets")

    async def test_state_persists_across_a_refresh(self, user: User) -> None:
        await user.open("/")
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"
        await user.open("/")
        await user.should_see(marker="cell:mapped:1:6")
        assert _cell_text(user, "cell:mapped:1:6") == "7"

    async def test_dragging_a_generator_row_onto_another_adds_it_in(self, user: User) -> None:
        await _enable(user, "drag to combine")
        row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
        assert row1() == ["0", "1", "4"]
        grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
        cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
        assert next(iter(grip(0)))._props.get("draggable")
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, cell(1, 0), None).trigger("drop.prevent")
        await user.should_see(marker="cell:mapping:1:0")
        assert row1() == ["1", "2", "4"]

    async def test_dropping_a_row_grip_directly_onto_another_grip_merges(self, user: User) -> None:
        await _enable(user, "drag to combine")
        row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
        assert row1() == ["0", "1", "4"]
        grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, grip(1), None).trigger("drop.prevent")
        await user.should_see(marker="cell:mapping:1:0")
        assert row1() == ["1", "2", "4"]

    async def test_dropping_an_interval_grip_directly_onto_another_grip_merges(self, user: User) -> None:
        await _enable(user, "drag to combine")
        tuning_value = lambda i: _cell_child(user, f"target:{i}").value
        before0, before1 = tuning_value(0), tuning_value(1)
        grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, grip(1), None).trigger("drop.prevent")
        await user.should_see(marker="target:1")
        assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)

    async def test_dragging_an_interval_onto_another_combines_them(self, user: User) -> None:
        await _enable(user, "drag to combine")
        tuning_value = lambda i: _cell_child(user, f"target:{i}").value
        before0, before1 = tuning_value(0), tuning_value(1)
        grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
        cell = lambda i, p: set(user.find(marker=f"cell:vector:targets:{i}:{p}").elements)
        assert next(iter(grip(0)))._props.get("draggable")
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, cell(1, 0), None).trigger("drop.prevent")
        await user.should_see(marker="target:1")
        assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)
        assert tuning_value(0) == before0

    async def test_dragging_over_an_interval_previews_the_product_then_reverts(self, user: User) -> None:
        await _enable(user, "drag to combine")
        tuning_value = lambda i: _cell_child(user, f"target:{i}").value
        before0, before1 = tuning_value(0), tuning_value(1)
        grip = lambda i: set(user.find(marker=f"int_drag:target:{i}").elements)
        cell = lambda i, p: set(user.find(marker=f"cell:vector:targets:{i}:{p}").elements)
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, cell(1, 0), None).trigger("dragenter.prevent")
        assert Fraction(tuning_value(1)) == Fraction(before0) * Fraction(before1)
        UserInteraction(user, grip(0), None).trigger("dragend")
        assert tuning_value(1) == before1

    async def test_dragging_over_a_row_previews_the_change_then_reverts(self, user: User) -> None:
        await _enable(user, "drag to combine")
        row1 = lambda: [_cell_child(user, f"cell:mapping:1:{p}").value for p in range(3)]
        assert row1() == ["0", "1", "4"]
        grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
        cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, cell(1, 0), None).trigger("dragenter.prevent")
        assert row1() == ["1", "2", "4"]
        assert "rtt-preview-change" in _wrap_classes(user, "cell:mapping:1:0")
        assert "rtt-preview-change" in _wrap_classes(user, "generator:0")
        UserInteraction(user, grip(0), None).trigger("dragend")
        assert row1() == ["0", "1", "4"]
        assert "rtt-preview-change" not in _wrap_classes(user, "cell:mapping:1:0")
        assert "rtt-preview-change" not in _wrap_classes(user, "generator:0")

    async def test_dropping_a_row_on_its_own_cells_does_nothing(self, user: User) -> None:
        await _enable(user, "drag to combine")
        row0 = lambda: [_cell_child(user, f"cell:mapping:0:{p}").value for p in range(3)]
        assert row0() == ["1", "1", "0"]
        grip = lambda i: set(user.find(marker=f"map_drag:{i}").elements)
        cell = lambda i, p: set(user.find(marker=f"cell:mapping:{i}:{p}").elements)
        UserInteraction(user, grip(0), None).trigger("dragstart")
        UserInteraction(user, cell(0, 0), None).trigger("dragenter.prevent")
        assert row0() == ["1", "1", "0"], "no preview — self is not a valid target"
        UserInteraction(user, cell(0, 0), None).trigger("drop.prevent")
        assert row0() == ["1", "1", "0"]


    _ENABLE_HTML_CELLS = [
        ("units", "units:mapping:primes"),
        ("charts", "chart:retune:targets"),
        ("tuning ranges", "rangechart:tuning:generators"),
    ]

    @pytest.mark.parametrize("label, cell_id", _ENABLE_HTML_CELLS)
    async def test_enabled_html_cell_renders_non_blank_content(self, user: User, label: str, cell_id: str) -> None:
        await _enable(user, label)
        await user.should_see(marker=cell_id)
        assert getattr(_cell_child(user, cell_id), "content", ""), \
            f"{cell_id} rendered with empty html content — did render() drop its kind's branch?"


    _DEFAULT_HTML_CELLS = ["caption:mapping:primes", "bracket:map:0:l", "symbol:mapping:primes"]

    async def test_a_maximal_render_dispatches_every_emitted_cell_kind(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="select all / none").click()
        await user.should_see(marker="cell:mapping:0:0")

    async def test_a_mid_render_exception_restores_the_build_guard_so_handlers_stay_live(self, 
            user: User, monkeypatch) -> None:
        await user.open("/")
        live = _live()
        caught = []
        monkeypatch.setattr(core.app, "handle_exception", lambda e: caught.append(e))
        orig = live._Reconciler.update_cell
        fired = {"n": 0}

        def boom(self, cell_box):
            if fired["n"] == 0:
                fired["n"] = 1
                raise RuntimeError("mid-render boom")
            return orig(self, cell_box)

        monkeypatch.setattr(live._Reconciler, "update_cell", boom)
        user.find(marker="toggle:row:tuning").click()
        assert caught and isinstance(caught[0], RuntimeError)
        monkeypatch.setattr(live._Reconciler, "update_cell", orig)
        _cell_child(user, "cell:mapping:1:2").set_value("7")
        _commit(user, "cell:mapping:1:2")
        assert "7" in _live_assets()._MEMORY_STORE[_live_assets()._STORE_KEY]["mapping_ebk"], "NOT swallowed by a stuck guard"

    async def test_the_reconcile_updates_only_changed_cells_not_the_whole_page(self, 
            user: User, monkeypatch) -> None:
        await user.open("/")
        live = _live()
        calls: list = []
        orig = live._Reconciler.update_cell

        def counting(self, cell_box):
            calls.append(cell_box.id)
            return orig(self, cell_box)

        monkeypatch.setattr(live._Reconciler, "update_cell", counting)
        await user.open("/")
        full = len(calls)
        assert full > 50
        calls.clear()
        user.find(marker="toggle:row:tuning").click()
        folded = len(calls)
        assert folded < full * 0.6, f"a one-row fold updated {folded} of {full} cells — reconcile not skipping unchanged"

    async def test_a_corrupt_persisted_field_keeps_the_saved_document_and_warns(self, 
            user: User, caplog) -> None:
        await user.open("/")
        live = _live()
        _cell_child(user, "cell:mapping:1:2").set_value("5")
        _commit(user, "cell:mapping:1:2")
        stored = _live_assets()._MEMORY_STORE[_live_assets()._STORE_KEY]
        assert "5" in stored["mapping_ebk"]
        corrupt = copy.deepcopy(stored)
        corrupt["held_vectors"] = [["x", 0, 0]]
        _live_assets()._MEMORY_STORE[_live_assets()._STORE_KEY] = corrupt
        with caplog.at_level(logging.CRITICAL, logger="rtt.app.app"):
            await user.open("/")
        after = _live_assets()._MEMORY_STORE[_live_assets()._STORE_KEY]
        assert "5" in after["mapping_ebk"], "the user's bytes are NOT wiped to defaults"
        assert after["held_vectors"] == [["x", 0, 0]], "the exact stored blob is preserved for recovery"
        assert user.notify.contains("Your saved data is kept")

    async def test_a_zero_prescaler_diagonal_entry_is_rejected_not_committed(self, user: User) -> None:
        await user.open("/")
        user.find(kind=ui.checkbox, content="optimization").click()
        user.find(kind=ui.checkbox, content="weighting").click()
        user.find(kind=ui.checkbox, content="all-interval").click()
        _cell_child(user, "control:all_interval").set_value(True)
        user.find(kind=ui.checkbox, content="alternative complexity").click()
        await user.should_see(marker="cell:prescaling:primes:0:0")
        before = _cell_child(user, "cell:prescaling:primes:0:0").value
        _cell_child(user, "cell:prescaling:primes:0:0").set_value("0")
        assert _cell_child(user, "cell:prescaling:primes:0:0").value == before
        assert user.notify.contains("positive, finite number")

    async def test_an_invalid_unchanged_basis_cell_reverts_with_a_toast(self, user: User) -> None:
        await _enable(user, "projection")
        await user.should_see(marker="cell:unchanged:0:0")
        before = _cell_child(user, "cell:unchanged:0:0").value
        _cell_child(user, "cell:unchanged:0:0").set_value("zz")
        _commit(user, "cell:unchanged:0:0")
        assert _cell_child(user, "cell:unchanged:0:0").value == before
        assert _cell_child(user, "cell:unchanged:0:0").value != "zz"
        assert user.notify.contains("valid unchanged-interval basis")
