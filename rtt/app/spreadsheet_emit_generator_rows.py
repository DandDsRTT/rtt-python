from __future__ import annotations

from fractions import Fraction

from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import BANDS
from rtt.app.layout import Cell
from rtt.app.spreadsheet_closed_form import (
    _superspace_closed_form,
    closed_form_operand,
    operand_cell,
)
from rtt.app.spreadsheet_constants import (
    BRACKET_WIDTH,
    CHART_HEIGHT,
    COLUMN_WIDTH,
    DASH,
    ROW_HEIGHT,
)
from rtt.app.spreadsheet_emit_model import voice


def tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, group, values, editable_kind=None) -> None:
    if not query.tile_open(geometry, context.collapsed, key, group):
        return
    values = tuple(values)
    if key in BANDS["chart"].rows:
        chart_tiles.append((key, group, values))
    y = geometry.rows[key].y
    is_generator_group = group in ("generators", "superspace_generators")
    is_prime_group = group in ("primes", "superspace_primes")
    for i, v in enumerate(values):
        cell_id = f"{key}:{geometry.group_elem[group]}:{query.column_token(resolved, group, i)}"
        x = geometry.group_left[group][query.comma_value_pos(resolved, i) if group == "commas" else i]
        u = query.cell_unit(resolved, key, group, generator=i if is_generator_group else None, prime=i if is_prime_group else None)
        operand = closed_form_operand(resolved, geometry, context, key, group, i, v) if resolved.flags.math_expressions else None
        kind, text = operand_cell(resolved, operand, v, editable_kind or "tuning_value")
        cells.append(Cell(cell_id, x, y, COLUMN_WIDTH, ROW_HEIGHT, kind, text=text, unit=u))
        if key in ("tuning", "just"):
            voice(cells, f"{key}:{group}", i, v)
    pending_index = query.pending_draft_index(resolved, group)
    if pending_index is not None and pending_index[0] is not None:
        cells.append(Cell(f"{key}:{geometry.group_elem[group]}:draft", geometry.group_left[group][pending_index[1]],
                             y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text="", pending=True))


def chart(cells, geometry, context, row_key, column_key, values, indicator=None, indicator_label="") -> None:
    values = tuple(values)
    if values and row_key in geometry.rows and geometry.rows[row_key].chart_top is not None and query.tile_open(geometry, context.collapsed, row_key, column_key):
        x = geometry.group_left[column_key][0] - BRACKET_WIDTH
        gap = query.interval_col_gap(column_key)
        width = 2 * BRACKET_WIDTH + len(values) * COLUMN_WIDTH + max(len(values) - 1, 0) * gap
        cells.append(Cell(f"chart:{row_key}:{column_key}", x, geometry.rows[row_key].chart_top,
                             width, CHART_HEIGHT, "chart", values=values, column_gap=gap,
                             indicator=indicator, indicator_label=indicator_label))


def dashed_generator_column(cells, resolved, geometry, key, group, count) -> None:
    y = geometry.rows[key].y
    for g in range(count):
        cells.append(Cell(f"{key}:{geometry.group_elem[group]}:{g}", geometry.group_left[group][g], y,
                             COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text=DASH,
                             unit=query.cell_unit(resolved, key, group, generator=g)))


def _superspace_generator_map(resolved, prime_map):
    gl = resolved.projection.superspace_embedding_matrix
    dL, rL = resolved.dimensions.superspace_dimensionality, resolved.dimensions.superspace_rank
    return tuple(sum(prime_map[p] * float(Fraction(gl[p][g])) for p in range(dL)) for g in range(rL))


def emit_superspace_generator_sizes(cells, chart_tiles, resolved, geometry, context, superspace_tuning_map) -> None:
    full = resolved.projection.superspace_embedding_matrix is not None
    for key, prime_map in (("just", superspace_tuning_map.just_map), ("retune", superspace_tuning_map.retuning_map)):
        if not (query.row_open(geometry, context.collapsed, key) and query.tile_open(geometry, context.collapsed, key, "superspace_generators")):
            continue
        if full:
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "superspace_generators", _superspace_generator_map(resolved, prime_map))
        else:
            dashed_generator_column(cells, resolved, geometry, key, "superspace_generators", resolved.dimensions.superspace_rank)


def emit_superspace_generator_row(cells, chart_tiles, resolved, geometry, context, superspace_tuning_map) -> None:
    if not resolved.flags.superspace_generators:
        tuning_value_row(cells, chart_tiles, resolved, geometry, context, "tuning", "superspace_generators", superspace_tuning_map.generator_map)
        return
    superspace_closed_form = _superspace_closed_form(resolved, context) if resolved.flags.math_expressions else None
    for i, v in enumerate(superspace_tuning_map.generator_map):
        operand = superspace_closed_form.generator_operand(i, v) if superspace_closed_form is not None else None
        kind, text = operand_cell(resolved, operand, v, "generator_tuning_cell")
        cells.append(Cell(f"tuning:superspace_generator:{i}", geometry.group_left["superspace_generators"][i], geometry.rows["tuning"].y,
                             COLUMN_WIDTH, ROW_HEIGHT, kind, text=text,
                             unit=query.cell_unit(resolved, "tuning", "superspace_generators", generator=i)))
        voice(cells, "tuning:superspace_generators", i, v)


def emit_detempering_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    if not resolved.flags.generator_detempering:
        return
    for key, values in (("just", resolved.detempering.sizes.just),
                        ("retune", resolved.detempering.sizes.errors)):
        if query.row_open(geometry, context.collapsed, key):
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "generators", values)


def _canonical_detempering_columns(resolved):
    det = resolved.canonical.detempering
    if not resolved.flags.generator_detempering or not det:
        return None
    d = resolved.dimensions.dimensionality
    rank = resolved.dimensions.canonical_rank
    return [[int(det[p][g]) for p in range(d)] for g in range(rank)]


def emit_canonical_detempering_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    cols = _canonical_detempering_columns(resolved)
    if cols is None:
        return
    tm = resolved.tuning.tuning_map
    d = resolved.dimensions.dimensionality
    for key, prime_map in (("just", tm.just_map), ("retune", tm.retuning_map)):
        if query.row_open(geometry, context.collapsed, key):
            values = tuple(sum(prime_map[p] * col[p] for p in range(d)) for col in cols)
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "canonical_generators", values)


def emit_embedding_rows(cells, chart_tiles, resolved, geometry, context) -> None:
    sizes = resolved.projection.embedding_sizes
    if not resolved.flags.projection:
        return
    for key, field in (("tuning", "tempered"), ("just", "just"), ("retune", "errors")):
        if not (query.row_open(geometry, context.collapsed, key)
                and query.tile_open(geometry, context.collapsed, key, "generator_embedding")):
            continue
        if sizes is None:
            dashed_generator_column(cells, resolved, geometry, key, "generator_embedding", resolved.dimensions.rank)
        else:
            tuning_value_row(cells, chart_tiles, resolved, geometry, context, key, "generator_embedding", getattr(sizes, field))
