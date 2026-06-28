from __future__ import annotations

import functools

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BRACE_H,
    BRACKET_W,
    COL_W,
    FRAME_GAP,
    FRAME_H,
    FRAME_OVERHANG,
    MARK_INSET,
    ROW_H,
    SEP_W,
    TRANSPOSE_W,
    V_SPLIT_GAP,
    VAL_BRACKET_H,
)
from rtt.app.spreadsheet_emit_model import EmitResult


def emit_brackets(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_canon_stacked_brackets(cells, resolved, geometry, context)
    _emit_canon_fit_brackets(cells, resolved, geometry, context)
    _emit_projection_brackets(cells, resolved, geometry, context)
    _emit_mapping_brackets(cells, resolved, geometry, context)
    _emit_ss_stacked_brackets(cells, resolved, geometry, context)
    _emit_ss_projection_fit_brackets(cells, resolved, geometry, context)
    _emit_ss_rest_brackets(cells, resolved, geometry, context)
    _emit_vector_stacked_brackets(cells, resolved, geometry, context)
    _emit_ss_vectors_list_brackets(cells, resolved, geometry, context)
    _emit_ss_mapped_list_brackets(cells, resolved, geometry, context)
    _emit_vec_list_brackets(cells, resolved, geometry, context)
    _emit_prescaling_brackets(cells, resolved, geometry, context)
    _emit_scalar_row_brackets(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def emit_ebk_frames_and_marks(resolved, geometry, context, accum) -> EmitResult:
    cells: list = []
    _emit_ebk_frames(cells, resolved, geometry, context)
    _emit_ebk_marks(cells, resolved, geometry, context)
    _emit_ebk_vector_marks(cells, resolved, geometry, context, accum)
    return EmitResult(cells=tuple(cells))


def bracket(cells, resolved, geometry, bid: str, row_key: str, column_key: str, y, h, *, fit=False, span=None,
            pending=False, stacked=False) -> None:
    if not resolved.flags.ebk:
        if stacked:
            return
        glyphs = ("[", "]")
    else:
        c = _ebk(resolved, row_key, column_key)
        glyphs = (c.inner_open, c.inner_close) if stacked else (c.outer_open, c.outer_close)
    gx, gw = span if span else query.matrix_span(geometry, resolved, column_key)
    if fit and not resolved.flags.ebk:
        by, bh = y, h
    elif fit:
        by = y - (FRAME_H + FRAME_GAP) - FRAME_OVERHANG
        bh = h + (FRAME_H + FRAME_GAP) + (FRAME_GAP + BRACE_H) + 2 * FRAME_OVERHANG
    else:
        by, bh = y + (h - VAL_BRACKET_H) / 2, VAL_BRACKET_H
    cells.append(CellBox(f"bracket:{bid}:l", gx, by, BRACKET_W, bh, "bracket", text=glyphs[0], pending=pending))
    cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, by, BRACKET_W, bh, "bracket", text=glyphs[1], pending=pending))


def _ebk(resolved, row_key, column_key):
    return service.ebk_convention(row_key, column_key, superspace=resolved.flags.superspace)


def _ebk_foot(resolved, row_key, column_key, *, outer: bool) -> str:
    c = _ebk(resolved, row_key, column_key)
    return "ebkbrace" if (c.outer_close if outer else c.inner_close) == "}" else "ebkangle"


def matrix_frame(cells, resolved, geometry, context, row_key: str, column_key: str, bid: str, span=None) -> None:
    if not query.tile_open(geometry, context.collapsed, row_key, column_key):
        return
    foot = _ebk_foot(resolved, row_key, column_key, outer=True)
    gx, gw = span if span else query.matrix_span(geometry, resolved, column_key)
    if not resolved.flags.ebk:
        y, h = geometry.rows[row_key].y, geometry.rows[row_key].h
        cells.append(CellBox(f"bracket:{bid}:l", gx, y, BRACKET_W, h, "bracket", text="["))
        cells.append(CellBox(f"bracket:{bid}:r", gx + gw - BRACKET_W, y, BRACKET_W, h, "bracket", text="]"))
        return
    cells.append(CellBox(f"ebktop:{bid}", gx, query.frame_top_y(geometry, row_key), gw, FRAME_H, "ebktop"))
    cells.append(CellBox(f"{foot}:{bid}", gx, query.frame_brace_y(geometry, row_key), gw, BRACE_H, foot))


