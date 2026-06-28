from __future__ import annotations

from rtt.app import ids, service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    COMMAPICK_GAP,
    DASH,
    ROW_H,
    ROW_HANDLE_W,
)
from rtt.app.spreadsheet_emit_mapping import emit_mapped_grid
from rtt.app.spreadsheet_emit_model import EmitResult, element_cell_kind, voice
from rtt.app.spreadsheet_models import _VecGrid


def emit_vectors(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, ctx.collapsed, "vectors"):
        return EmitResult()
    if query.tile_open(geometry, ctx.collapsed, "vectors", "quantities"):
        _emit_vectors_basis_col(cells, resolved, geometry, ctx)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "commas"):
        _emit_vectors_commas_col(cells, resolved, geometry, ctx)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "targets"):
        target_kind = "targetcell" if resolved.scalars.targets_editable else "vec"
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("targets", resolved.dims.k, ids.target_cell,
            lambda i: query.target_left(geometry, i), target_kind, "targetcell",
            resolved.targets.vectors, resolved.targets.pending, resolved.tuning.target_sizes))
    if query.tile_open(geometry, ctx.collapsed, "vectors", "held"):
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("held", resolved.dims.nh, ids.held_cell,
            lambda i: query.held_left(geometry, i), "heldcell", "heldcell",
            resolved.held.vectors, resolved.held.pending, resolved.tuning.held_sizes))
    if query.tile_open(geometry, ctx.collapsed, "vectors", "detempering"):
        _emit_vectors_detempering_col(cells, resolved, geometry)
    if query.tile_open(geometry, ctx.collapsed, "vectors", "interest"):
        _emit_vec_grid(cells, resolved, geometry, _VecGrid("interest", resolved.dims.mi, ids.interest_cell,
            lambda i: query.interest_left(geometry, i), "interestcell", "interestcell",
            resolved.interest.vectors, resolved.interest.pending, resolved.tuning.interest_sizes))
    _emit_vectors_int_handles(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_vec_grid(cells, resolved, geometry, g: _VecGrid) -> None:
    for col in range(g.count):
        for p in range(resolved.dims.d):
            cells.append(CellBox(g.id_fn(query.col_token(resolved, g.group, col), p), g.left_fn(col), query.vec_top(geometry, p), COL_W, ROW_H, g.committed_kind, text=str(g.data[col][p]), prime=p, comma=col, unit=query.cell_unit(resolved, "vectors", g.group, prime=p)))
            voice(cells, f"vectors:{g.group}", col, g.sizes.just[col])
    if g.pending is not None:
        for p in range(resolved.dims.d):
            v = g.pending[p]
            cells.append(CellBox(g.id_fn(query.pending_col_token(resolved, g.group), p), g.left_fn(g.count), query.vec_top(geometry, p), COL_W, ROW_H, g.pending_kind,
                                 text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=query.cell_unit(resolved, "vectors", g.group, prime=p)))


def _basis_col_x(geometry):
    bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
    basis_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "vectors") else geometry.node_edge
    return bx, basis_bus_x


def _emit_basis_minus(cells, geometry, cid, p, kind, **kw):
    bx, basis_bus_x = _basis_col_x(geometry)
    cells.append(CellBox(cid, basis_bus_x, query.vec_top(geometry, p),
                         (bx + COL_W) - basis_bus_x, ROW_H, kind, **kw))


