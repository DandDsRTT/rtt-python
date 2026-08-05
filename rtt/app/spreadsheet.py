from __future__ import annotations

from rtt.app.layout import Block, Cell, Layout, Line
from rtt.app.spreadsheet_audio import annotate_aria, assign_audio, assign_matrix, assign_pump
from rtt.app.spreadsheet_brackets import emit_brackets, emit_ebk_frames_and_marks
from rtt.app.spreadsheet_constants import (
    GAP,
    GRIP_BAND,
    GRIP_BAND_STUB,
    PAD,
)
from rtt.app.spreadsheet_controls import (
    emit_controls,
    emit_tile_toggles,
    transform_cells,
)
from rtt.app.spreadsheet_decorations import emit_decorations
from rtt.app.spreadsheet_emit_mapping import (
    emit_canonical_band,
    emit_mapping,
    emit_projection_band,
)
from rtt.app.spreadsheet_emit_matrix import (
    emit_band_grips,
    emit_column_plus_controls,
    emit_counts_row,
    emit_headers,
    emit_quantities_row,
    emit_rehomed_minus_controls,
    emit_subrow_grips,
    emit_units,
)
from rtt.app.spreadsheet_emit_model import build_context
from rtt.app.spreadsheet_emit_tuning import emit_tuning
from rtt.app.spreadsheet_emit_vectors import (
    emit_identity_objects,
    emit_superspace_rows,
    emit_vectors,
)
from rtt.app.spreadsheet_resolve import Resolver
from rtt.app.spreadsheet_resolved import Resolved
from rtt.app.spreadsheet_text import (
    _title_w,
)


class _GridBuilder(Resolver):
    def layout(self) -> Layout:
        geometry = self.geometry
        cells, lines, blocks, approach_panel = assemble(
            self.resolved, geometry, build_context(self)
        )
        title_right = max(
            (c.x + c.width / 2 + _title_w(c.text) / 2 for c in cells if c.kind == "column_header"),
            default=geometry.total_width,
        )
        right_overhang = max(0.0, title_right - geometry.total_width)

        return Layout(
            geometry.total_width,
            geometry.total_height,
            lines,
            blocks,
            cells,
            freeze_x=geometry.node_edge + GAP + GRIP_BAND + GRIP_BAND_STUB - PAD,
            freeze_y=geometry.branch_top_y + GAP + GRIP_BAND + GRIP_BAND_STUB - PAD,
            right_overhang=right_overhang,
            identities=self.resolved.column_ids,
            approach_panel=approach_panel,
            pretransform=bool(geometry.size_factor) or self.resolved.scalars.prescaler_is_matrix,
        )


def _drop_disabled_controls(cells, settings):
    grips = not settings.get("reorder_grips", True)
    folds = not settings.get("rowcol_collapse", True)
    buttons = not settings.get("add_remove_buttons", True)
    if not (grips or folds or buttons):
        return cells

    def keep(kind: str) -> bool:
        if grips and kind in (
            "subcolumngrip",
            "subrowgrip",
            "rowgrip",
            "columngrip",
            "colgap",
            "rowgap",
            "element_reorder",
        ):
            return False
        if folds and kind in ("rowtoggle", "columntoggle", "alltoggle"):
            return False
        return not (buttons and (kind in ("plus", "minus") or kind.endswith(("_plus", "_minus"))))

    return [cell for cell in cells if keep(cell.kind)]


def assemble(resolved, geometry, context):
    cells: list[Cell] = []
    lines: list[Line] = []
    blocks: list[Block] = []
    region_panels: list[Block] = []
    cells.extend(emit_headers(resolved, geometry, context).cells)
    cells.extend(emit_band_grips(resolved, geometry, context).cells)
    cells.extend(emit_subrow_grips(resolved, geometry, context).cells)
    cells.extend(emit_counts_row(resolved, geometry, context).cells)
    cells.extend(emit_units(resolved, geometry, context).cells)
    cells.extend(emit_quantities_row(resolved, geometry, context).cells)
    cells.extend(emit_column_plus_controls(resolved, geometry).cells)
    cells.extend(emit_rehomed_minus_controls(resolved, geometry, context).cells)
    cells.extend(emit_mapping(resolved, geometry, context).cells)
    cells.extend(emit_projection_band(resolved, geometry, context).cells)
    cells.extend(emit_canonical_band(resolved, geometry, context).cells)
    cells.extend(emit_vectors(resolved, geometry, context).cells)
    cells.extend(emit_superspace_rows(resolved, geometry, context).cells)
    cells.extend(emit_identity_objects(resolved, geometry, context).cells)
    tuning = emit_tuning(resolved, geometry, context)
    cells.extend(tuning.cells)
    region_panels.extend(tuning.region_panels)
    cells = _drop_disabled_controls(cells, context.settings)
    assign_audio(cells, resolved, geometry)
    assign_pump(cells, resolved, context)
    assign_matrix(cells, resolved, geometry)
    annotate_aria(cells, geometry)
    cells.extend(emit_brackets(resolved, geometry, context).cells)
    decorations = emit_decorations(
        resolved,
        geometry,
        context,
        region_panels,
        tuning.extra["tuning_ranges_panel"],
        tuning.extra["optimization_panel"],
    )
    cells.extend(decorations.cells)
    lines.extend(decorations.lines)
    blocks.extend(decorations.blocks)
    controls = emit_controls(resolved, geometry, context)
    cells.extend(controls.cells)
    blocks.extend(controls.blocks)
    cells.extend(emit_ebk_frames_and_marks(resolved, geometry, context, cells).cells)
    cells.extend(emit_tile_toggles(geometry, context).cells)
    cells = list(transform_cells(cells, resolved, geometry, context))
    return tuple(cells), tuple(lines), tuple(blocks), tuning.extra["approach_panel"]


def build(state, settings=None, collapsed=None, **inputs) -> Layout:
    return _GridBuilder(state, settings=settings, collapsed=collapsed, **inputs).layout()


def resolve(state, settings=None, collapsed=None, **inputs) -> Resolved:
    return Resolver(
        state, settings=settings, collapsed=collapsed, resolve_only=True, **inputs
    ).resolved
