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
    COLUMN_WIDTH,
    MATLABEL_H,
    ROW_H,
    SYMBOL_H,
    UNIT_H,
    WASH_PAD,
)
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _bus_span, _sub, _subscript_coord


def emit_decorations(resolved, geometry, context, region_boxes, gtm_box, opt_box, approach_frame) -> EmitResult:
    cells: list = []
    lines: list = []
    blocks: list = []
    _emit_matrix_labels(cells, resolved, geometry, context)
    _emit_axes(lines, resolved, geometry, context)
    _emit_panels(blocks, geometry, context, region_boxes, gtm_box, opt_box, approach_frame)
    _emit_washes(blocks, resolved, geometry, context)
    _emit_symbols_captions(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells), lines=tuple(lines), blocks=tuple(blocks))


def _gridline(lines, lid, orientation, pos, start, length, *, dotted) -> None:
    lines.append(Line(lid, orientation, pos, start, length, dotted=dotted))


def _column_axis(lines, resolved, geometry, context, fanned_columns, bot_bus_y, key, prefix, n, center_open) -> None:
    if key not in geometry.column_x:
        return
    fanned_columns.add(key)
    dotted = f"col:{key}" in context.collapsed
    matrix_x, matrix_width = query.matrix_span(geometry, resolved, key)
    center_x = matrix_x + matrix_width / 2
    if n == 0:
        _gridline(lines, f"trunk:{key}", "v", center_x, geometry.branch_top_y, geometry.fanout_y - geometry.branch_top_y, dotted=dotted)
        _gridline(lines, f"foot:{key}", "v", center_x, geometry.fanout_y, geometry.total_h - geometry.fanout_y, dotted=dotted)
        return
    xs = [center_x] * n if dotted else [center_open(i) for i in range(n)]
    for i in range(n):
        _gridline(lines, f"v:{prefix}:{i}", "v", xs[i], geometry.fanout_y, bot_bus_y - geometry.fanout_y, dotted=dotted)
    bus_x, bus_width = _bus_span(xs)
    top_end = max(geometry.plus_stub_x[key], bus_x + bus_width) if key in geometry.plus_stub_x else bus_x + bus_width
    bus_left = min(geometry.plus_stub_x[key], bus_x) if key in geometry.plus_stub_x else bus_x
    _gridline(lines, f"bus:{key}:top", "h", geometry.fanout_y, bus_left, top_end - bus_left, dotted=dotted)
    _gridline(lines, f"bus:{key}:bot", "h", bot_bus_y, bus_x, bus_width, dotted=dotted)
    _gridline(lines, f"trunk:{key}", "v", center_x, geometry.branch_top_y, geometry.fanout_y - geometry.branch_top_y, dotted=dotted)
    _gridline(lines, f"foot:{key}", "v", center_x, bot_bus_y, geometry.total_h - bot_bus_y, dotted=dotted)


def _row_axis(lines, geometry, context, right_bus_x, key) -> None:
    n = geometry.rows[key].num_subrows
    folded = f"row:{key}" in context.collapsed
    center_y = geometry.rows[key].y + geometry.rows[key].height / 2
    ys = [center_y] * n if folded else [query.subrow_top(geometry, key, i) + ROW_H / 2 for i in range(n)]
    left_bus_x = geometry.node_edge + geometry.FAN if (query.row_fans(geometry, key) and not folded) else geometry.node_edge
    for i in range(n):
        _gridline(lines, f"h:{key}:{i}", "h", ys[i], left_bus_x, right_bus_x - left_bus_x, dotted=folded)
    bus_y, bus_h = _bus_span(ys)
    left_bottom = geometry.row_plus_y[key] if key in geometry.row_plus_y else bus_y + bus_h
    _gridline(lines, f"vbar:{key}:left", "v", left_bus_x, bus_y, left_bottom - bus_y, dotted=folded)
    _gridline(lines, f"vbar:{key}:right", "v", right_bus_x, bus_y, bus_h, dotted=folded)
    _gridline(lines, f"trunk:{key}", "h", center_y, geometry.node_edge, left_bus_x - geometry.node_edge, dotted=folded)
    _gridline(lines, f"foot:{key}", "h", center_y, right_bus_x, geometry.total_w - right_bus_x, dotted=folded)


