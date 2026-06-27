from __future__ import annotations

import functools

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    _FACTOR_GROUP,
    ALL_INTERVAL_CAPTIONS,
    ALL_INTERVAL_EQUIVALENCES,
    ALL_INTERVAL_MNEMONICS,
    ALL_INTERVAL_SYMBOLS,
    BANDS,
    CELL_FACTORS,
    EQUIVALENCES,
    FORM_EQUIVALENCES,
    MNEMONICS,
    SPINE_COLUMN_GROUP,
    SPINE_COLUMNS,
    SPINE_ROW_GROUP,
    SPINE_ROWS,
    SUBSCRIPT_C,
    SUPERSPACE_REGION_COLUMNS,
    SUPERSPACE_REGION_ROWS,
    SYMBOLS,
    WEIGHT_EQUIVALENCE_BY_SLOPE,
)
from rtt.app.layout import Block, CellBox, Line
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    COL_W,
    MATLABEL_H,
    ROW_H,
    SYMBOL_H,
    UNIT_H,
    WASH_PAD,
)
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _bus_span, _sub, _subscript_coord


def emit_decorations(resolved, geometry, ctx, region_boxes, gtm_box, opt_box, approach_frame) -> EmitResult:
    cells: list = []
    lines: list = []
    blocks: list = []
    _emit_matrix_labels(cells, resolved, geometry, ctx)
    _emit_axes(lines, resolved, geometry, ctx)
    _emit_panels(blocks, geometry, ctx, region_boxes, gtm_box, opt_box, approach_frame)
    _emit_washes(blocks, resolved, geometry, ctx)
    _emit_symbols_captions(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells), lines=tuple(lines), blocks=tuple(blocks))


def _gridline(lines, lid, orientation, pos, start, length, *, dotted) -> None:
    lines.append(Line(lid, orientation, pos, start, length, dotted=dotted))


def _column_axis(lines, resolved, geometry, ctx, fanned_columns, bot_bus_y, key, prefix, n, center_open) -> None:
    if key not in geometry.col_x:
        return
    fanned_columns.add(key)
    dotted = f"col:{key}" in ctx.collapsed
    mx, mw = query.matrix_span(geometry, resolved, key)
    cx = mx + mw / 2
    if n == 0:
        _gridline(lines, f"trunk:{key}", "v", cx, geometry.branch_top_y, geometry.fanout_y - geometry.branch_top_y, dotted=dotted)
        _gridline(lines, f"foot:{key}", "v", cx, geometry.fanout_y, geometry.total_h - geometry.fanout_y, dotted=dotted)
        return
    xs = [cx] * n if dotted else [center_open(i) for i in range(n)]
    for i in range(n):
        _gridline(lines, f"v:{prefix}:{i}", "v", xs[i], geometry.fanout_y, bot_bus_y - geometry.fanout_y, dotted=dotted)
    bx, bw = _bus_span(xs)
    top_end = max(geometry.plus_stub_x[key], bx + bw) if key in geometry.plus_stub_x else bx + bw
    bus_left = min(geometry.plus_stub_x[key], bx) if key in geometry.plus_stub_x else bx
    _gridline(lines, f"bus:{key}:top", "h", geometry.fanout_y, bus_left, top_end - bus_left, dotted=dotted)
    _gridline(lines, f"bus:{key}:bot", "h", bot_bus_y, bx, bw, dotted=dotted)
    _gridline(lines, f"trunk:{key}", "v", cx, geometry.branch_top_y, geometry.fanout_y - geometry.branch_top_y, dotted=dotted)
    _gridline(lines, f"foot:{key}", "v", cx, bot_bus_y, geometry.total_h - bot_bus_y, dotted=dotted)


