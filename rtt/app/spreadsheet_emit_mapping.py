from __future__ import annotations

import functools

from rtt.app import ids
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BTN,
    COL_W,
    DASH,
    ETPICK_GAP,
    ETPICK_W,
    ROW_H,
    ROW_HANDLE_W,
)
from rtt.app.spreadsheet_emit_model import EmitResult, voice
from rtt.app.spreadsheet_models import _MappedTile


def emit_mapping(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, context.collapsed, "mapping"):
        return EmitResult()
    _emit_mapping_gens(cells, resolved, geometry, context)
    _emit_mapping_drag(cells, resolved, geometry, context)
    _emit_mapping_rows(cells, resolved, geometry, context)
    if resolved.scalars.row_draft:
        _emit_mapping_draft_row(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_mapping_gens(cells, resolved, geometry, context) -> None:
    if not query.tile_open(geometry, context.collapsed, "mapping", "quantities"):
        return
    for i in range(resolved.dims.r):
        cells.append(CellBox(f"gen:{query.col_token(resolved, 'gens', i)}", geometry.col_x["quantities"], query.map_top(geometry, i), geometry.col_w["quantities"], ROW_H, "genratio", text=resolved.scalars.gens[i] if i < len(resolved.scalars.gens) else "", gen=i))
    map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
    gen_right = geometry.col_x["quantities"] + geometry.col_w["quantities"]
    if resolved.dims.r > 1:
        for i in range(resolved.dims.r):
            cells.append(CellBox(f"map_minus:{query.col_token(resolved, 'gens', i)}", map_bus_x, query.map_top(geometry, i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
    if "mapping" in geometry.row_plus_y:
        cells.append(CellBox("map_plus", map_bus_x - BTN / 2, geometry.row_plus_y["mapping"] - BTN / 2, BTN, BTN, "map_plus"))


def _emit_mapping_drag(cells, resolved, geometry, context) -> None:
    if context.settings.get("drag_to_combine") and resolved.dims.r > 1 and query.tile_open(geometry, context.collapsed, "mapping", "primes"):
        for i in range(resolved.dims.r):
            cells.append(CellBox(f"map_drag:{query.col_token(resolved, 'gens', i)}", geometry.primes_x + query.etpick_left_pad(geometry, "primes"), query.map_top(geometry, i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))


def _emit_mapping_rows(cells, resolved, geometry, context) -> None:
    mx, mw = query.matrix_span(geometry, resolved, "primes")
    etpick_x = mx + mw + ETPICK_GAP
    for i in range(resolved.dims.r):
        rt = query.col_token(resolved, "gens", i)
        if query.tile_open(geometry, context.collapsed, "mapping", "primes"):
            if resolved.flags.presets:
                cells.append(CellBox(f"etpick:{rt}", etpick_x, query.map_top(geometry, i), ETPICK_W, ROW_H, "etpick", gen=i))
            for p in range(resolved.dims.d):
                cells.append(CellBox(ids.mapping_cell(rt, p), query.prime_left(geometry, p), query.map_top(geometry, i), COL_W, ROW_H, "mapping", text=str(context.state.mapping[i][p]), gen=i, prime=p, unit=query.cell_unit(resolved, "mapping", "primes", gen=i, prime=p)))
        if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("mapped", "targets", resolved.dims.k, lambda c: query.target_left(geometry, c), resolved.targets.mapped, resolved.targets.pending, resolved.tuning.target_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("imapped", "interest", resolved.dims.mi, lambda c: query.interest_left(geometry, c), resolved.interest.mapped, resolved.interest.pending, resolved.tuning.interest_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "held"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("hmapped", "held", resolved.dims.nh, lambda c: query.held_left(geometry, c), resolved.tuning.held_mapped, resolved.held.pending, resolved.tuning.held_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
            _emit_mapping_comma_row(cells, resolved, geometry, i, rt)


def _emit_mapping_comma_row(cells, resolved, geometry, i, rt) -> None:
    for c in range(resolved.dims.nc):
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.commas.mapped[i][c]), gen=i, unit=query.cell_unit(resolved, "mapping", "commas", gen=i)))
        voice(cells, "mapped:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        mc_text = str(resolved.ghosts.comma_mapped[i]) if (resolved.ghosts.comma and i < len(resolved.ghosts.comma_mapped)) else ""
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dims.nc), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
    for j in range(resolved.dims.nu):
        mapped_text = DASH if resolved.unchanged.mapped[i][j] is None else str(resolved.unchanged.mapped[i][j])
        cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=query.cell_unit(resolved, "mapping", "commas", gen=i)))
        voice(cells, "mapped:commas", resolved.dims.nc + j, resolved.unchanged.sizes.tempered[j])


def _emit_mapping_draft_row(cells, resolved, geometry, context) -> None:
    dr = resolved.dims.r
    drt = query.pending_col_token(resolved, "gens")
    if query.tile_open(geometry, context.collapsed, "mapping", "quantities"):
        gen_text = resolved.ghosts.row_ratio if resolved.ghosts.row else "?"
        cells.append(CellBox("gen:pending", geometry.col_x["quantities"], query.map_top(geometry, dr), geometry.col_w["quantities"], ROW_H, "genratio", text=gen_text, gen=dr, pending=True))
        if not resolved.ghosts.row:
            map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
            gen_right = geometry.col_x["quantities"] + geometry.col_w["quantities"]
            cells.append(CellBox("map_minus:pending", map_bus_x, query.map_top(geometry, dr), gen_right - map_bus_x, ROW_H, "map_minus", gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "primes"):
        row_kind = "mapped" if resolved.ghosts.row else "mapping"
        for p in range(resolved.dims.d):
            v = resolved.ghosts.row_map[p] if resolved.ghosts.row else context.pending_mapping_row[p]
            cells.append(CellBox(ids.mapping_cell(drt, p), query.prime_left(geometry, p), query.map_top(geometry, dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
        if not resolved.ghosts.row and resolved.flags.presets:
            mx, mw = query.matrix_span(geometry, resolved, "primes")
            cells.append(CellBox("etpick:draft", mx + mw + ETPICK_GAP, query.map_top(geometry, dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
    _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt)


def _draft_mapped_text(resolved, key, j) -> str:
    vals = resolved.ghosts.row_mapped.get(key, ()) if resolved.ghosts.row else ()
    if j >= len(vals):
        return ""
    return DASH if vals[j] is None else str(vals[j])


def _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
        for j in range(resolved.dims.k):
            cells.append(CellBox(f"cell:mapped:{drt}:{query.col_token(resolved, 'targets', j)}", query.target_left(geometry, j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "targets", j), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
        for ii in range(resolved.dims.mi):
            cells.append(CellBox(f"cell:imapped:{drt}:{query.col_token(resolved, 'interest', ii)}", query.interest_left(geometry, ii), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "interest", ii), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "held"):
        for hi in range(resolved.dims.nh):
            cells.append(CellBox(f"cell:hmapped:{drt}:{query.col_token(resolved, 'held', hi)}", query.held_left(geometry, hi), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "held", hi), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
        _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt)


def _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt) -> None:
    for c in range(resolved.dims.nc):
        cells.append(CellBox(f"cell:mapped_comma:{drt}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "commas", c), gen=dr, pending=True))
    for j in range(resolved.dims.nu):
        cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "unchanged", j), gen=dr, pending=True))


def _emit_mapped_tile(cells, resolved, geometry, m: _MappedTile, i, rt) -> None:
    for col in range(m.count):
        cells.append(CellBox(f"cell:{m.prefix}:{rt}:{query.col_token(resolved, m.group, col)}", m.left_fn(col), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=str(m.data[i][col]), gen=i, unit=query.cell_unit(resolved, "mapping", m.group, gen=i)))
        if m.sizes is not None:
            voice(cells, f"mapped:{m.group}", col, m.sizes[col])
    if m.pending is not None:
        cells.append(CellBox(f"cell:{m.prefix}:{rt}:draft", m.left_fn(m.count), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))


def emit_mapped_grid(cells, resolved, geometry, collapsed, tile, prefix, grid, n_cols, left, col_kw, *,
                     full=None, colwise=False, col_token_key=None,
                     row="projection", top=None, height=None, pending=None, audio=None) -> None:
    if not (query.row_open(geometry, collapsed, row) and query.tile_open(geometry, collapsed, row, tile)):
        return
    if full is None:
        full = grid is not None
    if top is None:
        top = functools.partial(query.proj_top, geometry)
    height = resolved.dims.d if height is None else height
    if colwise:
        _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                                  full, col_token_key, top, height, pending, audio)
    else:
        _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, col_kw, full, top, height)


def _projected_sizes(resolved, grid, n_cols, height):
    jm = resolved.tuning.tuning_map.just_map
    return [sum(jm[i] * grid[j][i] for i in range(height)) for j in range(n_cols)]


def _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                              full, col_token_key, top, height, pending, audio=None) -> None:
    sizes = _projected_sizes(resolved, grid, n_cols, height) if (audio is not None and full) else None
    for j in range(n_cols):
        for i in range(height):
            text = str(grid[j][i]) if full else DASH
            tok = j if col_token_key is None else query.col_token(resolved, col_token_key, j)
            cells.append(CellBox(f"cell:{prefix}:{tok}:{i}", left(j), top(i),
                                 COL_W, ROW_H, "mapped", text=text, prime=i, **{col_kw: j}))
            if sizes is not None:
                voice(cells, audio, j, sizes[j])
    if pending is not None:
        for i in range(height):
            cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols), top(i),
                                 COL_W, ROW_H, "mapped", text="", prime=i, pending=True))


def _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, col_kw,
                              full, top, height) -> None:
    for i in range(height):
        for j in range(n_cols):
            text = grid[i][j] if full else DASH
            cells.append(CellBox(f"cell:{prefix}:{i}:{j}", left(j), top(i),
                                 COL_W, ROW_H, "mapped", text=text, **{col_kw: j}))


def emit_projection_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    cl = context.collapsed
    emit_mapped_grid(cells, resolved, geometry, cl, "primes", "proj", resolved.projection.matrix, resolved.dims.d, lambda i: query.prime_left(geometry, i), "prime")
    emit_mapped_grid(cells, resolved, geometry, cl, "gens", "embed", resolved.projection.embedding_matrix, resolved.dims.r, lambda i: query.gen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, cl, "canongens", "embed_c", resolved.canon.embedding_matrix, resolved.dims.rc, lambda i: query.canongen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, cl, "ssgens", "embed_sl", resolved.projection.embedding_superspace, resolved.dims.rL, lambda i: query.ss_gen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, cl, "ssprimes", "proj_sl", resolved.projection.superspace, resolved.dims.dL, lambda i: query.ss_prime_left(geometry, i), "prime")
    _emit_projection_unchanged(cells, resolved, geometry, context)
    _emit_projection_basis(cells, resolved, geometry, context)
    full_proj = resolved.projection.rationals is not None
    emit_mapped_grid(cells, resolved, geometry, cl, "detempering", "proj_pd", resolved.projection.detempering, resolved.dims.r, lambda i: query.detempering_left(geometry, i), "gen",
                     full=full_proj, colwise=True, col_token_key="detempering", audio="proj:detempering")
    emit_mapped_grid(cells, resolved, geometry, cl, "targets", "proj_pt", resolved.projection.targets, resolved.dims.k, lambda i: query.target_left(geometry, i), "comma",
                     full=full_proj, colwise=True, pending=resolved.targets.pending, audio="proj:targets")
    emit_mapped_grid(cells, resolved, geometry, cl, "held", "proj_ph", resolved.projection.held, resolved.dims.nh, lambda i: query.held_left(geometry, i), "comma",
                     full=full_proj, colwise=True, pending=resolved.held.pending, audio="proj:held")
    emit_mapped_grid(cells, resolved, geometry, cl, "interest", "proj_pi", resolved.projection.interest, resolved.dims.mi, lambda i: query.interest_left(geometry, i), "comma",
                     full=full_proj, colwise=True, pending=resolved.interest.pending, audio="proj:interest")
    _emit_scaling_factors(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_projection_unchanged(cells, resolved, geometry, context) -> None:
    if not (resolved.unchanged.shown and query.row_open(geometry, context.collapsed, "projection")
            and query.tile_open(geometry, context.collapsed, "projection", "commas")):
        return
    for c in range(resolved.dims.nc):
        for p in range(resolved.dims.d):
            cells.append(CellBox(f"cell:proj_v:{p}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            voice(cells, "proj:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        for p in range(resolved.dims.d):
            cells.append(CellBox(f"cell:proj_v:{p}:draft", query.comma_left(geometry, resolved, resolved.dims.nc), query.proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0" if resolved.ghosts.comma else "", prime=p, pending=True))
    for j in range(resolved.dims.nu):
        dashed = resolved.unchanged.basis[j] is None
        for p in range(resolved.dims.d):
            cells.append(CellBox(f"cell:proj_v:{p}:u{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.proj_top(geometry, p),
                                 COL_W, ROW_H, "mapped",
                                 text=DASH if dashed else str(resolved.unchanged.basis[j][p]), prime=p, comma=resolved.dims.nc + j))
            if not dashed:
                voice(cells, "proj:commas", resolved.dims.nc + j, resolved.unchanged.sizes.tempered[j])


def _emit_projection_basis(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "projection") and query.tile_open(geometry, context.collapsed, "projection", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(resolved.dims.d):
            cells.append(CellBox(f"proj_basis:{p}", bx, query.proj_top(geometry, p), COL_W, ROW_H, "commaratio", text=str(resolved.dims.elements[p]), prime=p))


def _emit_scaling_factors(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "scaling_factors") and query.tile_open(geometry, context.collapsed, "scaling_factors", "commas"):
        scaling = ["0"] * resolved.dims.nc + [(DASH if v is None else "1") for v in resolved.unchanged.basis]
        for c, lam in enumerate(scaling):
            cells.append(CellBox(f"cell:scaling:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, query.comma_value_pos(resolved, c)), geometry.rows["scaling_factors"].y,
                                 COL_W, ROW_H, "mapped", text=lam, comma=c))
        if resolved.scalars.comma_draft:
            cells.append(CellBox("cell:scaling:draft", query.comma_left(geometry, resolved, resolved.dims.nc), geometry.rows["scaling_factors"].y,
                                 COL_W, ROW_H, "mapped", text="0" if resolved.ghosts.comma else "", pending=True))


def emit_canon_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, context.collapsed, "canon"):
        _emit_canon_gens(cells, resolved, geometry, context)
        _emit_canon_primes(cells, resolved, geometry, context)
        _emit_canon_form(cells, resolved, geometry, context)
        for i in range(resolved.dims.rc):
            _emit_canon_row(cells, resolved, geometry, context, i)
    _emit_canon_finv(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_canon_gens(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "quantities"):
        for i in range(resolved.dims.rc):
            cells.append(CellBox(f"canon:gen:{i}", geometry.col_x["quantities"], query.canon_top(geometry, i), geometry.col_w["quantities"], ROW_H, "genratio", text=resolved.canon.gens[i] if i < len(resolved.canon.gens) else ""))


def _emit_canon_primes(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "primes"):
        for i in range(resolved.dims.rc):
            for p in range(resolved.dims.d):
                cells.append(CellBox(f"cell:canon:{i}:{p}", query.prime_left(geometry, p), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapping[i][p]), gen=i, prime=p, unit=query.cell_unit(resolved, "canon", "primes", gen=i, prime=p)))


def _emit_canon_form(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "gens"):
        for i in range(len(resolved.canon.form_M)):
            for j in range(len(resolved.canon.form_M)):
                cells.append(CellBox(f"cell:form:{i}:{j}", query.gen_left(geometry, j), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.form_M[i][j]), unit=query.cell_unit(resolved, "canon", "gens", gen=i)))


def _emit_canon_row(cells, resolved, geometry, context, i) -> None:
    cl = context.collapsed
    if query.tile_open(geometry, cl, "canon", "detempering"):
        for c in range(resolved.dims.r):
            cells.append(CellBox(f"cell:canon_detempering:{i}:{query.col_token(resolved, 'detempering', c)}", query.detempering_left(geometry, c), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapped_detempering[i][c]), gen=i, unit=query.cell_unit(resolved, "canon", "detempering", gen=i)))
    if query.tile_open(geometry, cl, "canon", "targets"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_mapped", "targets", resolved.dims.k, lambda c: query.target_left(geometry, c), resolved.canon.mapped, resolved.targets.pending, i)
    if query.tile_open(geometry, cl, "canon", "interest"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_imapped", "interest", resolved.dims.mi, lambda c: query.interest_left(geometry, c), resolved.canon.interest_mapped, resolved.interest.pending, i)
    if query.tile_open(geometry, cl, "canon", "held"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_hmapped", "held", resolved.dims.nh, lambda c: query.held_left(geometry, c), resolved.canon.held_mapped, resolved.held.pending, i)
    if query.tile_open(geometry, cl, "canon", "commas"):
        _emit_canon_comma_row(cells, resolved, geometry, i)


def _emit_canon_comma_row(cells, resolved, geometry, i) -> None:
    for c in range(resolved.dims.nc):
        cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapped_commas[i][c]), gen=i, unit=query.cell_unit(resolved, "canon", "commas", gen=i)))
    if resolved.scalars.comma_draft:
        cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dims.nc), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
    for j in range(resolved.dims.nu):
        ut = DASH if resolved.canon.unchanged_mapped[i][j] is None else str(resolved.canon.unchanged_mapped[i][j])
        cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", query.comma_left(geometry, resolved, resolved.dims.nc_shown + j), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=query.cell_unit(resolved, "canon", "commas", gen=i)))


def _emit_canon_finv(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "canongens"):
        for i in range(resolved.dims.r):
            for j in range(resolved.dims.rc):
                cells.append(CellBox(f"cell:finv:{i}:{j}", query.canongen_left(geometry, j), query.map_top(geometry, i), COL_W, ROW_H,
                                     "formcell", text=str(resolved.canon.inverse_form_M[i][j]), unit=query.cell_unit(resolved, "mapping", "canongens", gen=i)))


def _emit_canon_mapped_tile(cells, resolved, geometry, prefix, group, count, left_fn, data, pending, i) -> None:
    for col in range(count):
        cells.append(CellBox(f"cell:{prefix}:{i}:{query.col_token(resolved, group, col)}", left_fn(col), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=query.cell_unit(resolved, "canon", group, gen=i)))
    if pending is not None:
        cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))


