from __future__ import annotations

from fractions import Fraction

from rtt.app import service
from rtt.app.spreadsheet_text import _log_operand


def closed_form_operand(resolved, geometry, ctx, key, group, i, value=None):
    _r = resolved
    if key == "just":
        ratio = geometry.group_ratio[group][i]
        return _log_operand(ratio) if ratio is not None else None
    if group == "commas" and key == "retune" and i < _r.dims.nc:
        recip = 1 / Fraction(_r.commas.ratios[i])
        return _log_operand(f"{recip.numerator}/{recip.denominator}")
    if key in ("tuning", "retune") and value is not None:
        if group in ("ssprimes", "ssgens"):
            return _ss_closed_form_operand(resolved, ctx, key, group, i, value)
        closed_form = _closed_form(resolved, ctx)
        vector = _tempered_vector(resolved, ctx, group, i) if closed_form is not None else None
        if vector is not None:
            return (
                closed_form.tempered_operand(vector, value)
                if key == "tuning"
                else closed_form.retune_operand(vector, value)
            )
    return None


def _ss_closed_form_operand(resolved, ctx, key, group, i, value):
    ss = _ss_closed_form(resolved, ctx)
    if ss is None:
        return None
    if group == "ssgens":
        return ss.generator_operand(i, value) if key == "tuning" else None
    vector = tuple(1 if k == i else 0 for k in range(len(ss.primes)))
    return (
        ss.tempered_operand(vector, value) if key == "tuning" else ss.retune_operand(vector, value)
    )


def _closed_form(resolved, ctx):
    _r = resolved
    if not _r.flags.math_expressions or _r.tuning.from_generators:
        return None
    return service.closed_form_tuning(
        ctx.state.mapping,
        ctx.tuning_scheme,
        _r.dims.elements,
        ctx.nonprime_approach,
        held=_r.held.ratios,
        prescaler_override=ctx.custom_prescaler,
        targets=_r.tuning.optimum_target_override,
        weights_override=ctx.custom_weights,
    )


def _ss_closed_form(resolved, ctx):
    _r = resolved
    if not (_r.flags.math_expressions and _r.flags.superspace):
        return None
    return service.closed_form_superspace_tuning(ctx.state, ctx.tuning_scheme)


def _tempered_vector(resolved, ctx, group, i):
    _r = resolved
    if group == "primes":
        return tuple(1 if k == i else 0 for k in range(_r.dims.d))
    if group == "commas":
        return _comma_tempered_vector(resolved, ctx, i)
    seqs = {
        "targets": _r.targets.vectors,
        "interest": _r.interest.vectors,
        "held": _r.held.vectors,
        "detempering": _r.detempering.vectors,
    }
    seq = seqs.get(group)
    if seq is None:
        return None
    return seq[i] if i < len(seq) else None


def _comma_tempered_vector(resolved, ctx, i):
    _r = resolved
    if i < _r.dims.nc:
        return ctx.state.comma_basis[i]
    j = i - _r.dims.nc
    return _r.unchanged.basis[j] if _r.unchanged.basis and j < len(_r.unchanged.basis) else None
