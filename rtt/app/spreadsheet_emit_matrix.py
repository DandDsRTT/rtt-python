from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    COUNTS,
    DETEMPERING_COUNTS,
    OPTIMIZATION_COUNTS,
    SUBSCRIPT_C,
    SUBSCRIPT_L,
    SUPERSPACE_COUNTS,
)
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BUTTON,
    COL_W,
    DASH,
    GAP,
    GRIP_BAND,
    HEADER_H,
    LABEL_W,
    PAD,
    ROW_H,
    TOGGLE,
    V_SPLIT_GAP,
)
from rtt.app.spreadsheet_emit_model import EmitResult, element_cell_kind, voice
from rtt.app.spreadsheet_models import _QtyList
from rtt.app.spreadsheet_text import (
    _count_sym,
    _fold_glyph,
    _foldable_ids,
    _pretransform_label,
    _sub,
)


def emit_headers(resolved, geometry, context) -> EmitResult:
    cells: list = []
    for key in geometry.col_x:
        hx = geometry.col_x[key] + query.outer_gutter_w(geometry, key)
        hw = geometry.col_w[key] - 2 * query.outer_gutter_w(geometry, key)
        cells.append(CellBox(f"header:{key}", hx, geometry.header_y, hw, HEADER_H, "colheader", text=geometry.col_header[key]))
        if geometry.col_collapsible[key]:
            glyph = _fold_glyph(f"col:{key}" in context.collapsed)
            tx = hx + (hw - TOGGLE) / 2
            cells.append(CellBox(f"toggle:col:{key}", tx, geometry.col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))
    for key in geometry.rows:
        label = geometry.rows[key].label
        if geometry.size_factor or resolved.scalars.prescaler_is_matrix:
            label = _pretransform_label(label)
            label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
        cells.append(CellBox(f"label:{key}", 0, geometry.rows[key].y, LABEL_W, geometry.rows[key].h, "rowlabel", text=label))
        if geometry.rows[key].collapsible:
            glyph = _fold_glyph(f"row:{key}" in context.collapsed)
            ty = geometry.rows[key].y + (geometry.rows[key].h - TOGGLE) / 2
            cells.append(CellBox(f"toggle:row:{key}", geometry.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))
    foldable = _foldable_ids(cells)
    all_collapsed = bool(foldable) and foldable <= context.collapsed
    cells.append(CellBox("toggle:all", geometry.node_x, geometry.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                         text=_fold_glyph(all_collapsed)))
    return EmitResult(cells=tuple(cells))


def emit_counts_row(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, context.collapsed, "counts"):
        return EmitResult()
    cardinality = {"gens": resolved.dims.rank, "primes": resolved.dims.dimensionality, "commas": context.state.n, "targets": resolved.dims.target_count, "held": resolved.dims.held_count,
                   "detempering": resolved.dims.rank,
                   "superspace_generators": resolved.dims.superspace_rank, "superspace_primes": resolved.dims.superspace_dimensionality}
    for column_key, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
        if not query.tile_open(geometry, context.collapsed, "counts", column_key):
            continue
        if column_key == "commas" and resolved.unchanged.shown:
            comma_half_w = resolved.dims.comma_count * COL_W + resolved.unchanged.empty_comma_w
            if comma_half_w:
                comma_half_x = geometry.commas_x if resolved.unchanged.empty_comma_w else query.comma_left(geometry, resolved, 0)
                cells.append(CellBox("count:commas", comma_half_x, geometry.rows["counts"].y, comma_half_w, ROW_H,
                                     "count", text=f"{_count_sym('n')} = {context.state.n}"))
            cells.append(CellBox("count:commas:u", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown), geometry.rows["counts"].y, resolved.dims.unchanged_count * COL_W, ROW_H,
                                 "count", text=f"{_count_sym('u')} = {resolved.dims.unchanged_count}"))
            continue
        cnt_x, cnt_w = query.tile_span_box(geometry, "counts", column_key)
        cells.append(CellBox(f"count:{column_key}", cnt_x, geometry.rows["counts"].y, cnt_w, ROW_H,
                             "count", text=f"{_count_sym(sym)} = {cardinality[column_key]}"))
    return EmitResult(cells=tuple(cells))