def _emit_vectors_basis_col(cells, resolved, geometry, ctx) -> None:
    bx, basis_bus_x = _basis_col_x(geometry)
    for p in range(resolved.dims.d):
        text = str(resolved.dims.elements[p])
        kind = element_cell_kind(text) if resolved.flags.nonstandard_domain else "prime"
        cells.append(CellBox(f"basis:{p}", bx, query.vec_top(geometry, p), COL_W, ROW_H, kind, text=text, prime=p))
    if resolved.scalars.element_draft:
        draft_text = ctx.pending_element or "?/?"
        cells.append(CellBox("basis:pending", bx, query.vec_top(geometry, resolved.dims.d), COL_W, ROW_H,
                                  element_cell_kind(draft_text), text=draft_text, prime=resolved.dims.d, pending=True))
        _emit_basis_minus(cells, geometry, "element_minus:basis:pending", resolved.dims.d, "element_minus")
    if resolved.flags.nonstandard_domain:
        if resolved.dims.d > 1:
            for p in range(resolved.dims.d):
                _emit_basis_minus(cells, geometry, f"element_minus:basis:{p}", p, "element_minus", prime=p)
    elif resolved.scalars.domain_can_shrink:
        _emit_basis_minus(cells, geometry, "basis_minus", resolved.dims.d - 1, "basis_minus")
    if "vectors" in geometry.row_plus_y:
        plus_kind = "element_plus" if resolved.flags.nonstandard_domain else "plus"
        cells.append(CellBox("basis_plus", basis_bus_x - BTN / 2, geometry.row_plus_y["vectors"] - BTN / 2,
                             BTN, BTN, plus_kind))