def vector_list_marks(cells, resolved, geometry, context, row_key, name, column_key, left, n_cols, top="ebktop",
                      separators=True, pending_col=-1) -> None:
    if not query.tile_open(geometry, context.collapsed, row_key, column_key):
        return
    foot = _ebk_foot(resolved, row_key, column_key, outer=False)
    if resolved.flags.ebk:
        mark_w = COL_W - 2 * MARK_INSET
        for c in range(n_cols):
            mx = left(c) + MARK_INSET
            pend = (c == pending_col)
            cells.append(CellBox(f"{top}:{name}:{c}", mx, query.frame_top_y(geometry, row_key), mark_w, FRAME_H, top, pending=pend))
            cells.append(CellBox(f"{foot}:{name}:{c}", mx, query.frame_brace_y(geometry, row_key), mark_w, BRACE_H, foot, pending=pend))
    elif n_cols:
        if column_key == "interest":
            for c in range(n_cols):
                transpose_mark(cells, geometry, f"{name}:{c}", left(c) + COL_W - MARK_INSET, row_key, pending=(c == pending_col))
        else:
            gx, gw = query.matrix_span(geometry, resolved, column_key)
            transpose_mark(cells, geometry, name, gx + gw, row_key)
    if not separators:
        return
    sep_y, sep_h = query.separator_span(resolved, geometry, row_key)
    for c in range(1, n_cols):
        cells.append(CellBox(f"sep:{name}:{c}", (left(c - 1) + COL_W + left(c)) / 2 - SEP_W / 2, sep_y, SEP_W, sep_h, "vbar"))


def transpose_mark(cells, geometry, name, x, row_key, pending: bool = False) -> None:
    cells.append(CellBox(f"transpose:{name}", x, geometry.rows[row_key].y - FRAME_GAP, TRANSPOSE_W, ROW_H,
                         "transpose", text="ᵀ", pending=pending))


def v_split_bars(cells, resolved, geometry, context, accum) -> None:
    if not resolved.unchanged.shown or geometry.commas_x is None or resolved.dims.comma_count_shown == 0 or resolved.dims.unchanged_count == 0:
        return
    x = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown) - V_SPLIT_GAP / 2 - SEP_W / 2
    u_left = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown)
    u_right = u_left + resolved.dims.unchanged_count * COL_W
    rows_with_u = set()
    for cell in accum:
        if u_left - 0.5 <= cell.x < u_right:
            for row_key, band in geometry.rows.items():
                if band.y <= cell.y < band.y + band.h:
                    rows_with_u.add(row_key)
                    break
    for row_key in rows_with_u:
        if row_key != "counts" and query.tile_open(geometry, context.collapsed, row_key, "commas"):
            sy, sh = query.separator_span(resolved, geometry, row_key)
            cells.append(CellBox(f"vsplit:{row_key}", x, sy, SEP_W, sh, "vbar"))


def _emit_canon_stacked_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "canon") and query.tile_open(geometry, cl, "canon", "primes"):
        for i in range(resolved.dims.canonical_rank):
            bracket(cells, resolved, geometry, f"canon:map:{i}", "canon", "primes", query.canon_top(geometry, i), ROW_H, stacked=True)
            bracket(cells, resolved, geometry, f"form:map:{i}", "canon", "gens", query.canon_top(geometry, i), ROW_H, stacked=True)
    if query.row_open(geometry, cl, "canon") and query.tile_open(geometry, cl, "canon", "canongens"):
        for i in range(resolved.dims.canonical_rank):
            bracket(cells, resolved, geometry, f"fcancel:map:{i}", "canon", "canongens", query.canon_top(geometry, i), ROW_H, stacked=True)
    if query.tile_open(geometry, cl, "mapping", "canongens"):
        for i in range(resolved.dims.rank):
            bracket(cells, resolved, geometry, f"finv:map:{i}", "mapping", "canongens", query.map_top(geometry, i), ROW_H, stacked=True)


