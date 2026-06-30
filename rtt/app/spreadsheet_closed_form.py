from __future__ import annotations

from fractions import Fraction

from rtt.app import service
from rtt.app.spreadsheet_text import _log_operand


def closed_form_operand(resolved, geometry, context, key, group, i, value=None):
    if key == "just":
        ratio = geometry.group_ratio[group][i]
        return _log_operand(ratio) if ratio is not None else None
    if group == "commas" and key == "retune" and i < resolved.dimensions.comma_count:
        reciprocal = 1 / Fraction(resolved.commas.ratios[i])
        return _log_operand(f"{reciprocal.numerator}/{reciprocal.denominator}")
    if key in ("tuning", "retune") and value is not None:
        if group in ("superspace_primes", "superspace_generators"):
            return _superspace_closed_form_operand(resolved, context, key, group, i, value)
        closed_form = _closed_form(resolved, context)
        vector = _tempered_vector(resolved, context, group, i) if closed_form is not None else None
        if vector is not None:
            return (
                closed_form.tempered_operand(vector, value)
                if key == "tuning"
                else closed_form.retune_operand(vector, value)
            )
    return None


def _superspace_closed_form_operand(resolved, context, key, group, i, value):
    superspace = _superspace_closed_form(resolved, context)
    if superspace is None:
        return None
    if group == "superspace_generators":
        return superspace.generator_operand(i, value) if key == "tuning" else None
    vector = tuple(1 if k == i else 0 for k in range(len(superspace.primes)))
    return (
        superspace.tempered_operand(vector, value)
        if key == "tuning"
        else superspace.retune_operand(vector, value)
    )


def _closed_form(resolved, context):
    if not resolved.flags.math_expressions or resolved.tuning.from_generators:
        return None
    return service.closed_form_tuning(
        context.state.mapping,
        context.tuning_scheme,
        resolved.dimensions.elements,
        context.nonprime_approach,
        held=resolved.held.ratios,
        prescaler_override=context.custom_prescaler,
        targets=resolved.tuning.optimum_target_override,
        weights_override=context.custom_weights,
    )


def _superspace_closed_form(resolved, context):
    if not (resolved.flags.math_expressions and resolved.flags.superspace):
        return None
    return service.closed_form_superspace_tuning(context.state, context.tuning_scheme)


def _tempered_vector(resolved, context, group, i):
    if group == "primes":
        return tuple(1 if k == i else 0 for k in range(resolved.dimensions.dimensionality))
    if group == "commas":
        return _comma_tempered_vector(resolved, context, i)
    seqs = {
        "targets": resolved.targets.vectors,
        "interest": resolved.interest.vectors,
        "held": resolved.held.vectors,
        "detempering": resolved.detempering.vectors,
    }
    seq = seqs.get(group)
    if seq is None:
        return None
    return seq[i] if i < len(seq) else None


def _comma_tempered_vector(resolved, context, i):
    if i < resolved.dimensions.comma_count:
        return context.state.comma_basis[i]
    j = i - resolved.dimensions.comma_count
    return (
        resolved.unchanged.basis[j]
        if resolved.unchanged.basis and j < len(resolved.unchanged.basis)
        else None
    )
