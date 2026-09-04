import dataclasses

import pytest

from rtt.app import _rendering_ops, preview_engine, service, spreadsheet
from rtt.app.editor import Editor
from _spreadsheet_support import _hover_hybrid


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
        plan = preview_engine.plan_structural(current, future)
        assert plan.removed, "the narrower TILT genuinely drops target columns"
        assert plan.mode == preview_engine.REFLOW, "no axis shrinks, so a structural plan reflows even though target cells drop"
        assert preview_engine.plan_preview(current, future).mode != preview_engine.REFLOW

    def test_structural_classification_holds_when_an_axis_shrinks(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, ed.shrink, current)
        plan = preview_engine.plan_structural(current, future)
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


class TestSourceAnchoring:
    def _anchored(self, base, future_state, source_id):
        current = spreadsheet.build(base)
        future = spreadsheet.build(future_state, previous_ids=current.identities)
        return current, future, preview_engine.anchor_to_source(future, current, source_id)

    def test_a_preview_offsets_by_exactly_what_would_have_moved_the_hovered_control(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        source = "comma_minus:0"
        current, future, anchored = self._anchored(base, service.remove_mapping_row(base, 0), source)
        at = lambda lay: next(c.x for c in lay.cells if c.id == source)
        assert at(future) != at(current), "this action does shift the control"
        assert anchored.preview_offset == (at(current) - at(future), 0.0)

    def test_anchoring_keeps_the_whole_pane_footprint_so_it_cannot_recenter(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        current, future, anchored = self._anchored(
            base, service.remove_mapping_row(base, 0), "comma_minus:0")
        assert future.width != current.width
        footprint = lambda lay: (lay.width, lay.height, lay.right_overhang)
        assert footprint(anchored) == footprint(current), \
            "size_panes sizes the pane from all three, so any one of them moves the held control"

    def test_anchoring_holds_the_overhang_a_future_would_have_widened(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        current = spreadsheet.build(base)
        wider = dataclasses.replace(
            spreadsheet.build(service.remove_mapping_row(base, 0),
                              previous_ids=current.identities),
            right_overhang=current.right_overhang + 40)
        anchored = preview_engine.anchor_to_source(wider, current, "comma_minus:0")
        assert anchored.right_overhang == current.right_overhang

    def test_anchoring_leaves_the_freeze_split_and_every_coordinate_alone(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        _, future, anchored = self._anchored(
            base, service.remove_mapping_row(base, 0), "comma_minus:0")
        assert (anchored.freeze_x, anchored.freeze_y) == (future.freeze_x, future.freeze_y), \
            "moving the freeze split would drag the frozen bands and re-home cells across them"
        assert anchored.cells == future.cells and anchored.lines == future.lines
        assert anchored.blocks == future.blocks

    def test_the_frozen_bands_do_not_take_the_offset(self):
        offset = (-37.0, -12.0)
        assert _rendering_ops.pane_offset(offset, "body") == (-37.0, -12.0)
        assert _rendering_ops.pane_offset(offset, "row") == (0.0, -12.0), \
            "the frozen row band never rides the horizontal shift"
        assert _rendering_ops.pane_offset(offset, "col") == (-37.0, 0.0)
        assert _rendering_ops.pane_offset(offset, "corner") == (0.0, 0.0)

    def test_a_plans_future_is_the_natural_layout_a_commit_can_render(self):
        ed = _editor()
        current = ed.layout()
        future = preview_engine.compute_future(ed, ed.expand, current)
        for plan in (preview_engine.plan_preview(current, future, "basis_plus"),
                     preview_engine.plan_structural(current, future)):
            assert plan.future.preview_offset == (0, 0), \
                "a counter-shifted future would commit a grid translated off its own origin"
            assert (plan.future.width, plan.future.height) == (future.width, future.height)
            assert min(c.x for c in plan.future.cells) == 0
            assert min(c.y for c in plan.future.cells) == 0

    def test_a_preview_that_moves_nothing_is_returned_untouched(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        current = spreadsheet.build(base)
        assert preview_engine.anchor_to_source(current, current, "comma_minus:0") is current
        assert preview_engine.anchor_to_source(current, current, None) is current
        assert preview_engine.anchor_to_source(current, None, "comma_minus:0") is current, \
            "a gesture armed before the first paint has no baseline to hold against"