def _emit_canon_fit_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if not query.row_open(geometry, cl, "canon"):
        return
    canon_y, canon_h = (geometry.rows["canon"].y if "canon" in geometry.rows else 0), resolved.dims.canonical_rank * ROW_H
    if query.tile_open(geometry, cl, "canon", "detempering"):
        bracket(cells, resolved, geometry, "canon_detempering", "canon", "detempering", canon_y, canon_h, fit=True)
    if query.tile_open(geometry, cl, "canon", "commas"):
        bracket(cells, resolved, geometry, "canon_comma", "canon", "commas", canon_y, canon_h, fit=True)
    if query.tile_open(geometry, cl, "canon", "targets"):
        bracket(cells, resolved, geometry, "canon_mapped", "canon", "targets", canon_y, canon_h, fit=True)
    if resolved.dims.held_count and query.tile_open(geometry, cl, "canon", "held"):
        bracket(cells, resolved, geometry, "canon_hmapped", "canon", "held", canon_y, canon_h, fit=True)


def _emit_projection_brackets(cells, resolved, geometry, context) -> None:
    if not query.row_open(geometry, context.collapsed, "projection"):
        return
    _emit_projection_embed_brackets(cells, resolved, geometry, context)
    _emit_projection_list_brackets(cells, resolved, geometry, context)


def _emit_projection_embed_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    py, ph = geometry.rows["projection"].y, resolved.dims.dimensionality * ROW_H
    if query.tile_open(geometry, cl, "projection", "primes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"projection:{i}", "projection", "primes", query.projection_top(geometry, i), ROW_H, stacked=True)
    if query.tile_open(geometry, cl, "projection", "gens"):
        bracket(cells, resolved, geometry, "embed", "projection", "gens", py, ph, fit=True)
    if query.tile_open(geometry, cl, "projection", "canongens"):
        bracket(cells, resolved, geometry, "embed_c", "projection", "canongens", py, ph, fit=True)
    if query.tile_open(geometry, cl, "projection", "ssgens"):
        bracket(cells, resolved, geometry, "embed_sl", "projection", "ssgens", py, ph, fit=True)


def _emit_projection_list_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    py, ph = geometry.rows["projection"].y, resolved.dims.dimensionality * ROW_H
    if query.tile_open(geometry, cl, "projection", "ssprimes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"projection_superspace:{i}", "projection", "ssprimes", query.projection_top(geometry, i), ROW_H, stacked=True)
    if resolved.unchanged.shown and query.tile_open(geometry, cl, "projection", "commas"):
        bracket(cells, resolved, geometry, "projection_vectors", "projection", "commas", py, ph, fit=True)
    if query.tile_open(geometry, cl, "projection", "detempering"):
        bracket(cells, resolved, geometry, "projection_detempering", "projection", "detempering", py, ph, fit=True)
    if query.tile_open(geometry, cl, "projection", "targets"):
        bracket(cells, resolved, geometry, "projection_targets", "projection", "targets", py, ph, fit=True)
    if query.tile_open(geometry, cl, "projection", "held"):
        bracket(cells, resolved, geometry, "projection_held", "projection", "held", py, ph, fit=True)


def _emit_mapping_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "scaling_factors") and query.tile_open(geometry, cl, "scaling_factors", "commas"):
        bracket(cells, resolved, geometry, "scaling", "scaling_factors", "commas", geometry.rows["scaling_factors"].y, ROW_H)
    if query.row_open(geometry, cl, "mapping"):
        if query.tile_open(geometry, cl, "mapping", "primes"):
            for i in range(resolved.dims.rank):
                bracket(cells, resolved, geometry, f"map:{i}", "mapping", "primes", query.map_top(geometry, i), ROW_H, stacked=True)
            if context.pending_mapping_row is not None:
                bracket(cells, resolved, geometry, "map:pending", "mapping", "primes", query.map_top(geometry, resolved.dims.rank), ROW_H, pending=True, stacked=True)
        if query.tile_open(geometry, cl, "mapping", "commas"):
            bracket(cells, resolved, geometry, "mapped_comma", "mapping", "commas", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_H, fit=True)
        if query.tile_open(geometry, cl, "mapping", "targets"):
            bracket(cells, resolved, geometry, "mapped", "mapping", "targets", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_H, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, cl, "mapping", "held"):
            bracket(cells, resolved, geometry, "hmapped", "mapping", "held", geometry.rows["mapping"].y, resolved.dims.rank_shown * ROW_H, fit=True)


def _emit_ss_stacked_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssprimes"):
        for i in range(resolved.dims.superspace_rank):
            bracket(cells, resolved, geometry, f"ss_map:{i}", "ss_mapping", "ssprimes", query.ss_map_top(geometry, i), ROW_H, stacked=True)
    if query.row_open(geometry, cl, "ss_projection") and query.tile_open(geometry, cl, "ss_projection", "ssprimes"):
        for i in range(resolved.dims.superspace_dimensionality):
            bracket(cells, resolved, geometry, f"ss_projection:{i}", "ss_projection", "ssprimes", query.ss_projection_top(geometry, i), ROW_H, stacked=True)


def _emit_ss_projection_fit_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    ssp_top, ssp_h = (geometry.rows["ss_projection"].y if "ss_projection" in geometry.rows else 0), resolved.dims.superspace_dimensionality * ROW_H
    if query.row_open(geometry, cl, "ss_projection"):
        if query.tile_open(geometry, cl, "ss_projection", "ssgens"):
            bracket(cells, resolved, geometry, "ss_embed", "ss_projection", "ssgens", ssp_top, ssp_h, fit=True)
        if query.tile_open(geometry, cl, "ss_projection", "primes"):
            bracket(cells, resolved, geometry, "ss_projection_basis_lift", "ss_projection", "primes", ssp_top, ssp_h, fit=True)
        if query.tile_open(geometry, cl, "ss_projection", "detempering"):
            bracket(cells, resolved, geometry, "ss_projection_detempering", "ss_projection", "detempering", ssp_top, ssp_h, fit=True)
        if resolved.unchanged.shown and query.tile_open(geometry, cl, "ss_projection", "commas"):
            bracket(cells, resolved, geometry, "ss_projection_vectors", "ss_projection", "commas", ssp_top, ssp_h, fit=True)
        if query.tile_open(geometry, cl, "ss_projection", "targets"):
            bracket(cells, resolved, geometry, "ss_projection_targets", "ss_projection", "targets", ssp_top, ssp_h, fit=True)
        if query.tile_open(geometry, cl, "ss_projection", "held"):
            bracket(cells, resolved, geometry, "ss_projection_held", "ss_projection", "held", ssp_top, ssp_h, fit=True)


def _emit_ss_rest_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "ssprimes"):
        for i in range(resolved.dims.superspace_dimensionality):
            bracket(cells, resolved, geometry, f"ss_vec_jmap:{i}", "ss_vectors", "ssprimes", query.ss_vec_top(geometry, i), ROW_H, stacked=True)
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "primes"):
        for i in range(resolved.dims.superspace_rank):
            bracket(cells, resolved, geometry, f"ss_msl:{i}", "ss_mapping", "primes", query.ss_map_top(geometry, i), ROW_H, stacked=True)
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssgens"):
        bracket(cells, resolved, geometry, "ss_selfmap", "ss_mapping", "ssgens",
                geometry.rows["ss_mapping"].y, resolved.dims.superspace_rank * ROW_H, fit=True)