def emit_units(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_units_matrix(cells, resolved, geometry, context)
    _emit_units_const(cells, resolved, geometry, context)
    _emit_units_columns(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_units_matrix(cells, resolved, geometry, context) -> None:
    matrix_units = {
        "vectors": (resolved.dims.dimensionality, lambda i: query.vector_top(geometry, i), lambda i: f"{resolved.labels.domain_label}{_sub(i + 1)}/"),
        "canon": (resolved.dims.canonical_rank, lambda i: query.canon_top(geometry, i), lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
        "projection": (resolved.dims.dimensionality, lambda i: query.projection_top(geometry, i), lambda i: f"{resolved.labels.domain_label}{_sub(i + 1)}/"),
        "mapping": (resolved.dims.rank_shown, lambda i: query.map_top(geometry, i), lambda i: f"g{_sub(i + 1)}/"),
        "superspace_vectors": (resolved.dims.superspace_dimensionality, lambda i: query.superspace_vector_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
        "superspace_mapping": (resolved.dims.superspace_rank, lambda i: query.superspace_map_top(geometry, i), lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
        "superspace_projection": (resolved.dims.superspace_dimensionality, lambda i: query.superspace_projection_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
    }
    for key, (n, top, label) in matrix_units.items():
        if not query.tile_open(geometry, context.collapsed, key, "units"):
            continue
        for i in range(n):
            cells.append(CellBox(f"ucol:{key}:{i}", geometry.col_x["units"], top(i),
                                 geometry.col_w["units"], ROW_H, "units", text=label(i)))


def _emit_units_const(cells, resolved, geometry, context) -> None:
    const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                   "complexity": f"{resolved.scalars.complexity_unit}/", "weight": f"{resolved.scalars.weight_unit}/",
                   "damage": f"{resolved.scalars.damage_unit}/"}
    for key, text in const_units.items():
        if not query.tile_open(geometry, context.collapsed, key, "units"):
            continue
        n = geometry.rows[key].num_subrows
        for i in range(n):
            cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
            cells.append(CellBox(cid, geometry.col_x["units"], geometry.rows[key].y + i * ROW_H,
                                 geometry.col_w["units"], ROW_H, "units", text=text))


def _emit_units_columns(cells, resolved, geometry, context) -> None:
    if "units" not in geometry.rows:
        return
    uy = geometry.rows["units"].y
    column_units = {
        "canongens": (resolved.dims.canonical_rank, lambda i: query.canongen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
        "gens": (resolved.dims.rank, lambda i: query.gen_left(geometry, i), lambda i: f"/g{_sub(i + 1)}"),
        "primes": (resolved.dims.dimensionality, lambda i: query.prime_left(geometry, i), lambda i: f"/{resolved.labels.domain_label}{_sub(i + 1)}"),
        "superspace_generators": (resolved.dims.superspace_rank, lambda i: query.superspace_gen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
        "superspace_primes": (resolved.dims.superspace_dimensionality, lambda i: query.superspace_prime_left(geometry, i), lambda i: f"/p{_sub(i + 1)}"),
        "commas": (resolved.dims.vector_count_shown, lambda i: query.comma_left(geometry, resolved, i), lambda _i: "/1"),
        "detempering": (resolved.dims.rank, lambda i: query.detempering_left(geometry, i), lambda _i: "/1"),
        "targets": (resolved.dims.target_count_shown, lambda i: query.target_left(geometry, i), lambda _i: "/1"),
        "interest": (resolved.dims.interest_count_shown, lambda i: query.interest_left(geometry, i), lambda _i: "/1"),
        "held": (resolved.dims.held_count_shown, lambda i: query.held_left(geometry, i), lambda _i: "/1"),
    }
    for key, (n, left, label) in column_units.items():
        if not query.tile_open(geometry, context.collapsed, "units", key):
            continue
        for i in range(n):
            cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                 "units", text=label(i)))


def emit_quantities_row(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if "quantities" not in geometry.rows:
        return EmitResult()
    qy = geometry.rows["quantities"].y

    def branch_minus(cid, column_key, i, kind, **kw):
        cells.append(CellBox(cid, query.sub_axis_x(geometry, column_key, i) - COL_W / 2, geometry.fanout_y, COL_W,
                             qy - geometry.fanout_y, kind, **kw))

    _emit_qty_gens(cells, resolved, geometry, context, qy, branch_minus)
    _emit_qty_canongens(cells, resolved, geometry, context, qy)
    _emit_qty_primes(cells, resolved, geometry, context, qy, branch_minus)
    _emit_qty_superspace_generators(cells, resolved, geometry, context, qy)
    _emit_qty_superspace_primes(cells, resolved, geometry, context, qy)
    _emit_qty_commas(cells, resolved, geometry, context, qy, branch_minus)
    _emit_qty_detempering(cells, resolved, geometry, context, qy)
    _emit_qty_interests(cells, resolved, geometry, context, qy, branch_minus)
    _emit_qty_grips(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_qty_gens(cells, resolved, geometry, context, qy, branch_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "gens"):
        for g in range(resolved.dims.rank):
            cells.append(CellBox(f"qgen:{g}", query.gen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=resolved.scalars.gens[g], gen=g))
        if resolved.dims.rank > 1:
            branch_minus("gen_minus", "gens", resolved.dims.rank - 1, "gen_minus", gen=resolved.dims.rank - 1)


def _emit_qty_canongens(cells, resolved, geometry, context, qy) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "canongens"):
        for g in range(resolved.dims.canonical_rank):
            cells.append(CellBox(f"cangen:{g}", query.canongen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=resolved.canon.gens[g]))


def _emit_qty_primes(cells, resolved, geometry, context, qy, branch_minus) -> None:
    if not query.tile_open(geometry, context.collapsed, "quantities", "primes"):
        return
    for p in range(resolved.dims.dimensionality):
        text = str(resolved.dims.elements[p])
        kind = element_cell_kind(text) if resolved.flags.nonstandard_domain else "prime"
        cells.append(CellBox(f"prime:{p}", query.prime_left(geometry, p), qy, COL_W, ROW_H, kind, text=text, prime=p))
        voice(cells, "quantities:primes", p, resolved.tuning.tuning_map.just_map[p])
    if resolved.scalars.element_draft:
        draft_text = context.pending_element or "?/?"
        cells.append(CellBox("prime:pending", query.prime_left(geometry, resolved.dims.dimensionality), qy, COL_W, ROW_H,
                             element_cell_kind(draft_text), text=draft_text, prime=resolved.dims.dimensionality, pending=True))
        branch_minus("element_minus:pending", "primes", resolved.dims.dimensionality, "element_minus")
    if resolved.flags.nonstandard_domain:
        if resolved.dims.dimensionality > 1:
            for p in range(resolved.dims.dimensionality):
                branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
    elif resolved.scalars.domain_can_shrink:
        branch_minus("minus", "primes", resolved.dims.dimensionality - 1, "minus")


def _emit_qty_superspace_generators(cells, resolved, geometry, context, qy) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "superspace_generators"):
        superspace_gens = service.superspace_generators(context.state)
        for g in range(resolved.dims.superspace_rank):
            cells.append(CellBox(f"superspace_quantity_generator:{g}", query.superspace_gen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=superspace_gens[g]))


def _emit_qty_superspace_primes(cells, resolved, geometry, context, qy) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "superspace_primes"):
        for p in range(resolved.dims.superspace_dimensionality):
            cells.append(CellBox(f"superspace_quantity_prime:{p}", query.superspace_prime_left(geometry, p), qy, COL_W, ROW_H, "commaratio", text=str(resolved.dims.superspace_primes[p]), prime=p))


def _emit_qty_commas(cells, resolved, geometry, context, qy, branch_minus) -> None:
    if not query.tile_open(geometry, context.collapsed, "quantities", "commas"):
        return
    for c in range(resolved.dims.comma_count):
        cells.append(CellBox(f"comma:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), qy, COL_W, ROW_H, "ratiocell", text=resolved.commas.ratios[c], comma=c))
        voice(cells, "quantities:commas", c, resolved.tuning.comma_sizes.just[c])
    if resolved.scalars.comma_draft:
        cells.append(CellBox("comma:pending", query.comma_left(geometry, resolved, resolved.dims.comma_count), qy, COL_W, ROW_H,
                             "commaratio" if resolved.ghosts.comma else "ratiocell",
                             text=(resolved.ghosts.comma_ratio or DASH) if resolved.ghosts.comma else "?/?",
                             comma=resolved.dims.comma_count, pending=True))
    if resolved.unchanged.shown:
        full_u = resolved.unchanged.basis is not None and all(v is not None for v in resolved.unchanged.basis)
        for j in range(resolved.dims.unchanged_count):
            doomed = resolved.commas.pending is not None and j == resolved.dims.unchanged_count - 1
            cells.append(CellBox(f"unchanged:{j}", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + j), qy, COL_W, ROW_H,
                                 "ratiocell" if (full_u and not doomed) else "commaratio",
                                 text=resolved.unchanged.ratios[j] or DASH, comma=resolved.dims.comma_count + j))
            voice(cells, "quantities:commas", resolved.dims.comma_count + j, resolved.unchanged.sizes.just[j])
    for c in range(resolved.dims.comma_count):
        branch_minus(f"comma_minus:{query.col_token(resolved, 'commas', c)}", "commas", c, "comma_minus", comma=c)
    if resolved.commas.pending is not None:
        branch_minus("comma_minus:pending", "commas", resolved.dims.comma_count, "comma_minus")


def _emit_qty_detempering(cells, resolved, geometry, context, qy) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "detempering"):
        for i in range(resolved.dims.rank):
            cells.append(CellBox(f"detempering:{i}", query.detempering_left(geometry, i), qy, COL_W, ROW_H, "commaratio", text=resolved.scalars.gens[i]))
            voice(cells, "quantities:detempering", i, resolved.detempering.sizes.just[i])


def _emit_qty_interests(cells, resolved, geometry, context, qy, branch_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "quantities", "targets"):
        _emit_qty_list(cells, resolved, _QtyList("targets", "target", resolved.dims.target_count, lambda i: query.target_left(geometry, i), resolved.targets.ratios,
                                     resolved.tuning.target_sizes, resolved.targets.pending,
                                     "ratiocell" if resolved.scalars.targets_editable else "commaratio",
                                     resolved.scalars.targets_editable), qy, branch_minus)
    if query.tile_open(geometry, context.collapsed, "quantities", "held"):
        _emit_qty_list(cells, resolved, _QtyList("held", "held", resolved.dims.held_count, lambda i: query.held_left(geometry, i), resolved.held.ratios,
                                     resolved.tuning.held_sizes, resolved.held.pending, "ratiocell", True), qy, branch_minus)
    if query.tile_open(geometry, context.collapsed, "quantities", "interest"):
        _emit_qty_list(cells, resolved, _QtyList("interest", "interest", resolved.dims.interest_count, lambda i: query.interest_left(geometry, i), resolved.interest.ratios,
                                     resolved.tuning.interest_sizes, resolved.interest.pending, "ratiocell", True), qy, branch_minus)


def _emit_qty_list(cells, resolved, q: _QtyList, qy: float, branch_minus) -> None:
    for j in range(q.count):
        cells.append(CellBox(f"{q.singular}:{query.col_token(resolved, q.group, j)}", q.left_fn(j), qy, COL_W, ROW_H, q.kind, text=q.ratios[j], comma=j))
        voice(cells, f"quantities:{q.group}", j, q.sizes.just[j])
        if q.minus_gate:
            branch_minus(f"{q.singular}_minus:{j}", q.group, j, f"{q.singular}_minus", comma=j)
    if q.pending is not None:
        cells.append(CellBox(f"{q.singular}:pending", q.left_fn(q.count), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=q.count, pending=True))
        branch_minus(f"{q.singular}_minus:pending", q.group, q.count, f"{q.singular}_minus")


def _emit_qty_grips(cells, resolved, geometry, context) -> None:
    grip_top = geometry.branch_top_y + GAP - PAD
    counts = {"commas": resolved.dims.comma_count, "targets": resolved.dims.target_count, "held": resolved.dims.held_count, "interest": resolved.dims.interest_count}
    for column_key in ("commas", "targets", "held", "interest"):
        if query.row_open(geometry, context.collapsed, "quantities") and query.plus_shows(geometry, resolved, context.collapsed, context.state, column_key):
            _qty_drag_controls(cells, resolved, geometry, column_key, counts[column_key], grip_top)
    if resolved.unchanged.shown:
        for j in range(resolved.dims.unchanged_count):
            if resolved.unchanged.basis[j] is not None:
                cells.append(CellBox(f"grip:unchanged:{j}", query.sub_axis_x(geometry, "commas", resolved.dims.comma_count_shown + j) - COL_W / 2,
                                     grip_top, COL_W, GRIP_BAND, "colgrip", comma=j))


def _qty_drag_controls(cells, resolved, geometry, column_key, n, grip_top) -> None:
    for i in range(n):
        cells.append(CellBox(f"grip:{column_key}:{i}", query.sub_axis_x(geometry, column_key, i) - COL_W / 2,
                             grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
    add_w = COL_W
    if column_key == "commas" and resolved.unchanged.shown:
        add_w = resolved.unchanged.empty_comma_w if resolved.dims.comma_count_shown == 0 else V_SPLIT_GAP
    cells.append(CellBox(f"grip:{column_key}:add", geometry.plus_stub_x[column_key] - add_w / 2,
                         grip_top, add_w, GRIP_BAND, "colgrip"))


def emit_column_plus_controls(resolved, geometry) -> EmitResult:
    cells: list = []
    primes_plus = "element_plus" if resolved.flags.nonstandard_domain else "plus"
    for column_key, cid in (("gens", "gen_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                      ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
        if column_key in geometry.plus_stub_x:
            cells.append(CellBox(cid, geometry.plus_stub_x[column_key] - BUTTON / 2, geometry.fanout_y - BUTTON / 2, BUTTON, BUTTON, cid))
    return EmitResult(cells=tuple(cells))


def emit_rehomed_minus_controls(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, context.collapsed, "quantities") or not query.row_open(geometry, context.collapsed, "vectors"):
        return EmitResult()
    vtop = geometry.rows["vectors"].y

    def vector_minus(cid, column_key, i, kind, **kw):
        cells.append(CellBox(cid, query.sub_axis_x(geometry, column_key, i) - COL_W / 2, geometry.fanout_y,
                             COL_W, vtop - geometry.fanout_y, kind, **kw))

    _emit_rehomed_commas(resolved, geometry, context, vector_minus)
    _emit_rehomed_targets(resolved, geometry, context, vector_minus)
    _emit_rehomed_held(resolved, geometry, context, vector_minus)
    _emit_rehomed_interest(resolved, geometry, context, vector_minus)
    return EmitResult(cells=tuple(cells))


def _emit_rehomed_commas(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "commas"):
        for c in range(resolved.dims.comma_count):
            vector_minus(f"comma_minus:{query.col_token(resolved, 'commas', c)}", "commas", c, "comma_minus", comma=c)
        if resolved.commas.pending is not None:
            vector_minus("comma_minus:pending", "commas", resolved.dims.comma_count, "comma_minus")


def _emit_rehomed_targets(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "targets"):
        if resolved.scalars.targets_editable:
            for j in range(resolved.dims.target_count):
                vector_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
        if resolved.targets.pending is not None:
            vector_minus("target_minus:pending", "targets", resolved.dims.target_count, "target_minus")


def _emit_rehomed_held(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "held"):
        for i in range(resolved.dims.held_count):
            vector_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
        if resolved.held.pending is not None:
            vector_minus("held_minus:pending", "held", resolved.dims.held_count, "held_minus")


def _emit_rehomed_interest(resolved, geometry, context, vector_minus) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "interest"):
        for i in range(resolved.dims.interest_count):
            vector_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
        if resolved.interest.pending is not None:
            vector_minus("interest_minus:pending", "interest", resolved.dims.interest_count, "interest_minus")

