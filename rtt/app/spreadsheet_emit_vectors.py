from __future__ import annotations

from rtt.app import ids, service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    COMMAPICK_GAP,
    DASH,
    KET_INSET,
    ROW_H,
    ROW_HANDLE_W,
)
from rtt.app.spreadsheet_emit_mapping import emit_mapped_grid
from rtt.app.spreadsheet_emit_model import EmitResult, element_cell_kind, voice
from rtt.app.spreadsheet_models import _VecGrid


def emit_vectors(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    if not query.row_open(geometry, ctx.collapsed, "vectors"):
        return EmitResult()
    if query.tile_open(geometry, ctx.collapsed, "vectors", "quantities"):
        _emit_vectors_basis_col(cells, resolved, geometry, ctx)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "commas"):
        _emit_vectors_commas_col(cells, resolved, geometry, ctx)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "targets"):
        target_kind = "targetcell" if _r.scalars.targets_editable else "vec"
        cell_inset = KET_INSET if _r.scalars.targets_editable else 0
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("targets", _r.dims.k, ids.target_cell,
            lambda i: query.target_left(geometry, i), cell_inset, target_kind, "targetcell",
            _r.targets.vectors, _r.targets.pending, _r.tuning.target_sizes))
    if query.tile_open(geometry, ctx.collapsed, "vectors", "held"):
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("held", _r.dims.nh, ids.held_cell,
            lambda i: query.held_left(geometry, i), 0, "heldcell", "heldcell",
            _r.held.vectors, _r.held.pending, _r.tuning.held_sizes))
    if query.tile_open(geometry, ctx.collapsed, "vectors", "detempering"):
        _emit_vectors_detempering_col(cells, resolved, geometry)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "interest"):
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("interest", _r.dims.mi, ids.interest_cell,
            lambda i: query.interest_left(geometry, i), KET_INSET, "interestcell", "interestcell",
            _r.interest.vectors, _r.interest.pending, _r.tuning.interest_sizes))
    _emit_vectors_int_handles(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_vec_grid(cells, resolved, geometry, g: _VecGrid) -> None:
    _r = resolved
    for col in range(g.count):
        for p in range(_r.dims.d):
            cells.append(CellBox(g.id_fn(query.col_token(_r, g.group, col), p), g.left_fn(col) + g.inset, query.vec_top(geometry, p), COL_W - 2 * g.inset, ROW_H, g.committed_kind, text=str(g.data[col][p]), prime=p, comma=col, unit=query.cell_unit(_r, "vectors", g.group, prime=p)))
            voice(cells, f"vectors:{g.group}", col, g.sizes.just[col])
    if g.pending is not None:
        for p in range(_r.dims.d):
            v = g.pending[p]
            cells.append(CellBox(g.id_fn(query.pending_col_token(_r, g.group), p), g.left_fn(g.count) + g.inset, query.vec_top(geometry, p), COL_W - 2 * g.inset, ROW_H, g.pending_kind,
                                 text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=query.cell_unit(_r, "vectors", g.group, prime=p)))


def _basis_col_x(geometry):
    bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
    basis_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "vectors") else geometry.node_edge
    return bx, basis_bus_x


def _emit_basis_minus(cells, geometry, cid, p, kind, **kw):
    bx, basis_bus_x = _basis_col_x(geometry)
    cells.append(CellBox(cid, basis_bus_x, query.vec_top(geometry, p),
                         (bx + COL_W) - basis_bus_x, ROW_H, kind, **kw))


def _emit_vectors_basis_col(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    bx, basis_bus_x = _basis_col_x(geometry)
    for p in range(_r.dims.d):
        text = str(_r.dims.elements[p])
        kind = element_cell_kind(text) if _r.flags.nonstandard_domain else "prime"
        cells.append(CellBox(f"basis:{p}", bx, query.vec_top(geometry, p), COL_W, ROW_H, kind, text=text, prime=p))
    if _r.scalars.element_draft:
        draft_text = ctx.pending_element or "?/?"
        cells.append(CellBox("basis:pending", bx, query.vec_top(geometry, _r.dims.d), COL_W, ROW_H,
                                  element_cell_kind(draft_text), text=draft_text, prime=_r.dims.d, pending=True))
        _emit_basis_minus(cells, geometry, "element_minus:basis:pending", _r.dims.d, "element_minus")
    if _r.flags.nonstandard_domain:
        if _r.dims.d > 1:
            for p in range(_r.dims.d):
                _emit_basis_minus(cells, geometry, f"element_minus:basis:{p}", p, "element_minus", prime=p)
    elif _r.scalars.domain_can_shrink:
        _emit_basis_minus(cells, geometry, "basis_minus", _r.dims.d - 1, "basis_minus")
    if "vectors" in geometry.row_plus_y:
        plus_kind = "element_plus" if _r.flags.nonstandard_domain else "plus"
        cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, geometry.row_plus_y["vectors"] - BTN / 2,
                             BTN, BTN, plus_kind))