def _emit_axes(lines, resolved, geometry, context) -> None:
    bot_bus_y = geometry.total_h - geometry.FAN
    fanned_columns: set = set()
    for key in geometry.group_left:
        _column_axis(lines, resolved, geometry, context, fanned_columns, bot_bus_y, key, geometry.group_elem[key], geometry.group_n[key],
                     lambda i, k=key: geometry.group_left[k][i] + COLUMN_WIDTH / 2)
    for key in geometry.column_x:
        if key in fanned_columns:
            continue
        center_x = geometry.column_x[key] + geometry.column_width[key] / 2
        _gridline(lines, f"trunk:{key}", "v", center_x, geometry.branch_top_y, geometry.total_h - geometry.branch_top_y,
                  dotted=f"col:{key}" in context.collapsed)
    right_bus_x = geometry.total_w - geometry.FAN
    for key in geometry.rows:
        if query.row_fans(geometry, key):
            _row_axis(lines, geometry, context, right_bus_x, key)
        else:
            _gridline(lines, f"h:{key}", "h", geometry.rows[key].y + geometry.rows[key].height / 2, geometry.node_edge, geometry.total_w - geometry.node_edge,
                      dotted=f"row:{key}" in context.collapsed)


def _matlabel_group_count(resolved):
    return {"gens": resolved.dims.rank, "primes": resolved.dims.dimensionality, "commas": resolved.dims.comma_count + resolved.dims.unchanged_count, "targets": resolved.dims.target_count,
            "held": resolved.dims.held_count, "detempering": resolved.dims.rank, "interest": resolved.dims.interest_count,
            "canongens": resolved.dims.canonical_rank, "superspace_generators": resolved.dims.superspace_rank, "superspace_primes": resolved.dims.superspace_dimensionality}


def _emit_matrix_row_labels(cells, resolved, geometry, context) -> None:

    def prescale_top(i):
        return query.subrow_top(geometry, "prescaling", i)
    row_top = {
        ("mapping", "primes"): lambda i: query.map_top(geometry, i),
        ("canon", "primes"): lambda i: query.canon_top(geometry, i),
        ("mapping", "canongens"): lambda i: query.map_top(geometry, i),
        ("vectors", "primes"): lambda i: query.vector_top(geometry, i),
        ("projection", "primes"): lambda i: query.projection_top(geometry, i),
        ("projection", "superspace_primes"): lambda i: query.projection_top(geometry, i),
        ("prescaling", "primes"): prescale_top,
        ("prescaling", "superspace_primes"): prescale_top,
        ("superspace_mapping", "superspace_primes"): lambda i: query.superspace_map_top(geometry, i),
        ("superspace_mapping", "primes"): lambda i: query.superspace_map_top(geometry, i),
        ("superspace_vectors", "superspace_primes"): lambda i: query.superspace_vector_top(geometry, i),
        ("superspace_projection", "superspace_primes"): lambda i: query.superspace_projection_top(geometry, i),
    }
    row_count = {("mapping", "primes"): resolved.dims.rank,
                 ("canon", "primes"): resolved.dims.canonical_rank,
                 ("mapping", "canongens"): resolved.dims.rank,
                 ("vectors", "primes"): resolved.dims.dimensionality,
                 ("projection", "primes"): resolved.dims.dimensionality,
                 ("projection", "superspace_primes"): resolved.dims.dimensionality,
                 ("prescaling", "primes"): geometry.prescale_rows + geometry.size_rows,
                 ("prescaling", "superspace_primes"): geometry.prescale_rows + geometry.size_rows,
                 ("superspace_mapping", "superspace_primes"): resolved.dims.superspace_rank,
                 ("superspace_mapping", "primes"): resolved.dims.superspace_rank,
                 ("superspace_vectors", "superspace_primes"): resolved.dims.superspace_dimensionality,
                 ("superspace_projection", "superspace_primes"): resolved.dims.superspace_dimensionality}
    for (row_key, column_key), glyph in resolved.labels.row_labels.items():
        if not query.tile_open(geometry, context.collapsed, row_key, column_key):
            continue
        top = row_top[(row_key, column_key)]
        for i in range(row_count[(row_key, column_key)]):
            size_row = row_key == "prescaling" and i == geometry.prescale_rows and geometry.size_rows
            g = query.form_subscripted(resolved, glyph, row_key, column_key)
            text = "𝒛" if size_row else f"{g}{_sub(i + 1)}"
            cells.append(CellBox(
                f"matlabel:row:{row_key}:{column_key}:{i}",
                geometry.content_x[column_key] + query.etpick_left_pad(geometry, column_key) + query.handle_gutter_w(geometry, column_key), top(i),
                query.matlabel_gutter_w(geometry, column_key), ROW_H,
                "matlabel", text=text,
            ))