def _emit_vector_stacked_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.tile_open(geometry, cl, "vectors", "primes"):
        for i in range(resolved.dims.dimensionality):
            bracket(cells, resolved, geometry, f"vec:primes:{i}", "vectors", "primes", query.vec_top(geometry, i), ROW_H, stacked=True)
    if query.tile_open(geometry, cl, "mapping", "gens"):
        bracket(cells, resolved, geometry, "selfmap", "mapping", "gens",
                geometry.rows["mapping"].y, resolved.dims.rank * ROW_H, fit=True)
    if query.tile_open(geometry, cl, "mapping", "detempering"):
        bracket(cells, resolved, geometry, "mapped_detempering", "mapping", "detempering",
                geometry.rows["mapping"].y, resolved.dims.rank * ROW_H, fit=True)


def _emit_ss_vectors_list_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "ss_vectors"):
        if query.tile_open(geometry, cl, "ss_vectors", "primes"):
            bracket(cells, resolved, geometry, "ss_vec:primes", "ss_vectors", "primes", geometry.rows["ss_vectors"].y, resolved.dims.superspace_dimensionality * ROW_H, fit=True)
        for group in ("commas", "targets"):
            if query.tile_open(geometry, cl, "ss_vectors", group):
                bracket(cells, resolved, geometry, f"ss_vec:{group}", "ss_vectors", group, geometry.rows["ss_vectors"].y, resolved.dims.superspace_dimensionality * ROW_H, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, cl, "ss_vectors", "held"):
            bracket(cells, resolved, geometry, "ss_vec:held", "ss_vectors", "held", geometry.rows["ss_vectors"].y, resolved.dims.superspace_dimensionality * ROW_H, fit=True)
        if query.tile_open(geometry, cl, "ss_vectors", "detempering"):
            bracket(cells, resolved, geometry, "ss_vec:detempering", "ss_vectors", "detempering", geometry.rows["ss_vectors"].y, resolved.dims.superspace_dimensionality * ROW_H, fit=True)