def _emit_vectors_commas_col(cells, resolved, geometry, ctx) -> None:
    for c in range(resolved.dims.nc):
        for p in range(resolved.dims.d):
            cells.append(CellBox(ids.comma_cell(query.col_token(resolved, 'commas', c), p), query.comma_left(geometry, resolved, c), query.vec_top(geometry, p), COL_W, ROW_H, "commacell", text=str(ctx.state.comma_basis[c][p]), prime=p, comma=c, unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
            voice(cells, "vectors:commas", c, resolved.tuning.comma_sizes.just[c])
        if resolved.flags.presets:
            cells.append(CellBox(f"commapick:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.cpick_band_y(geometry, "vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=c))
    full_u = resolved.unchanged.basis is not None and all(v is not None for v in resolved.unchanged.basis)
    for j in range(resolved.dims.nu):
        doomed = resolved.commas.pending is not None and j == resolved.dims.nu - 1
        born = resolved.unchanged.born and j == resolved.dims.nu - 1
        for p in range(resolved.dims.d):
            vec_text = DASH if resolved.unchanged.basis[j] is None else str(resolved.unchanged.basis[j][p])
            cells.append(CellBox(ids.unchanged_cell(j, p), query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.vec_top(geometry, p), COL_W, ROW_H,
                                 "unchangedcell" if (full_u and not doomed and not born) else "vec", text=vec_text, prime=p, comma=resolved.dims.nc + j,
                                 unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
        voice(cells, "vectors:commas", resolved.dims.nc + j, resolved.unchanged.sizes.just[j])
    if resolved.scalars.comma_draft:
        col_kind = "vec" if resolved.ghosts.comma else "commacell"
        for p in range(resolved.dims.d):
            v = resolved.ghosts.comma_vec[p] if resolved.ghosts.comma else resolved.commas.pending[p]
            cells.append(CellBox(ids.comma_cell(query.pending_col_token(resolved, 'commas'), p), query.comma_left(geometry, resolved, resolved.dims.nc), query.vec_top(geometry, p), COL_W, ROW_H, col_kind,
                                 text="" if v is None else str(v), prime=p, comma=resolved.dims.nc, pending=True, unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
        if resolved.commas.pending is not None and resolved.flags.presets:
            cells.append(CellBox("commapick:draft", query.comma_left(geometry, resolved, resolved.dims.nc), query.cpick_band_y(geometry, "vectors") + COMMAPICK_GAP, COL_W, ROW_H, "commapick", comma=resolved.dims.nc, pending=True))


def _emit_vectors_detempering_col(cells, resolved, geometry) -> None:
    for i in range(resolved.dims.r):
        for p in range(resolved.dims.d):
            cells.append(CellBox(f"cell:vec:detempering:{query.col_token(resolved, 'detempering', i)}:{p}", query.detempering_left(geometry, i), query.vec_top(geometry, p), COL_W, ROW_H, "vec", text=str(resolved.detempering.vectors[i][p]), unit=query.cell_unit(resolved, "vectors", "detempering", prime=p)))
            voice(cells, "vectors:detempering", i, resolved.detempering.sizes.just[i])


def _emit_vectors_int_handles(cells, resolved, geometry, ctx) -> None:
    if "vectors" in geometry.rows and geometry.rows["vectors"].int_handle_top is not None:
        hy = geometry.rows["vectors"].int_handle_top
        for group, count, col_left, column_key in (("comma", resolved.dims.nc, lambda i: query.comma_left(geometry, resolved, i), "commas"),
                                             ("target", resolved.dims.k, lambda i: query.target_left(geometry, i), "targets"),
                                             ("held", resolved.dims.nh, lambda i: query.held_left(geometry, i), "held"),
                                             ("interest", resolved.dims.mi, lambda i: query.interest_left(geometry, i), "interest")):
            if count >= 2 and query.tile_open(geometry, ctx.collapsed, "vectors", column_key) and (column_key != "targets" or resolved.scalars.targets_editable):
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
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"ss_basis:{p}", bx, query.ss_vec_top(geometry, p), COL_W, ROW_H,
                                 "commaratio", text=str(resolved.dims.superspace_primes[p]), prime=p))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "quantities"):
        ss_gens = service.superspace_generators(ctx.state)
        for i in range(resolved.dims.rL):
            cells.append(CellBox(f"ss_gen:{i}", geometry.col_x["quantities"], query.ss_map_top(geometry, i),
                                 geometry.col_w["quantities"], ROW_H, "genratio",
                                 text=ss_gens[i] if i < len(ss_gens) else ""))
    if query.row_open(geometry, cl, "ss_projection") and query.tile_open(geometry, cl, "ss_projection", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"ss_proj_basis:{p}", bx, query.ss_proj_top(geometry, p), COL_W, ROW_H, "commaratio",
                                 text=str(resolved.dims.superspace_primes[p]), prime=p))


def _emit_ss_matrix_vectors(cells, resolved, geometry, ctx) -> None:
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "primes"):
        basis = service.basis_in_superspace(resolved.dims.elements)
        for ss_prime_idx in range(resolved.dims.dL):
            for elem_idx in range(resolved.dims.d):
                value = basis[elem_idx][ss_prime_idx]
                cells.append(CellBox(
                    f"cell:ss_vectors:primes:{ss_prime_idx}:{elem_idx}",
                    query.prime_left(geometry, elem_idx), query.ss_vec_top(geometry, ss_prime_idx), COL_W, ROW_H,
                    "vec", text=str(value), prime=ss_prime_idx, comma=elem_idx,
                    unit=query.cell_unit(resolved, "ss_vectors", "primes", prime=ss_prime_idx, elem=elem_idx)))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssprimes"):
        ml = service.superspace_mapping(ctx.state)
        for gen_idx in range(resolved.dims.rL):
            for ss_prime_idx in range(resolved.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_mapping:ssprimes:{gen_idx}:{ss_prime_idx}",
                    query.ss_prime_left(geometry, ss_prime_idx), query.ss_map_top(geometry, gen_idx), COL_W, ROW_H,
                    "mapped", text=str(ml[gen_idx][ss_prime_idx]), gen=gen_idx, prime=ss_prime_idx,
                    unit=query.cell_unit(resolved, "ss_mapping", "ssprimes", gen=gen_idx, prime=ss_prime_idx)))
    if query.row_open(geometry, cl, "ss_vectors") and query.tile_open(geometry, cl, "ss_vectors", "ssprimes"):
        mjl = service.superspace_just_mapping(resolved.dims.superspace_primes)
        for i in range(resolved.dims.dL):
            for j in range(resolved.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_vectors:ssprimes:{i}:{j}",
                    query.ss_prime_left(geometry, j), query.ss_vec_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(mjl[i][j]), gen=i, prime=j,
                    unit=query.cell_unit(resolved, "ss_vectors", "ssprimes", prime=j)))


