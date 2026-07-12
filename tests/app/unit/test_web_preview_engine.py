import pytest

from rtt.app import preview_engine, service
from rtt.app.editor import Editor
from _spreadsheet_support import _memoized_build, _hover_hybrid


def _editor():
    ed = Editor()
    ed.layout()
    return ed


class TestComputeFuture:
    def test_the_document_is_untouched_after_computing_a_future(self):
        ed = _editor()
        before = ed.serialize()
        current = ed.layout()
        future = preview_engine.compute_future(ed, lambda: ed.remove_comma(0), current)
        assert ed.serialize() == before
        assert future.axis_counts["commas"] == current.axis_counts["commas"] - 1

    def test_the_document_is_restored_even_when_the_op_raises(self):
        ed = _editor()
        before = ed.serialize()
        current = ed.layout()

        def exploding():
            ed.remove_comma(0)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            preview_engine.compute_future(ed, exploding, current)
        assert ed.serialize() == before

    def test_the_future_threads_the_current_identities(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, lambda: ed.remove_mapping_row(0), current)
        current_tokens = {token for token, _ in current.identities["commas"]}
        future_tokens = {token for token, _ in future.identities["commas"]}
        assert current_tokens <= future_tokens, "surviving commas keep their tokens; the born one is fresh"


class TestPlanPreview:
    def test_a_pure_value_change_plans_a_reflow(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, lambda: ed.flip_generator(1), current)
        plan = preview_engine.plan_preview(current, future)
        assert plan.mode == preview_engine.REFLOW
        assert plan.changed and not plan.removed

    def test_a_removal_holds_the_current_grid(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, ed.shrink, current)
        plan = preview_engine.plan_preview(current, future)
        assert plan.removed
        assert plan.mode != preview_engine.REFLOW

    def test_a_rank_dual_removal_plans_a_hybrid_with_the_born_axis_slot(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, lambda: ed.remove_comma(0), current)
        plan = preview_engine.plan_preview(current, future)
        assert plan.mode == preview_engine.HYBRID
        assert "generators" in plan.ghost_axes
        assert plan.removed and plan.added

    def test_a_moved_source_control_blocks_the_reflow(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, ed.expand, current)
        anchored = preview_engine.plan_preview(current, future, source_id=None)
        moving_source = next(
            cell.id
            for cell in current.cells
            if preview_engine._position(current, cell.id)
            != preview_engine._position(future, cell.id)
            and cell.id in {c.id for c in future.cells}
        )
        held = preview_engine.plan_preview(current, future, source_id=moving_source)
        assert anchored.mode == preview_engine.REFLOW or anchored.removed
        assert held.mode != preview_engine.REFLOW

    def test_structural_classification_reflows_despite_removed_cells(self):
        ed = _editor()
        current = ed.layout()

        def retarget():
            ed.set_target_spec("5-TILT")

        future = preview_engine.compute_future(ed, retarget, current)
        plan = preview_engine.plan_preview(current, future, structural=True)
        assert plan.removed, "the narrower TILT genuinely drops target columns"
        assert plan.mode == preview_engine.REFLOW, "no axis shrinks, so a structural plan reflows even though target cells drop"
        assert preview_engine.plan_preview(current, future).mode != preview_engine.REFLOW

    def test_structural_classification_holds_when_an_axis_shrinks(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, ed.shrink, current)
        plan = preview_engine.plan_preview(current, future, structural=True)
        assert plan.mode != preview_engine.REFLOW

    def test_an_occupied_axis_never_opens_a_ghost_slot(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, lambda: ed.remove_comma(0), current)
        plan = preview_engine.plan_preview(current, future, occupied_axes=frozenset({"generators"}))
        assert "generators" not in plan.ghost_axes


class TestAnyOpPreviewsForFree:
    def test_a_never_wired_compound_op_still_yields_a_full_plan(self):
        ed = _editor()
        current = ed.layout()

        def novel_op():
            ed.flip_generator(1)
            ed.expand()

        future = preview_engine.compute_future(ed, novel_op, current)
        plan = preview_engine.plan_preview(current, future)
        assert plan.added, "the born prime column previews green with zero feature wiring"
        assert plan.changed, "the flipped generator's ripple previews amber with zero feature wiring"
        assert plan.future is future

    def test_a_reorder_op_previews_by_identity_not_position(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(
            ed, lambda: ed.move_interval("generators", 0, "generators", 1), current
        )
        plan = preview_engine.plan_preview(current, future)
        assert not plan.removed and not plan.added, "a pure reorder removes and births nothing"
        assert plan.moved, "the traded rows register as moved"


class TestGraft:
    def test_ghost_slot_cells_take_their_values_from_the_future_layout(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        _, cells = _hover_hybrid(base, service.remove_comma(base, 0))
        assert [cells[f"cell:mapping:2:{p}"].text for p in range(3)] == ["0", "0", "1"]
        assert all(cells[f"cell:mapping:2:{p}"].pending for p in range(3))

    def test_marker_keyed_slot_ids_alias_to_the_future_token(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        _, cells = _hover_hybrid(base, service.remove_mapping_row(base, 0))
        assert cells["comma:pending"].text not in ("", "?/?", "–")
        assert cells["tuning:comma:draft"].text == "0.000"

    def test_a_dying_members_cell_in_the_born_slot_is_an_orphan_not_a_draft(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        plan, cells = _hover_hybrid(base, service.remove_mapping_row(base, 0))
        assert not cells["cell:mapped_comma:0:1"].pending

    def test_slot_aliases_substitute_each_marker_segment(self):
        assert preview_engine._slot_aliases("generator:pending", (2,)) == ("generator:2",)
        assert preview_engine._slot_aliases("cell:prescaling:commas:1:draft", (1, 4)) == (
            "cell:prescaling:commas:1:1",
            "cell:prescaling:commas:1:4",
        )
        assert preview_engine._slot_aliases("cell:mapping:2:0", (2,)) == ()