def _emit_vectors_commas_col(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    for c in range(_r.dims.nc):
        for p in range(_r.dims.d):
            cells.append(CellBox(ids.comma_cell(query.col_token(_r, 'commas', c), p), query.comma_left(geometry, _r, c), query.vec_top(geometry, p), COL_W, ROW_H, "commacell", text=str(ctx.state.comma_basis[c][p]), prime=p, comma=c, unit=query.cell_unit(_r, "vectors", "commas", prime=p)))
            voice(cells, "vectors:commas", c, _r.tuning.comma_sizes.just[c])
        if _r.flags.presets:
            cells.append(CellBox(f"commapick:{query.col_token(_r, 'commas', c)}", query.comma_left(geometry, _r, c), query.cpick_band_y(geometry, "vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=c))
    full_u = _r.unchanged.basis is not None and all(v is not None for v in _r.unchanged.basis)
    for j in range(_r.dims.nu):
        doomed = _r.commas.pending is not None and j == _r.dims.nu - 1
        born = _r.unchanged.born and j == _r.dims.nu - 1
        for p in range(_r.dims.d):
            vec_text = DASH if _r.unchanged.basis[j] is None else str(_r.unchanged.basis[j][p])
            cells.append(CellBox(ids.unchanged_cell(j, p), query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.vec_top(geometry, p), COL_W, ROW_H,
                                 "unchangedcell" if (full_u and not doomed and not born) else "vec", text=vec_text, prime=p, comma=_r.dims.nc + j,
                                 unit=query.cell_unit(_r, "vectors", "commas", prime=p)))
        voice(cells, "vectors:commas", _r.dims.nc + j, _r.unchanged.sizes.just[j])
    if _r.scalars.comma_draft:
        col_kind = "vec" if _r.ghosts.comma else "commacell"
        for p in range(_r.dims.d):
            v = _r.ghosts.comma_vec[p] if _r.ghosts.comma else _r.commas.pending[p]
            cells.append(CellBox(ids.comma_cell(query.pending_col_token(_r, 'commas'), p), query.comma_left(geometry, _r, _r.dims.nc), query.vec_top(geometry, p), COL_W, ROW_H, col_kind,
                                 text="" if v is None else str(v), prime=p, comma=_r.dims.nc, pending=True, unit=query.cell_unit(_r, "vectors", "commas", prime=p)))
        if _r.commas.pending is not None and _r.flags.presets:
            cells.append(CellBox("commapick:draft", query.comma_left(geometry, _r, _r.dims.nc), query.cpick_band_y(geometry, "vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=_r.dims.nc, pending=True))


def _emit_vectors_detempering_col(cells, resolved, geometry) -> None:
    _r = resolved
    for i in range(_r.dims.r):
        for p in range(_r.dims.d):
            cells.append(CellBox(f"cell:vec:detempering:{query.col_token(_r, 'detempering', i)}:{p}", query.detempering_left(geometry, i), query.vec_top(geometry, p), COL_W, ROW_H, "vec", text=str(_r.detempering.vectors[i][p]), unit=query.cell_unit(_r, "vectors", "detempering", prime=p)))
            voice(cells, "vectors:detempering", i, _r.detempering.sizes.just[i])


def _emit_vectors_int_handles(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if "vectors" in geometry.rows and geometry.rows["vectors"].int_handle_top is not None:
        hy = geometry.rows["vectors"].int_handle_top
        for group, count, col_left, ckey in (("comma", _r.dims.nc, lambda i: query.comma_left(geometry, _r, i), "commas"),
                                             ("target", _r.dims.k, lambda i: query.target_left(geometry, i), "targets"),
                                             ("held", _r.dims.nh, lambda i: query.held_left(geometry, i), "held"),
                                             ("interest", _r.dims.mi, lambda i: query.interest_left(geometry, i), "interest")):
            if count >= 2 and query.tile_open(geometry, ctx.collapsed, "vectors", ckey) and (ckey != "targets" or _r.scalars.targets_editable):
                for i in range(count):
                    cells.append(CellBox(f"int_drag:{group}:{i}", col_left(i), hy, COL_W, ROW_HANDLE_W, "int_drag", comma=i))


def emit_superspace_rows(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    _emit_ss_quantity_rows(cells, resolved, geometry, ctx)
    _emit_ss_matrix_vectors(cells, resolved, geometry, ctx)
    _emit_ss_matrix_mapping(cells, resolved, geometry, ctx)
    _emit_ss_vector_lists(cells, resolved, geometry, ctx)
    _emit_ss_projection_rows(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_ss_quantity_rows(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"ss_basis:{p}", bx, query.ss_vec_top(geometry, p), COL_W, ROW_H,
                                 "prime", text=str(_r.dims.superspace_primes[p]), prime=p))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "quantities"):
        ss_gens = service.superspace_generators(ctx.state)
        for i in range(_r.dims.rL):
            cells.append(CellBox(f"ss_gen:{i}", geometry.col_x["quantities"], query.ss_map_top(geometry, i),
                                 geometry.col_w["quantities"], ROW_H, "genratio",
                                 text=ss_gens[i] if i < len(ss_gens) else ""))
    if query.row_open(geometry, cl, "ss_projection") and query.tile_open(geometry, cl, "ss_projection", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"ss_proj_basis:{p}", bx, query.ss_proj_top(geometry, p), COL_W, ROW_H, "prime",
                                 text=str(_r.dims.superspace_primes[p]), prime=p))


def _emit_ss_matrix_vectors(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "primes"):
        basis = service.basis_in_superspace(_r.dims.elements)
        for ss_prime_idx in range(_r.dims.dL):
            for elem_idx in range(_r.dims.d):
                value = basis[elem_idx][ss_prime_idx]
                cells.append(CellBox(
                    f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}",
                    query.prime_left(geometry, elem_idx), query.ss_vec_top(geometry, ss_prime_idx), COL_W, ROW_H,
                    "vec", text=str(value), prime=ss_prime_idx, comma=elem_idx,
                    unit=query.cell_unit(_r, "ss_vectors", "primes", prime=ss_prime_idx, elem=elem_idx)))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssprimes"):
        ml = service.superspace_mapping(ctx.state)
        for gen_idx in range(_r.dims.rL):
            for ss_prime_idx in range(_r.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}",
                    query.ss_prime_left(geometry, ss_prime_idx), query.ss_map_top(geometry, gen_idx), COL_W, ROW_H,
                    "mapped", text=str(ml[gen_idx][ss_prime_idx]), gen=gen_idx, prime=ss_prime_idx,
                    unit=query.cell_unit(_r, "ss_mapping", "ssprimes", gen=gen_idx, prime=ss_prime_idx)))
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "ssprimes"):
        mjl = service.superspace_just_mapping(_r.dims.superspace_primes)
        for i in range(_r.dims.dL):
            for j in range(_r.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_vectors:ssprimes:{i}:{j}",
                    query.ss_prime_left(geometry, j), query.ss_vec_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(mjl[i][j]), gen=i, prime=j,
                    unit=query.cell_unit(_r, "ss_vectors", "ssprimes", prime=j)))


def _emit_ss_matrix_mapping(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssgens"):
        mlgl = service.superspace_self_map(ctx.state)
        for i in range(_r.dims.rL):
            for j in range(_r.dims.rL):
                cells.append(CellBox(
                    f"cell:ss_mapping:ssgens:{i}:{j}",
                    query.ss_gen_left(geometry, j), query.ss_map_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(mlgl[i][j]), gen=i,
                    unit=query.cell_unit(_r, "ss_mapping", "ssgens", gen=i)))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "primes"):
        msl = service.mapping_to_superspace_generators(ctx.state)
        for i in range(_r.dims.rL):
            for e in range(_r.dims.d):
                cells.append(CellBox(
                    f"cell:ss_mapping:primes:{i}:{e}",
                    query.prime_left(geometry, e), query.ss_map_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(msl[i][e]), gen=i,
                    unit=query.cell_unit(_r, "ss_mapping", "primes", gen=i, elem=e)))


def _emit_ss_vector_lists(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    ss_lists = (("commas", ctx.state.comma_basis, _r.dims.nc, lambda c: query.comma_left(geometry, _r, c), _r.scalars.comma_draft),
                ("targets", _r.targets.vectors, _r.dims.k, lambda c: query.target_left(geometry, c), _r.targets.pending is not None),
                ("held", _r.held.vectors, _r.dims.nh, lambda c: query.held_left(geometry, c), _r.held.pending is not None),
                ("interest", _r.interest.vectors, _r.dims.mi, lambda c: query.interest_left(geometry, c), _r.interest.pending is not None),
                ("detempering", _r.detempering.vectors, _r.dims.r, lambda c: query.detempering_left(geometry, c), False))
    for row in ss_lists:
        _emit_ss_vector_list_lift(cells, resolved, geometry, ctx, row)
        _emit_ss_vector_list_map(cells, resolved, geometry, ctx, row)


def _emit_ss_vector_list_lift(cells, resolved, geometry, ctx, row) -> None:
    _r = resolved
    ckey, vectors, n, left, draft = row
    cols = tuple(vectors)[:n]
    if not (query.row_open(geometry, ctx.collapsed, "ss_vectors") and query.tile_open(geometry, ctx.collapsed, "ss_vectors", ckey)):
        return
    lifted = service.lift_vectors_to_superspace(_r.dims.elements, cols)
    for c in range(len(lifted)):
        for p in range(_r.dims.dL):
            cells.append(CellBox(
                f"cell:ss_vectors:{ckey}:{p}:{c}", left(c), query.ss_vec_top(geometry, p),
                COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                unit=query.cell_unit(_r, "ss_vectors", ckey, prime=p)))
    if draft:
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"cell:ss_vectors:{ckey}:{p}:draft", left(n), query.ss_vec_top(geometry, p),
                                 COL_W, ROW_H, "vec", text="", prime=p, pending=True))
    if ckey == "commas":
        for j in range(_r.dims.nu):
            uj = _r.projection.ss_unchanged[j]
            for p in range(_r.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_vectors:commas:{p}:u{j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.ss_vec_top(geometry, p),
                    COL_W, ROW_H, "vec", text=DASH if uj is None else str(uj[p]), prime=p, comma=_r.dims.nc + j,
                    unit=query.cell_unit(_r, "ss_vectors", "commas", prime=p)))


def _emit_ss_vector_list_map(cells, resolved, geometry, ctx, row) -> None:
    _r = resolved
    ckey, vectors, n, left, draft = row
    cols = tuple(vectors)[:n]
    if not (query.row_open(geometry, ctx.collapsed, "ss_mapping") and query.tile_open(geometry, ctx.collapsed, "ss_mapping", ckey)):
        return
    mapped = service.map_vectors_into_superspace_generators(ctx.state, cols)
    for c in range(len(mapped)):
        for g in range(_r.dims.rL):
            cells.append(CellBox(
                f"cell:ss_mapping:{ckey}:{g}:{c}", left(c), query.ss_map_top(geometry, g),
                COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                unit=query.cell_unit(_r, "ss_mapping", ckey, gen=g)))
    if draft:
        for g in range(_r.dims.rL):
            cells.append(CellBox(f"cell:ss_mapping:{ckey}:{g}:draft", left(n), query.ss_map_top(geometry, g),
                                 COL_W, ROW_H, "mapped", text="", gen=g, pending=True))
    if ckey == "commas":
        for j in range(_r.dims.nu):
            uj = _r.projection.ss_unchanged_mapped[j]
            for g in range(_r.dims.rL):
                cells.append(CellBox(
                    f"cell:ss_mapping:commas:{g}:u{j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.ss_map_top(geometry, g),
                    COL_W, ROW_H, "mapped", text=DASH if uj is None else str(uj[g]), gen=g, comma=_r.dims.nc + j,
                    unit=query.cell_unit(_r, "ss_mapping", "commas", gen=g)))


def _emit_ss_projection_rows(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    cl = ctx.collapsed
    _emit_ss_proj_ssprimes(cells, resolved, geometry, ctx)
    ss_full = _r.projection.ss_rationals is not None
    _emit_ss_proj_ssgens(cells, resolved, geometry, ctx, ss_full)
    _emit_ss_proj_primes(cells, resolved, geometry, ctx, ss_full)
    ssp = {"full": ss_full, "colwise": True, "row": "ss_projection",
           "top": lambda i: query.ss_proj_top(geometry, i), "height": _r.dims.dL}
    emit_mapped_grid(cells, resolved, geometry, cl, "detempering", "ss_proj_pd", _r.projection.ss_detempering, _r.dims.r, lambda i: query.detempering_left(geometry, i), "gen", **ssp)
    _emit_ss_proj_commas(cells, resolved, geometry, ctx)
    emit_mapped_grid(cells, resolved, geometry, cl, "targets", "ss_proj_pt", _r.projection.ss_targets, _r.dims.k, lambda i: query.target_left(geometry, i), "comma",
                     pending=_r.targets.pending, **ssp)
    emit_mapped_grid(cells, resolved, geometry, cl, "held", "ss_proj_ph", _r.projection.ss_held, _r.dims.nh, lambda i: query.held_left(geometry, i), "comma",
                     pending=_r.held.pending, **ssp)
    emit_mapped_grid(cells, resolved, geometry, cl, "interest", "ss_proj_pi", _r.projection.ss_interest, _r.dims.mi, lambda i: query.interest_left(geometry, i), "comma",
                     inset=KET_INSET, pending=_r.interest.pending, **ssp)


def _emit_ss_proj_ssprimes(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "ssprimes"):
        full = _r.projection.ss_matrix is not None
        for i in range(_r.dims.dL):
            for j in range(_r.dims.dL):
                text = DASH if not full else _r.projection.ss_matrix[i][j]
                cells.append(CellBox(
                    f"cell:ss_projection:ssprimes:{i}:{j}",
                    query.ss_prime_left(geometry, j), query.ss_proj_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=text, gen=i, prime=j,
                    unit=query.cell_unit(_r, "ss_projection", "ssprimes", gen=i, prime=j)))


def _emit_ss_proj_ssgens(cells, resolved, geometry, ctx, ss_full) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "ssgens"):
        for i in range(_r.dims.dL):
            for g in range(_r.dims.rL):
                text = DASH if not ss_full else _r.projection.ss_embedding_matrix[i][g]
                cells.append(CellBox(f"cell:ss_embed:{i}:{g}", query.ss_gen_left(geometry, g), query.ss_proj_top(geometry, i),
                                     COL_W, ROW_H, "mapped", text=text, gen=g))


def _emit_ss_proj_primes(cells, resolved, geometry, ctx, ss_full) -> None:
    _r = resolved
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "primes"):
        for e in range(_r.dims.d):
            for p in range(_r.dims.dL):
                text = DASH if not ss_full else str(_r.projection.ss_basis[e][p])
                cells.append(CellBox(f"cell:ss_proj_bls:{e}:{p}", query.prime_left(geometry, e), query.ss_proj_top(geometry, p),
                                     COL_W, ROW_H, "mapped", text=text, prime=p, comma=e))