def _emit_ss_matrix_mapping(cells, resolved, geometry, ctx) -> None:
    cl = ctx.collapsed
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "ssgens"):
        mlgl = service.superspace_self_map(ctx.state)
        for i in range(resolved.dims.rL):
            for j in range(resolved.dims.rL):
                cells.append(CellBox(
                    f"cell:ss_mapping:ssgens:{i}:{j}",
                    query.ss_gen_left(geometry, j), query.ss_map_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(mlgl[i][j]), gen=i,
                    unit=query.cell_unit(resolved, "ss_mapping", "ssgens", gen=i)))
    if query.row_open(geometry, cl, "ss_mapping") and query.tile_open(geometry, cl, "ss_mapping", "primes"):
        msl = service.mapping_to_superspace_generators(ctx.state)
        for i in range(resolved.dims.rL):
            for e in range(resolved.dims.d):
                cells.append(CellBox(
                    f"cell:ss_mapping:primes:{i}:{e}",
                    query.prime_left(geometry, e), query.ss_map_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=str(msl[i][e]), gen=i,
                    unit=query.cell_unit(resolved, "ss_mapping", "primes", gen=i, elem=e)))


def _emit_ss_vector_lists(cells, resolved, geometry, ctx) -> None:
    ss_lists = (("commas", ctx.state.comma_basis, resolved.dims.nc, lambda c: query.comma_left(geometry, resolved, c), resolved.scalars.comma_draft),
                ("targets", resolved.targets.vectors, resolved.dims.k, lambda c: query.target_left(geometry, c), resolved.targets.pending is not None),
                ("held", resolved.held.vectors, resolved.dims.nh, lambda c: query.held_left(geometry, c), resolved.held.pending is not None),
                ("interest", resolved.interest.vectors, resolved.dims.mi, lambda c: query.interest_left(geometry, c), resolved.interest.pending is not None),
                ("detempering", resolved.detempering.vectors, resolved.dims.r, lambda c: query.detempering_left(geometry, c), False))
    for row in ss_lists:
        _emit_ss_vector_list_lift(cells, resolved, geometry, ctx, row)
        _emit_ss_vector_list_map(cells, resolved, geometry, ctx, row)


def _emit_ss_vector_list_lift(cells, resolved, geometry, ctx, row) -> None:
    column_key, vectors, n, left, draft = row
    cols = tuple(vectors)[:n]
    if not (query.row_open(geometry, ctx.collapsed, "ss_vectors") and query.tile_open(geometry, ctx.collapsed, "ss_vectors", column_key)):
        return
    lifted = service.lift_vectors_to_superspace(resolved.dims.elements, cols)
    for c in range(len(lifted)):
        for p in range(resolved.dims.dL):
            cells.append(CellBox(
                f"cell:ss_vectors:{column_key}:{p}:{c}", left(c), query.ss_vec_top(geometry, p),
                COL_W, ROW_H, "vec", text=str(lifted[c][p]), prime=p, comma=c,
                unit=query.cell_unit(resolved, "ss_vectors", column_key, prime=p)))
    if draft:
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"cell:ss_vectors:{column_key}:{p}:draft", left(n), query.ss_vec_top(geometry, p),
                                 COL_W, ROW_H, "vec", text="", prime=p, pending=True))
    if column_key == "commas":
        for j in range(resolved.dims.nu):
            uj = resolved.projection.ss_unchanged[j]
            for p in range(resolved.dims.dL):
                cells.append(CellBox(
                    f"cell:ss_vectors:commas:{p}:u{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.ss_vec_top(geometry, p),
                    COL_W, ROW_H, "vec", text=DASH if uj is None else str(uj[p]), prime=p, comma=resolved.dims.nc + j,
                    unit=query.cell_unit(resolved, "ss_vectors", "commas", prime=p)))


