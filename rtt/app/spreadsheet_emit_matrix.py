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
    BTN,
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


def emit_headers(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    for key in geometry.col_x:
        hx = geometry.col_x[key] + query.outer_gutter_w(geometry, key)
        hw = geometry.col_w[key] - 2 * query.outer_gutter_w(geometry, key)
        cells.append(CellBox(f"header:{key}", hx, geometry.header_y, hw, HEADER_H, "colheader", text=geometry.col_header[key]))
        if geometry.col_collapsible[key]:
            glyph = _fold_glyph(f"col:{key}" in ctx.collapsed)
            tx = hx + (hw - TOGGLE) / 2
            cells.append(CellBox(f"toggle:col:{key}", tx, geometry.col_node_y, TOGGLE, TOGGLE, "coltoggle", text=glyph))
    for key in geometry.rows:
        label = geometry.rows[key].label
        if geometry.size_factor or _r.scalars.prescaler_is_matrix:
            label = _pretransform_label(label)
            label = label.replace(" pretransforming", chr(160) + "pre-" + chr(10) + "transforming")
        cells.append(CellBox(f"label:{key}", 0, geometry.rows[key].y, LABEL_W, geometry.rows[key].h, "rowlabel", text=label))
        if geometry.rows[key].collapsible:
            glyph = _fold_glyph(f"row:{key}" in ctx.collapsed)
            ty = geometry.rows[key].y + (geometry.rows[key].h - TOGGLE) / 2
            cells.append(CellBox(f"toggle:row:{key}", geometry.node_x, ty, TOGGLE, TOGGLE, "rowtoggle", text=glyph))
    foldable = _foldable_ids(cells)
    all_collapsed = bool(foldable) and foldable <= ctx.collapsed
    cells.append(CellBox("toggle:all", geometry.node_x, geometry.col_node_y, TOGGLE, TOGGLE, "alltoggle",
                         text=_fold_glyph(all_collapsed)))
    return EmitResult(cells=tuple(cells))


def emit_counts_row(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    if not query.row_open(geometry, ctx.collapsed, "counts"):
        return EmitResult()
    cardinality = {"gens": _r.dims.r, "primes": _r.dims.d, "commas": ctx.state.n, "targets": _r.dims.k, "held": _r.dims.nh,
                   "detempering": _r.dims.r,
                   "ssgens": _r.dims.rL, "ssprimes": _r.dims.dL}
    for ckey, sym, _name in COUNTS + OPTIMIZATION_COUNTS + DETEMPERING_COUNTS + SUPERSPACE_COUNTS:
        if not query.tile_open(geometry, ctx.collapsed, "counts", ckey):
            continue
        if ckey == "commas" and _r.unchanged.shown:
            comma_half_w = _r.dims.nc * COL_W + _r.unchanged.empty_comma_w
            if comma_half_w:
                comma_half_x = geometry.commas_x if _r.unchanged.empty_comma_w else query.comma_left(geometry, _r, 0)
                cells.append(CellBox("count:commas", comma_half_x, geometry.rows["counts"].y, comma_half_w, ROW_H,
                                     "count", text=f"{_count_sym('n')} = {ctx.state.n}"))
            cells.append(CellBox("count:commas:u", query.comma_left(geometry, _r, _r.dims.nc_shown), geometry.rows["counts"].y, _r.dims.nu * COL_W, ROW_H,
                                 "count", text=f"{_count_sym('u')} = {_r.dims.nu}"))
            continue
        cnt_x, cnt_w = query.tile_span_box(geometry, "counts", ckey)
        cells.append(CellBox(f"count:{ckey}", cnt_x, geometry.rows["counts"].y, cnt_w, ROW_H,
                             "count", text=f"{_count_sym(sym)} = {cardinality[ckey]}"))
    return EmitResult(cells=tuple(cells))


def emit_units(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    _emit_units_matrix(cells, resolved, geometry, ctx)
    _emit_units_const(cells, resolved, geometry, ctx)
    _emit_units_columns(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_units_matrix(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    matrix_units = {
        "vectors": (_r.dims.d, lambda i: query.vec_top(geometry, i), lambda i: f"{_r.labels.domain_label}{_sub(i + 1)}/"),
        "canon": (_r.dims.rc, lambda i: query.canon_top(geometry, i), lambda i: f"g{SUBSCRIPT_C}{_sub(i + 1)}/"),
        "projection": (_r.dims.d, lambda i: query.proj_top(geometry, i), lambda i: f"{_r.labels.domain_label}{_sub(i + 1)}/"),
        "mapping": (_r.dims.r_shown, lambda i: query.map_top(geometry, i), lambda i: f"g{_sub(i + 1)}/"),
        "ss_vectors": (_r.dims.dL, lambda i: query.ss_vec_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
        "ss_mapping": (_r.dims.rL, lambda i: query.ss_map_top(geometry, i), lambda i: f"g{SUBSCRIPT_L}{_sub(i + 1)}/"),
        "ss_projection": (_r.dims.dL, lambda i: query.ss_proj_top(geometry, i), lambda i: f"p{_sub(i + 1)}/"),
    }
    for key, (n, top, label) in matrix_units.items():
        if not query.tile_open(geometry, ctx.collapsed, key, "units"):
            continue
        for i in range(n):
            cells.append(CellBox(f"ucol:{key}:{i}", geometry.col_x["units"], top(i),
                                 geometry.col_w["units"], ROW_H, "units", text=label(i)))


def _emit_units_const(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    const_units = {"tuning": "¢/", "just": "¢/", "retune": "¢/", "prescaling": "oct/",
                   "complexity": f"{_r.scalars.complexity_unit}/", "weight": f"{_r.scalars.weight_unit}/",
                   "damage": f"{_r.scalars.damage_unit}/"}
    for key, text in const_units.items():
        if not query.tile_open(geometry, ctx.collapsed, key, "units"):
            continue
        n = geometry.rows[key].nsub
        for i in range(n):
            cid = f"ucol:{key}:{i}" if n > 1 else f"ucol:{key}"
            cells.append(CellBox(cid, geometry.col_x["units"], geometry.rows[key].y + i * ROW_H,
                                 geometry.col_w["units"], ROW_H, "units", text=text))


def _emit_units_columns(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if "units" not in geometry.rows:
        return
    uy = geometry.rows["units"].y
    column_units = {
        "canongens": (_r.dims.rc, lambda i: query.canongen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_C}{_sub(i + 1)}"),
        "gens": (_r.dims.r, lambda i: query.gen_left(geometry, i), lambda i: f"/g{_sub(i + 1)}"),
        "primes": (_r.dims.d, lambda i: query.prime_left(geometry, i), lambda i: f"/{_r.labels.domain_label}{_sub(i + 1)}"),
        "ssgens": (_r.dims.rL, lambda i: query.ss_gen_left(geometry, i), lambda i: f"/g{SUBSCRIPT_L}{_sub(i + 1)}"),
        "ssprimes": (_r.dims.dL, lambda i: query.ss_prime_left(geometry, i), lambda i: f"/p{_sub(i + 1)}"),
        "commas": (_r.dims.nv_shown, lambda i: query.comma_left(geometry, _r, i), lambda _i: "/1"),
        "detempering": (_r.dims.r, lambda i: query.detempering_left(geometry, i), lambda _i: "/1"),
        "targets": (_r.dims.k_shown, lambda i: query.target_left(geometry, i), lambda _i: "/1"),
        "interest": (_r.dims.mi_shown, lambda i: query.interest_left(geometry, i), lambda _i: "/1"),
        "held": (_r.dims.nh_shown, lambda i: query.held_left(geometry, i), lambda _i: "/1"),
    }
    for key, (n, left, label) in column_units.items():
        if not query.tile_open(geometry, ctx.collapsed, "units", key):
            continue
        for i in range(n):
            cells.append(CellBox(f"urow:{key}:{i}", left(i), uy, COL_W, ROW_H,
                                 "units", text=label(i)))


def emit_quantities_row(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    if "quantities" not in geometry.rows:
        return EmitResult()
    qy = geometry.rows["quantities"].y

    def branch_minus(cid, ckey, i, kind, **kw):
        cells.append(CellBox(cid, query.sub_axis_x(geometry, ckey, i) - COL_W / 2, geometry.fanout_y, COL_W,
                             qy - geometry.fanout_y, kind, **kw))

    _emit_qty_gens(cells, resolved, geometry, ctx, qy, branch_minus)
    _emit_qty_canongens(cells, resolved, geometry, ctx, qy)
    _emit_qty_primes(cells, resolved, geometry, ctx, qy, branch_minus)
    _emit_qty_ssgens(cells, resolved, geometry, ctx, qy)
    _emit_qty_ssprimes(cells, resolved, geometry, ctx, qy)
    _emit_qty_commas(cells, resolved, geometry, ctx, qy, branch_minus)
    _emit_qty_detempering(cells, resolved, geometry, ctx, qy)
    _emit_qty_interests(cells, resolved, geometry, ctx, qy, branch_minus)
    _emit_qty_grips(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_qty_gens(cells, resolved, geometry, ctx, qy, branch_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "gens"):
        for g in range(_r.dims.r):
            cells.append(CellBox(f"qgen:{g}", query.gen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=_r.scalars.gens[g], gen=g))
        if _r.dims.r > 1:
            branch_minus("gen_minus", "gens", _r.dims.r - 1, "gen_minus", gen=_r.dims.r - 1)


def _emit_qty_canongens(cells, resolved, geometry, ctx, qy) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "canongens"):
        for g in range(_r.dims.rc):
            cells.append(CellBox(f"cangen:{g}", query.canongen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=_r.canon.gens[g]))


def _emit_qty_primes(cells, resolved, geometry, ctx, qy, branch_minus) -> None:
    _r = resolved
    if not query.tile_open(geometry, ctx.collapsed, "quantities", "primes"):
        return
    for p in range(_r.dims.d):
        text = str(_r.dims.elements[p])
        kind = element_cell_kind(text) if _r.flags.nonstandard_domain else "prime"
        cells.append(CellBox(f"prime:{p}", query.prime_left(geometry, p), qy, COL_W, ROW_H, kind, text=text, prime=p))
        voice(cells, "quantities:primes", p, _r.tuning.tun.just_map[p])
    if _r.scalars.element_draft:
        draft_text = ctx.pending_element or "?/?"
        cells.append(CellBox("prime:pending", query.prime_left(geometry, _r.dims.d), qy, COL_W, ROW_H,
                             element_cell_kind(draft_text), text=draft_text, prime=_r.dims.d, pending=True))
        branch_minus("element_minus:pending", "primes", _r.dims.d, "element_minus")
    if _r.flags.nonstandard_domain:
        if _r.dims.d > 1:
            for p in range(_r.dims.d):
                branch_minus(f"element_minus:{p}", "primes", p, "element_minus", prime=p)
    elif _r.scalars.domain_can_shrink:
        branch_minus("minus", "primes", _r.dims.d - 1, "minus")


def _emit_qty_ssgens(cells, resolved, geometry, ctx, qy) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "ssgens"):
        ss_gens = service.superspace_generators(ctx.state)
        for g in range(_r.dims.rL):
            cells.append(CellBox(f"ssqgen:{g}", query.ss_gen_left(geometry, g), qy, COL_W, ROW_H, "genratio", text=ss_gens[g]))


def _emit_qty_ssprimes(cells, resolved, geometry, ctx, qy) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "ssprimes"):
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"ssqprime:{p}", query.ss_prime_left(geometry, p), qy, COL_W, ROW_H, "prime", text=str(_r.dims.superspace_primes[p]), prime=p))


def _emit_qty_commas(cells, resolved, geometry, ctx, qy, branch_minus) -> None:
    _r = resolved
    if not query.tile_open(geometry, ctx.collapsed, "quantities", "commas"):
        return
    for c in range(_r.dims.nc):
        cells.append(CellBox(f"comma:{query.col_token(_r, 'commas', c)}", query.comma_left(geometry, _r, c), qy, COL_W, ROW_H, "ratiocell", text=_r.commas.ratios[c], comma=c))
        voice(cells, "quantities:commas", c, _r.tuning.comma_sizes.just[c])
    if _r.scalars.comma_draft:
        cells.append(CellBox("comma:pending", query.comma_left(geometry, _r, _r.dims.nc), qy, COL_W, ROW_H,
                             "commaratio" if _r.ghosts.comma else "ratiocell",
                             text=(_r.ghosts.comma_ratio or DASH) if _r.ghosts.comma else "?/?",
                             comma=_r.dims.nc, pending=True))
    if _r.unchanged.shown:
        full_u = _r.unchanged.basis is not None and all(v is not None for v in _r.unchanged.basis)
        for j in range(_r.dims.nu):
            doomed = _r.commas.pending is not None and j == _r.dims.nu - 1
            cells.append(CellBox(f"unchanged:{j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), qy, COL_W, ROW_H,
                                 "ratiocell" if (full_u and not doomed) else "commaratio",
                                 text=_r.unchanged.ratios[j] or DASH, comma=_r.dims.nc + j))
            voice(cells, "quantities:commas", _r.dims.nc + j, _r.unchanged.sizes.just[j])
    for c in range(_r.dims.nc):
        branch_minus(f"comma_minus:{query.col_token(_r, 'commas', c)}", "commas", c, "comma_minus", comma=c)
    if _r.commas.pending is not None:
        branch_minus("comma_minus:pending", "commas", _r.dims.nc, "comma_minus")


def _emit_qty_detempering(cells, resolved, geometry, ctx, qy) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "detempering"):
        for i in range(_r.dims.r):
            cells.append(CellBox(f"detempering:{i}", query.detempering_left(geometry, i), qy, COL_W, ROW_H, "commaratio", text=_r.scalars.gens[i]))
            voice(cells, "quantities:detempering", i, _r.detempering.sizes.just[i])


def _emit_qty_interests(cells, resolved, geometry, ctx, qy, branch_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "quantities", "targets"):
        _emit_qty_list(cells, resolved, _QtyList("targets", "target", _r.dims.k, lambda i: query.target_left(geometry, i), _r.targets.ratios,
                                     _r.tuning.target_sizes, _r.targets.pending,
                                     "ratiocell" if _r.scalars.targets_editable else "commaratio",
                                     _r.scalars.targets_editable), qy, branch_minus)
    if query.tile_open(geometry, ctx.collapsed, "quantities", "held"):
        _emit_qty_list(cells, resolved, _QtyList("held", "held", _r.dims.nh, lambda i: query.held_left(geometry, i), _r.held.ratios,
                                     _r.tuning.held_sizes, _r.held.pending, "ratiocell", True), qy, branch_minus)
    if query.tile_open(geometry, ctx.collapsed, "quantities", "interest"):
        _emit_qty_list(cells, resolved, _QtyList("interest", "interest", _r.dims.mi, lambda i: query.interest_left(geometry, i), _r.interest.ratios,
                                     _r.tuning.interest_sizes, _r.interest.pending, "ratiocell", True), qy, branch_minus)


def _emit_qty_list(cells, resolved, q: _QtyList, qy: float, branch_minus) -> None:
    for j in range(q.count):
        cells.append(CellBox(f"{q.singular}:{query.col_token(resolved, q.group, j)}", q.left_fn(j), qy, COL_W, ROW_H, q.kind, text=q.ratios[j], comma=j))
        voice(cells, f"quantities:{q.group}", j, q.sizes.just[j])
        if q.minus_gate:
            branch_minus(f"{q.singular}_minus:{j}", q.group, j, f"{q.singular}_minus", comma=j)
    if q.pending is not None:
        cells.append(CellBox(f"{q.singular}:pending", q.left_fn(q.count), qy, COL_W, ROW_H, "ratiocell", text="?/?", comma=q.count, pending=True))
        branch_minus(f"{q.singular}_minus:pending", q.group, q.count, f"{q.singular}_minus")


def _emit_qty_grips(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    grip_top = geometry.branch_top_y + GAP - PAD
    counts = {"commas": _r.dims.nc, "targets": _r.dims.k, "held": _r.dims.nh, "interest": _r.dims.mi}
    for ckey in ("commas", "targets", "held", "interest"):
        if query.row_open(geometry, ctx.collapsed, "quantities") and query.plus_shows(geometry, resolved, ctx.collapsed, ctx.state, ckey):
            _qty_drag_controls(cells, resolved, geometry, ckey, counts[ckey], grip_top)
    if _r.unchanged.shown:
        for j in range(_r.dims.nu):
            if _r.unchanged.basis[j] is not None:
                cells.append(CellBox(f"grip:unchanged:{j}", query.sub_axis_x(geometry, "commas", _r.dims.nc_shown + j) - COL_W / 2,
                                     grip_top, COL_W, GRIP_BAND, "colgrip", comma=j))


def _qty_drag_controls(cells, resolved, geometry, ckey, n, grip_top) -> None:
    _r = resolved
    for i in range(n):
        cells.append(CellBox(f"grip:{ckey}:{i}", query.sub_axis_x(geometry, ckey, i) - COL_W / 2,
                             grip_top, COL_W, GRIP_BAND, "colgrip", comma=i))
    add_w = COL_W
    if ckey == "commas" and _r.unchanged.shown:
        add_w = _r.unchanged.empty_comma_w if _r.dims.nc_shown == 0 else V_SPLIT_GAP
    cells.append(CellBox(f"grip:{ckey}:add", geometry.plus_stub_x[ckey] - add_w / 2,
                         grip_top, add_w, GRIP_BAND, "colgrip"))


def emit_column_plus_controls(resolved, geometry) -> EmitResult:
    _r = resolved
    cells: list = []
    primes_plus = "element_plus" if _r.flags.nonstandard_domain else "plus"
    for ckey, cid in (("gens", "gen_plus"), ("primes", primes_plus), ("commas", "comma_plus"),
                      ("targets", "target_plus"), ("held", "held_plus"), ("interest", "interest_plus")):
        if ckey in geometry.plus_stub_x:
            cells.append(CellBox(cid, geometry.plus_stub_x[ckey] - BTN / 2, geometry.fanout_y - BTN / 2, BTN, BTN, cid))
    return EmitResult(cells=tuple(cells))


def emit_rehomed_minus_controls(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, ctx.collapsed, "quantities") or not query.row_open(geometry, ctx.collapsed, "vectors"):
        return EmitResult()
    vtop = geometry.rows["vectors"].y

    def vec_minus(cid, ckey, i, kind, **kw):
        cells.append(CellBox(cid, query.sub_axis_x(geometry, ckey, i) - COL_W / 2, geometry.fanout_y,
                             COL_W, vtop - geometry.fanout_y, kind, **kw))

    _emit_rehomed_commas(resolved, geometry, ctx, vec_minus)
    _emit_rehomed_targets(resolved, geometry, ctx, vec_minus)
    _emit_rehomed_held(resolved, geometry, ctx, vec_minus)
    _emit_rehomed_interest(resolved, geometry, ctx, vec_minus)
    return EmitResult(cells=tuple(cells))


def _emit_rehomed_commas(resolved, geometry, ctx, vec_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "vectors", "commas"):
        for c in range(_r.dims.nc):
            vec_minus(f"comma_minus:{query.col_token(_r, 'commas', c)}", "commas", c, "comma_minus", comma=c)
        if _r.commas.pending is not None:
            vec_minus("comma_minus:pending", "commas", _r.dims.nc, "comma_minus")


def _emit_rehomed_targets(resolved, geometry, ctx, vec_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "vectors", "targets"):
        if _r.scalars.targets_editable:
            for j in range(_r.dims.k):
                vec_minus(f"target_minus:{j}", "targets", j, "target_minus", comma=j)
        if _r.targets.pending is not None:
            vec_minus("target_minus:pending", "targets", _r.dims.k, "target_minus")


def _emit_rehomed_held(resolved, geometry, ctx, vec_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "vectors", "held"):
        for i in range(_r.dims.nh):
            vec_minus(f"held_minus:{i}", "held", i, "held_minus", comma=i)
        if _r.held.pending is not None:
            vec_minus("held_minus:pending", "held", _r.dims.nh, "held_minus")


def _emit_rehomed_interest(resolved, geometry, ctx, vec_minus) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "vectors", "interest"):
        for i in range(_r.dims.mi):
            vec_minus(f"interest_minus:{i}", "interest", i, "interest_minus", comma=i)
        if _r.interest.pending is not None:
            vec_minus("interest_minus:pending", "interest", _r.dims.mi, "interest_minus")

