from __future__ import annotations

from rtt.app.service.core import DEFAULT_TARGET_SPEC, DEFAULT_TUNING_SCHEME
from rtt.app.service.state import TemperamentState
from rtt.app.service.text_context import DerivedQuantities, _build_context, _Inputs
from rtt.app.service.text_emit import (
    _base_prescale_complexity,
    _base_sizes,
    _base_structural,
    _held_values,
    _interest_values,
    _projection_values,
    _superspace_values,
)


def plain_text_values(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
    target_spec: str = DEFAULT_TARGET_SPEC,
    held=(),
    interest=(),
    generator_tuning=None,
    target_override=None,
    nonprime_approach: str = "",
    superspace: bool = False,
    superspace_generator_override=None,
    consolidate_v: bool = False,
    held_basis_ratios=(),
    custom_prescaler=None,
    derived: DerivedQuantities | None = None,
    decimals: bool = True,
) -> dict[tuple[str, str], str]:
    inp = _Inputs(
        state,
        scheme,
        target_spec,
        held,
        interest,
        generator_tuning,
        target_override,
        nonprime_approach,
        superspace,
        superspace_generator_override,
        consolidate_v,
        held_basis_ratios,
        custom_prescaler,
        derived,
        decimals,
    )
    context = _build_context(inp)
    values = _base_structural(context)
    values.update(_base_sizes(context))
    values.update(_base_prescale_complexity(context))
    if context.held:
        values.update(_held_values(context))
    if context.interest:
        values.update(_interest_values(context))
    if context.consolidate_v:
        values.update(_projection_values(context))
    if context.superspace:
        values.update(_superspace_values(context))
    return values
