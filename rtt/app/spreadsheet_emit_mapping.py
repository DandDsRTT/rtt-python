from __future__ import annotations

import functools

from rtt.app import ids
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BUTTON,
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
    for i in range(resolved.dims.rank):
        cells.append(CellBox(f"gen:{query.col_token(resolved, 'gens', i)}", geometry.col_x["quantities"], query.map_top(geometry, i), geometry.col_w["quantities"], ROW_H, "genratio", text=resolved.scalars.gens[i] if i < len(resolved.scalars.gens) else "", gen=i))
    map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
    gen_right = geometry.col_x["quantities"] + geometry.col_w["quantities"]
    if resolved.dims.rank > 1:
        for i in range(resolved.dims.rank):
            cells.append(CellBox(f"map_minus:{query.col_token(resolved, 'gens', i)}", map_bus_x, query.map_top(geometry, i), gen_right - map_bus_x, ROW_H, "map_minus", gen=i))
    if "mapping" in geometry.row_plus_y:
        cells.append(CellBox("map_plus", map_bus_x - BUTTON / 2, geometry.row_plus_y["mapping"] - BUTTON / 2, BUTTON, BUTTON, "map_plus"))


def _emit_mapping_drag(cells, resolved, geometry, context) -> None:
    if context.settings.get("drag_to_combine") and resolved.dims.rank > 1 and query.tile_open(geometry, context.collapsed, "mapping", "primes"):
        for i in range(resolved.dims.rank):
            cells.append(CellBox(f"map_drag:{query.col_token(resolved, 'gens', i)}", geometry.primes_x + query.etpick_left_pad(geometry, "primes"), query.map_top(geometry, i), ROW_HANDLE_W, ROW_H, "map_drag", gen=i))


def _emit_mapping_rows(cells, resolved, geometry, context) -> None:
    matrix_x, matrix_width = query.matrix_span(geometry, resolved, "primes")
    etpick_x = matrix_x + matrix_width + ETPICK_GAP
    for i in range(resolved.dims.rank):
        rt = query.col_token(resolved, "gens", i)
        if query.tile_open(geometry, context.collapsed, "mapping", "primes"):
            if resolved.flags.presets:
                cells.append(CellBox(f"etpick:{rt}", etpick_x, query.map_top(geometry, i), ETPICK_W, ROW_H, "etpick", gen=i))
            for p in range(resolved.dims.dimensionality):
                cells.append(CellBox(ids.mapping_cell(rt, p), query.prime_left(geometry, p), query.map_top(geometry, i), COL_W, ROW_H, "mapping", text=str(context.state.mapping[i][p]), gen=i, prime=p, unit=query.cell_unit(resolved, "mapping", "primes", gen=i, prime=p)))
        if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("mapped", "targets", resolved.dims.target_count, lambda c: query.target_left(geometry, c), resolved.targets.mapped, resolved.targets.pending, resolved.tuning.target_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("imapped", "interest", resolved.dims.interest_count, lambda c: query.interest_left(geometry, c), resolved.interest.mapped, resolved.interest.pending, resolved.tuning.interest_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "held"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("hmapped", "held", resolved.dims.held_count, lambda c: query.held_left(geometry, c), resolved.tuning.held_mapped, resolved.held.pending, resolved.tuning.held_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
            _emit_mapping_comma_row(cells, resolved, geometry, i, rt)


def _emit_mapping_comma_row(cells, resolved, geometry, i, rt) -> None:
    for c in range(resolved.dims.comma_count):
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.commas.mapped[i][c]), gen=i, unit=query.cell_unit(resolved, "mapping", "commas", gen=i)))
        voice(cells, "mapped:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        mc_text = str(resolved.ghosts.comma_mapped[i]) if (resolved.ghosts.comma and i < len(resolved.ghosts.comma_mapped)) else ""
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dims.comma_count), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mc_text, gen=i, pending=True))
    for j in range(resolved.dims.unchanged_count):
        mapped_text = DASH if resolved.unchanged.mapped[i][j] is None else str(resolved.unchanged.mapped[i][j])
        cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + j), query.map_top(geometry, i), COL_W, ROW_H, "mapped", text=mapped_text, gen=i, unit=query.cell_unit(resolved, "mapping", "commas", gen=i)))
        voice(cells, "mapped:commas", resolved.dims.comma_count + j, resolved.unchanged.sizes.tempered[j])