def _emit_matrix_col_labels(cells, resolved, geometry, context) -> None:
    group_count = _matlabel_group_count(resolved)
    for (row_key, column_key), label in resolved.labels.column_labels.items():
        if column_key not in group_count or row_key not in geometry.rows or geometry.rows[row_key].matrix_label_top is None:
            continue
        if not query.tile_open(geometry, context.collapsed, row_key, column_key):
            continue
        column_label = label
        if (row_key, column_key) == ("weight", "targets") and geometry.all_interval_simplicity_weight:
            column_label = functools.partial(query.weight_simplicity_header, resolved)
        left = geometry.group_left[column_key]
        y = geometry.rows[row_key].matrix_label_top
        for i in range(group_count[column_key]):
            glyph = column_label if callable(column_label) else query.form_subscripted(resolved, column_label, row_key, column_key)
            text = glyph(i) if callable(glyph) else f"{glyph}{_sub(i + 1)}"
            if resolved.unchanged.shown and column_key == "commas":
                text = text.replace("𝐜", "𝐯")
            x = left[query.comma_value_pos(resolved, i)] if column_key == "commas" else left[i]
            cells.append(CellBox(
                f"matlabel:col:{row_key}:{column_key}:{i}",
                x, y, COLUMN_WIDTH, MATLABEL_H,
                "matlabel", text=text,
            ))


def _emit_matrix_labels(cells, resolved, geometry, context) -> None:
    if not resolved.flags.header_symbols:
        return
    _emit_matrix_row_labels(cells, resolved, geometry, context)
    _emit_matrix_col_labels(cells, resolved, geometry, context)


def _panel(blocks, geometry, context, bid, column_key, row_key) -> None:
    if column_key not in geometry.column_x or row_key not in geometry.rows:
        return
    blocks.append(Block(bid, *query.panel_rect(geometry, context.collapsed, row_key, column_key)))


def _emit_panels(blocks, geometry, context, region_boxes, gtm_box, opt_box, approach_frame) -> None:
    for bid, row_key, column_key in geometry.tiles:
        if (row_key, column_key) in geometry.declared_tiles:
            _panel(blocks, geometry, context, bid, column_key, row_key)
    blocks.extend(region_boxes)
    if gtm_box is not None:
        blocks.append(Block("block:tuning:rangesbox", *gtm_box, boxed=True))
    if opt_box is not None:
        blocks.append(Block("block:optimization:box", *opt_box, boxed=True))
    if approach_frame is not None:
        blocks.append(Block("block:optimization:approach:box", *approach_frame, boxed=True))


def _as_groups(g):
    return {g} if isinstance(g, str) else set(g)


def _tile_groups(resolved, row_key, column_key):
    region = set()
    if row_key == "canon" or column_key == "canongens":
        region |= {"temperament", "form"}
    if row_key in ("projection", "tuning"):
        region |= {"tuning"}
    if resolved.unchanged.shown and column_key == "commas":
        return {"temperament", "tuning"} | region
    if row_key in SPINE_ROWS and column_key in SPINE_COLUMN_GROUP:
        return _as_groups(SPINE_COLUMN_GROUP[column_key]) | region
    if column_key in SPINE_COLUMNS and row_key in SPINE_ROW_GROUP:
        return _as_groups(SPINE_ROW_GROUP[row_key]) | region
    if column_key in SUPERSPACE_REGION_COLUMNS or row_key in SUPERSPACE_REGION_ROWS:
        groups = {"tuning"}
        if SPINE_COLUMN_GROUP.get(column_key) == "temperament":
            groups.add("temperament")
        return groups | region
    return {_FACTOR_GROUP[f] for f in CELL_FACTORS.get((row_key, column_key), ())} | region


def _wash_segments(resolved, geometry, row_key, column_key):
    if (row_key, column_key) == ("counts", "gens") and "canongens" in geometry.column_x:
        return [("gens", query.tile_box(geometry, "gens"), _tile_groups(resolved, "counts", "gens")),
                ("canongens", query.tile_box(geometry, "canongens"), _tile_groups(resolved, "counts", "canongens"))]
    return [(column_key, query.tile_span_box(geometry, row_key, column_key), _tile_groups(resolved, row_key, column_key))]