def _emit_ss_vector_list_map(cells, resolved, geometry, ctx, row) -> None:
    column_key, vectors, n, left, draft = row
    cols = tuple(vectors)[:n]
    if not (query.row_open(geometry, ctx.collapsed, "ss_mapping") and query.tile_open(geometry, ctx.collapsed, "ss_mapping", column_key)):
        return
    mapped = service.map_vectors_into_superspace_generators(ctx.state, cols)
    for c in range(len(mapped)):
        for g in range(resolved.dims.rL):
            cells.append(CellBox(
                f"cell:ss_mapping:{column_key}:{g}:{c}", left(c), query.ss_map_top(geometry, g),
                COL_W, ROW_H, "mapped", text=str(mapped[c][g]), gen=g, comma=c,
                unit=query.cell_unit(resolved, "ss_mapping", column_key, gen=g)))
    if draft:
        for g in range(resolved.dims.rL):
            cells.append(CellBox(f"cell:ss_mapping:{column_key}:{g}:draft", left(n), query.ss_map_top(geometry, g),
                                 COL_W, ROW_H, "mapped", text="", gen=g, pending=True))
    if column_key == "commas":
        for j in range(resolved.dims.nu):
            uj = resolved.projection.ss_unchanged_mapped[j]
            for g in range(resolved.dims.rL):
                cells.append(CellBox(
                    f"cell:ss_mapping:commas:{g}:u{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.ss_map_top(geometry, g),
                    COL_W, ROW_H, "mapped", text=DASH if uj is None else str(uj[g]), gen=g, comma=resolved.dims.nc + j,
                    unit=query.cell_unit(resolved, "ss_mapping", "commas", gen=g)))


def _emit_ss_projection_rows(cells, resolved, geometry, ctx) -> None:
    cl = ctx.collapsed
    _emit_ss_proj_ssprimes(cells, resolved, geometry, ctx)
    ss_full = resolved.projection.ss_rationals is not None
    _emit_ss_proj_ssgens(cells, resolved, geometry, ctx, ss_full)
    _emit_ss_proj_primes(cells, resolved, geometry, ctx, ss_full)
    ssp = {"full": ss_full, "colwise": True, "row": "ss_projection",
           "top": lambda i: query.ss_proj_top(geometry, i), "height": resolved.dims.dL}
    emit_mapped_grid(cells, resolved, geometry, cl, "detempering", "ss_proj_pd", resolved.projection.ss_detempering, resolved.dims.r, lambda i: query.detempering_left(geometry, i), "gen", **ssp)
    _emit_ss_proj_commas(cells, resolved, geometry, ctx)
    emit_mapped_grid(cells, resolved, geometry, cl, "targets", "ss_proj_pt", resolved.projection.ss_targets, resolved.dims.k, lambda i: query.target_left(geometry, i), "comma",
                     pending=resolved.targets.pending, **ssp)
    emit_mapped_grid(cells, resolved, geometry, cl, "held", "ss_proj_ph", resolved.projection.ss_held, resolved.dims.nh, lambda i: query.held_left(geometry, i), "comma",
                     pending=resolved.held.pending, **ssp)
    emit_mapped_grid(cells, resolved, geometry, cl, "interest", "ss_proj_pi", resolved.projection.ss_interest, resolved.dims.mi, lambda i: query.interest_left(geometry, i), "comma",
                     pending=resolved.interest.pending, **ssp)


def _emit_ss_proj_ssprimes(cells, resolved, geometry, ctx) -> None:
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "ssprimes"):
        full = resolved.projection.ss_matrix is not None
        for i in range(resolved.dims.dL):
            for j in range(resolved.dims.dL):
                text = DASH if not full else resolved.projection.ss_matrix[i][j]
                cells.append(CellBox(
                    f"cell:ss_projection:ssprimes:{i}:{j}",
                    query.ss_prime_left(geometry, j), query.ss_proj_top(geometry, i), COL_W, ROW_H,
                    "mapped", text=text, gen=i, prime=j,
                    unit=query.cell_unit(resolved, "ss_projection", "ssprimes", gen=i, prime=j)))