def _emit_mapping_draft_row(cells, resolved, geometry, context) -> None:
    dr = resolved.dims.rank
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
        for p in range(resolved.dims.dimensionality):
            v = resolved.ghosts.row_map[p] if resolved.ghosts.row else context.pending_mapping_row[p]
            cells.append(CellBox(ids.mapping_cell(drt, p), query.prime_left(geometry, p), query.map_top(geometry, dr), COL_W, ROW_H, row_kind, text="" if v is None else str(v), gen=dr, prime=p, pending=True))
        if not resolved.ghosts.row and resolved.flags.presets:
            matrix_x, matrix_width = query.matrix_span(geometry, resolved, "primes")
            cells.append(CellBox("etpick:draft", matrix_x + matrix_width + ETPICK_GAP, query.map_top(geometry, dr), ETPICK_W, ROW_H, "etpick", gen=dr, pending=True))
    _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt)


def _draft_mapped_text(resolved, key, j) -> str:
    vals = resolved.ghosts.row_mapped.get(key, ()) if resolved.ghosts.row else ()
    if j >= len(vals):
        return ""
    return DASH if vals[j] is None else str(vals[j])


def _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
        for j in range(resolved.dims.target_count):
            cells.append(CellBox(f"cell:mapped:{drt}:{query.col_token(resolved, 'targets', j)}", query.target_left(geometry, j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "targets", j), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
        for ii in range(resolved.dims.interest_count):
            cells.append(CellBox(f"cell:imapped:{drt}:{query.col_token(resolved, 'interest', ii)}", query.interest_left(geometry, ii), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "interest", ii), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "held"):
        for hi in range(resolved.dims.held_count):
            cells.append(CellBox(f"cell:hmapped:{drt}:{query.col_token(resolved, 'held', hi)}", query.held_left(geometry, hi), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "held", hi), gen=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
        _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt)


def _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt) -> None:
    for c in range(resolved.dims.comma_count):
        cells.append(CellBox(f"cell:mapped_comma:{drt}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "commas", c), gen=dr, pending=True))
    for j in range(resolved.dims.unchanged_count):
        cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + j), query.map_top(geometry, dr), COL_W, ROW_H, "mapped", text=_draft_mapped_text(resolved, "unchanged", j), gen=dr, pending=True))


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
        top = functools.partial(query.projection_top, geometry)
    height = resolved.dims.dimensionality if height is None else height
    if colwise:
        _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                                  full, col_token_key, top, height, pending, audio)
    else:
        _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, col_kw, full, top, height)


def _projected_sizes(resolved, grid, n_cols, height):
    just_map = resolved.tuning.tuning_map.just_map
    return [sum(just_map[i] * grid[j][i] for i in range(height)) for j in range(n_cols)]


