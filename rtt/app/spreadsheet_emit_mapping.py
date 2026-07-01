from __future__ import annotations

import functools

from rtt.app import ids
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import (
    BUTTON,
    COLUMN_WIDTH,
    DASH,
    ETPICK_GAP,
    ETPICK_WIDTH,
    ROW_HANDLE_WIDTH,
    ROW_HEIGHT,
)
from rtt.app.spreadsheet_emit_model import EmitResult, dash_or_str, voice
from rtt.app.spreadsheet_models import _MappedTile


def emit_mapping(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, context.collapsed, "mapping"):
        return EmitResult()
    _emit_mapping_generators(cells, resolved, geometry, context)
    _emit_mapping_drag(cells, resolved, geometry, context)
    _emit_mapping_rows(cells, resolved, geometry, context)
    if resolved.scalars.row_draft:
        _emit_mapping_draft_row(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _map_minus_span(geometry):
    map_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "mapping") else geometry.node_edge
    generator_right = geometry.column_x["quantities"] + geometry.column_width["quantities"]
    return map_bus_x, generator_right


def _emit_mapping_generators(cells, resolved, geometry, context) -> None:
    if not query.tile_open(geometry, context.collapsed, "mapping", "quantities"):
        return
    for i in range(resolved.dimensions.rank):
        cells.append(CellBox(f"generator:{query.column_token(resolved, 'generators', i)}", geometry.column_x["quantities"], query.map_top(geometry, i), geometry.column_width["quantities"], ROW_HEIGHT, "generator_ratio", text=resolved.scalars.generators[i] if i < len(resolved.scalars.generators) else "", generator=i))
    map_bus_x, generator_right = _map_minus_span(geometry)
    if resolved.dimensions.rank > 1:
        for i in range(resolved.dimensions.rank):
            cells.append(CellBox(f"map_minus:{query.column_token(resolved, 'generators', i)}", map_bus_x, query.map_top(geometry, i), generator_right - map_bus_x, ROW_HEIGHT, "map_minus", generator=i))
    if "mapping" in geometry.row_plus_y:
        cells.append(CellBox("map_plus", map_bus_x - BUTTON / 2, geometry.row_plus_y["mapping"] - BUTTON / 2, BUTTON, BUTTON, "map_plus"))


def _emit_mapping_drag(cells, resolved, geometry, context) -> None:
    if context.settings.get("drag_to_combine") and resolved.dimensions.rank > 1 and query.tile_open(geometry, context.collapsed, "mapping", "primes"):
        for i in range(resolved.dimensions.rank):
            cells.append(CellBox(f"map_drag:{query.column_token(resolved, 'generators', i)}", geometry.primes_x + query.etpick_left_padding(geometry, "primes"), query.map_top(geometry, i), ROW_HANDLE_WIDTH, ROW_HEIGHT, "map_drag", generator=i))