def _emit_ss_proj_ssgens(cells, resolved, geometry, ctx, ss_full) -> None:
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "ssgens"):
        for i in range(resolved.dims.dL):
            for g in range(resolved.dims.rL):
                text = DASH if not ss_full else resolved.projection.ss_embedding_matrix[i][g]
                cells.append(CellBox(f"cell:ss_embed:{i}:{g}", query.ss_gen_left(geometry, g), query.ss_proj_top(geometry, i),
                                     COL_W, ROW_H, "mapped", text=text, gen=g))


def _emit_ss_proj_primes(cells, resolved, geometry, ctx, ss_full) -> None:
    if query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "primes"):
        for e in range(resolved.dims.d):
            for p in range(resolved.dims.dL):
                text = DASH if not ss_full else str(resolved.projection.ss_basis[e][p])
                cells.append(CellBox(f"cell:ss_proj_bls:{e}:{p}", query.prime_left(geometry, e), query.ss_proj_top(geometry, p),
                                     COL_W, ROW_H, "mapped", text=text, prime=p, comma=e))


def _emit_ss_proj_commas(cells, resolved, geometry, ctx) -> None:
    if not (resolved.unchanged.shown and query.row_open(geometry, ctx.collapsed, "ss_projection") and query.tile_open(geometry, ctx.collapsed, "ss_projection", "commas")):
        return
    for c in range(resolved.dims.nc):
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:{c}", query.comma_left(geometry, resolved, c), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
    if resolved.commas.pending is not None:
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:draft", query.comma_left(geometry, resolved, resolved.dims.nc), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="", prime=p, pending=True))
    for j in range(resolved.dims.nu):
        dashed = resolved.projection.ss_unchanged[j] is None
        for p in range(resolved.dims.dL):
            cells.append(CellBox(f"cell:ss_proj_v:{p}:{resolved.dims.nc + j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.ss_proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped",
                                 text=DASH if dashed else str(resolved.projection.ss_unchanged[j][p]), prime=p, comma=resolved.dims.nc + j))


def emit_identity_objects(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    _emit_identity_vec_primes(cells, resolved, geometry, ctx)
    for column_key, prefix, left in (("gens", "selfmap", lambda k: query.gen_left(geometry, k)),
                               ("detempering", "mapped_detempering", lambda k: query.detempering_left(geometry, k))):
        if query.tile_open(geometry, ctx.collapsed, "mapping", column_key):
            for i in range(resolved.dims.r):
                for k in range(resolved.dims.r):
                    cells.append(CellBox(
                        f"cell:{prefix}:{i}:{k}", left(k), query.map_top(geometry, i), COL_W, ROW_H,
                        "mapped", text="1" if i == k else "0", gen=i,
                        unit=query.cell_unit(resolved, "mapping", column_key, gen=i)))
    _emit_identity_canongens(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells))


def _emit_identity_vec_primes(cells, resolved, geometry, ctx) -> None:
    if query.tile_open(geometry, ctx.collapsed, "vectors", "primes"):
        for i in range(resolved.dims.d):
            for k in range(resolved.dims.d):
                cells.append(CellBox(
                    f"cell:vec:primes:{i}:{k}", query.prime_left(geometry, k), query.vec_top(geometry, i), COL_W, ROW_H,
                    "mapped", text="1" if i == k else "0", gen=i, prime=k,
                    unit=query.cell_unit(resolved, "vectors", "primes", prime=k)))


def _emit_identity_canongens(cells, resolved, geometry, ctx) -> None:
    if query.tile_open(geometry, ctx.collapsed, "canon", "canongens"):
        for i in range(resolved.dims.rc):
            for k in range(resolved.dims.rc):
                cells.append(CellBox(
                    f"cell:fcancel:{i}:{k}", query.canongen_left(geometry, k), query.canon_top(geometry, i), COL_W, ROW_H,
                    "mapped", text="1" if i == k else "0", gen=i,
                    unit=query.cell_unit(resolved, "canon", "canongens", gen=i)))