def _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, col_kw,
                              full, col_token_key, top, height, pending, audio=None) -> None:
    sizes = _projected_sizes(resolved, grid, n_cols, height) if (audio is not None and full) else None
    for j in range(n_cols):
        for i in range(height):
            text = str(grid[j][i]) if full else DASH
            token = j if col_token_key is None else query.col_token(resolved, col_token_key, j)
            cells.append(CellBox(f"cell:{prefix}:{token}:{i}", left(j), top(i),
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
    collapsed = context.collapsed
    emit_mapped_grid(cells, resolved, geometry, collapsed, "primes", "projection", resolved.projection.matrix, resolved.dims.dimensionality, lambda i: query.prime_left(geometry, i), "prime")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "gens", "embed", resolved.projection.embedding_matrix, resolved.dims.rank, lambda i: query.gen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "canongens", "embed_c", resolved.canon.embedding_matrix, resolved.dims.canonical_rank, lambda i: query.canongen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "superspace_generators", "embed_sl", resolved.projection.embedding_superspace, resolved.dims.superspace_rank, lambda i: query.superspace_gen_left(geometry, i), "gen")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "superspace_primes", "projection_superspace", resolved.projection.superspace, resolved.dims.superspace_dimensionality, lambda i: query.superspace_prime_left(geometry, i), "prime")
    _emit_projection_unchanged(cells, resolved, geometry, context)
    _emit_projection_basis(cells, resolved, geometry, context)
    full_projection = resolved.projection.rationals is not None
    emit_mapped_grid(cells, resolved, geometry, collapsed, "detempering", "projection_detempering", resolved.projection.detempering, resolved.dims.rank, lambda i: query.detempering_left(geometry, i), "gen",
                     full=full_projection, colwise=True, col_token_key="detempering", audio="projection:detempering")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "targets", "projection_targets", resolved.projection.targets, resolved.dims.target_count, lambda i: query.target_left(geometry, i), "comma",
                     full=full_projection, colwise=True, pending=resolved.targets.pending, audio="projection:targets")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "held", "projection_held", resolved.projection.held, resolved.dims.held_count, lambda i: query.held_left(geometry, i), "comma",
                     full=full_projection, colwise=True, pending=resolved.held.pending, audio="projection:held")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "interest", "projection_interest", resolved.projection.interest, resolved.dims.interest_count, lambda i: query.interest_left(geometry, i), "comma",
                     full=full_projection, colwise=True, pending=resolved.interest.pending, audio="projection:interest")
    _emit_scaling_factors(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_projection_unchanged(cells, resolved, geometry, context) -> None:
    if not (resolved.unchanged.shown and query.row_open(geometry, context.collapsed, "projection")
            and query.tile_open(geometry, context.collapsed, "projection", "commas")):
        return
    for c in range(resolved.dims.comma_count):
        for p in range(resolved.dims.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.projection_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0", prime=p, comma=c))
            voice(cells, "projection:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        for p in range(resolved.dims.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:draft", query.comma_left(geometry, resolved, resolved.dims.comma_count), query.projection_top(geometry, p),
                                 COL_W, ROW_H, "mapped", text="0" if resolved.ghosts.comma else "", prime=p, pending=True))
    for j in range(resolved.dims.unchanged_count):
        dashed = resolved.unchanged.basis[j] is None
        for p in range(resolved.dims.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:u{j}", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + j), query.projection_top(geometry, p),
                                 COL_W, ROW_H, "mapped",
                                 text=DASH if dashed else str(resolved.unchanged.basis[j][p]), prime=p, comma=resolved.dims.comma_count + j))
            if not dashed:
                voice(cells, "projection:commas", resolved.dims.comma_count + j, resolved.unchanged.sizes.tempered[j])


def _emit_projection_basis(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "projection") and query.tile_open(geometry, context.collapsed, "projection", "quantities"):
        bx = geometry.col_x["quantities"] + (geometry.col_w["quantities"] - COL_W) / 2
        for p in range(resolved.dims.dimensionality):
            cells.append(CellBox(f"projection_basis:{p}", bx, query.projection_top(geometry, p), COL_W, ROW_H, "commaratio", text=str(resolved.dims.elements[p]), prime=p))


def _emit_scaling_factors(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "scaling_factors") and query.tile_open(geometry, context.collapsed, "scaling_factors", "commas"):
        scaling = ["0"] * resolved.dims.comma_count + [(DASH if v is None else "1") for v in resolved.unchanged.basis]
        for c, lam in enumerate(scaling):
            cells.append(CellBox(f"cell:scaling:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, query.comma_value_pos(resolved, c)), geometry.rows["scaling_factors"].y,
                                 COL_W, ROW_H, "mapped", text=lam, comma=c))
        if resolved.scalars.comma_draft:
            cells.append(CellBox("cell:scaling:draft", query.comma_left(geometry, resolved, resolved.dims.comma_count), geometry.rows["scaling_factors"].y,
                                 COL_W, ROW_H, "mapped", text="0" if resolved.ghosts.comma else "", pending=True))