def _emit_ss_mapped_list_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "ss_mapping"):
        for group in ("commas", "targets"):
            if query.tile_open(geometry, cl, "ss_mapping", group):
                bracket(cells, resolved, geometry, f"ss_mapped:{group}", "ss_mapping", group, geometry.rows["ss_mapping"].y, resolved.dims.superspace_rank * ROW_H, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, cl, "ss_mapping", "held"):
            bracket(cells, resolved, geometry, "ss_mapped:held", "ss_mapping", "held", geometry.rows["ss_mapping"].y, resolved.dims.superspace_rank * ROW_H, fit=True)
        if query.tile_open(geometry, cl, "ss_mapping", "detempering"):
            bracket(cells, resolved, geometry, "ss_mapped:detempering", "ss_mapping", "detempering", geometry.rows["ss_mapping"].y, resolved.dims.superspace_rank * ROW_H, fit=True)


def _emit_vec_list_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "vectors"):
        for group in ("commas", "targets"):
            if query.tile_open(geometry, cl, "vectors", group):
                bracket(cells, resolved, geometry, f"vec:{group}", "vectors", group, geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_H, fit=True)
        if resolved.dims.held_count and query.tile_open(geometry, cl, "vectors", "held"):
            bracket(cells, resolved, geometry, "vec:held", "vectors", "held", geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_H, fit=True)
        if query.tile_open(geometry, cl, "vectors", "detempering"):
            bracket(cells, resolved, geometry, "vec:detempering", "vectors", "detempering", geometry.rows["vectors"].y, resolved.dims.dimensionality * ROW_H, fit=True)


def _emit_prescaling_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.row_open(geometry, cl, "prescaling"):
        ph = (geometry.prescale_rows + geometry.size_rows) * ROW_H + query.prescale_size_gap(geometry)
        bare_col = "ssprimes" if resolved.flags.superspace else "primes"
        for group in ("commas", "detempering", "targets", "held"):
            if query.tile_open(geometry, cl, "prescaling", group):
                bracket(cells, resolved, geometry, f"prescaling:{group}", "prescaling", group,
                        geometry.rows["prescaling"].y, ph, fit=True)
        if resolved.flags.superspace and query.tile_open(geometry, cl, "prescaling", "primes"):
            bracket(cells, resolved, geometry, "prescaling:primes", "prescaling", "primes",
                    geometry.rows["prescaling"].y, ph, fit=True)
        if query.tile_open(geometry, cl, "prescaling", bare_col):
            pspan = query.matrix_span(geometry, resolved, bare_col)
            for i in range(geometry.prescale_rows + geometry.size_rows):
                bracket(cells, resolved, geometry, f"prescaling:row:{i}", "prescaling", bare_col,
                        query.subrow_top(geometry, "prescaling", i), ROW_H, span=pspan, stacked=True)
            if geometry.size_rows:
                gx, gw = pspan
                bar_y = geometry.rows["prescaling"].y + geometry.prescale_rows * ROW_H + query.prescale_size_gap(geometry) / 2 - SEP_W / 2
                cells.append(CellBox("bar:prescaling", gx, bar_y, gw, SEP_W, "hbar"))


def _emit_scalar_row_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    _emit_tuning_map_brackets(cells, resolved, geometry, context)
    for key in ("tuning", "just", "retune", "complexity"):
        if query.row_open(geometry, cl, key):
            _emit_list_row_brackets(cells, resolved, geometry, context, key)
    if query.tile_open(geometry, cl, "weight", "targets"):
        bracket(cells, resolved, geometry, "weight", "weight", "targets", geometry.rows["weight"].y, ROW_H)
    if query.tile_open(geometry, cl, "damage", "targets"):
        bracket(cells, resolved, geometry, "damage", "damage", "targets", geometry.rows["damage"].y, ROW_H)


