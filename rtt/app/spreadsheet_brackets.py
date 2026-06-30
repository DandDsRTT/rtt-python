from __future__ import annotations

import functools

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BRACE_HEIGHT,
    BRACKET_WIDTH,
    COLUMN_WIDTH,
    FRAME_GAP,
    FRAME_HEIGHT,
    FRAME_OVERHANG,
    MARK_INSET,
    ROW_HEIGHT,
    SEP_WIDTH,
    TRANSPOSE_WIDTH,
    V_SPLIT_GAP,
    VAL_BRACKET_HEIGHT,
)
from rtt.app.spreadsheet_emit_model import EmitResult


def emit_brackets(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_canon_stacked_brackets(cells, resolved, geometry, context)
    _emit_canon_fit_brackets(cells, resolved, geometry, context)
    _emit_projection_brackets(cells, resolved, geometry, context)
    _emit_mapping_brackets(cells, resolved, geometry, context)
    _emit_superspace_stacked_brackets(cells, resolved, geometry, context)
    _emit_superspace_projection_fit_brackets(cells, resolved, geometry, context)
    _emit_superspace_rest_brackets(cells, resolved, geometry, context)
    _emit_vector_stacked_brackets(cells, resolved, geometry, context)
    _emit_superspace_vectors_list_brackets(cells, resolved, geometry, context)
    _emit_superspace_mapped_list_brackets(cells, resolved, geometry, context)
    _emit_vector_list_brackets(cells, resolved, geometry, context)
    _emit_prescaling_brackets(cells, resolved, geometry, context)
    _emit_scalar_row_brackets(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def emit_ebk_frames_and_marks(resolved, geometry, context, accum) -> EmitResult:
    cells: list = []
    _emit_ebk_frames(cells, resolved, geometry, context)
    _emit_ebk_marks(cells, resolved, geometry, context)
    _emit_ebk_vector_marks(cells, resolved, geometry, context, accum)
    return EmitResult(cells=tuple(cells))


def bracket(cells, resolved, geometry, bid: str, row_key: str, column_key: str, y, height, *, fit=False, span=None,
            pending=False, stacked=False) -> None:
    if not resolved.flags.ebk:
        if stacked:
            return
        glyphs = ("[", "]")
    else:
        c = _ebk(resolved, row_key, column_key)
        glyphs = (c.inner_open, c.inner_close) if stacked else (c.outer_open, c.outer_close)
    matrix_x, matrix_width = span if span else query.matrix_span(geometry, resolved, column_key)
    if fit and not resolved.flags.ebk:
        bracket_y, bracket_height = y, height
    elif fit:
        bracket_y = y - (FRAME_HEIGHT + FRAME_GAP) - FRAME_OVERHANG
        bracket_height = height + (FRAME_HEIGHT + FRAME_GAP) + (FRAME_GAP + BRACE_HEIGHT) + 2 * FRAME_OVERHANG
    else:
        bracket_y, bracket_height = y + (height - VAL_BRACKET_HEIGHT) / 2, VAL_BRACKET_HEIGHT
    cells.append(CellBox(f"bracket:{bid}:l", matrix_x, bracket_y, BRACKET_WIDTH, bracket_height, "bracket", text=glyphs[0], pending=pending))
    cells.append(CellBox(f"bracket:{bid}:r", matrix_x + matrix_width - BRACKET_WIDTH, bracket_y, BRACKET_WIDTH, bracket_height, "bracket", text=glyphs[1], pending=pending))


def _ebk(resolved, row_key, column_key):
    return service.ebk_convention(row_key, column_key, superspace=resolved.flags.superspace)


def _ebk_foot(resolved, row_key, column_key, *, outer: bool) -> str:
    c = _ebk(resolved, row_key, column_key)
    return "ebkbrace" if (c.outer_close if outer else c.inner_close) == "}" else "ebkangle"


def matrix_frame(cells, resolved, geometry, context, row_key: str, column_key: str, bid: str, span=None) -> None:
    if not query.tile_open(geometry, context.collapsed, row_key, column_key):
        return
    foot = _ebk_foot(resolved, row_key, column_key, outer=True)
    matrix_x, matrix_width = span if span else query.matrix_span(geometry, resolved, column_key)
    if not resolved.flags.ebk:
        y, height = geometry.rows[row_key].y, geometry.rows[row_key].height
        cells.append(CellBox(f"bracket:{bid}:l", matrix_x, y, BRACKET_WIDTH, height, "bracket", text="["))
        cells.append(CellBox(f"bracket:{bid}:r", matrix_x + matrix_width - BRACKET_WIDTH, y, BRACKET_WIDTH, height, "bracket", text="]"))
        return
    cells.append(CellBox(f"ebktop:{bid}", matrix_x, query.frame_top_y(geometry, row_key), matrix_width, FRAME_HEIGHT, "ebktop"))
    cells.append(CellBox(f"{foot}:{bid}", matrix_x, query.frame_brace_y(geometry, row_key), matrix_width, BRACE_HEIGHT, foot))


def vector_list_marks(cells, resolved, geometry, context, row_key, name, column_key, left, n_cols, top="ebktop",
                      separators=True, pending_col=-1) -> None:
    if not query.tile_open(geometry, context.collapsed, row_key, column_key):
        return
    foot = _ebk_foot(resolved, row_key, column_key, outer=False)
    if resolved.flags.ebk:
        mark_width = COLUMN_WIDTH - 2 * MARK_INSET
        for c in range(n_cols):
            mark_x = left(c) + MARK_INSET
            pend = (c == pending_col)
            cells.append(CellBox(f"{top}:{name}:{c}", mark_x, query.frame_top_y(geometry, row_key), mark_width, FRAME_HEIGHT, top, pending=pend))
            cells.append(CellBox(f"{foot}:{name}:{c}", mark_x, query.frame_brace_y(geometry, row_key), mark_width, BRACE_HEIGHT, foot, pending=pend))
    elif n_cols:
        if column_key == "interest":
            for c in range(n_cols):
                transpose_mark(cells, geometry, f"{name}:{c}", left(c) + COLUMN_WIDTH - MARK_INSET, row_key, pending=(c == pending_col))
        else:
            matrix_x, matrix_width = query.matrix_span(geometry, resolved, column_key)
            transpose_mark(cells, geometry, name, matrix_x + matrix_width, row_key)
    if not separators:
        return
    sep_y, sep_height = query.separator_span(resolved, geometry, row_key)
    for c in range(1, n_cols):
        cells.append(CellBox(f"sep:{name}:{c}", (left(c - 1) + COLUMN_WIDTH + left(c)) / 2 - SEP_WIDTH / 2, sep_y, SEP_WIDTH, sep_height, "vbar"))


def transpose_mark(cells, geometry, name, x, row_key, pending: bool = False) -> None:
    cells.append(CellBox(f"transpose:{name}", x, geometry.rows[row_key].y - FRAME_GAP, TRANSPOSE_WIDTH, ROW_HEIGHT,
                         "transpose", text="ᵀ", pending=pending))


def v_split_bars(cells, resolved, geometry, context, accum) -> None:
    if not resolved.unchanged.shown or geometry.commas_x is None or resolved.dims.comma_count_shown == 0 or resolved.dims.unchanged_count == 0:
        return
    x = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown) - V_SPLIT_GAP / 2 - SEP_WIDTH / 2
    u_left = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown)
    u_right = u_left + resolved.dims.unchanged_count * COLUMN_WIDTH
    rows_with_u = set()
    for cell in accum:
        if u_left - 0.5 <= cell.x < u_right:
            for row_key, band in geometry.rows.items():
                if band.y <= cell.y < band.y + band.height:
                    rows_with_u.add(row_key)
                    break
    for row_key in rows_with_u:
        if row_key != "counts" and query.tile_open(geometry, context.collapsed, row_key, "commas"):
            sy, sh = query.separator_span(resolved, geometry, row_key)
            cells.append(CellBox(f"vsplit:{row_key}", x, sy, SEP_WIDTH, sh, "vbar"))