def emit_canon_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, context.collapsed, "canon"):
        _emit_canon_gens(cells, resolved, geometry, context)
        _emit_canon_primes(cells, resolved, geometry, context)
        _emit_canon_form(cells, resolved, geometry, context)
        for i in range(resolved.dims.canonical_rank):
            _emit_canon_row(cells, resolved, geometry, context, i)
    _emit_canon_finv(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_canon_gens(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "quantities"):
        for i in range(resolved.dims.canonical_rank):
            cells.append(CellBox(f"canon:gen:{i}", geometry.col_x["quantities"], query.canon_top(geometry, i), geometry.col_w["quantities"], ROW_H, "genratio", text=resolved.canon.gens[i] if i < len(resolved.canon.gens) else ""))


def _emit_canon_primes(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "primes"):
        for i in range(resolved.dims.canonical_rank):
            for p in range(resolved.dims.dimensionality):
                cells.append(CellBox(f"cell:canon:{i}:{p}", query.prime_left(geometry, p), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapping[i][p]), gen=i, prime=p, unit=query.cell_unit(resolved, "canon", "primes", gen=i, prime=p)))


def _emit_canon_form(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canon", "gens"):
        for i in range(len(resolved.canon.form_M)):
            for j in range(len(resolved.canon.form_M)):
                cells.append(CellBox(f"cell:form:{i}:{j}", query.gen_left(geometry, j), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.form_M[i][j]), unit=query.cell_unit(resolved, "canon", "gens", gen=i)))


def _emit_canon_row(cells, resolved, geometry, context, i) -> None:
    collapsed = context.collapsed
    if query.tile_open(geometry, collapsed, "canon", "detempering"):
        for c in range(resolved.dims.rank):
            cells.append(CellBox(f"cell:canon_detempering:{i}:{query.col_token(resolved, 'detempering', c)}", query.detempering_left(geometry, c), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapped_detempering[i][c]), gen=i, unit=query.cell_unit(resolved, "canon", "detempering", gen=i)))
    if query.tile_open(geometry, collapsed, "canon", "targets"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_mapped", "targets", resolved.dims.target_count, lambda c: query.target_left(geometry, c), resolved.canon.mapped, resolved.targets.pending, i)
    if query.tile_open(geometry, collapsed, "canon", "interest"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_imapped", "interest", resolved.dims.interest_count, lambda c: query.interest_left(geometry, c), resolved.canon.interest_mapped, resolved.interest.pending, i)
    if query.tile_open(geometry, collapsed, "canon", "held"):
        _emit_canon_mapped_tile(cells, resolved, geometry, "canon_hmapped", "held", resolved.dims.held_count, lambda c: query.held_left(geometry, c), resolved.canon.held_mapped, resolved.held.pending, i)
    if query.tile_open(geometry, collapsed, "canon", "commas"):
        _emit_canon_comma_row(cells, resolved, geometry, i)


def _emit_canon_comma_row(cells, resolved, geometry, i) -> None:
    for c in range(resolved.dims.comma_count):
        cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{query.col_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(resolved.canon.mapped_commas[i][c]), gen=i, unit=query.cell_unit(resolved, "canon", "commas", gen=i)))
    if resolved.scalars.comma_draft:
        cells.append(CellBox(f"cell:canon_mapped_comma:{i}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dims.comma_count), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))
    for j in range(resolved.dims.unchanged_count):
        ut = DASH if resolved.canon.unchanged_mapped[i][j] is None else str(resolved.canon.unchanged_mapped[i][j])
        cells.append(CellBox(f"cell:canon_mapped_unchanged:{i}:{j}", query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + j), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=ut, gen=i, unit=query.cell_unit(resolved, "canon", "commas", gen=i)))


def _emit_canon_finv(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "canongens"):
        for i in range(resolved.dims.rank):
            for j in range(resolved.dims.canonical_rank):
                cells.append(CellBox(f"cell:finv:{i}:{j}", query.canongen_left(geometry, j), query.map_top(geometry, i), COL_W, ROW_H,
                                     "formcell", text=str(resolved.canon.inverse_form_M[i][j]), unit=query.cell_unit(resolved, "mapping", "canongens", gen=i)))


def _emit_canon_mapped_tile(cells, resolved, geometry, prefix, group, count, left_fn, data, pending, i) -> None:
    for col in range(count):
        cells.append(CellBox(f"cell:{prefix}:{i}:{query.col_token(resolved, group, col)}", left_fn(col), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text=str(data[i][col]), gen=i, unit=query.cell_unit(resolved, "canon", group, gen=i)))
    if pending is not None:
        cells.append(CellBox(f"cell:{prefix}:{i}:draft", left_fn(count), query.canon_top(geometry, i), COL_W, ROW_H, "mapped", text="", gen=i, pending=True))