def _emit_tuning_map_brackets(cells, resolved, geometry, context) -> None:
    cl = context.collapsed
    if query.tile_open(geometry, cl, "tuning", "gens"):
        bracket(cells, resolved, geometry, "tuning:genmap", "tuning", "gens", geometry.rows["tuning"].y, ROW_H)
    if query.tile_open(geometry, cl, "tuning", "canongens"):
        bracket(cells, resolved, geometry, "tuning:cangenmap", "tuning", "canongens", geometry.rows["tuning"].y, ROW_H)
    if query.tile_open(geometry, cl, "tuning", "detempering"):
        bracket(cells, resolved, geometry, "tuning:detempering", "tuning", "detempering", geometry.rows["tuning"].y, ROW_H)
    if query.tile_open(geometry, cl, "tuning", "ssgens"):
        bracket(cells, resolved, geometry, "tuning:ssgenmap", "tuning", "ssgens", geometry.rows["tuning"].y, ROW_H)


def _emit_list_row_brackets(cells, resolved, geometry, context, key: str) -> None:
    cl = context.collapsed
    if query.tile_open(geometry, cl, key, "primes"):
        bracket(cells, resolved, geometry, f"{key}:map", key, "primes", geometry.rows[key].y, ROW_H)
    if query.tile_open(geometry, cl, key, "commas"):
        bracket(cells, resolved, geometry, f"{key}:commalist", key, "commas", geometry.rows[key].y, ROW_H)
    if query.tile_open(geometry, cl, key, "targets"):
        bracket(cells, resolved, geometry, f"{key}:list", key, "targets", geometry.rows[key].y, ROW_H)
    if resolved.dims.held_count and query.tile_open(geometry, cl, key, "held"):
        bracket(cells, resolved, geometry, f"{key}:hlist", key, "held", geometry.rows[key].y, ROW_H)
    if key != "tuning" and query.tile_open(geometry, cl, key, "detempering"):
        bracket(cells, resolved, geometry, f"{key}:detemperinglist", key, "detempering", geometry.rows[key].y, ROW_H)
    if (key != "complexity" or resolved.flags.superspace) and query.tile_open(geometry, cl, key, "ssprimes"):
        bracket(cells, resolved, geometry, f"{key}:ssprimes", key, "ssprimes", geometry.rows[key].y, ROW_H)


def _emit_ebk_frames(cells, resolved, geometry, context) -> None:
    matrix_frame(cells, resolved, geometry, context, "mapping", "primes", "primes")
    matrix_frame(cells, resolved, geometry, context, "projection", "primes", "projection")
    matrix_frame(cells, resolved, geometry, context, "projection", "ssprimes", "projection_superspace")
    matrix_frame(cells, resolved, geometry, context, "canon", "primes", "canon")
    matrix_frame(cells, resolved, geometry, context, "canon", "gens", "form")
    matrix_frame(cells, resolved, geometry, context, "canon", "canongens", "fcancel")
    matrix_frame(cells, resolved, geometry, context, "mapping", "canongens", "finv")
    matrix_frame(cells, resolved, geometry, context, "prescaling", "ssprimes" if resolved.flags.superspace else "primes", "prescaling")
    matrix_frame(cells, resolved, geometry, context, "ss_mapping", "ssprimes", "ss_mapping")
    matrix_frame(cells, resolved, geometry, context, "ss_projection", "ssprimes", "ss_projection")
    matrix_frame(cells, resolved, geometry, context, "ss_vectors", "ssprimes", "ss_vec_jmap")
    matrix_frame(cells, resolved, geometry, context, "ss_mapping", "primes", "ss_msl")
    matrix_frame(cells, resolved, geometry, context, "vectors", "primes", "vec:primes")