def _emit_ss_proj_commas(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if not (_r.unchanged.shown and query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "commas")):
        return
    for c in range(_r.dims.nc):
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:{c}", query.comma_left(geometry, _r, c), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
    if _r.commas.pending is not None:
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:draft", query.comma_left(geometry, _r, _r.dims.nc), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="", prime=p, pending=True))
    for j in range(_r.dims.nu):
        dashed = _r.projection.ss_unchanged[j] is None
        for p in range(_r.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:{_r.dims.nc + j}", query.comma_left(geometry, _r, _r.dims.nc_shown + j), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped",
                                 text=DASH if dashed else str(_r.projection.ss_unchanged[j][p]), prime=p, comma=_r.dims.nc + j))


def emit_identity_objects(resolved, geometry, ctx) -> EmitResult:
    _r = resolved
    cells: list = []
    _emit_identity_vec_primes(cells, resolved, geometry, ctx)
    for ckey, prefix, left in (("gens", "selfmap", lambda k: query.gen_left(geometry, k)),
                               ("detempering", "mapped_detempering", lambda k: query.detempering_left(geometry, k))):
        if query.tile_open(geometry, ctx.collapsed, "mapping", ckey):
            for i in range(_r.dims.r):
                for k in range(_r.dims.r):
                    cells.append(CellBox(
                        f"cell:{prefix}:{i}:{k}", left(k), query.map_top(geometry, i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i,
                        unit=query.cell_unit(_r, "mapping", ckey, gen=i)))
    _emit_identity_canongens(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_identity_vec_primes(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "vectors", "primes"):
        for i in range(_r.dims.d):
            for k in range(_r.dims.d):
                cells.append(CellBox(
                    f"cell:vec:primes:{i}:{k}", query.prime_left(geometry, k), query.vec_top(geometry, i), COL_W, ROW_H,
                    "mapped", text="1" if i == k else "0", gen=i, prime=k,
                    unit=query.cell_unit(_r, "vectors", "primes", prime=k)))


def _emit_identity_canongens(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if query.tile_open(geometry, ctx.collapsed, "canon", "canongens"):
        for i in range(_r.dims.rc):
            for k in range(_r.dims.rc):
                cells.append(CellBox(
                    f"cell:fcancel:{i}:{k}", query.canongen_left(geometry, k), query.canon_top(geometry, i), COL_W, ROW_H,
                    "mapped", text="1" if i == k else "0", gen=i,
                    unit=query.cell_unit(_r, "canon", "canongens", gen=i)))