def _wash_bands(resolved, geometry, context):
    bands = []
    for _bid, row_key, column_key in geometry.tiles:
        if (row_key, column_key) not in geometry.declared_tiles or not query.tile_open(geometry, context.collapsed, row_key, column_key):
            continue
        y, height = geometry.rows[row_key].tile_top - WASH_PAD, geometry.rows[row_key].tile_h + 2 * WASH_PAD
        for seg_key, (tile_x, tile_w), seg_groups in _wash_segments(resolved, geometry, row_key, column_key):
            groups = sorted(g for g in seg_groups if context.settings.get(f"{g}_colorization"))
            if not groups:
                continue
            x, width = tile_x - WASH_PAD, tile_w + 2 * WASH_PAD
            if len(groups) == 3:
                bands.append((f"white:{row_key}:{seg_key}", x, y, width, height, None))
            else:
                for group in groups:
                    bands.append((f"{group}:{row_key}:{seg_key}", x, y, width, height, group))
    return bands


def _emit_washes(blocks, resolved, geometry, context) -> None:
    if not (geometry.column_x and geometry.rows):
        return
    bands = _wash_bands(resolved, geometry, context)
    for bid, x, y, width, height, _ in bands:
        blocks.append(Block(f"washbase:{bid}", x, y, width, height, tint="base"))
    for bid, x, y, width, height, group in bands:
        if group is not None:
            blocks.append(Block(f"wash:{bid}", x, y, width, height, tint=group))


def _caption_equivalences(resolved, geometry, ai, slope) -> dict:
    equivalences = {**EQUIVALENCES,
                    ("weight", "targets"): "" if resolved.scalars.custom_weights_active else WEIGHT_EQUIVALENCE_BY_SLOPE[slope],
                    ("prescaling", "superspace_primes" if resolved.flags.superspace else "primes"): resolved.labels.prescaler_equivalence,
                    **(ALL_INTERVAL_EQUIVALENCES if ai else {}),
                    **(FORM_EQUIVALENCES if resolved.flags.form_subscript else {}),
                    **({("mapping", "primes"): f" = 𝐹𝑀{SUBSCRIPT_C}"} if resolved.flags.canon else {}),
                    **({("vectors", "commas"): " = C|U", ("mapping", "commas"): ""}
                       if resolved.unchanged.shown else {})}
    if resolved.flags.superspace:
        equivalences[("projection", "primes")] = (
            equivalences[("projection", "primes")] + query.projection_superspace_tail(resolved))
    if ai:
        if not resolved.scalars.prescaler_is_matrix and not geometry.size_factor:
            equivalences[("complexity", "targets")] = f" = diag({resolved.labels.prescaler_symbol})"
            equivalences[("weight", "targets")] = f" = diag({resolved.labels.prescaler_symbol})⁻¹"
        equivalences[("damage", "targets")] = f" = |𝒓|{resolved.labels.prescaler_symbol}⁻¹"
    if not resolved.flags.weighting:
        equivalences[("damage", "targets")] = " = |𝒓|" if ai else " = |𝐞|"
    return equivalences


def _emit_tile_symbol(cells, resolved, geometry, caption_equivs, caption_ai, row_key, column_key, center_y) -> float:
    center_y += BAND_GAP
    equiv = caption_equivs.get((row_key, column_key), "") if resolved.flags.equivalences else ""
    base_symbol = resolved.labels.prescaling_symbols.get((row_key, column_key), SYMBOLS.get((row_key, column_key), ""))
    if caption_ai and (row_key, column_key) in ALL_INTERVAL_SYMBOLS:
        base_symbol = ALL_INTERVAL_SYMBOLS[(row_key, column_key)]
    if resolved.unchanged.shown and column_key == "commas":
        base_symbol = base_symbol.replace(SUBSCRIPT_C, "\x00").replace("C", "V").replace("\x00", SUBSCRIPT_C)
    base_symbol = query.form_subscripted(resolved, base_symbol, row_key, column_key)
    glyph = base_symbol if (resolved.flags.symbols or equiv) else ""
    if glyph or equiv:
        cells.append(CellBox(f"symbol:{row_key}:{column_key}", geometry.column_x[column_key], center_y, geometry.column_width[column_key], SYMBOL_H, "symbol", text=glyph + equiv))
    return center_y + SYMBOL_H


