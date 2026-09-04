import dataclasses
from types import SimpleNamespace

import pytest

from rtt.app import _rendering_ops, layout as layout_module, preview_engine, service, spreadsheet
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

    def test_anchoring_leaves_the_futures_own_extents_honest(self):
        base = service.from_mapping(((1, 1, 0), (0, 1, 4)))
        current, future, anchored = self._anchored(
            base, service.remove_mapping_row(base, 0), "comma_minus:0")
        assert future.width != current.width, "this action does resize the grid"
        assert dataclasses.replace(anchored, preview_offset=future.preview_offset) == future, \
            "the shift alone holds the control; size_panes must still hear the future's real extents, or the frozen head's scroll-timeline range goes short and it slides off the body's rules"

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

    def test_a_rule_that_starts_in_a_frozen_band_is_stretched_not_moved(self):
        line = layout_module.Line("h:counts", "h", position=150.5, start=132.0, length=1329.0)
        held = _rendering_ops.line_across_the_seam(line, 190, 114.0, (-40.0, 0.0))
        assert held.start + -40.0 == line.start, \
            "the band keeps its own copy at rest, so the body's copy must still meet it at the seam"
        assert held.start + held.length + -40.0 == line.start + line.length - 40.0, \
            "...while its far end follows the shift onto the drawn grid's new edge"

    def test_a_rule_clear_of_the_bands_rides_the_shift_whole(self):
        line = layout_module.Line("bus:generators:top", "h", position=84.0, start=394.5, length=75.0)
        assert _rendering_ops.line_across_the_seam(line, 190, 114.0, (-40.0, 0.0)) is line, \
            "a stub bounded by content at both ends moves with that content"

    def test_only_the_span_axis_shift_stretches_a_rule(self):
        line = layout_module.Line("trunk:quantities", "v", position=255.0, start=56.0, length=1430.0)
        assert _rendering_ops.line_across_the_seam(line, 190, 114.0, (-40.0, 0.0)) is line, \
            "a vertical rule's own axis is x; only a vertical shift can pull its span off the seam"
        held = _rendering_ops.line_across_the_seam(line, 190, 114.0, (0.0, 251.0))
        assert held.start + 251.0 == line.start and held.length == line.length + 251.0

    def test_the_panes_are_sized_to_the_grid_as_drawn_not_as_computed(self):
        drawn = _rendering_ops.drawn_extent(
            SimpleNamespace(width=3592.0, height=1634.0, preview_offset=(-3.0, -148.0)))
        assert drawn == (3589.0, 1486.0), \
            "content drawn 148px up ends 148px short, so a box built from the raw height leaves a bare strip its rules never reach"
        held = SimpleNamespace(width=1816.0, height=3221.0, preview_offset=(178.0, 251.0))
        assert _rendering_ops.drawn_extent(held) == (1994.0, 3472.0), \
            "and content pushed away from the origin needs the box to grow to hold it"

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


class TestPlusReEnablesOnAValidDraft:
    def _comma_plus(self, layout):
        return {c.id: c.disabled for c in layout.cells if c.id == "comma_plus"}["comma_plus"]

    def test_a_committable_draft_value_re_enables_the_plus_in_the_preview(self):
        ed = Editor()
        ed.add_comma()
        base = ed.layout()
        assert self._comma_plus(base) is True, "an open draft dims the +"
        future = preview_engine.compute_future(ed, lambda: ed.set_pending_comma([7, 0, -3]), base)
        plan = preview_engine.plan_edit(base, base, future)
        merged = preview_engine.value_graft(base, plan, "comma:pending")
        assert self._comma_plus(merged) is False, "a valid (committable) draft value re-enables the + mid-edit"

    def test_a_hover_that_opens_a_draft_does_not_dim_the_plus_via_graft(self):
        ed = Editor()
        base = ed.layout()
        future = preview_engine.compute_future(ed, ed.add_comma, base)
        plan = preview_engine.plan_edit(base, base, future)
        merged = preview_engine.value_graft(base, plan, "comma_plus")
        assert self._comma_plus(merged) is False, "hovering to preview an add must not dim the +"


class TestDomainPrimePlusGhostsTheElementNotTheGenerator:
    def test_expand_future_raises_both_the_element_and_generator_counts(self):
        ed = Editor()
        base = ed.layout()
        future = preview_engine.compute_future(ed, ed.expand, base)
        raw = preview_engine.ghost_axes_between(base, future)
        assert "elements" in raw and "generators" in raw, \
            "adding a prime raises both the dimensionality and the rank in the raw axis diff"

    def test_hovering_the_domain_prime_plus_ghosts_only_the_element(self):
        ed = Editor()
        base = ed.layout()
        future = preview_engine.anchor_to_source(
            preview_engine.compute_future(ed, ed.expand, base), base, "plus"
        )
        plan = preview_engine.plan_preview(base, future, "plus", preview_engine.occupied_axes(ed))
        assert plan.mode == preview_engine.HYBRID
        assert plan.ghost_axes == ("elements",), \
            "the domain-prime + adds an element; its incidental rank bump must not draft a generator"

    def test_a_sourceless_reflow_hold_derives_both_raw_ghosts(self):
        ed = Editor()
        base = ed.layout()
        future = preview_engine.anchor_to_source(
            preview_engine.compute_future(ed, ed.expand, base), base, "plus"
        )
        plan = preview_engine.plan_preview(base, future, "plus", preview_engine.occupied_axes(ed))
        held = preview_engine.reflow_to_hold(plan, base, preview_engine.occupied_axes(ed))
        assert held.ghost_axes == ("generators", "elements"), "no source_id keeps the raw axis derivation"


class TestDomainPrimePlusHoverDraftsTheNewPrimeColumn:
    def _hover(self):
        ed = Editor()
        base = ed.layout()
        future = preview_engine.anchor_to_source(
            preview_engine.compute_future(ed, ed.expand, base), base, "plus"
        )
        plan = preview_engine.plan_preview(base, future, "plus", preview_engine.occupied_axes(ed))
        hybrid = preview_engine.build_hybrid(ed, base, plan, "plus")
        return base, future, hybrid

    def test_the_draft_column_carries_the_real_next_prime_values_not_the_previous_prime(self):
        base, future, hybrid = self._hover()
        hcells = {c.id: c for c in hybrid.cells}
        fcells = {c.id: c for c in future.cells}
        dp = base.axis_counts["elements"]
        pairs = [
            ("prime:pending", f"prime:{dp}"),
            ("basis:pending", f"basis:{dp}"),
            ("tuning:prime:draft", f"tuning:prime:{dp}"),
            ("just:prime:draft", f"just:prime:{dp}"),
            ("retune:prime:draft", f"retune:prime:{dp}"),
        ]
        for draft_id, future_id in pairs:
            assert draft_id in hcells, f"the draft column must emit {draft_id}"
            assert hcells[draft_id].pending, f"{draft_id} must be a green draft cell"
            assert hcells[draft_id].text == fcells[future_id].text, \
                f"{draft_id} must show the committed next-prime value from {future_id}"

    def test_the_draft_prime_header_renders_as_a_prime_not_an_editable_ratio(self):
        _, _, hybrid = self._hover()
        hcells = {c.id: c for c in hybrid.cells}
        assert hcells["prime:pending"].kind == "prime"
        assert hcells["basis:pending"].kind == "prime"

    def test_the_hover_drafts_no_generator(self):
        _, _, hybrid = self._hover()
        assert not any(c.id == "generator:pending" for c in hybrid.cells)
        assert not any(c.pending and "mapping:draft" in c.id for c in hybrid.cells), \
            "the incidental rank bump must not paint a generator draft row"