def _row_axis(lines, geometry, ctx, right_bus_x, key) -> None:
    n = geometry.rows[key].nsub
    folded = f"row:{key}" in ctx.collapsed
    cy = geometry.rows[key].y + geometry.rows[key].h / 2
    ys = [cy] * n if folded else [query.subrow_top(geometry, key, i) + ROW_H / 2 for i in range(n)]
    left_bus_x = geometry.node_edge + geometry.FAN if (query.row_fans(geometry, key) and not folded) else geometry.node_edge
    for i in range(n):
        _gridline(lines, f"h:{key}:{i}", "h", ys[i], left_bus_x, right_bus_x - left_bus_x, dotted=folded)
    bus_y, bus_h = _bus_span(ys)
    left_bottom = geometry.row_plus_y[key] if key in geometry.row_plus_y else bus_y + bus_h
    _gridline(lines, f"vbar:{key}:left", "v", left_bus_x, bus_y, left_bottom - bus_y, dotted=folded)
    _gridline(lines, f"vbar:{key}:right", "v", right_bus_x, bus_y, bus_h, dotted=folded)
    _gridline(lines, f"trunk:{key}", "h", cy, geometry.node_edge, left_bus_x - geometry.node_edge, dotted=folded)
    _gridline(lines, f"foot:{key}", "h", cy, right_bus_x, geometry.total_w - right_bus_x, dotted=folded)


def _emit_axes(lines, resolved, geometry, ctx) -> None:
    bot_bus_y = geometry.total_h - geometry.FAN
    fanned_columns: set = set()
    for key in geometry.group_left:
        _column_axis(lines, resolved, geometry, ctx, fanned_columns, bot_bus_y, key, geometry.group_elem[key], geometry.group_n[key],
                     lambda i, k=key: geometry.group_left[k][i] + COL_W / 2)
    for key in geometry.col_x:
        if key in fanned_columns:
            continue
        cx = geometry.col_x[key] + geometry.col_w[key] / 2
        _gridline(lines, f"trunk:{key}", "v", cx, geometry.branch_top_y, geometry.total_h - geometry.branch_top_y,
                  dotted=f"col:{key}" in ctx.collapsed)
    right_bus_x = geometry.total_w - geometry.FAN
    for key in geometry.rows:
        if query.row_fans(geometry, key):
            _row_axis(lines, geometry, ctx, right_bus_x, key)
        else:
            _gridline(lines, f"h:{key}", "h", geometry.rows[key].y + geometry.rows[key].h / 2, geometry.node_edge, geometry.total_w - geometry.node_edge,
                      dotted=f"row:{key}" in ctx.collapsed)