def _emit_ebk_marks(cells, resolved, geometry, context) -> None:
    gl = _left_fns(resolved, geometry)
    vlm = functools.partial(vector_list_marks, cells, resolved, geometry, context)
    vlm("mapping", "mapped_comma", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("projection", "projection_vectors", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("projection", "embed", "gens", gl["gen"], resolved.dims.rank, separators=False)
    vlm("projection", "embed_c", "canongens", gl["canongen"], resolved.dims.canonical_rank, separators=False)
    vlm("projection", "embed_sl", "ssgens", gl["ss_gen"], resolved.dims.superspace_rank, separators=False)
    vlm("projection", "projection_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    vlm("projection", "projection_targets", "targets", gl["target"], resolved.dims.target_count)
    vlm("projection", "projection_held", "held", gl["held"], resolved.dims.held_count)
    vlm("projection", "projection_interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("ss_projection", "ss_embed", "ssgens", gl["ss_gen"], resolved.dims.superspace_rank, separators=False)
    vlm("ss_projection", "ss_projection_basis_lift", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    vlm("ss_projection", "ss_projection_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    vlm("ss_projection", "ss_projection_vectors", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("ss_projection", "ss_projection_targets", "targets", gl["target"], resolved.dims.target_count)
    vlm("ss_projection", "ss_projection_held", "held", gl["held"], resolved.dims.held_count)
    vlm("ss_projection", "ss_projection_interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("mapping", "mapped", "targets", gl["target"], resolved.dims.target_count)
    vlm("mapping", "imapped", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("mapping", "hmapped", "held", gl["held"], resolved.dims.held_count)
    vlm("mapping", "selfmap", "gens", gl["gen"], resolved.dims.rank, separators=False)
    vlm("mapping", "mapped_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    vlm("canon", "canon_detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    vlm("canon", "canon_comma", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("canon", "canon_mapped", "targets", gl["target"], resolved.dims.target_count)
    vlm("canon", "canon_imapped", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("canon", "canon_hmapped", "held", gl["held"], resolved.dims.held_count)


def _emit_ebk_vector_marks(cells, resolved, geometry, context, accum) -> None:
    gl = _left_fns(resolved, geometry)
    vlm = functools.partial(vector_list_marks, cells, resolved, geometry, context)
    vlm("vectors", "vec:commas", "commas", gl["comma"], resolved.dims.vector_count_shown, separators=False,
        pending_col=(resolved.dims.comma_count if resolved.commas.pending is not None else -1))
    vlm("vectors", "vec:targets", "targets", gl["target"], resolved.dims.target_count_shown,
        pending_col=(resolved.dims.target_count if resolved.targets.pending is not None else -1))
    vlm("vectors", "vec:interest", "interest", gl["interest"], resolved.dims.interest_count_shown, separators=False,
        pending_col=(resolved.dims.interest_count if resolved.interest.pending is not None else -1))
    vlm("vectors", "vec:held", "held", gl["held"], resolved.dims.held_count_shown,
        pending_col=(resolved.dims.held_count if resolved.held.pending is not None else -1))
    vlm("vectors", "vec:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    vlm("ss_vectors", "ss_vec:primes", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    vlm("ss_vectors", "ss_vec:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("ss_vectors", "ss_vec:targets", "targets", gl["target"], resolved.dims.target_count)
    vlm("ss_vectors", "ss_vec:held", "held", gl["held"], resolved.dims.held_count)
    vlm("ss_vectors", "ss_vec:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("ss_vectors", "ss_vec:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    vlm("ss_mapping", "ss_mapped:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("ss_mapping", "ss_mapped:targets", "targets", gl["target"], resolved.dims.target_count)
    vlm("ss_mapping", "ss_mapped:held", "held", gl["held"], resolved.dims.held_count)
    if resolved.flags.superspace:
        vlm("prescaling", "prescaling:primes", "primes", gl["prime"], resolved.dims.dimensionality, separators=False)
    vlm("ss_mapping", "ss_mapped:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
    vlm("ss_mapping", "ss_mapped:detempering", "detempering", gl["detempering"], resolved.dims.rank)
    vlm("ss_mapping", "ss_selfmap", "ssgens", gl["ss_gen"], resolved.dims.superspace_rank, separators=False)
    vlm("prescaling", "prescaling:commas", "commas", gl["comma"], resolved.dims.comma_count + resolved.dims.unchanged_count, separators=False)
    vlm("prescaling", "prescaling:detempering", "detempering", gl["detempering"], resolved.dims.rank, separators=False)
    vlm("prescaling", "prescaling:targets", "targets", gl["target"], resolved.dims.target_count, separators=True)
    vlm("prescaling", "prescaling:held", "held", gl["held"], resolved.dims.held_count, separators=True)
    vlm("prescaling", "prescaling:interest", "interest", gl["interest"], resolved.dims.interest_count, separators=False)
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
        "ss_gen": lambda g: query.ss_gen_left(geometry, g),
    }
