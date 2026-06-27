from __future__ import annotations

from rtt.app import service
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.layout import CellBox
from rtt.app.spreadsheet_constants import COL_W, DASH, ROW_H
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _prescale_math_expr


def emit_prescaling_band(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    nrows = geometry.prescale_rows
    prescaler_diag, prescaler_is_matrix, ss_elements, prescale_vectors, groups, bare_group = _prescale_setup(resolved, ctx, nrows)
    prime_term = _prescale_prime_terms(resolved, ss_elements)
    for group in groups:
        if not query.tile_open(geometry, ctx.collapsed, "prescaling", group):
            continue
        _emit_prescale_group(cells, resolved, geometry, group, prescale_vectors[group], prescaler_diag,
                             prescaler_is_matrix, prime_term, bare_group, nrows)
        _emit_prescale_draft(cells, resolved, geometry, group, prescaler_diag, prescaler_is_matrix, nrows)
    return EmitResult(cells=tuple(cells))


def _lift_to_superspace(resolved, vs):
    _r = resolved
    return tuple(None if v is None else service.lift_vectors_to_superspace(_r.dims.elements, (v,))[0]
                 for v in vs)


def _prescale_setup(resolved, ctx, nrows):
    _r = resolved
    if _r.flags.superspace:
        prescaler_diag = service.superspace_complexity_prescaler(ctx.state, ctx.tuning_scheme)
        prescaler_is_matrix = False
        ss_elements = service.superspace_primes(_r.dims.elements)

        def lift(vs):
            return _lift_to_superspace(resolved, vs)
        prescale_vectors = {
            "ssprimes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
            "primes": service.basis_in_superspace(_r.dims.elements),
            "commas": lift(ctx.state.comma_basis) + (lift(_r.unchanged.basis) if _r.unchanged.shown else ()),
            "targets": lift(_r.targets.vectors),
            "interest": lift(_r.interest.vectors),
            "held": lift(_r.held.vectors),
            "detempering": lift(_r.detempering.vectors),
        }
        groups = ("ssprimes", "primes", "commas", "targets", "interest", "held", "detempering")
        bare_group = "ssprimes"
    else:
        prescaler_diag = _r.scalars.prescaler
        prescaler_is_matrix = _r.scalars.prescaler_is_matrix
        ss_elements = _r.dims.elements
        prescale_vectors = {
            "primes": tuple(tuple(1 if i == p else 0 for i in range(nrows)) for p in range(nrows)),
            "commas": ctx.state.comma_basis + (_r.unchanged.basis if _r.unchanged.shown else ()),
            "targets": _r.targets.vectors,
            "interest": _r.interest.vectors,
            "held": _r.held.vectors,
            "detempering": _r.detempering.vectors,
        }
        groups = ("primes", "commas", "targets", "interest", "held", "detempering")
        bare_group = "primes"
    return prescaler_diag, prescaler_is_matrix, ss_elements, prescale_vectors, groups, bare_group


def _prescale_prime_terms(resolved, ss_elements):
    _r = resolved
    if _r.labels.scheme_prescaler == "log-prime":
        return {i: f"log₂{p}" for i, p in enumerate(ss_elements)}
    if _r.labels.scheme_prescaler == "prime":
        return {i: str(p) for i, p in enumerate(ss_elements)}
    return {}


def _emit_prescale_group(cells, resolved, geometry, group, vectors, prescaler_diag, prescaler_is_matrix, prime_term, bare_group, nrows) -> None:
    left = geometry.group_left[group]
    for c, vec in enumerate(vectors):
        u = query.cell_unit(resolved, "prescaling", group, prime=c if group == bare_group else None)
        if vec is None:
            for i in range(nrows + geometry.size_rows):
                cid = f"cell:prescaling:{group}:{i}:{query.col_token(resolved, group, c)}"
                cx, cy = left[query.comma_value_pos(resolved, c) if group == "commas" else c], query.prescale_row_y(geometry, i)
                cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue", text=DASH, unit=u))
            continue
        prescaled = _prescale_vector(vec, prescaler_diag, prescaler_is_matrix, nrows)
        _emit_prescale_cells(cells, resolved, geometry, group, c, vec, prescaled, prime_term, left, u, nrows)


def _prescale_vector(vec, prescaler_diag, prescaler_is_matrix, nrows):
    return ([sum(prescaler_diag[i][k] * vec[k] for k in range(nrows)) for i in range(nrows)]
            if prescaler_is_matrix
            else [prescaler_diag[i] * vec[i] for i in range(nrows)])


def _emit_prescale_cells(cells, resolved, geometry, group, c, vec, prescaled, prime_term, left, u, nrows) -> None:
    _r = resolved
    for i in range(nrows + geometry.size_rows):
        value = prescaled[i] if i < nrows else geometry.size_factor * sum(prescaled)
        cid = f"cell:prescaling:{group}:{i}:{query.col_token(_r, group, c)}"
        cx, cy = left[query.comma_value_pos(_r, c) if group == "commas" else c], query.prescale_row_y(geometry, i)
        if i < nrows and not _r.flags.superspace and group == "primes" and (i == c or _r.flags.alt_complexity):
            cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "prescalercell",
                                 text=service.prescale_text(value, _r.flags.decimals), prime=i, unit=u))
        elif i < nrows and _r.flags.math and vec[i] != 0 and i in prime_term:
            cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "mathexpr",
                                 text=_prescale_math_expr(vec[i], prime_term[i], value, _r.flags.quantities, _r.flags.decimals), unit=u))
        else:
            cells.append(CellBox(cid, cx, cy, COL_W, ROW_H, "tuningvalue",
                                 text=service.prescale_text(value, _r.flags.decimals), unit=u))


def _emit_prescale_draft(cells, resolved, geometry, group, prescaler_diag, prescaler_is_matrix, nrows) -> None:
    _r = resolved
    pending_idx = query.pending_draft_idx(_r, group)
    if pending_idx is None or pending_idx[0] is None:
        return
    left = geometry.group_left[group]
    ghost_pre = None
    if _r.ghosts.comma and group == "commas" and _r.ghosts.comma_vec is not None:
        gvec = _lift_to_superspace(resolved, (_r.ghosts.comma_vec,))[0] if _r.flags.superspace else _r.ghosts.comma_vec
        ghost_pre = _prescale_vector(gvec, prescaler_diag, prescaler_is_matrix, nrows)
    for i in range(nrows + geometry.size_rows):
        cy = query.prescale_row_y(geometry, i)
        text = ""
        if ghost_pre is not None:
            value = ghost_pre[i] if i < nrows else geometry.size_factor * sum(ghost_pre)
            text = service.prescale_text(value, _r.flags.decimals)
        cells.append(CellBox(f"cell:prescaling:{group}:{i}:draft", left[pending_idx[1]],
                             cy, COL_W, ROW_H, "tuningvalue", text=text, pending=True))
