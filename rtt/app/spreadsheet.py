from __future__ import annotations

from rtt.app.layout import Block, CellBox, Layout, Line
from rtt.app.spreadsheet_brackets import _BracketsMixin
from rtt.app.spreadsheet_constants import (
    GAP,
    GRIP_BAND,
    PAD,
)
from rtt.app.spreadsheet_controls import _ControlsMixin
from rtt.app.spreadsheet_decorations import _DecorationsMixin
from rtt.app.spreadsheet_emit_mapping import _EmitMappingMixin
from rtt.app.spreadsheet_emit_matrix import _EmitMatrixMixin
from rtt.app.spreadsheet_emit_tuning import _EmitTuningMixin
from rtt.app.spreadsheet_emit_vectors import _EmitVectorsMixin
from rtt.app.spreadsheet_geometry import _GeometryMixin
from rtt.app.spreadsheet_layout import _LayoutMixin
from rtt.app.spreadsheet_resolve import _ResolveMixin
from rtt.app.spreadsheet_resolved import Resolved, from_builder
from rtt.app.spreadsheet_text import (
    _title_w,
)


class _GridBuilder(
    _ResolveMixin,
    _LayoutMixin,
    _GeometryMixin,
    _EmitMatrixMixin,
    _EmitMappingMixin,
    _EmitVectorsMixin,
    _EmitTuningMixin,
    _ControlsMixin,
    _BracketsMixin,
    _DecorationsMixin,
):
    def layout(self) -> Layout:
        self.cells: list[CellBox] = []
        self.lines: list[Line] = []
        self.blocks: list[Block] = []
        self._control_region_boxes: list[Block] = []

        self._emit_all()

        title_right = max((c.x + c.w / 2 + _title_w(c.text) / 2 for c in self.cells if c.kind == "colheader"),
                          default=self.total_w)
        right_overhang = max(0.0, title_right - self.total_w)

        return Layout(self.total_w, self.total_h, tuple(self.lines), tuple(self.blocks), tuple(self.cells),
                      freeze_x=self.node_edge + GAP - PAD, freeze_y=self.branch_top_y + GAP + GRIP_BAND - PAD,
                      right_overhang=right_overhang, identities=self._col_ids,
                      approach_box=self.approach_box)

    def _emit_all(self) -> None:
        self._emit_headers()
        self._emit_counts_row()
        self._emit_units()
        self._emit_quantities_row()
        self._emit_column_plus_controls()
        self._emit_rehomed_minus_controls()
        self._emit_mapping_band()
        self._emit_projection_band()
        self._emit_canon_band()
        self._emit_vectors_band()
        self._emit_superspace_rows()
        self._emit_identity_objects()
        chart_indicators = self._emit_tuning_rows()
        self._emit_prescaling_band()
        self._emit_lbox_control()
        self._emit_cbox_controls()
        self._emit_complexity_row()
        self._emit_weight_row()
        self._emit_damage_row(chart_indicators)
        self._emit_charts(chart_indicators)
        gtm_box = self._emit_tuning_ranges_box()
        opt_box = self._emit_optimization_box()
        approach_frame = self._emit_approach_box()
        self._emit_brackets()
        self._emit_matrix_labels()
        self._emit_axes()
        self._emit_panels(gtm_box, opt_box, approach_frame)
        self._emit_washes()
        self._emit_symbols_captions()
        self._emit_presets()
        self._emit_all_interval_check_fallback()
        self._emit_form_choosers()
        self._emit_scheme_buttons()
        self._emit_ptext_band()
        self._emit_ebk_frames_and_marks()
        self._emit_tile_toggles()
        self._apply_value_display_filters()


def build(state, settings=None, collapsed=None, **inputs) -> Layout:
    return _GridBuilder(state, settings=settings, collapsed=collapsed, **inputs).layout()


def resolve(state, settings=None, collapsed=None, **inputs) -> Resolved:
    return from_builder(_GridBuilder(state, settings=settings, collapsed=collapsed, **inputs))