def _emit_mapping_rows(cells, resolved, geometry, context) -> None:
    matrix_x, matrix_width = query.matrix_span(geometry, resolved, "primes")
    etpick_x = matrix_x + matrix_width + ETPICK_GAP
    for i in range(resolved.dimensions.rank):
        rt = query.column_token(resolved, "generators", i)
        if query.tile_open(geometry, context.collapsed, "mapping", "primes"):
            if resolved.flags.presets:
                cells.append(CellBox(f"etpick:{rt}", etpick_x, query.map_top(geometry, i), ETPICK_WIDTH, ROW_HEIGHT, "etpick", generator=i))
            for p in range(resolved.dimensions.dimensionality):
                cells.append(CellBox(ids.mapping_cell(rt, p), query.prime_left(geometry, p), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapping", text=str(context.state.mapping[i][p]), generator=i, prime=p, unit=query.cell_unit(resolved, "mapping", "primes", generator=i, prime=p)))
        if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("mapped", "targets", resolved.dimensions.target_count, lambda c: query.interval_left(geometry, "targets", c), resolved.targets.mapped, resolved.targets.pending, resolved.tuning.target_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("imapped", "interest", resolved.dimensions.interest_count, lambda c: query.interval_left(geometry, "interest", c), resolved.interest.mapped, resolved.interest.pending, resolved.tuning.interest_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "held"):
            _emit_mapped_tile(cells, resolved, geometry, _MappedTile("hmapped", "held", resolved.dimensions.held_count, lambda c: query.interval_left(geometry, "held", c), resolved.tuning.held_mapped, resolved.held.pending, resolved.tuning.held_sizes.tempered), i, rt)
        if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
            _emit_mapping_comma_row(cells, resolved, geometry, i, rt)


def _emit_mapping_comma_row(cells, resolved, geometry, i, rt) -> None:
    for c in range(resolved.dimensions.comma_count):
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(resolved.commas.mapped[i][c]), generator=i, unit=query.cell_unit(resolved, "mapping", "commas", generator=i)))
        voice(cells, "mapped:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        mc_text = str(resolved.ghosts.comma_mapped[i]) if (resolved.ghosts.comma and i < len(resolved.ghosts.comma_mapped)) else ""
        cells.append(CellBox(f"cell:mapped_comma:{rt}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=mc_text, generator=i, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        mapped_text = dash_or_str(resolved.unchanged.mapped[i][j])
        cells.append(CellBox(f"cell:mapped_unchanged:{rt}:{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=mapped_text, generator=i, unit=query.cell_unit(resolved, "mapping", "commas", generator=i)))
        voice(cells, "mapped:commas", resolved.dimensions.comma_count + j, resolved.unchanged.sizes.tempered[j])


def _emit_mapping_draft_row(cells, resolved, geometry, context) -> None:
    dr = resolved.dimensions.rank
    drt = query.pending_col_token(resolved, "generators")
    if query.tile_open(geometry, context.collapsed, "mapping", "quantities"):
        generator_text = resolved.ghosts.row_ratio if resolved.ghosts.row else "?"
        cells.append(CellBox("generator:pending", geometry.column_x["quantities"], query.map_top(geometry, dr), geometry.column_width["quantities"], ROW_HEIGHT, "generator_ratio", text=generator_text, generator=dr, pending=True))
        if not resolved.ghosts.row:
            map_bus_x, generator_right = _map_minus_span(geometry)
            cells.append(CellBox("map_minus:pending", map_bus_x, query.map_top(geometry, dr), generator_right - map_bus_x, ROW_HEIGHT, "map_minus", generator=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "primes"):
        row_kind = "mapped" if resolved.ghosts.row else "mapping"
        for p in range(resolved.dimensions.dimensionality):
            v = resolved.ghosts.row_map[p] if resolved.ghosts.row else context.pending_mapping_row[p]
            cells.append(CellBox(ids.mapping_cell(drt, p), query.prime_left(geometry, p), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, row_kind, text="" if v is None else str(v), generator=dr, prime=p, pending=True))
        if not resolved.ghosts.row and resolved.flags.presets:
            matrix_x, matrix_width = query.matrix_span(geometry, resolved, "primes")
            cells.append(CellBox("etpick:draft", matrix_x + matrix_width + ETPICK_GAP, query.map_top(geometry, dr), ETPICK_WIDTH, ROW_HEIGHT, "etpick", generator=dr, pending=True))
    _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt)


def _draft_mapped_text(resolved, key, j) -> str:
    vals = resolved.ghosts.row_mapped.get(key, ()) if resolved.ghosts.row else ()
    if j >= len(vals):
        return ""
    return dash_or_str(vals[j])


def _emit_mapping_draft_mapped(cells, resolved, geometry, context, dr, drt) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "targets"):
        for j in range(resolved.dimensions.target_count):
            cells.append(CellBox(f"cell:mapped:{drt}:{query.column_token(resolved, 'targets', j)}", query.interval_left(geometry, "targets", j), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=_draft_mapped_text(resolved, "targets", j), generator=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "interest"):
        for ii in range(resolved.dimensions.interest_count):
            cells.append(CellBox(f"cell:imapped:{drt}:{query.column_token(resolved, 'interest', ii)}", query.interval_left(geometry, "interest", ii), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=_draft_mapped_text(resolved, "interest", ii), generator=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "held"):
        for hi in range(resolved.dimensions.held_count):
            cells.append(CellBox(f"cell:hmapped:{drt}:{query.column_token(resolved, 'held', hi)}", query.interval_left(geometry, "held", hi), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=_draft_mapped_text(resolved, "held", hi), generator=dr, pending=True))
    if query.tile_open(geometry, context.collapsed, "mapping", "commas"):
        _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt)


def _emit_mapping_draft_commas(cells, resolved, geometry, dr, drt) -> None:
    for c in range(resolved.dimensions.comma_count):
        cells.append(CellBox(f"cell:mapped_comma:{drt}:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=_draft_mapped_text(resolved, "commas", c), generator=dr, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        cells.append(CellBox(f"cell:mapped_unchanged:{drt}:{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=_draft_mapped_text(resolved, "unchanged", j), generator=dr, pending=True))


def _emit_mapped_tile(cells, resolved, geometry, m: _MappedTile, i, id_index, top_fn=query.map_top, unit_row="mapping") -> None:
    for column in range(m.count):
        cells.append(CellBox(f"cell:{m.prefix}:{id_index}:{query.column_token(resolved, m.group, column)}", m.left_fn(column), top_fn(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(m.data[i][column]), generator=i, unit=query.cell_unit(resolved, unit_row, m.group, generator=i)))
        if m.sizes is not None:
            voice(cells, f"mapped:{m.group}", column, m.sizes[column])
    if m.pending is not None:
        cells.append(CellBox(f"cell:{m.prefix}:{id_index}:draft", m.left_fn(m.count), top_fn(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=i, pending=True))


def emit_mapped_grid(cells, resolved, geometry, collapsed, tile, prefix, grid, n_cols, left, column_kw, *,
                     full=None, colwise=False, column_token_key=None,
                     row="projection", top=None, height=None, pending=None, audio=None) -> None:
    if not (query.row_open(geometry, collapsed, row) and query.tile_open(geometry, collapsed, row, tile)):
        return
    if full is None:
        full = grid is not None
    if top is None:
        top = functools.partial(query.projection_top, geometry)
    height = resolved.dimensions.dimensionality if height is None else height
    if colwise:
        _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, column_kw,
                                  full, column_token_key, top, height, pending, audio)
    else:
        _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, column_kw, full, top, height)


def _projected_sizes(resolved, grid, n_cols, height):
    just_map = resolved.tuning.tuning_map.just_map
    return [sum(just_map[i] * grid[j][i] for i in range(height)) for j in range(n_cols)]


def _emit_mapped_grid_colwise(cells, resolved, prefix, grid, n_cols, left, column_kw,
                              full, column_token_key, top, height, pending, audio=None) -> None:
    sizes = _projected_sizes(resolved, grid, n_cols, height) if (audio is not None and full) else None
    for j in range(n_cols):
        for i in range(height):
            text = str(grid[j][i]) if full else DASH
            token = j if column_token_key is None else query.column_token(resolved, column_token_key, j)
            cells.append(CellBox(f"cell:{prefix}:{token}:{i}", left(j), top(i),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=text, prime=i, **{column_kw: j}))
            if sizes is not None:
                voice(cells, audio, j, sizes[j])
    if pending is not None:
        for i in range(height):
            cells.append(CellBox(f"cell:{prefix}:draft:{i}", left(n_cols), top(i),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", prime=i, pending=True))


def _emit_mapped_grid_rowwise(cells, prefix, grid, n_cols, left, column_kw,
                              full, top, height) -> None:
    for i in range(height):
        for j in range(n_cols):
            text = grid[i][j] if full else DASH
            cells.append(CellBox(f"cell:{prefix}:{i}:{j}", left(j), top(i),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=text, **{column_kw: j}))


def emit_projection_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    collapsed = context.collapsed
    emit_mapped_grid(cells, resolved, geometry, collapsed, "primes", "projection", resolved.projection.matrix, resolved.dimensions.dimensionality, lambda i: query.prime_left(geometry, i), "prime")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "generators", "embed", resolved.projection.embedding_matrix, resolved.dimensions.rank, lambda i: query.generator_left(geometry, i), "generator")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "canonical_generators", "embed_c", resolved.canonical.embedding_matrix, resolved.dimensions.canonical_rank, lambda i: query.canonical_generator_left(geometry, i), "generator")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "superspace_generators", "embed_sl", resolved.projection.embedding_superspace, resolved.dimensions.superspace_rank, lambda i: query.superspace_generator_left(geometry, i), "generator")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "superspace_primes", "projection_superspace", resolved.projection.superspace, resolved.dimensions.superspace_dimensionality, lambda i: query.superspace_prime_left(geometry, i), "prime")
    _emit_projection_unchanged(cells, resolved, geometry, context)
    _emit_projection_basis(cells, resolved, geometry, context)
    full_projection = resolved.projection.rationals is not None
    emit_mapped_grid(cells, resolved, geometry, collapsed, "detempering", "projection_detempering", resolved.projection.detempering, resolved.dimensions.rank, lambda i: query.detempering_left(geometry, i), "generator",
                     full=full_projection, colwise=True, column_token_key="detempering", audio="projection:detempering")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "targets", "projection_targets", resolved.projection.targets, resolved.dimensions.target_count, lambda i: query.interval_left(geometry, "targets", i), "comma",
                     full=full_projection, colwise=True, pending=resolved.targets.pending, audio="projection:targets")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "held", "projection_held", resolved.projection.held, resolved.dimensions.held_count, lambda i: query.interval_left(geometry, "held", i), "comma",
                     full=full_projection, colwise=True, pending=resolved.held.pending, audio="projection:held")
    emit_mapped_grid(cells, resolved, geometry, collapsed, "interest", "projection_interest", resolved.projection.interest, resolved.dimensions.interest_count, lambda i: query.interval_left(geometry, "interest", i), "comma",
                     full=full_projection, colwise=True, pending=resolved.interest.pending, audio="projection:interest")
    _emit_scaling_factors(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_projection_unchanged(cells, resolved, geometry, context) -> None:
    if not (resolved.unchanged.shown and query.row_open(geometry, context.collapsed, "projection")
            and query.tile_open(geometry, context.collapsed, "projection", "commas")):
        return
    for c in range(resolved.dimensions.comma_count):
        for p in range(resolved.dimensions.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="0", prime=p, comma=c))
            voice(cells, "projection:commas", c, resolved.tuning.comma_sizes.tempered[c])
    if resolved.scalars.comma_draft:
        for p in range(resolved.dimensions.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:draft", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="0" if resolved.ghosts.comma else "", prime=p, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        dashed = resolved.unchanged.basis[j] is None
        for p in range(resolved.dimensions.dimensionality):
            cells.append(CellBox(f"cell:projection_vectors:{p}:u{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped",
                                 text=DASH if dashed else str(resolved.unchanged.basis[j][p]), prime=p, comma=resolved.dimensions.comma_count + j))
            if not dashed:
                voice(cells, "projection:commas", resolved.dimensions.comma_count + j, resolved.unchanged.sizes.tempered[j])


def _emit_projection_basis(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "projection") and query.tile_open(geometry, context.collapsed, "projection", "quantities"):
        bx = query.basis_col_x(geometry)
        for p in range(resolved.dimensions.dimensionality):
            cells.append(CellBox(f"projection_basis:{p}", bx, query.projection_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, "comma_ratio", text=str(resolved.dimensions.elements[p]), prime=p))


def _emit_scaling_factors(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "scaling_factors") and query.tile_open(geometry, context.collapsed, "scaling_factors", "commas"):
        scaling = ["0"] * resolved.dimensions.comma_count + [(DASH if v is None else "1") for v in resolved.unchanged.basis]
        for c, lam in enumerate(scaling):
            cells.append(CellBox(f"cell:scaling:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, query.comma_value_pos(resolved, c)), geometry.rows["scaling_factors"].y,
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=lam, comma=c))
        if resolved.scalars.comma_draft:
            cells.append(CellBox("cell:scaling:draft", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), geometry.rows["scaling_factors"].y,
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="0" if resolved.ghosts.comma else "", pending=True))


def emit_canonical_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if query.row_open(geometry, context.collapsed, "canonical"):
        _emit_canonical_generators(cells, resolved, geometry, context)
        _emit_canonical_primes(cells, resolved, geometry, context)
        _emit_canonical_form(cells, resolved, geometry, context)
        for i in range(resolved.dimensions.canonical_rank):
            _emit_canonical_row(cells, resolved, geometry, context, i)
    _emit_canonical_finv(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_canonical_generators(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canonical", "quantities"):
        for i in range(resolved.dimensions.canonical_rank):
            cells.append(CellBox(f"canonical:generator:{i}", geometry.column_x["quantities"], query.canonical_top(geometry, i), geometry.column_width["quantities"], ROW_HEIGHT, "generator_ratio", text=resolved.canonical.generators[i] if i < len(resolved.canonical.generators) else ""))


def _emit_canonical_primes(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canonical", "primes"):
        for i in range(resolved.dimensions.canonical_rank):
            for p in range(resolved.dimensions.dimensionality):
                cells.append(CellBox(f"cell:canonical:{i}:{p}", query.prime_left(geometry, p), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(resolved.canonical.mapping[i][p]), generator=i, prime=p, unit=query.cell_unit(resolved, "canonical", "primes", generator=i, prime=p)))


def _emit_canonical_form(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canonical", "generators"):
        for i in range(len(resolved.canonical.form_M)):
            for j in range(len(resolved.canonical.form_M)):
                cells.append(CellBox(f"cell:form:{i}:{j}", query.generator_left(geometry, j), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(resolved.canonical.form_M[i][j]), unit=query.cell_unit(resolved, "canonical", "generators", generator=i)))


def _emit_canonical_row(cells, resolved, geometry, context, i) -> None:
    collapsed = context.collapsed
    if query.tile_open(geometry, collapsed, "canonical", "detempering"):
        for c in range(resolved.dimensions.rank):
            cells.append(CellBox(f"cell:canonical_detempering:{i}:{query.column_token(resolved, 'detempering', c)}", query.detempering_left(geometry, c), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(resolved.canonical.mapped_detempering[i][c]), generator=i, unit=query.cell_unit(resolved, "canonical", "detempering", generator=i)))
    if query.tile_open(geometry, collapsed, "canonical", "targets"):
        _emit_mapped_tile(cells, resolved, geometry, _MappedTile("canonical_mapped", "targets", resolved.dimensions.target_count, lambda c: query.interval_left(geometry, "targets", c), resolved.canonical.mapped, resolved.targets.pending), i, i, query.canonical_top, "canonical")
    if query.tile_open(geometry, collapsed, "canonical", "interest"):
        _emit_mapped_tile(cells, resolved, geometry, _MappedTile("canonical_imapped", "interest", resolved.dimensions.interest_count, lambda c: query.interval_left(geometry, "interest", c), resolved.canonical.interest_mapped, resolved.interest.pending), i, i, query.canonical_top, "canonical")
    if query.tile_open(geometry, collapsed, "canonical", "held"):
        _emit_mapped_tile(cells, resolved, geometry, _MappedTile("canonical_hmapped", "held", resolved.dimensions.held_count, lambda c: query.interval_left(geometry, "held", c), resolved.canonical.held_mapped, resolved.held.pending), i, i, query.canonical_top, "canonical")
    if query.tile_open(geometry, collapsed, "canonical", "commas"):
        _emit_canonical_comma_row(cells, resolved, geometry, i)


def _emit_canonical_comma_row(cells, resolved, geometry, i) -> None:
    for c in range(resolved.dimensions.comma_count):
        cells.append(CellBox(f"cell:canonical_mapped_comma:{i}:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(resolved.canonical.mapped_commas[i][c]), generator=i, unit=query.cell_unit(resolved, "canonical", "commas", generator=i)))
    if resolved.scalars.comma_draft:
        cells.append(CellBox(f"cell:canonical_mapped_comma:{i}:{query.pending_col_token(resolved, 'commas')}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=i, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        ut = dash_or_str(resolved.canonical.unchanged_mapped[i][j])
        cells.append(CellBox(f"cell:canonical_mapped_unchanged:{i}:{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=ut, generator=i, unit=query.cell_unit(resolved, "canonical", "commas", generator=i)))


def _emit_canonical_finv(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "mapping", "canonical_generators"):
        for i in range(resolved.dimensions.rank):
            for j in range(resolved.dimensions.canonical_rank):
                cells.append(CellBox(f"cell:finv:{i}:{j}", query.canonical_generator_left(geometry, j), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                                     "form_cell", text=str(resolved.canonical.inverse_form_M[i][j]), unit=query.cell_unit(resolved, "mapping", "canonical_generators", generator=i)))
