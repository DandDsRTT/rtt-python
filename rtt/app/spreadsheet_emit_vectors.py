from __future__ import annotations

from rtt.app import ids, service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import Cell
from rtt.app.spreadsheet_constants import (
    BUTTON,
    COLUMN_WIDTH,
    COMMAPICK_GAP,
    DASH,
    ROW_HANDLE_WIDTH,
    ROW_HEIGHT,
)
from rtt.app.spreadsheet_emit_mapping import emit_mapped_grid
from rtt.app.spreadsheet_emit_model import (
    EmitResult,
    _element_draft_kind,
    draft_open,
    element_cell_kind,
    pending_col_token,
    voice,
)
from rtt.app.spreadsheet_models import _VecGrid


def emit_vectors(resolved, geometry, context) -> EmitResult:
    cells: list = []
    if not query.row_open(geometry, context.collapsed, "vectors"):
        return EmitResult()
    if query.tile_open(geometry, context.collapsed, "vectors", "quantities"):
        _emit_vectors_basis_col(cells, resolved, geometry, context)
    if query.tile_open(geometry, context.collapsed, "vectors", "commas"):
        _emit_vectors_commas_col(cells, resolved, geometry, context)
    if query.tile_open(geometry, context.collapsed, "vectors", "targets"):
        target_kind = "target_cell" if resolved.scalars.targets_editable else "vector"
        _emit_vector_grid(cells, resolved, geometry, _VecGrid("targets", resolved.dimensions.target_count, ids.target_cell,
            lambda i: query.interval_left(geometry, "targets", i), target_kind, "target_cell",
            resolved.targets.vectors, resolved.targets.pending, resolved.tuning.target_sizes))
    if query.tile_open(geometry, context.collapsed, "vectors", "held"):
        _emit_vector_grid(cells, resolved, geometry, _VecGrid("held", resolved.dimensions.held_count, ids.held_cell,
            lambda i: query.interval_left(geometry, "held", i), "held_cell", "held_cell",
            resolved.held.vectors, resolved.held.pending, resolved.tuning.held_sizes))
    if query.tile_open(geometry, context.collapsed, "vectors", "detempering"):
        _emit_vectors_detempering_col(cells, resolved, geometry)
    if query.tile_open(geometry, context.collapsed, "vectors", "interest"):
        _emit_vector_grid(cells, resolved, geometry, _VecGrid("interest", resolved.dimensions.interest_count, ids.interest_cell,
            lambda i: query.interval_left(geometry, "interest", i), "interest_cell", "interest_cell",
            resolved.interest.vectors, resolved.interest.pending, resolved.tuning.interest_sizes))
    _emit_vectors_int_handles(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_vector_grid(cells, resolved, geometry, g: _VecGrid) -> None:
    for column in range(g.count):
        for p in range(resolved.dimensions.dimensionality):
            cells.append(Cell(g.id_fn(query.column_token(resolved, g.group, column), p), g.left_fn(column), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, g.committed_kind, text=str(g.data[column][p]), prime=p, comma=column, unit=query.cell_unit(resolved, "vectors", g.group, prime=p)))
            voice(cells, f"vectors:{g.group}", column, g.sizes.just[column])
    if g.pending is not None:
        for p in range(resolved.dimensions.dimensionality):
            v = g.pending[p]
            cells.append(Cell(g.id_fn(pending_col_token(resolved, g.group), p), g.left_fn(g.count), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, g.pending_kind,
                                 text="" if v is None else str(v), prime=p, comma=g.count, pending=True, unit=query.cell_unit(resolved, "vectors", g.group, prime=p)))
    if resolved.scalars.element_draft:
        dp = resolved.dimensions.dimensionality
        for column in range(g.count):
            cells.append(Cell(g.id_fn(query.column_token(resolved, g.group, column), dp), g.left_fn(column), query.vector_top(geometry, dp), COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", prime=dp, comma=column, pending=True))


def _basis_col_x(geometry):
    basis_x = query.basis_col_x(geometry)
    basis_bus_x = geometry.node_edge + geometry.FAN if query.row_fans(geometry, "vectors") else geometry.node_edge
    return basis_x, basis_bus_x


def _emit_basis_minus(cells, geometry, cell_id, p, kind, **kw):
    basis_x, basis_bus_x = _basis_col_x(geometry)
    cells.append(Cell(cell_id, basis_bus_x, query.vector_top(geometry, p),
                         (basis_x + COLUMN_WIDTH) - basis_bus_x, ROW_HEIGHT, kind, **kw))


def _emit_vectors_basis_col(cells, resolved, geometry, context) -> None:
    basis_x, basis_bus_x = _basis_col_x(geometry)
    for p in range(resolved.dimensions.dimensionality):
        text = str(resolved.dimensions.elements[p])
        kind = element_cell_kind(text) if resolved.flags.nonstandard_domain else "prime"
        cells.append(Cell(f"basis:{p}", basis_x, query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, kind, text=text, prime=p))
    if resolved.scalars.element_draft:
        draft_kind = _element_draft_kind(resolved, context.pending_element)
        cells.append(Cell("basis:pending", basis_x, query.vector_top(geometry, resolved.dimensions.dimensionality), COLUMN_WIDTH, ROW_HEIGHT,
                                  draft_kind, text=context.pending_element or "", prime=resolved.dimensions.dimensionality, pending=True))
        if not resolved.ghosts.element:
            _emit_basis_minus(cells, geometry, "element_minus:basis:pending", resolved.dimensions.dimensionality, "element_minus")
    if resolved.flags.nonstandard_domain:
        if resolved.dimensions.dimensionality > 1:
            for p in range(resolved.dimensions.dimensionality):
                _emit_basis_minus(cells, geometry, f"element_minus:basis:{p}", p, "element_minus", prime=p)
    elif resolved.scalars.domain_can_shrink:
        _emit_basis_minus(cells, geometry, "basis_minus", resolved.dimensions.dimensionality - 1, "basis_minus")
    if "vectors" in geometry.row_plus_y:
        plus_kind = "element_plus" if resolved.flags.nonstandard_domain else "plus"
        cells.append(Cell("basis_plus", basis_bus_x - BUTTON / 2, geometry.row_plus_y["vectors"] - BUTTON / 2,
                             BUTTON, BUTTON, plus_kind, disabled=draft_open(resolved)))


def _emit_commas_element_draft_row(cells, resolved, geometry) -> None:
    if not resolved.scalars.element_draft:
        return
    dp = resolved.dimensions.dimensionality
    for c in range(resolved.dimensions.comma_count):
        cells.append(Cell(ids.comma_cell(query.column_token(resolved, "commas", c), dp), query.comma_left(geometry, resolved, c), query.vector_top(geometry, dp), COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", prime=dp, comma=c, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        cells.append(Cell(ids.unchanged_cell(j, dp), query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.vector_top(geometry, dp), COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", prime=dp, comma=resolved.dimensions.comma_count + j, pending=True))


def _emit_vectors_commas_col(cells, resolved, geometry, context) -> None:
    for c in range(resolved.dimensions.comma_count):
        for p in range(resolved.dimensions.dimensionality):
            cells.append(Cell(ids.comma_cell(query.column_token(resolved, 'commas', c), p), query.comma_left(geometry, resolved, c), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, "comma_cell", text=str(context.state.comma_basis[c][p]), prime=p, comma=c, unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
            voice(cells, "vectors:commas", c, resolved.tuning.comma_sizes.just[c])
        if resolved.flags.presets:
            cells.append(Cell(f"commapick:{query.column_token(resolved, 'commas', c)}", query.comma_left(geometry, resolved, c), query.comma_picker_band_y(geometry, "vectors") + COMMAPICK_GAP, COLUMN_WIDTH, ROW_HEIGHT, "commapick", comma=c))
    _emit_commas_element_draft_row(cells, resolved, geometry)
    for j in range(resolved.dimensions.unchanged_count):
        doomed = resolved.commas.pending is not None and j == resolved.dimensions.unchanged_count - 1
        born = resolved.unchanged.born and j == resolved.dimensions.unchanged_count - 1
        for p in range(resolved.dimensions.dimensionality):
            vector_text = DASH if resolved.unchanged.basis[j] is None else str(resolved.unchanged.basis[j][p])
            cells.append(Cell(ids.unchanged_cell(j, p), query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT,
                                 "unchanged_cell" if (resolved.unchanged.full and not doomed and not born) else "vector", text=vector_text, prime=p, comma=resolved.dimensions.comma_count + j,
                                 unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
        voice(cells, "vectors:commas", resolved.dimensions.comma_count + j, resolved.unchanged.sizes.just[j])
    if resolved.scalars.comma_draft:
        column_kind = "vector" if resolved.ghosts.comma else "comma_cell"
        for p in range(resolved.dimensions.dimensionality):
            v = None if resolved.ghosts.comma else resolved.commas.pending[p]
            cells.append(Cell(ids.comma_cell(pending_col_token(resolved, 'commas'), p), query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, column_kind,
                                 text="" if v is None else str(v), prime=p, comma=resolved.dimensions.comma_count, pending=True, unit=query.cell_unit(resolved, "vectors", "commas", prime=p)))
        if resolved.commas.pending is not None and resolved.flags.presets:
            cells.append(Cell("commapick:draft", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.comma_picker_band_y(geometry, "vectors") + COMMAPICK_GAP, COLUMN_WIDTH, ROW_HEIGHT, "commapick", comma=resolved.dimensions.comma_count, pending=True))


def _emit_vectors_detempering_col(cells, resolved, geometry) -> None:
    for i in range(resolved.dimensions.rank):
        for p in range(resolved.dimensions.dimensionality):
            cells.append(Cell(f"cell:vector:detempering:{query.column_token(resolved, 'detempering', i)}:{p}", query.detempering_left(geometry, i), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, "vector", text=str(resolved.detempering.vectors[i][p]), unit=query.cell_unit(resolved, "vectors", "detempering", prime=p)))
            voice(cells, "vectors:detempering", i, resolved.detempering.sizes.just[i])
    if resolved.scalars.element_draft:
        dp = resolved.dimensions.dimensionality
        for i in range(resolved.dimensions.rank):
            cells.append(Cell(f"cell:vector:detempering:{query.column_token(resolved, 'detempering', i)}:{dp}", query.detempering_left(geometry, i), query.vector_top(geometry, dp), COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", pending=True))
    if resolved.scalars.row_draft:
        dr = resolved.dimensions.rank
        for p in range(resolved.dimensions.dimensionality):
            cells.append(Cell(f"cell:vector:detempering:draft:{p}", query.detempering_left(geometry, dr), query.vector_top(geometry, p), COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", pending=True))


def _emit_vectors_int_handles(cells, resolved, geometry, context) -> None:
    if not ("vectors" in geometry.rows and geometry.rows["vectors"].interval_handle_top is not None):
        return
    hy = geometry.rows["vectors"].interval_handle_top
    columns = (
        ("comma", resolved.dimensions.comma_count, lambda i: query.comma_left(geometry, resolved, i), "commas", "grip"),
        ("unchanged", resolved.dimensions.unchanged_count, lambda i: query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + i), "commas", "derived"),
        ("target", resolved.dimensions.target_count, lambda i: query.interval_left(geometry, "targets", i), "targets", "grip" if resolved.scalars.targets_editable else None),
        ("held", resolved.dimensions.held_count, lambda i: query.interval_left(geometry, "held", i), "held", "grip"),
        ("detempering", resolved.dimensions.rank, lambda i: query.detempering_left(geometry, i), "detempering", "derived"),
        ("interest", resolved.dimensions.interest_count, lambda i: query.interval_left(geometry, "interest", i), "interest", "grip"),
    )
    shown = [(group, count, column_left, role)
             for group, count, column_left, column_key, role in columns
             if role and count >= 1 and query.tile_open(geometry, context.collapsed, "vectors", column_key)]
    if sum(count for _, count, _, role in shown if role == "grip") < 2:
        return
    for group, count, column_left, role in shown:
        kind = "int_drag" if role == "grip" else "int_derived"
        for i in range(count):
            cells.append(Cell(f"{kind}:{group}:{i}", column_left(i), hy, COLUMN_WIDTH, ROW_HANDLE_WIDTH, kind, comma=i))


def emit_superspace_rows(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_superspace_quantity_rows(cells, resolved, geometry, context)
    _emit_superspace_matrix_vectors(cells, resolved, geometry, context)
    _emit_superspace_matrix_mapping(cells, resolved, geometry, context)
    _emit_superspace_vector_lists(cells, resolved, geometry, context)
    _emit_superspace_projection_rows(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_superspace_basis_column(cells, resolved, geometry, context, row_key, id_prefix, top_fn) -> None:
    if not (query.row_open(geometry, context.collapsed, row_key) and query.tile_open(geometry, context.collapsed, row_key, "quantities")):
        return
    basis_x = query.basis_col_x(geometry)
    for p in range(resolved.dimensions.superspace_dimensionality):
        cells.append(Cell(f"{id_prefix}:{p}", basis_x, top_fn(geometry, p), COLUMN_WIDTH, ROW_HEIGHT,
                             "comma_ratio", text=str(resolved.dimensions.superspace_primes[p]), prime=p))


def _emit_superspace_quantity_rows(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    _emit_superspace_basis_column(cells, resolved, geometry, context, "superspace_vectors", "superspace_basis", query.superspace_vector_top)
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "quantities"):
        superspace_generators = service.superspace_generators(context.state)
        for i in range(resolved.dimensions.superspace_rank):
            cells.append(Cell(f"superspace_generator:{i}", query.basis_col_x(geometry), query.superspace_map_top(geometry, i),
                                 COLUMN_WIDTH, ROW_HEIGHT, "generator_ratio",
                                 text=superspace_generators[i] if i < len(superspace_generators) else ""))
    _emit_superspace_basis_column(cells, resolved, geometry, context, "superspace_projection", "superspace_projection_basis", query.superspace_projection_top)


def _emit_superspace_element_lift(cells, resolved, geometry, context) -> None:
    if not (query.row_open(geometry, context.collapsed, "superspace_vectors") and query.tile_open(geometry, context.collapsed, "superspace_vectors", "primes")):
        return
    basis = service.basis_in_superspace(resolved.dimensions.elements)
    for superspace_prime_index in range(resolved.dimensions.superspace_dimensionality):
        for element_index in range(resolved.dimensions.dimensionality):
            value = basis[element_index][superspace_prime_index]
            cells.append(Cell(
                f"cell:superspace_vectors:primes:{superspace_prime_index}:{element_index}",
                query.prime_left(geometry, element_index), query.superspace_vector_top(geometry, superspace_prime_index), COLUMN_WIDTH, ROW_HEIGHT,
                "vector", text=str(value), prime=superspace_prime_index, comma=element_index,
                unit=query.cell_unit(resolved, "superspace_vectors", "primes", prime=superspace_prime_index, element=element_index)))
    if resolved.scalars.element_draft:
        de = resolved.dimensions.dimensionality
        for superspace_prime_index in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(
                f"cell:superspace_vectors:primes:{superspace_prime_index}:{de}",
                query.prime_left(geometry, de), query.superspace_vector_top(geometry, superspace_prime_index), COLUMN_WIDTH, ROW_HEIGHT,
                "vector", text="", prime=superspace_prime_index, comma=de, pending=True))


def _emit_superspace_matrix_vectors(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    _emit_superspace_element_lift(cells, resolved, geometry, context)
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "superspace_primes"):
        ml = service.superspace_mapping(context.state)
        for generator_index in range(resolved.dimensions.superspace_rank):
            for superspace_prime_index in range(resolved.dimensions.superspace_dimensionality):
                cells.append(Cell(
                    f"cell:superspace_mapping:superspace_primes:{generator_index}:{superspace_prime_index}",
                    query.superspace_prime_left(geometry, superspace_prime_index), query.superspace_map_top(geometry, generator_index), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text=str(ml[generator_index][superspace_prime_index]), generator=generator_index, prime=superspace_prime_index,
                    unit=query.cell_unit(resolved, "superspace_mapping", "superspace_primes", generator=generator_index, prime=superspace_prime_index)))
    if query.row_open(geometry, collapsed, "superspace_vectors") and query.tile_open(geometry, collapsed, "superspace_vectors", "superspace_primes"):
        mjl = service.superspace_just_mapping(resolved.dimensions.superspace_primes)
        for i in range(resolved.dimensions.superspace_dimensionality):
            for j in range(resolved.dimensions.superspace_dimensionality):
                cells.append(Cell(
                    f"cell:superspace_vectors:superspace_primes:{i}:{j}",
                    query.superspace_prime_left(geometry, j), query.superspace_vector_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text=str(mjl[i][j]), generator=i, prime=j,
                    unit=query.cell_unit(resolved, "superspace_vectors", "superspace_primes", prime=j)))


def _emit_superspace_matrix_mapping(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "superspace_generators"):
        mlgl = service.superspace_self_map(context.state)
        for i in range(resolved.dimensions.superspace_rank):
            for j in range(resolved.dimensions.superspace_rank):
                cells.append(Cell(
                    f"cell:superspace_mapping:superspace_generators:{i}:{j}",
                    query.superspace_generator_left(geometry, j), query.superspace_map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text=str(mlgl[i][j]), generator=i,
                    unit=query.cell_unit(resolved, "superspace_mapping", "superspace_generators", generator=i)))
    if query.row_open(geometry, collapsed, "superspace_mapping") and query.tile_open(geometry, collapsed, "superspace_mapping", "primes"):
        msl = service.mapping_to_superspace_generators(context.state)
        for i in range(resolved.dimensions.superspace_rank):
            for e in range(resolved.dimensions.dimensionality):
                cells.append(Cell(
                    f"cell:superspace_mapping:primes:{i}:{e}",
                    query.prime_left(geometry, e), query.superspace_map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text=str(msl[i][e]), generator=i,
                    unit=query.cell_unit(resolved, "superspace_mapping", "primes", generator=i, element=e)))
        if resolved.scalars.element_draft:
            de = resolved.dimensions.dimensionality
            for i in range(resolved.dimensions.superspace_rank):
                cells.append(Cell(
                    f"cell:superspace_mapping:primes:{i}:{de}",
                    query.prime_left(geometry, de), query.superspace_map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text="", generator=i, pending=True))


def _emit_superspace_vector_lists(cells, resolved, geometry, context) -> None:
    superspace_lists = (("commas", context.state.comma_basis, resolved.dimensions.comma_count, lambda c: query.comma_left(geometry, resolved, c), resolved.scalars.comma_draft),
                ("targets", resolved.targets.vectors, resolved.dimensions.target_count, lambda c: query.interval_left(geometry, "targets", c), resolved.targets.pending is not None),
                ("held", resolved.held.vectors, resolved.dimensions.held_count, lambda c: query.interval_left(geometry, "held", c), resolved.held.pending is not None),
                ("interest", resolved.interest.vectors, resolved.dimensions.interest_count, lambda c: query.interval_left(geometry, "interest", c), resolved.interest.pending is not None),
                ("detempering", resolved.detempering.vectors, resolved.dimensions.rank, lambda c: query.detempering_left(geometry, c), False))
    for row in superspace_lists:
        _emit_superspace_vector_list_lift(cells, resolved, geometry, context, row)
        _emit_superspace_vector_list_map(cells, resolved, geometry, context, row)


def _emit_superspace_vector_list_lift(cells, resolved, geometry, context, row) -> None:
    column_key, vectors, n, left, draft = row
    columns = tuple(vectors)[:n]
    if not (query.row_open(geometry, context.collapsed, "superspace_vectors") and query.tile_open(geometry, context.collapsed, "superspace_vectors", column_key)):
        return
    lifted = service.lift_vectors_to_superspace(resolved.dimensions.elements, columns)
    for c in range(len(lifted)):
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(
                f"cell:superspace_vectors:{column_key}:{p}:{c}", left(c), query.superspace_vector_top(geometry, p),
                COLUMN_WIDTH, ROW_HEIGHT, "vector", text=str(lifted[c][p]), prime=p, comma=c,
                unit=query.cell_unit(resolved, "superspace_vectors", column_key, prime=p)))
    if draft:
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(f"cell:superspace_vectors:{column_key}:{p}:draft", left(n), query.superspace_vector_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "vector", text="", prime=p, pending=True))
    if column_key == "commas":
        for j in range(resolved.dimensions.unchanged_count):
            uj = resolved.projection.superspace_unchanged[j]
            for p in range(resolved.dimensions.superspace_dimensionality):
                cells.append(Cell(
                    f"cell:superspace_vectors:commas:{p}:u{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.superspace_vector_top(geometry, p),
                    COLUMN_WIDTH, ROW_HEIGHT, "vector", text=DASH if uj is None else str(uj[p]), prime=p, comma=resolved.dimensions.comma_count + j,
                    unit=query.cell_unit(resolved, "superspace_vectors", "commas", prime=p)))


def _emit_superspace_vector_list_map(cells, resolved, geometry, context, row) -> None:
    column_key, vectors, n, left, draft = row
    columns = tuple(vectors)[:n]
    if not (query.row_open(geometry, context.collapsed, "superspace_mapping") and query.tile_open(geometry, context.collapsed, "superspace_mapping", column_key)):
        return
    mapped = service.map_vectors_into_superspace_generators(context.state, columns)
    for c in range(len(mapped)):
        for g in range(resolved.dimensions.superspace_rank):
            cells.append(Cell(
                f"cell:superspace_mapping:{column_key}:{g}:{c}", left(c), query.superspace_map_top(geometry, g),
                COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=str(mapped[c][g]), generator=g, comma=c,
                unit=query.cell_unit(resolved, "superspace_mapping", column_key, generator=g)))
    if draft:
        for g in range(resolved.dimensions.superspace_rank):
            cells.append(Cell(f"cell:superspace_mapping:{column_key}:{g}:draft", left(n), query.superspace_map_top(geometry, g),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=g, pending=True))
    if column_key == "commas":
        for j in range(resolved.dimensions.unchanged_count):
            uj = resolved.projection.superspace_unchanged_mapped[j]
            for g in range(resolved.dimensions.superspace_rank):
                cells.append(Cell(
                    f"cell:superspace_mapping:commas:{g}:u{j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.superspace_map_top(geometry, g),
                    COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=DASH if uj is None else str(uj[g]), generator=g, comma=resolved.dimensions.comma_count + j,
                    unit=query.cell_unit(resolved, "superspace_mapping", "commas", generator=g)))


def _emit_superspace_projection_rows(cells, resolved, geometry, context) -> None:
    collapsed = context.collapsed
    _emit_superspace_projection_superspace_primes(cells, resolved, geometry, context)
    superspace_full = resolved.projection.superspace_rationals is not None
    _emit_superspace_projection_superspace_generators(cells, resolved, geometry, context, superspace_full)
    _emit_superspace_projection_primes(cells, resolved, geometry, context, superspace_full)
    superspace_projection_options = {"full": superspace_full, "colwise": True, "row": "superspace_projection",
           "top": lambda i: query.superspace_projection_top(geometry, i), "height": resolved.dimensions.superspace_dimensionality}
    emit_mapped_grid(cells, resolved, geometry, collapsed, "detempering", "superspace_projection_detempering", resolved.projection.superspace_detempering, resolved.dimensions.rank, lambda i: query.detempering_left(geometry, i), "generator", **superspace_projection_options)
    _emit_superspace_projection_commas(cells, resolved, geometry, context)
    emit_mapped_grid(cells, resolved, geometry, collapsed, "targets", "superspace_projection_targets", resolved.projection.superspace_targets, resolved.dimensions.target_count, lambda i: query.interval_left(geometry, "targets", i), "comma",
                     pending=resolved.targets.pending, **superspace_projection_options)
    emit_mapped_grid(cells, resolved, geometry, collapsed, "held", "superspace_projection_held", resolved.projection.superspace_held, resolved.dimensions.held_count, lambda i: query.interval_left(geometry, "held", i), "comma",
                     pending=resolved.held.pending, **superspace_projection_options)
    emit_mapped_grid(cells, resolved, geometry, collapsed, "interest", "superspace_projection_interest", resolved.projection.superspace_interest, resolved.dimensions.interest_count, lambda i: query.interval_left(geometry, "interest", i), "comma",
                     pending=resolved.interest.pending, **superspace_projection_options)


def _emit_superspace_projection_superspace_primes(cells, resolved, geometry, context) -> None:
    if query.row_open(geometry, context.collapsed, "superspace_projection") and query.tile_open(geometry, context.collapsed, "superspace_projection", "superspace_primes"):
        full = resolved.projection.superspace_matrix is not None
        for i in range(resolved.dimensions.superspace_dimensionality):
            for j in range(resolved.dimensions.superspace_dimensionality):
                text = DASH if not full else resolved.projection.superspace_matrix[i][j]
                cells.append(Cell(
                    f"cell:superspace_projection:superspace_primes:{i}:{j}",
                    query.superspace_prime_left(geometry, j), query.superspace_projection_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text=text, generator=i, prime=j,
                    unit=query.cell_unit(resolved, "superspace_projection", "superspace_primes", generator=i, prime=j)))


def _emit_superspace_projection_superspace_generators(cells, resolved, geometry, context, superspace_full) -> None:
    if query.row_open(geometry, context.collapsed, "superspace_projection") and query.tile_open(geometry, context.collapsed, "superspace_projection", "superspace_generators"):
        for i in range(resolved.dimensions.superspace_dimensionality):
            for g in range(resolved.dimensions.superspace_rank):
                text = DASH if not superspace_full else resolved.projection.superspace_embedding_matrix[i][g]
                cells.append(Cell(f"cell:superspace_embed:{i}:{g}", query.superspace_generator_left(geometry, g), query.superspace_projection_top(geometry, i),
                                     COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=text, generator=g))


def _emit_superspace_projection_primes(cells, resolved, geometry, context, superspace_full) -> None:
    if query.row_open(geometry, context.collapsed, "superspace_projection") and query.tile_open(geometry, context.collapsed, "superspace_projection", "primes"):
        for e in range(resolved.dimensions.dimensionality):
            for p in range(resolved.dimensions.superspace_dimensionality):
                text = DASH if not superspace_full else str(resolved.projection.superspace_basis[e][p])
                cells.append(Cell(f"cell:superspace_projection_basis_lift:{e}:{p}", query.prime_left(geometry, e), query.superspace_projection_top(geometry, p),
                                     COLUMN_WIDTH, ROW_HEIGHT, "mapped", text=text, prime=p, comma=e))
        if resolved.scalars.element_draft:
            de = resolved.dimensions.dimensionality
            for p in range(resolved.dimensions.superspace_dimensionality):
                cells.append(Cell(f"cell:superspace_projection_basis_lift:{de}:{p}", query.prime_left(geometry, de), query.superspace_projection_top(geometry, p),
                                     COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", prime=p, comma=de, pending=True))


def _emit_superspace_projection_commas(cells, resolved, geometry, context) -> None:
    if not (resolved.unchanged.shown and query.row_open(geometry, context.collapsed, "superspace_projection") and query.tile_open(geometry, context.collapsed, "superspace_projection", "commas")):
        return
    for c in range(resolved.dimensions.comma_count):
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(f"cell:superspace_projection_vectors:{p}:{c}", query.comma_left(geometry, resolved, c), query.superspace_projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="0", prime=p, comma=c))
    if resolved.commas.pending is not None:
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(f"cell:superspace_projection_vectors:{p}:draft", query.comma_left(geometry, resolved, resolved.dimensions.comma_count), query.superspace_projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", prime=p, pending=True))
    for j in range(resolved.dimensions.unchanged_count):
        dashed = resolved.projection.superspace_unchanged[j] is None
        for p in range(resolved.dimensions.superspace_dimensionality):
            cells.append(Cell(f"cell:superspace_projection_vectors:{p}:{resolved.dimensions.comma_count + j}", query.comma_left(geometry, resolved, resolved.dimensions.comma_count_shown + j), query.superspace_projection_top(geometry, p),
                                 COLUMN_WIDTH, ROW_HEIGHT, "mapped",
                                 text=DASH if dashed else str(resolved.projection.superspace_unchanged[j][p]), prime=p, comma=resolved.dimensions.comma_count + j))


def emit_identity_objects(resolved, geometry, context) -> EmitResult:
    cells: list = []
    _emit_identity_vector_primes(cells, resolved, geometry, context)
    for column_key, prefix, left in (("generators", "selfmap", lambda k: query.generator_left(geometry, k)),
                               ("detempering", "mapped_detempering", lambda k: query.detempering_left(geometry, k))):
        if query.tile_open(geometry, context.collapsed, "mapping", column_key):
            for i in range(resolved.dimensions.rank):
                for k in range(resolved.dimensions.rank):
                    cells.append(Cell(
                        f"cell:{prefix}:{i}:{k}", left(k), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                        "mapped", text="1" if i == k else "0", generator=i,
                        unit=query.cell_unit(resolved, "mapping", column_key, generator=i)))
            if resolved.scalars.row_draft:
                dr = resolved.dimensions.rank
                for i in range(dr):
                    cells.append(Cell(
                        f"cell:{prefix}:{i}:{dr}", left(dr), query.map_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                        "mapped", text="", generator=i, pending=True))
                for k in range(dr + 1):
                    cells.append(Cell(
                        f"cell:{prefix}:{dr}:{k}", left(k), query.map_top(geometry, dr), COLUMN_WIDTH, ROW_HEIGHT,
                        "mapped", text="", generator=dr, pending=True))
    _emit_identity_canonical_generators(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells))


def _emit_identity_vector_primes(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "vectors", "primes"):
        for i in range(resolved.dimensions.dimensionality):
            for k in range(resolved.dimensions.dimensionality):
                cells.append(Cell(
                    f"cell:vector:primes:{i}:{k}", query.prime_left(geometry, k), query.vector_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text="1" if i == k else "0", generator=i, prime=k,
                    unit=query.cell_unit(resolved, "vectors", "primes", prime=k)))
        if resolved.scalars.element_draft:
            dp = resolved.dimensions.dimensionality
            for i in range(dp):
                cells.append(Cell(f"cell:vector:primes:{i}:{dp}", query.prime_left(geometry, dp), query.vector_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=i, prime=dp, pending=True))
            for k in range(dp + 1):
                cells.append(Cell(f"cell:vector:primes:{dp}:{k}", query.prime_left(geometry, k), query.vector_top(geometry, dp), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=dp, prime=k, pending=True))


def _emit_identity_canonical_generators(cells, resolved, geometry, context) -> None:
    if query.tile_open(geometry, context.collapsed, "canonical", "canonical_generators"):
        for i in range(resolved.dimensions.canonical_rank):
            for k in range(resolved.dimensions.canonical_rank):
                cells.append(Cell(
                    f"cell:fcancel:{i}:{k}", query.canonical_generator_left(geometry, k), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT,
                    "mapped", text="1" if i == k else "0", generator=i,
                    unit=query.cell_unit(resolved, "canonical", "canonical_generators", generator=i)))
        if resolved.scalars.row_draft:
            cr = resolved.dimensions.canonical_rank
            for i in range(cr):
                cells.append(Cell(f"cell:fcancel:{i}:{cr}", query.canonical_generator_left(geometry, cr), query.canonical_top(geometry, i), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=i, pending=True))
            for k in range(cr + 1):
                cells.append(Cell(f"cell:fcancel:{cr}:{k}", query.canonical_generator_left(geometry, k), query.canonical_top(geometry, cr), COLUMN_WIDTH, ROW_HEIGHT, "mapped", text="", generator=cr, pending=True))