def _emit_canon_stacked_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "canon") and query.tile_open(geometry, collapsed, "canon", "primes"):
        for i in range(resolved.dims.canonical_rank):
            bracket(cells, resolved, geometry, f"canon:map:{i}", "canon", "primes", query.canon_top(geometry, i), ROW_HEIGHT, stacked=True)
            bracket(cells, resolved, geometry, f"form:map:{i}", "canon", "gens", query.canon_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.row_open(geometry, collapsed, "canon") and query.tile_open(geometry, collapsed, "canon", "canongens"):
        for i in range(resolved.dims.canonical_rank):
            bracket(cells, resolved, geometry, f"fcancel:map:{i}", "canon", "canongens", query.canon_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.tile_open(geometry, collapsed, "mapping", "canongens"):
        for i in range(resolved.dims.rank):
            bracket(cells, resolved, geometry, f"finv:map:{i}", "mapping", "canongens", query.map_top(geometry, i), ROW_HEIGHT, stacked=True)


def _emit_canon_fit_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if not query.row_open(geometry, collapsed, "canon"):
        return
    canon_y, canon_height = (geometry.rows["canon"].y if "canon" in geometry.rows else 0), resolved.dims.canonical_rank * ROW_HEIGHT
    if query.tile_open(geometry, collapsed, "canon", "detempering"):
        bracket(cells, resolved, geometry, "canon_detempering", "canon", "detempering", canon_y, canon_height, fit=True)
    if query.tile_open(geometry, collapsed, "canon", "commas"):
        bracket(cells, resolved, geometry, "canon_comma", "canon", "commas", canon_y, canon_height, fit=True)
    if query.tile_open(geometry, collapsed, "canon", "targets"):
        bracket(cells, resolved, geometry, "canon_mapped", "canon", "targets", canon_y, canon_height, fit=True)
    if resolved.dims.held_count and query.tile_open(geometry, collapsed, "canon", "held"):
        bracket(cells, resolved, geometry, "canon_hmapped", "canon", "held", canon_y, canon_height, fit=True)


def _emit_projection_brackets(cells, resolved, geometry, context) -> None:
    if not query.row_open(geometry, context.collapsed, "projection"):
        return
    _emit_projection_embed_brackets(cells, resolved, geometry, context)
    _emit_projection_list_brackets(cells, resolved, geometry, context)


def _emit_projection_embed_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    py, ph = geometry.rows["projection"].y, resolved.dims.dimensionality * ROW_HEIGHT
    if query.tile_open(geometry, collapsed, "projection", "primes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"projection:{i}", "projection", "primes", query.projection_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.tile_open(geometry, collapsed, "projection", "gens"):
        bracket(cells, resolved, geometry, "embed", "projection", "gens", py, ph, fit=True)
    if query.tile_open(geometry, collapsed, "projection", "canongens"):
        bracket(cells, resolved, geometry, "embed_c", "projection", "canongens", py, ph, fit=True)
    if query.tile_open(geometry, collapsed, "projection", "superspace_generators"):
        bracket(cells, resolved, geometry, "embed_sl", "projection", "superspace_generators", py, ph, fit=True)


def _emit_projection_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    py, ph = geometry.rows["projection"].y, resolved.dims.dimensionality * ROW_HEIGHT
    if query.tile_open(geometry, collapsed, "projection", "superspace_primes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"projection_superspace:{i}", "projection", "superspace_primes", query.projection_top(geometry, i), ROW_HEIGHT, stacked=True)
    if resolved.unchanged.shown and query.tile_open(geometry, collapsed, "projection", "commas"):
        bracket(cells, resolved, geometry, "projection_vectors", "projection", "commas", py, ph, fit=True)
    if query.tile_open(geometry, collapsed, "projection", "detempering"):
        bracket(cells, resolved, geometry, "projection_detempering", "projection", "detempering", py, ph, fit=True)
    if query.tile_open(geometry, collapsed, "projection", "targets"):
        bracket(cells, resolved, geometry, "projection_targets", "projection", "targets", py, ph, fit=True)
    if query.tile_open(geometry, collapsed, "projection", "held"):
        bracket(cells, resolved, geometry, "projection_held", "projection", "held", py, ph, fit=True)


def _emit_mapping_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "scaling_factors") and query.tile_open(geometry, collapsed, "scaling_factors", "commas"):
        bracket(cells, resolved, geometry, "scaling", "scaling_factors", "commas", geometry.rows["scaling_factors"].y, ROW_HEIGHT)
    if query.row_open(geometry, collapsed, "mapping"):
        if query.tile_open(geometry, collapsed, "mapping", "primes"):
            for i in range(resolved.dims.rank):
                bracket(cells, resolved, geometry, f"map:{i}", "mapping", "primes", query.map_top(geometry, i), ROW_HEIGHT, stacked=True)
            if context.pending_mapping_row is not None:
                bracket(cells, resolved, geometry, "map:pending", "mapping", "primes", query.map_top(geometry, resolved.dims.rank), ROW_HEIGHT, pending=True, stacked=True)
        if query.tile_open(geometry, collapsed, "mapping", "commas"):
            bracket(cells, resolved, geometry, "mapped_comma", "mapping", "commas", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_HEIGHT, fit=True)
        if query.tile_open(geometry, collapsed, "mapping", "targets"):
            bracket(cells, resolved, geometry, "mapped", "mapping", "targets", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_HEIGHT, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, collapsed, "mapping", "held"):
            bracket(cells, resolved, geometry, "hmapped", "mapping", "held", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_HEIGHT, fit=True)


def _emit_superspace_stacked_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "superspace_primes"):
        for i in range(resolved.dims.superspace_rank):
            bracket(cells, resolved, geometry, f"superspace_map:{i}", "superspace_mapping", "superspace_primes", query.superspace_map_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.row_open(geometry, collapsed, "superspace_projection") and query.tile_open(geometry, collapsed, "superspace_projection", "superspace_primes"):
        for i in range(resolved.dims.superspace_dimensionality):
            bracket(cells, resolved, geometry, f"superspace_projection:{i}", "superspace_projection", "superspace_primes", query.superspace_projection_top(geometry, i), ROW_HEIGHT, stacked=True)


def _emit_superspace_projection_fit_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    superspace_projection_top, superspace_projection_height = (geometry.rows["superspace_projection"].y if "superspace_projection" in geometry.rows else 0), resolved.dims.superspace_dimensionality * ROW_HEIGHT
    if query.row_open(geometry, collapsed, "superspace_projection"):
        if query.tile_open(geometry, collapsed, "superspace_projection", "superspace_generators"):
            bracket(cells, resolved, geometry, "superspace_embed", "superspace_projection", "superspace_generators", superspace_projection_top, superspace_projection_height, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_projection", "primes"):
            bracket(cells, resolved, geometry, "superspace_projection_basis_lift", "superspace_projection", "primes", superspace_projection_top, superspace_projection_height, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_projection", "detempering"):
            bracket(cells, resolved, geometry, "superspace_projection_detempering", "superspace_projection", "detempering", superspace_projection_top, superspace_projection_height, fit=True)
        if resolved.unchanged.shown and query.tile_open(geometry, collapsed, "superspace_projection", "commas"):
            bracket(cells, resolved, geometry, "superspace_projection_vectors", "superspace_projection", "commas", superspace_projection_top, superspace_projection_height, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_projection", "targets"):
            bracket(cells, resolved, geometry, "superspace_projection_targets", "superspace_projection", "targets", superspace_projection_top, superspace_projection_height, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_projection", "held"):
            bracket(cells, resolved, geometry, "superspace_projection_held", "superspace_projection", "held", superspace_projection_top, superspace_projection_height, fit=True)


def _emit_superspace_rest_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_vectors") and query.tile_open(geometry, collapsed, "superspace_vectors", "superspace_primes"):
        for i in range(resolved.dims.superspace_dimensionality):
            bracket(cells, resolved, geometry, f"superspace_vector_ji_map:{i}", "superspace_vectors", "superspace_primes", query.superspace_vector_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "primes"):
        for i in range(resolved.dims.superspace_rank):
            bracket(cells, resolved, geometry, f"superspace_mapping_lift:{i}", "superspace_mapping", "primes", query.superspace_map_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "superspace_generators"):
        bracket(cells, resolved, geometry, "superspace_self_map", "superspace_mapping", "superspace_generators",
                geometry.rows["superspace_mapping"].y, resolved.dims.superspace_rank * ROW_HEIGHT, fit=True)


def _emit_vector_stacked_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.tile_open(geometry, collapsed, "vectors", "primes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"vector:primes:{i}", "vectors", "primes", query.vector_top(geometry, i), ROW_HEIGHT, stacked=True)
    if query.tile_open(geometry, collapsed, "mapping", "gens"):
        bracket(cells, resolved, geometry, "selfmap", "mapping", "gens",
                geometry.rows["mapping"].y, resolved.dims.rank * ROW_HEIGHT, fit=True)
    if query.tile_open(geometry, collapsed, "mapping", "detempering"):
        bracket(cells, resolved, geometry, "mapped_detempering", "mapping", "detempering",
                geometry.rows["mapping"].y, resolved.dims.rank * ROW_HEIGHT, fit=True)


def _emit_superspace_vectors_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_vectors"):
        if query.tile_open(geometry, collapsed, "superspace_vectors", "primes"):
            bracket(cells, resolved, geometry, "superspace_vector:primes", "superspace_vectors", "primes", geometry.rows["superspace_vectors"].y, resolved.dims.superspace_dimensionality * ROW_HEIGHT, fit=True)
        for group in ("commas", "targets"):
            if query.tile_open(geometry, collapsed, "superspace_vectors", group):
                bracket(cells, resolved, geometry, f"superspace_vector:{group}", "superspace_vectors", group, geometry.rows["superspace_vectors"].y, resolved.dims.superspace_dimensionality * ROW_HEIGHT, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, collapsed, "superspace_vectors", "held"):
            bracket(cells, resolved, geometry, "superspace_vector:held", "superspace_vectors", "held", geometry.rows["superspace_vectors"].y, resolved.dims.superspace_dimensionality * ROW_HEIGHT, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_vectors", "detempering"):
            bracket(cells, resolved, geometry, "superspace_vector:detempering", "superspace_vectors", "detempering", geometry.rows["superspace_vectors"].y, resolved.dims.superspace_dimensionality * ROW_HEIGHT, fit=True)


def _emit_superspace_mapped_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_mapping"):
        for group in ("commas", "targets"):
            if query.tile_open(geometry, collapsed, "superspace_mapping", group):
                bracket(cells, resolved, geometry, f"superspace_mapped:{group}", "superspace_mapping", group, geometry.rows["superspace_mapping"].y, resolved.dims.superspace_rank * ROW_HEIGHT, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, collapsed, "superspace_mapping", "held"):
            bracket(cells, resolved, geometry, "superspace_mapped:held", "superspace_mapping", "held", geometry.rows["superspace_mapping"].y, resolved.dims.superspace_rank * ROW_HEIGHT, fit=True)
        if query.tile_open(geometry, collapsed, "superspace_mapping", "detempering"):
            bracket(cells, resolved, geometry, "superspace_mapped:detempering", "superspace_mapping", "detempering", geometry.rows["superspace_mapping"].y, resolved.dims.superspace_rank * ROW_HEIGHT, fit=True)


def _emit_vector_list_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "vectors"):
        for group in ("commas", "targets"):
            if query.tile_open(geometry, collapsed, "vectors", group):
                bracket(cells, resolved, geometry, f"vector:{group}", "vectors", group, geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_HEIGHT, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, collapsed, "vectors", "held"):
            bracket(cells, resolved, geometry, "vector:held", "vectors", "held", geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_HEIGHT, fit=True)
        if query.tile_open(geometry, collapsed, "vectors", "detempering"):
            bracket(cells, resolved, geometry, "vector:detempering", "vectors", "detempering", geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_HEIGHT, fit=True)


def _emit_prescaling_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "prescaling"):
        ph = (geometry.prescale_rows + geometry.size_rows) * ROW_HEIGHT + query.prescale_size_gap(geometry)
        bare_col = "superspace_primes" if resolved.flags.superspace else "primes"
        for group in ("commas", "detempering", "targets", "held"):
            if query.tile_open(geometry, collapsed, "prescaling", group):
                bracket(cells, resolved, geometry, f"prescaling:{group}", "prescaling", group,
                        geometry.rows["prescaling"].y, ph, fit=True)
        if resolved.flags.superspace and query.tile_open(geometry, collapsed, "prescaling", "primes"):
            bracket(cells, resolved, geometry, "prescaling:primes", "prescaling", "primes",
                    geometry.rows["prescaling"].y, ph, fit=True)
        if query.tile_open(geometry, collapsed, "prescaling", bare_col):
            pspan = query.matrix_span(geometry, resolved, bare_col)
            for i in range(geometry.prescale_rows + geometry.size_rows):
                bracket(cells, resolved, geometry, f"prescaling:row:{i}", "prescaling", bare_col,
                        query.subrow_top(geometry, "prescaling", i), ROW_HEIGHT, span=pspan, stacked=True)
            if geometry.size_rows:
                matrix_x, matrix_width = pspan
                bar_y = geometry.rows["prescaling"].y + geometry.prescale_rows * ROW_HEIGHT + query.prescale_size_gap(geometry) / 2 - SEP_WIDTH / 2
                cells.append(CellBox("bar:prescaling", matrix_x, bar_y, matrix_width, SEP_WIDTH, "hbar"))


def _emit_scalar_row_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    _emit_tuning_map_brackets(cells, resolved, geometry, context)
    for key in ("tuning", "just", "retune", "complexity"):
        if query.row_open(geometry, collapsed, key):
            _emit_list_row_brackets(cells, resolved, geometry, context, key)
    if query.tile_open(geometry, collapsed, "weight", "targets"):
        bracket(cells, resolved, geometry, "weight", "weight", "targets", geometry.rows["weight"].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, "damage", "targets"):
        bracket(cells, resolved, geometry, "damage", "damage", "targets", geometry.rows["damage"].y, ROW_HEIGHT)


def _emit_tuning_map_brackets(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.tile_open(geometry, collapsed, "tuning", "gens"):
        bracket(cells, resolved, geometry, "tuning:genmap", "tuning", "gens", geometry.rows["tuning"].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, "tuning", "canongens"):
        bracket(cells, resolved, geometry, "tuning:cangenmap", "tuning", "canongens", geometry.rows["tuning"].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, "tuning", "detempering"):
        bracket(cells, resolved, geometry, "tuning:detempering", "tuning", "detempering", geometry.rows["tuning"].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, "tuning", "superspace_generators"):
        bracket(cells, resolved, geometry, "tuning:superspace_generator_map", "tuning", "superspace_generators", geometry.rows["tuning"].y, ROW_HEIGHT)


def _emit_list_row_brackets(cells, resolved, geometry, context, key: str) -> None:
    collapsed = context.collapsed
    if query.tile_open(geometry, collapsed, key, "primes"):
        bracket(cells, resolved, geometry, f"{key}:map", key, "primes", geometry.rows[key].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, key, "commas"):
        bracket(cells, resolved, geometry, f"{key}:commalist", key, "commas", geometry.rows[key].y, ROW_HEIGHT)
    if query.tile_open(geometry, collapsed, key, "targets"):
        bracket(cells, resolved, geometry, f"{key}:list", key, "targets", geometry.rows[key].y, ROW_HEIGHT)
    if resolved.dims.held_count and query.tile_open(geometry, collapsed, key, "held"):
        bracket(cells, resolved, geometry, f"{key}:hlist", key, "held", geometry.rows[key].y, ROW_HEIGHT)
    if key != "tuning" and query.tile_open(geometry, collapsed, key, "detempering"):
        bracket(cells, resolved, geometry, f"{key}:detemperinglist", key, "detempering", geometry.rows[key].y, ROW_HEIGHT)
    if (key != "complexity" or resolved.flags.superspace) and query.tile_open(geometry, collapsed, key, "superspace_primes"):
        bracket(cells, resolved, geometry, f"{key}:superspace_primes", key, "superspace_primes", geometry.rows[key].y, ROW_HEIGHT)


def _emit_ebk_frames(cells, resolved, geometry, context) -> None:
    matrix_frame(cells, resolved, geometry, context, "mapping", "primes", "primes")
    matrix_frame(cells, resolved, geometry, context, "projection", "primes", "projection")
    matrix_frame(cells, resolved, geometry, context, "projection", "superspace_primes", "projection_superspace")
    matrix_frame(cells, resolved, geometry, context, "canon", "primes", "canon")
    matrix_frame(cells, resolved, geometry, context, "canon", "gens", "form")
    matrix_frame(cells, resolved, geometry, context, "canon", "canongens", "fcancel")
    matrix_frame(cells, resolved, geometry, context, "mapping", "canongens", "finv")
    matrix_frame(cells, resolved, geometry, context, "prescaling", "superspace_primes" if resolved.flags.superspace else "primes", "prescaling")
    matrix_frame(cells, resolved, geometry, context, "superspace_mapping", "superspace_primes", "superspace_mapping")
    matrix_frame(cells, resolved, geometry, context, "superspace_projection", "superspace_primes", "superspace_projection")
    matrix_frame(cells, resolved, geometry, context, "superspace_vectors", "superspace_primes", "superspace_vector_ji_map")
    matrix_frame(cells, resolved, geometry, context, "superspace_mapping", "primes", "superspace_mapping_lift")
    matrix_frame(cells, resolved, geometry, context, "vectors", "primes", "vector:primes")


def _emit_ebk_marks(cells, resolved, geometry, context) -> None:
    gl = _left_fns(resolved, geometry)
    mark_vector_list = functools.partial(vector_list_marks, cells, resolved, geometry, context)
    mark_vector_list("mapping", "mapped_comma", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("projection", "projection_vectors", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("projection", "embed", "gens", gl["gen"], resolved.dims.rank, separators=False)
    mark_vector_list("projection", "embed_c", "canongens", gl["canongen"], resolved.dims.canonical_rank, separators=False)
    mark_vector_list("projection", "embed_sl", "superspace_generators", gl["superspace_gen"], resolved.dims.superspace_rank, separators=False)
    mark_vector_list("projection", "projection_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    mark_vector_list("projection", "projection_targets", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("projection", "projection_held", "held", gl["held"], resolved.dims.held_count)
    mark_vector_list("projection", "projection_interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("superspace_projection", "superspace_embed", "superspace_generators", gl["superspace_gen"], resolved.dims.superspace_rank, separators=False)
    mark_vector_list("superspace_projection", "superspace_projection_basis_lift", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    mark_vector_list("superspace_projection", "superspace_projection_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    mark_vector_list("superspace_projection", "superspace_projection_vectors", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("superspace_projection", "superspace_projection_targets", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("superspace_projection", "superspace_projection_held", "held", gl["held"], resolved.dims.held_count)
    mark_vector_list("superspace_projection", "superspace_projection_interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("mapping", "mapped", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("mapping", "imapped", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("mapping", "hmapped", "held", gl["held"], resolved.dims.held_count)
    mark_vector_list("mapping", "selfmap", "gens", gl["gen"], resolved.dims.rank, separators=False)
    mark_vector_list("mapping", "mapped_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    mark_vector_list("canon", "canon_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    mark_vector_list("canon", "canon_comma", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("canon", "canon_mapped", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("canon", "canon_imapped", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("canon", "canon_hmapped", "held", gl["held"], resolved.dims.held_count)


def _emit_ebk_vector_marks(cells, resolved, geometry, context, accum) -> None:
    gl = _left_fns(resolved, geometry)
    mark_vector_list = functools.partial(vector_list_marks, cells, resolved, geometry, context)
    mark_vector_list("vectors", "vector:commas", "commas", gl["comma"], resolved.dims.vector_count_shown, separators=False,
        pending_col=(resolved.dims.comma_count if resolved.commas.pending is not None else -1))
    mark_vector_list("vectors", "vector:targets", "targets", gl["target"], resolved.dims.target_count_shown,
        pending_col=(resolved.dims.target_count if resolved.targets.pending is not None else -1))
    mark_vector_list("vectors", "vector:interest", "interest", gl["interest"], resolved.dims.interest_count_shown, separators=False,
        pending_col=(resolved.dims.interest_count if resolved.interest.pending is not None else -1))
    mark_vector_list("vectors", "vector:held", "held", gl["held"], resolved.dims.held_count_shown,
        pending_col=(resolved.dims.held_count if resolved.held.pending is not None else -1))
    mark_vector_list("vectors", "vector:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    mark_vector_list("superspace_vectors", "superspace_vector:primes", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    mark_vector_list("superspace_vectors", "superspace_vector:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("superspace_vectors", "superspace_vector:targets", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("superspace_vectors", "superspace_vector:held", "held", gl["held"], resolved.dims.held_count)
    mark_vector_list("superspace_vectors", "superspace_vector:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("superspace_vectors", "superspace_vector:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    mark_vector_list("superspace_mapping", "superspace_mapped:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("superspace_mapping", "superspace_mapped:targets", "targets", gl["target"], resolved.dims.target_count)
    mark_vector_list("superspace_mapping", "superspace_mapped:held", "held", gl["held"], resolved.dims.held_count)
    if resolved.flags.superspace:
        mark_vector_list("prescaling", "prescaling:primes", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    mark_vector_list("superspace_mapping", "superspace_mapped:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    mark_vector_list("superspace_mapping", "superspace_mapped:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    mark_vector_list("superspace_mapping", "superspace_self_map", "superspace_generators", gl["superspace_gen"], resolved.dims.superspace_rank, separators=False)
    mark_vector_list("prescaling", "prescaling:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    mark_vector_list("prescaling", "prescaling:detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    mark_vector_list("prescaling", "prescaling:targets", "targets", gl["target"], resolved.dims.target_count, separators=True)
    mark_vector_list("prescaling", "prescaling:held", "held", gl["held"], resolved.dims.held_count, separators=True)
    mark_vector_list("prescaling", "prescaling:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    v_split_bars(cells, resolved, geometry, context, list(accum) + cells)


def _left_fns(resolved, geometry):
    return {
        "comma": lambda c: query.comma_left(geometry, resolved, c),
        "prime": lambda p: query.prime_left(geometry, p),
        "target": lambda j: query.target_left(geometry, j),
        "interest": lambda i: query.interest_left(geometry, i),
        "held": lambda i: query.held_left(geometry, i),
        "detempering": lambda i: query.detempering_left(geometry, i),
        "gen": lambda g: query.gen_left(geometry, g),
        "canongen": lambda g: query.canongen_left(geometry, g),
        "superspace_gen": lambda g: query.superspace_gen_left(geometry, g),
    }
