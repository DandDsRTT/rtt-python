from functools import partial

import pytest

from rtt.app import (
    grid_tables,
    service,
    settings,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_geometry_query as query,
    spreadsheet_models,
    spreadsheet_text,
)
from rtt.app.editor import Editor
from rtt.app.layout import Cell, Layout
from rtt.app.spreadsheet_decorations import _tile_groups
from rtt.app.spreadsheet_geometry import plain_text_band
from _spreadsheet_support import _memoized_build, _diff_layout, _diff_cell


class TestPreviewCellIds:
    def test_changed_cell_ids_is_empty_for_an_unchanged_layout(self):
        layout = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
        assert spreadsheet_text.changed_cell_ids(layout, layout) == frozenset()

    def test_changed_cell_ids_flags_a_cell_whose_text_changed(self):
        old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
        new = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "9"))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset({"b"})

    def test_changed_cell_ids_ignores_a_cell_that_only_moved(self):
        old = _diff_layout(Cell("a", 0, 0, 10, 10, "tuning_value", text="1"))
        new = _diff_layout(Cell("a", 99, 50, 20, 20, "tuning_value", text="1"))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset()

    def test_moved_cell_ids_flags_a_cell_that_only_changed_position(self):
        old = _diff_layout(Cell("a", 0, 0, 10, 10, "tuning_value", text="1"))
        new = _diff_layout(Cell("a", 99, 0, 10, 10, "tuning_value", text="1"))
        assert spreadsheet_text.moved_cell_ids(old, new) == frozenset({"a"})

    def test_moved_cell_ids_ignores_an_unmoved_cell_and_a_new_one(self):
        old = _diff_layout(Cell("a", 0, 0, 10, 10, "tuning_value", text="1"))
        new = _diff_layout(Cell("a", 0, 0, 10, 10, "tuning_value", text="1"),
                           Cell("b", 40, 0, 10, 10, "tuning_value", text="2"))
        assert spreadsheet_text.moved_cell_ids(old, new) == frozenset()

    def test_moved_cell_ids_skips_a_relocated_but_non_ringable_cell(self):
        old = _diff_layout(Cell("g", 0, 0, 10, 10, "columngrip"))
        new = _diff_layout(Cell("g", 99, 0, 10, 10, "columngrip"))
        assert spreadsheet_text.moved_cell_ids(old, new) == frozenset()

    def test_restaged_cell_ids_unions_the_content_changed_and_the_relocated(self):
        old = _diff_layout(Cell("a", 0, 0, 10, 10, "tuning_value", text="1"),
                           Cell("b", 40, 0, 10, 10, "tuning_value", text="2"))
        new = _diff_layout(Cell("a", 99, 0, 10, 10, "tuning_value", text="1"),
                           Cell("b", 40, 0, 10, 10, "tuning_value", text="9"))
        assert spreadsheet_text.restaged_cell_ids(old, new) == frozenset({"a", "b"})

    def test_changed_cell_ids_flags_a_newly_added_cell(self):
        old = _diff_layout(_diff_cell("a", "1"))
        new = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset({"b"})

    def test_changed_cell_ids_omits_a_removed_cell(self):
        old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
        new = _diff_layout(_diff_cell("a", "1"))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset()

    def test_changed_cell_ids_flags_a_value_flag_change_not_just_text(self):
        old = _diff_layout(_diff_cell("a", "701.955"))
        new = _diff_layout(_diff_cell("a", "701.955", blank=True))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset({"a"})

    def test_changed_cell_ids_tracks_a_mapping_edit_through_a_real_layout(self):
        ed = Editor()
        before = ed.layout()
        ed.edit_mapping([[1, 1, 0], [0, 1, 7]])
        changed = spreadsheet_text.changed_cell_ids(before, ed.layout())
        assert "cell:mapped:1:6" in changed
        assert "cell:mapping:1:2" in changed, "the mapping cell ITSELF — an input cell whose value must"
        assert "prime:2" not in changed

    def test_reordering_generators_rings_both_the_generators_and_the_mapping_rows(self):
        ed = Editor()
        before = ed.layout()
        assert ed.move_interval("generators", 0, "generators", 1) is True
        restaged = spreadsheet_text.restaged_cell_ids(before, ed.layout(previous_ids=before.identities))
        ringed = {c.kind for c in ed.layout(previous_ids=before.identities).cells if c.id in restaged}
        assert "generator_ratio" in ringed, "the reordered generator ratios highlight"
        assert "mapping" in ringed, "and the mapping rows they carry highlight too"

    def test_changed_cell_ids_rings_only_value_cells_not_marks_or_controls(self):
        old = _diff_layout(_diff_cell("v", "1"))
        new = _diff_layout(
            _diff_cell("v", "2"),
            Cell("ebktop:targets:0", 0, 0, 10, 10, "ebktop"),
            Cell("ebkbrace:targets:0", 0, 0, 10, 10, "ebkbrace"),
            Cell("ebkangle:vector:commas:1", 0, 0, 10, 10, "ebkangle"),
            Cell("sep:targets:1", 0, 0, 10, 10, "vbar"),
            Cell("grip:targets:0", 0, 0, 10, 10, "subcolumngrip"),
            Cell("comma_minus:0", 0, 0, 10, 10, "comma_minus"),
        )
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset({"v"})

    def test_removed_cell_ids_flags_a_value_cell_gone_from_the_new_layout(self):
        old = _diff_layout(_diff_cell("a", "1"), _diff_cell("b", "2"))
        new = _diff_layout(_diff_cell("a", "1"))
        assert spreadsheet_text.removed_cell_ids(old, new) == frozenset({"b"})

    def test_removed_cell_ids_ignores_survivors_added_cells_and_removed_scaffolding(self):
        old = _diff_layout(
            _diff_cell("survivor", "1"),
            _diff_cell("value", "2"),
            Cell("ebkangle:vector:commas:1", 0, 0, 10, 10, "ebkangle"),
            Cell("sep:targets:1", 0, 0, 10, 10, "vbar"),
            Cell("grip:commas:1", 0, 0, 10, 10, "subcolumngrip"),
            Cell("comma_minus:1", 0, 0, 10, 10, "comma_minus"),
        )
        new = _diff_layout(_diff_cell("survivor", "1"), _diff_cell("added", "9"))
        assert spreadsheet_text.removed_cell_ids(old, new) == frozenset({"value"})

    def test_a_domain_change_keeps_target_columns_shared_by_ratio(self):
        ed = Editor()
        base = ed.layout()
        base = ed.layout(previous_ids=base.identities)
        token = ed.capture_for_preview()
        try:
            ed.shrink()
            shrunk = ed.layout(previous_ids=base.identities)
        finally:
            ed.restore_for_preview(token)
        base_ratios = {r for _, r in base.identities["targets"]}
        shrunk_ratios = {r for _, r in shrunk.identities["targets"]}
        shared, dropped = base_ratios & shrunk_ratios, base_ratios - shrunk_ratios
        assert shared and dropped, "the two TILTs genuinely overlap AND differ (so the test bites both ways)"
        shared_tok = next(token for token, r in base.identities["targets"] if r in shared)
        dropped_tok = next(token for token, r in base.identities["targets"] if r in dropped)
        removed = spreadsheet_text.removed_cell_ids(base, shrunk)
        assert f"target:{shared_tok}" not in removed
        assert f"target:{dropped_tok}" in removed