def _emit_unchanged_counts_caption(cells, resolved, geometry, row_key, center_y) -> None:
    comma_half_w = resolved.dims.comma_count * COLUMN_WIDTH + resolved.unchanged.empty_comma_w
    if comma_half_w:
        comma_half_x = geometry.commas_x if resolved.unchanged.empty_comma_w else query.comma_left(geometry, resolved, 0)
        cells.append(CellBox("caption:counts:commas", comma_half_x, center_y, comma_half_w,
                             geometry.rows[row_key].caption, "caption", text="nullity"))
    cells.append(CellBox("caption:counts:commas:u", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown), center_y, resolved.dims.unchanged_count * COLUMN_WIDTH,
                         geometry.rows[row_key].caption, "caption", text="unchanged interval count"))


def _emit_tile_caption(cells, resolved, geometry, caption_ai, row_key, column_key, name, center_y) -> None:
    kw = MNEMONICS.get((row_key, column_key)) if resolved.flags.mnemonics else None
    underlines = ((name.index(kw), 1),) if (kw and kw in name) else ()
    if resolved.flags.mnemonics and caption_ai:
        underlines += tuple((name.index(width), 1)
                            for width in ALL_INTERVAL_MNEMONICS.get((row_key, column_key), ()) if width in name)
    cap_x, cap_w = query.tile_span_box(geometry, row_key, column_key)
    cells.append(CellBox(f"caption:{row_key}:{column_key}", cap_x, center_y, cap_w, geometry.rows[row_key].caption,
                         "caption", text=name, underlines=underlines))


def _emit_tile_units(cells, resolved, geometry, row_key, column_key) -> None:
    unit = query.tile_unit(resolved, row_key, column_key)
    if unit and not (row_key.startswith("superspace_") or column_key in ("superspace_generators", "superspace_primes")):
        unit = _subscript_coord(unit, "p", resolved.labels.domain_label)
    if resolved.flags.units and unit:
        uy = geometry.rows[row_key].y + geometry.rows[row_key].height + geometry.rows[row_key].frame + geometry.rows[row_key].comma_picker + geometry.rows[row_key].symbol + geometry.rows[row_key].caption
        cells.append(CellBox(f"units:{row_key}:{column_key}", geometry.column_x[column_key], uy, geometry.column_width[column_key], UNIT_H,
                             "units", text=f"units: {unit}"))


def _emit_tile_symbols_captions(cells, resolved, geometry, caption_equivs, caption_ai, row_key, column_key, name) -> None:
    if caption_ai and (row_key, column_key) in ALL_INTERVAL_CAPTIONS:
        name = ALL_INTERVAL_CAPTIONS[(row_key, column_key)]
    center_y = geometry.rows[row_key].y + geometry.rows[row_key].height + geometry.rows[row_key].frame + geometry.rows[row_key].comma_picker
    if (resolved.flags.symbols or resolved.flags.equivalences) and row_key in BANDS["symbol"].rows:
        center_y = _emit_tile_symbol(cells, resolved, geometry, caption_equivs, caption_ai, row_key, column_key, center_y)
    if resolved.flags.names and resolved.unchanged.shown and (row_key, column_key) == ("counts", "commas"):
        _emit_unchanged_counts_caption(cells, resolved, geometry, row_key, center_y)
        return
    if resolved.flags.names:
        _emit_tile_caption(cells, resolved, geometry, caption_ai, row_key, column_key, name, center_y)
    _emit_tile_units(cells, resolved, geometry, row_key, column_key)


def _emit_symbols_captions(cells, resolved, geometry, context) -> None:
    caption_ai = service.is_all_interval(context.tuning_scheme)
    slope = service.damage_weight_slope(context.tuning_scheme)
    caption_equivs = _caption_equivalences(resolved, geometry, caption_ai, slope)
    for (row_key, column_key), name in resolved.labels.captions.items():
        if column_key == "interest" and not resolved.interest.vectors:
            continue
        if not query.tile_open(geometry, context.collapsed, row_key, column_key):
            continue
        _emit_tile_symbols_captions(cells, resolved, geometry, caption_equivs, caption_ai, row_key, column_key, name)
