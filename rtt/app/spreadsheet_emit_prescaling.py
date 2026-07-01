from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import COLUMN_WIDTH, DASH, ROW_HEIGHT
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _prescale_math_expr


def emit_prescaling_band(resolved, geometry, context) -> EmitResult:
    cells: list = []
    nrows = geometry.prescale_rows
    prescaler_diag, prescaler_is_matrix, superspace_elements, prescale_vectors, groups, bare_group = _prescale_setup(resolved, context, nrows)
    prime_term = _prescale_prime_terms(resolved, superspace_elements)
    for group in groups:
        if not query.tile_open(geometry, context.collapsed, "prescaling", group):
            continue
        _emit_prescale_group(cells, resolved, geometry, group, prescale_vectors[group], prescaler_diag,
                             prescaler_is_matrix, prime_term, bare_group, nrows)
        _emit_prescale_draft(cells, resolved, geometry, group, prescaler_diag, prescaler_is_matrix, nrows)
    return EmitResult(cells=tuple(cells))


def _lift_to_superspace(resolved, vs):
    return tuple(None if v is None else service.lift_vectors_to_superspace(resolved.dimensions.elements, (v,))[0]
                 for v in vs)


def _prescale_setup(resolved, context, nrows):
    if resolved.flags.superspace:
        prescaler_diag = service.superspace_complexity_prescaler(context.state, context.tuning_scheme)
        prescaler_is_matrix = False
        superspace_elements = service.superspace_primes(resolved.dimensions.elements)

        def lift(vs):
            return _lift_to_superspace(resolved, vs)
        prescale_vectors = {
            "superspace_primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
            "primes": service.basis_in_superspace(resolved.dimensions.elements),
            "commas": lift(context.state.comma_basis) + (lift(resolved.unchanged.basis) if resolved.unchanged.shown else ()),
            "targets": lift(resolved.targets.vectors),
            "interest": lift(resolved.interest.vectors),
            "held": lift(resolved.held.vectors),
            "detempering": lift(resolved.detempering.vectors),
        }
        groups = ("superspace_primes", "primes", "commas", "targets", "interest", "held", "detempering")
        bare_group = "superspace_primes"
    else:
        prescaler_diag = resolved.scalars.prescaler
        prescaler_is_matrix = resolved.scalars.prescaler_is_matrix
        superspace_elements = resolved.dimensions.elements
        prescale_vectors = {
            "primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
            "commas": context.state.comma_basis + (resolved.unchanged.basis if resolved.unchanged.shown else ()),
            "targets": resolved.targets.vectors,
            "interest": resolved.interest.vectors,
            "held": resolved.held.vectors,
            "detempering": resolved.detempering.vectors,
        }
        groups = ("primes", "commas", "targets", "interest", "held", "detempering")
        bare_group = "primes"
    return prescaler_diag, prescaler_is_matrix, superspace_elements, prescale_vectors, groups, bare_group


def _prescale_prime_terms(resolved, superspace_elements):
    if resolved.labels.scheme_prescaler == "log-prime":
        return {i: f"log₂{p}" for i, p in enumerate(superspace_elements)}
    if resolved.labels.scheme_prescaler == "prime":
        return {i: str(p) for i, p in enumerate(superspace_elements)}
    return {}


def _emit_prescale_group(cells, resolved, geometry, group, vectors, prescaler_diag, prescaler_is_matrix, prime_term, bare_group, nrows) -> None:
    left = geometry.group_left[group]
    for c, vector in enumerate(vectors):
        u = query.cell_unit(resolved, "prescaling", group, prime=c if group == bare_group else None)
        if vector is None:
            for i in range(nrows + geometry.size_rows):
                cell_id = f"cell:prescaling:{group}:{i}:{query.column_token(resolved, group, c)}"
                cell_x, cell_y = left[query.comma_value_pos(resolved, c) if group == "commas" else c], query.subrow_top(geometry, "prescaling", i)
                cells.append(CellBox(cell_id, cell_x, cell_y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text=DASH, unit=u))
            continue
        prescaled = _prescale_vector(vector, prescaler_diag, prescaler_is_matrix, nrows)
        _emit_prescale_cells(cells, resolved, geometry, group, c, vector, prescaled, prime_term, left, u, nrows)


def _prescale_vector(vector, prescaler_diag, prescaler_is_matrix, nrows):
    return ([sum(prescaler_diag[i][k] * vector[k] for k in range(nrows)) for i in range(nrows)]
            if prescaler_is_matrix
            else [prescaler_diag[i] * vector[i] for i in range(nrows)])


def _emit_prescale_cells(cells, resolved, geometry, group, c, vector, prescaled, prime_term, left, u, nrows) -> None:
    for i in range(nrows + geometry.size_rows):
        value = prescaled[i] if i < nrows else geometry.size_factor * sum(prescaled)
        cell_id = f"cell:prescaling:{group}:{i}:{query.column_token(resolved, group, c)}"
        cell_x, cell_y = left[query.comma_value_pos(resolved, c) if group == "commas" else c], query.subrow_top(geometry, "prescaling", i)
        if i < nrows and not resolved.flags.superspace and group == "primes" and (i == c or resolved.flags.alt_complexity):
            cells.append(CellBox(cell_id, cell_x, cell_y, COLUMN_WIDTH, ROW_HEIGHT, "prescaler_cell",
                                 text=service.prescale_text(value, resolved.flags.decimals), prime=i, unit=u))
        elif i < nrows and resolved.flags.math_expressions and vector[i] != 0 and i in prime_term:
            cells.append(CellBox(cell_id, cell_x, cell_y, COLUMN_WIDTH, ROW_HEIGHT, "math_expression",
                                 text=_prescale_math_expr(vector[i], prime_term[i], value, resolved.flags.quantities, resolved.flags.decimals), unit=u))
        else:
            cells.append(CellBox(cell_id, cell_x, cell_y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value",
                                 text=service.prescale_text(value, resolved.flags.decimals), unit=u))


def _emit_prescale_draft(cells, resolved, geometry, group, prescaler_diag, prescaler_is_matrix, nrows) -> None:
    pending_index = query.pending_draft_index(resolved, group)
    if pending_index is None or pending_index[0] is None:
        return
    left = geometry.group_left[group]
    ghost_pre = None
    if resolved.ghosts.comma and group == "commas" and resolved.ghosts.comma_vector is not None:
        ghost_vector = _lift_to_superspace(resolved, (resolved.ghosts.comma_vector,))[0] if resolved.flags.superspace else resolved.ghosts.comma_vector
        ghost_pre = _prescale_vector(ghost_vector, prescaler_diag, prescaler_is_matrix, nrows)
    for i in range(nrows + geometry.size_rows):
        cell_y = query.subrow_top(geometry, "prescaling", i)
        text = ""
        if ghost_pre is not None:
            value = ghost_pre[i] if i < nrows else geometry.size_factor * sum(ghost_pre)
            text = service.prescale_text(value, resolved.flags.decimals)
        cells.append(CellBox(f"cell:prescaling:{group}:{i}:draft", left[pending_index[1]],
                             cell_y, COLUMN_WIDTH, ROW_HEIGHT, "tuning_value", text=text, pending=True))