def _matlabel_group_count(resolved):
    _r = resolved
    return {"gens": _r.dims.r, "primes": _r.dims.d, "commas": _r.dims.nc + _r.dims.nu, "targets": _r.dims.k,
            "held": _r.dims.nh, "detempering": _r.dims.r, "interest": _r.dims.mi,
            "canongens": _r.dims.rc, "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}


def _emit_matrix_row_labels(cells, resolved, geometry, ctx) -> None:
    _r = resolved

    def prescale_top(i):
        return query.subrow_top(geometry, "prescaling", i)
    row_top = {
        ("mapping", "primes"): lambda i: query.map_top(geometry, i),
        ("canon", "primes"): lambda i: query.canon_top(geometry, i),
        ("mapping", "canongens"): lambda i: query.map_top(geometry, i),
        ("vectors", "primes"): lambda i: query.vec_top(geometry, i),
        ("projection", "primes"): lambda i: query.proj_top(geometry, i),
        ("projection", "ssprimes"): lambda i: query.proj_top(geometry, i),
        ("prescaling", "primes"): prescale_top,
        ("prescaling", "ssprimes"): prescale_top,
        ("ss_mapping", "ssprimes"): lambda i: query.ss_map_top(geometry, i),
        ("ss_mapping", "primes"): lambda i: query.ss_map_top(geometry, i),
        ("ss_vectors", "ssprimes"): lambda i: query.ss_vec_top(geometry, i),
        ("ss_projection", "ssprimes"): lambda i: query.ss_proj_top(geometry, i),
    }
    row_count = {("mapping", "primes"): _r.dims.r,
                 ("canon", "primes"): _r.dims.rc,
                 ("mapping", "canongens"): _r.dims.r,
                 ("vectors", "primes"): _r.dims.d,
                 ("projection", "primes"): _r.dims.d,
                 ("projection", "ssprimes"): _r.dims.d,
                 ("prescaling", "primes"): geometry.prescale_rows + geometry.size_rows,
                 ("prescaling", "ssprimes"): geometry.prescale_rows + geometry.size_rows,
                 ("ss_mapping", "ssprimes"): _r.dims.rL,
                 ("ss_mapping", "primes"): _r.dims.rL,
                 ("ss_vectors", "ssprimes"): _r.dims.dL,
                 ("ss_projection", "ssprimes"): _r.dims.dL}
    for (rkey, ckey), glyph in _r.labels.row_labels.items():
        if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
            continue
        top = row_top[(rkey, ckey)]
        for i in range(row_count[(rkey, ckey)]):
            size_row = rkey == "prescaling" and i == geometry.prescale_rows and geometry.size_rows
            g = query.form_subscripted(_r, glyph, rkey, ckey)
            text = "𝒛" if size_row else f"{g}{_sub(i + 1)}"
            cells.append(CellBox(
                f"matlabel:row:{rkey}:{ckey}:{i}",
                geometry.content_x[ckey] + query.etpick_left_pad(geometry, ckey) + query.handle_gutter_w(geometry, ckey), top(i),
                query.matlabel_gutter_w(geometry, ckey), ROW_H,
                "matlabel", text=text,
            ))


def _emit_matrix_col_labels(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    group_count = _matlabel_group_count(resolved)
    for (rkey, ckey), label in _r.labels.col_labels.items():
        if ckey not in group_count or rkey not in geometry.rows or geometry.rows[rkey].matlabel_top is None:
            continue
        if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
            continue
        col_label = label
        if (rkey, ckey) == ("weight", "targets") and geometry.all_interval_simplicity_weight:
            col_label = functools.partial(query.weight_simplicity_header, _r)
        left = geometry.group_left[ckey]
        y = geometry.rows[rkey].matlabel_top
        for i in range(group_count[ckey]):
            glyph = col_label if callable(col_label) else query.form_subscripted(_r, col_label, rkey, ckey)
            text = glyph(i) if callable(glyph) else f"{glyph}{_sub(i + 1)}"
            if _r.unchanged.shown and ckey == "commas":
                text = text.replace("𝐜", "𝐯")
            x = left[query.comma_value_pos(_r, i)] if ckey == "commas" else left[i]
            cells.append(CellBox(
                f"matlabel:col:{rkey}:{ckey}:{i}",
                x, y, COL_W, MATLABEL_H,
                "matlabel", text=text,
            ))


def _emit_matrix_labels(cells, resolved, geometry, ctx) -> None:
    if not resolved.flags.header_symbols:
        return
    _emit_matrix_row_labels(cells, resolved, geometry, ctx)
    _emit_matrix_col_labels(cells, resolved, geometry, ctx)


def _panel(blocks, geometry, ctx, bid, ckey, rkey) -> None:
    if ckey not in geometry.col_x or rkey not in geometry.rows:
        return
    blocks.append(Block(bid, *query.panel_rect(geometry, ctx.collapsed, rkey, ckey)))


def _emit_panels(blocks, geometry, ctx, region_boxes, gtm_box, opt_box, approach_frame) -> None:
    for bid, rkey, ckey in geometry.tiles:
        if (rkey, ckey) in geometry.declared_tiles:
            _panel(blocks, geometry, ctx, bid, ckey, rkey)
    blocks.extend(region_boxes)
    if gtm_box is not None:
        blocks.append(Block("block:tuning:rangesbox", *gtm_box, boxed=True))
    if opt_box is not None:
        blocks.append(Block("block:optimization:box", *opt_box, boxed=True))
    if approach_frame is not None:
        blocks.append(Block("block:optimization:approach:box", *approach_frame, boxed=True))


def _as_groups(g):
    return {g} if isinstance(g, str) else set(g)


def _tile_groups(resolved, rkey, ckey):
    _r = resolved
    region = set()
    if rkey == "canon" or ckey == "canongens":
        region |= {"temperament", "form"}
    if rkey in ("projection", "tuning"):
        region |= {"tuning"}
    if _r.unchanged.shown and ckey == "commas":
        return {"temperament", "tuning"} | region
    if rkey in SPINE_ROWS and ckey in SPINE_COLUMN_GROUP:
        return _as_groups(SPINE_COLUMN_GROUP[ckey]) | region
    if ckey in SPINE_COLUMNS and rkey in SPINE_ROW_GROUP:
        return _as_groups(SPINE_ROW_GROUP[rkey]) | region
    if ckey in SUPERSPACE_REGION_COLUMNS or rkey in SUPERSPACE_REGION_ROWS:
        groups = {"tuning"}
        if SPINE_COLUMN_GROUP.get(ckey) == "temperament":
            groups.add("temperament")
        return groups | region
    return {_FACTOR_GROUP[f] for f in CELL_FACTORS.get((rkey, ckey), ())} | region


def _wash_segments(resolved, geometry, rkey, ckey):
    if (rkey, ckey) == ("counts", "gens") and "canongens" in geometry.col_x:
        return [("gens", query.tile_box(geometry, "gens"), _tile_groups(resolved, "counts", "gens")),
                ("canongens", query.tile_box(geometry, "canongens"), _tile_groups(resolved, "counts", "canongens"))]
    return [(ckey, query.tile_span_box(geometry, rkey, ckey), _tile_groups(resolved, rkey, ckey))]


def _wash_bands(resolved, geometry, ctx):
    bands = []
    for _bid, rkey, ckey in geometry.tiles:
        if (rkey, ckey) not in geometry.declared_tiles or not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
            continue
        y, h = geometry.rows[rkey].tile_top - WASH_PAD, geometry.rows[rkey].tile_h + 2 * WASH_PAD
        for seg_key, (tile_x, tile_w), seg_groups in _wash_segments(resolved, geometry, rkey, ckey):
            groups = sorted(g for g in seg_groups if ctx.settings.get(f"{g}_colorization"))
            if not groups:
                continue
            x, w = tile_x - WASH_PAD, tile_w + 2 * WASH_PAD
            if len(groups) == 3:
                bands.append((f"white:{rkey}:{seg_key}", x, y, w, h, None))
            else:
                for group in groups:
                    bands.append((f"{group}:{rkey}:{seg_key}", x, y, w, h, group))
    return bands


def _emit_washes(blocks, resolved, geometry, ctx) -> None:
    if not (geometry.col_x and geometry.rows):
        return
    bands = _wash_bands(resolved, geometry, ctx)
    for bid, x, y, w, h, _ in bands:
        blocks.append(Block(f"washbase:{bid}", x, y, w, h, tint="base"))
    for bid, x, y, w, h, group in bands:
        if group is not None:
            blocks.append(Block(f"wash:{bid}", x, y, w, h, tint=group))


def _caption_equivalences(resolved, geometry, ai, slope) -> dict:
    _r = resolved
    equivalences = {**EQUIVALENCES,
                    ("weight", "targets"): "" if _r.scalars.custom_weights_active else WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                    ("prescaling", "ssprimes" if _r.flags.superspace else "primes"): _r.labels.prescaler_equivalence,
                    **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                    **(FORM_EQUIVALENCES if _r.flags.form_subscript else {}),
                    **({("mapping", "primes"): f" = 𝐹𝑀{SUBSCRIPT_C}"} if _r.flags.canon else {}),
                    **({("vectors", "commas"): " = C|U", ("mapping", "commas"): ""}
                       if _r.unchanged.shown else {})}
    if _r.flags.superspace:
        equivalences[("projection", "primes")] = (
            equivalences[("projection", "primes")] + query.projection_superspace_tail(_r))
    if ai:
        if not _r.scalars.prescaler_is_matrix and not geometry.size_factor:
            equivalences[("complexity", "targets")] = f" = diag({_r.labels.prescaler_symbol})"
            equivalences[("weight", "targets")] = f" = diag({_r.labels.prescaler_symbol})⁻¹"
        equivalences[("damage", "targets")] = f" = |𝒓|{_r.labels.prescaler_symbol}⁻¹"
    if not _r.flags.weighting:
        equivalences[("damage", "targets")] = " = |𝒓|" if ai else " = |𝐞|"
    return equivalences


def _emit_tile_symbol(cells, resolved, geometry, caption_equivs, caption_ai, rkey, ckey, cy) -> float:
    _r = resolved
    cy += BAND_GAP
    equiv = caption_equivs.get((rkey, ckey), "") if _r.flags.equivalences else ""
    base_symbol = _r.labels.prescaling_symbols.get((rkey, ckey), SYMBOLS.get((rkey, ckey), ""))
    if caption_ai and (rkey, ckey) in ALL_INTERVAL_SYMBOLS:
        base_symbol = ALL_INTERVAL_SYMBOLS[(rkey, ckey)]
    if _r.unchanged.shown and ckey == "commas":
        base_symbol = base_symbol.replace(SUBSCRIPT_C, "\x00").replace("C", "V").replace("\x00", SUBSCRIPT_C)
    base_symbol = query.form_subscripted(_r, base_symbol, rkey, ckey)
    glyph = base_symbol if (_r.flags.symbols or equiv) else ""
    if glyph or equiv:
        cells.append(CellBox(f"symbol:{rkey}:{ckey}", geometry.col_x[ckey], cy, geometry.col_w[ckey], SYMBOL_H, "symbol", text=glyph + equiv))
    return cy + SYMBOL_H


def _emit_unchanged_counts_caption(cells, resolved, geometry, rkey, cy) -> None:
    _r = resolved
    comma_half_w = _r.dims.nc * COL_W + _r.unchanged.empty_comma_w
    if comma_half_w:
        comma_half_x = geometry.commas_x if _r.unchanged.empty_comma_w else query.comma_left(geometry, _r, 0)
        cells.append(CellBox("caption:counts:commas", comma_half_x, cy, comma_half_w,
                             geometry.rows[rkey].cap, "caption", text="nullity"))
    cells.append(CellBox("caption:counts:commas:u", query.comma_left(geometry, _r, _r.dims.nc_shown), cy, _r.dims.nu * COL_W,
                         geometry.rows[rkey].cap, "caption", text="unchanged interval count"))


def _emit_tile_caption(cells, resolved, geometry, caption_ai, rkey, ckey, name, cy) -> None:
    _r = resolved
    kw = MNEMONICS.get((rkey, ckey)) if _r.flags.mnemonics else None
    underlines = ((name.index(kw), 1),) if (kw and kw in name) else ()
    if _r.flags.mnemonics and caption_ai:
        underlines += tuple((name.index(w), 1)
                            for w in ALL_INTERVAL_MNEMONICS.get((rkey, ckey), ()) if w in name)
    cap_x, cap_w = query.tile_span_box(geometry, rkey, ckey)
    cells.append(CellBox(f"caption:{rkey}:{ckey}", cap_x, cy, cap_w, geometry.rows[rkey].cap,
                         "caption", text=name, underlines=underlines))


def _emit_tile_units(cells, resolved, geometry, rkey, ckey) -> None:
    _r = resolved
    unit = query.tile_unit(_r, rkey, ckey)
    if unit and not (rkey.startswith("ss_") or ckey in ("ssgens", "ssprimes")):
        unit = _subscript_coord(unit, "p", _r.labels.domain_label)
    if _r.flags.units and unit:
        uy = geometry.rows[rkey].y + geometry.rows[rkey].h + geometry.rows[rkey].frame + geometry.rows[rkey].cpick + geometry.rows[rkey].sym + geometry.rows[rkey].cap
        cells.append(CellBox(f"units:{rkey}:{ckey}", geometry.col_x[ckey], uy, geometry.col_w[ckey], UNIT_H,
                             "units", text=f"units: {unit}"))


def _emit_tile_symbols_captions(cells, resolved, geometry, caption_equivs, caption_ai, rkey, ckey, name) -> None:
    _r = resolved
    if caption_ai and (rkey, ckey) in ALL_INTERVAL_CAPTIONS:
        name = ALL_INTERVAL_CAPTIONS[(rkey, ckey)]
    cy = geometry.rows[rkey].y + geometry.rows[rkey].h + geometry.rows[rkey].frame + geometry.rows[rkey].cpick
    if (_r.flags.symbols or _r.flags.equivalences) and rkey in BANDS["symbol"].rows:
        cy = _emit_tile_symbol(cells, resolved, geometry, caption_equivs, caption_ai, rkey, ckey, cy)
    if _r.flags.names and _r.unchanged.shown and (rkey, ckey) == ("counts", "commas"):
        _emit_unchanged_counts_caption(cells, resolved, geometry, rkey, cy)
        return
    if _r.flags.names:
        _emit_tile_caption(cells, resolved, geometry, caption_ai, rkey, ckey, name, cy)
    _emit_tile_units(cells, resolved, geometry, rkey, ckey)


def _emit_symbols_captions(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    caption_ai = service.is_all_interval(ctx.tuning_scheme)
    slope = service.damage_weight_slope(ctx.tuning_scheme)
    caption_equivs = _caption_equivalences(resolved, geometry, caption_ai, slope)
    for (rkey, ckey), name in _r.labels.captions.items():
        if ckey == "interest" and not _r.interest.vectors:
            continue
        if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
            continue
        _emit_tile_symbols_captions(cells, resolved, geometry, caption_equivs, caption_ai, rkey, ckey, name)
