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
from rtt.app.layout import CellBox, Layout
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
        old = _diff_layout(CellBox("a", 0, 0, 10, 10, "tuningvalue", text="1"))
        new = _diff_layout(CellBox("a", 99, 50, 20, 20, "tuningvalue", text="1"))
        assert spreadsheet_text.changed_cell_ids(old, new) == frozenset()

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

    def test_changed_cell_ids_rings_only_value_cells_not_marks_or_controls(self):
        old = _diff_layout(_diff_cell("v", "1"))
        new = _diff_layout(
            _diff_cell("v", "2"),
            CellBox("ebktop:targets:0", 0, 0, 10, 10, "ebktop"),
            CellBox("ebkbrace:targets:0", 0, 0, 10, 10, "ebkbrace"),
            CellBox("ebkangle:vector:commas:1", 0, 0, 10, 10, "ebkangle"),
            CellBox("sep:targets:1", 0, 0, 10, 10, "vbar"),
            CellBox("grip:targets:0", 0, 0, 10, 10, "columngrip"),
            CellBox("comma_minus:0", 0, 0, 10, 10, "comma_minus"),
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
            CellBox("ebkangle:vector:commas:1", 0, 0, 10, 10, "ebkangle"),
            CellBox("sep:targets:1", 0, 0, 10, 10, "vbar"),
            CellBox("grip:commas:1", 0, 0, 10, 10, "columngrip"),
            CellBox("comma_minus:1", 0, 0, 10, 10, "comma_minus"),
        )
        new = _diff_layout(_diff_cell("survivor", "1"), _diff_cell("added", "9"))
        assert spreadsheet_text.removed_cell_ids(old, new) == frozenset({"value"})

    def test_a_domain_change_keeps_target_columns_shared_by_ratio(self):
        ed = Editor()
        base = ed.layout()
        base = ed.layout(prev_ids=base.identities)
        token = ed.capture_for_preview()
        try:
            ed.shrink()
            shrunk = ed.layout(prev_ids=base.identities)
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
