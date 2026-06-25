from __future__ import annotations

from rtt.app.layout import Block, CellBox, Layout, Line
from rtt.app.spreadsheet_brackets import emit_brackets, emit_ebk_frames_and_marks
from rtt.app.spreadsheet_constants import (
    GAP,
    GRIP_BAND,
    PAD,
)
from rtt.app.spreadsheet_controls import (
    emit_controls,
    emit_tile_toggles,
    transform_cells,
)
from rtt.app.spreadsheet_decorations import emit_decorations
from rtt.app.spreadsheet_emit_mapping import (
    _EmitMappingMixin,
    emit_canon_band,
    emit_mapping,
    emit_projection_band,
)
from rtt.app.spreadsheet_emit_matrix import (
    emit_column_plus_controls,
    emit_counts_row,
    emit_headers,
    emit_quantities_row,
    emit_rehomed_minus_controls,
    emit_units,
)
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_emit_tuning import emit_tuning
from rtt.app.spreadsheet_emit_vectors import (
    emit_identity_objects,
    emit_superspace_rows,
    emit_vectors,
)
from rtt.app.spreadsheet_geometry import _GeometryMixin
from rtt.app.spreadsheet_geometry_model import _GeometryAccess
from rtt.app.spreadsheet_layout import _LayoutMixin
from rtt.app.spreadsheet_resolve import Resolver
from rtt.app.spreadsheet_resolved import Resolved
from rtt.app.spreadsheet_text import (
    _title_w,
)


class _GridBuilder(
    Resolver,
    _GeometryAccess,
    _LayoutMixin,
    _GeometryMixin,
    _EmitMappingMixin,
):
    def layout(self) -> Layout:
        cells, lines, blocks, approach_box = assemble(
            self.resolved, self.geometry, build_context(self)
        )
        title_right = max(
            (c.x + c.w / 2 + _title_w(c.text) / 2 for c in cells if c.kind == "colheader"),
            default=self.total_w,
        )
        right_overhang = max(0.0, title_right - self.total_w)

        return Layout(
            self.total_w,
            self.total_h,
            lines,
            blocks,
            cells,
            freeze_x=self.node_edge + GAP - PAD,
            freeze_y=self.branch_top_y + GAP + GRIP_BAND - PAD,
            right_overhang=right_overhang,
            identities=self.resolved.col_ids,
            approach_box=approach_box,
            pretransform=bool(self.size_factor) or self.resolved.scalars.prescaler_is_matrix,
        )


def assemble(resolved, geometry, ctx):
    cells: list[CellBox] = []
    lines: list[Line] = []
    blocks: list[Block] = []
    region_boxes: list[Block] = []
    cells.extend(emit_headers(resolved, geometry, ctx).cells)
    cells.extend(emit_counts_row(resolved, geometry, ctx).cells)
    cells.extend(emit_units(resolved, geometry, ctx).cells)
    cells.extend(emit_quantities_row(resolved, geometry, ctx).cells)
    cells.extend(emit_column_plus_controls(resolved, geometry).cells)
    cells.extend(emit_rehomed_minus_controls(resolved, geometry, ctx).cells)
    cells.extend(emit_mapping(resolved, geometry, ctx).cells)
    cells.extend(emit_projection_band(resolved, geometry, ctx).cells)
    cells.extend(emit_canon_band(resolved, geometry, ctx).cells)
    cells.extend(emit_vectors(resolved, geometry, ctx).cells)
    cells.extend(emit_superspace_rows(resolved, geometry, ctx).cells)
    cells.extend(emit_identity_objects(resolved, geometry, ctx).cells)
    tuning = emit_tuning(resolved, geometry, ctx)
    cells.extend(tuning.cells)
    region_boxes.extend(tuning.region_boxes)
    cells.extend(emit_brackets(resolved, geometry, ctx).cells)
    decorations = emit_decorations(
        resolved,
        geometry,
        ctx,
        region_boxes,
        tuning.extra["gtm_box"],
        tuning.extra["opt_box"],
        tuning.extra["approach_frame"],
    )
    cells.extend(decorations.cells)
    lines.extend(decorations.lines)
    blocks.extend(decorations.blocks)
    controls = emit_controls(resolved, geometry, ctx)
    cells.extend(controls.cells)
    blocks.extend(controls.blocks)
    cells.extend(emit_ebk_frames_and_marks(resolved, geometry, ctx, cells).cells)
    cells.extend(emit_tile_toggles(geometry, ctx).cells)
    cells = list(transform_cells(cells, resolved, geometry, ctx))
    return tuple(cells), tuple(lines), tuple(blocks), tuning.extra["approach_box"]


def build(state, settings=None, collapsed=None, **inputs) -> Layout:
    return _GridBuilder(state, settings=settings, collapsed=collapsed, **inputs).layout()


def resolve(state, settings=None, collapsed=None, **inputs) -> Resolved:
    return Resolver(
        state, settings=settings, collapsed=collapsed, resolve_only=True, **inputs
    ).resolved
