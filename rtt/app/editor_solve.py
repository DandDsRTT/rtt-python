from __future__ import annotations

import logging
from dataclasses import dataclass

from rtt.app import presets, service, terminology
from rtt.app.editor_state import _same_cents_map
from rtt.app.service.state import TemperamentState

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Solve:
    state: TemperamentState
    tuning_scheme: object
    nonprime_basis_approach: str
    custom_prescaler: tuple | None
    custom_weights: tuple[float, ...] | None
    held_vectors: tuple[tuple[int, ...], ...]
    interest_vectors: tuple[tuple[int, ...], ...]
    target_override: tuple[str, ...] | None
    generator_tuning: tuple[float, ...] | None
    manual_tuning: bool
    projection_basis: tuple[str, ...]
    superspace_generator_tuning: tuple[float, ...] | None
    target_spec: str
    settings: dict[str, bool]


def solve_model(doc) -> Solve:
    return Solve(
        state=doc.state,
        tuning_scheme=doc.tuning_scheme,
        nonprime_basis_approach=doc.nonprime_basis_approach,
        custom_prescaler=doc.custom_prescaler,
        custom_weights=doc.custom_weights,
        held_vectors=tuple(doc.held_vectors),
        interest_vectors=tuple(doc.interest_vectors),
        target_override=doc.target_override,
        generator_tuning=doc.generator_tuning,
        manual_tuning=doc.manual_tuning,
        projection_basis=doc.projection_basis,
        superspace_generator_tuning=doc.pending.superspace_generator_tuning,
        target_spec=doc.target_spec,
        settings=dict(doc.settings),
    )


def optimum_tuning(s: Solve) -> service.Tuning:
    held = service.comma_ratios(s.held_vectors, s.state.domain_basis) if s.held_vectors else ()
    return service.tuning(
        s.state.mapping,
        s.tuning_scheme,
        s.state.domain_basis,
        s.nonprime_basis_approach,
        held=held,
        prescaler_override=s.custom_prescaler,
        targets=s.target_override,
        weights_override=s.custom_weights,
    )


def optimum_generator_tuning(s: Solve) -> tuple[float, ...]:
    return optimum_tuning(s).generator_map


def optimum_superspace_generator_tuning(s: Solve) -> tuple[float, ...]:
    return service.superspace_tuning(s.state, s.tuning_scheme, "prime-based").generator_map


def effective_generator_tuning(s: Solve) -> tuple[float, ...] | None:
    superspace = s.superspace_generator_tuning
    if (
        superspace is not None
        and s.nonprime_basis_approach == "prime-based"
        and service.domain_has_nonprimes(s.state.domain_basis)
    ):
        return service.project_superspace_generators_to_domain(s.state, superspace)
    return s.generator_tuning


def displayed_tuning_scheme_name(s: Solve) -> str | None:
    bare = service.tuning(
        s.state.mapping,
        s.tuning_scheme,
        s.state.domain_basis,
        s.nonprime_basis_approach,
        prescaler_override=s.custom_prescaler,
        targets=s.target_override,
        weights_override=s.custom_weights,
    ).generator_map
    held_optimum = optimum_generator_tuning(s) if s.held_vectors else bare
    override = effective_generator_tuning(s)
    displayed = (
        override if override is not None and len(override) == len(s.state.mapping) else held_optimum
    )
    if not _same_cents_map(displayed, held_optimum):
        if s.manual_tuning:
            return None
    elif not _same_cents_map(held_optimum, bare):
        return None
    return terminology.scheme_name(
        service.base_scheme_name(s.tuning_scheme), s.settings.get("dd_terminology", True)
    )


def tuning_is_optimized(s: Solve) -> bool:
    override = effective_generator_tuning(s)
    if override is None or len(override) != len(s.state.mapping):
        return True
    return _same_cents_map(override, optimum_generator_tuning(s))


def displayed_prescaler_name(s: Solve) -> str | None:
    return service.displayed_prescaler_name(s.state.mapping, s.tuning_scheme, s.custom_prescaler)


def displayed_retuning_map(s: Solve) -> tuple[float, ...] | None:
    try:
        generators = effective_generator_tuning(s)
        if generators is not None and len(generators) == s.state.r:
            optimum = optimum_tuning(s)
            if not _same_cents_map(generators, optimum.generator_map):
                return service.tuning_from_generators(
                    s.state.mapping, generators, s.state.domain_basis
                ).retuning_map
            return optimum.retuning_map
        return optimum_tuning(s).retuning_map
    except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
        _log.debug("displayed_retuning_map dashed: %r", exc)
        return None


def unchanged_ratios(s: Solve) -> tuple[str, ...]:
    retuning = displayed_retuning_map(s)
    if retuning is None:
        return ()
    held = (
        tuple(service.comma_ratios(s.held_vectors, s.state.domain_basis)) if s.held_vectors else ()
    )
    candidates = (
        held
        + s.projection_basis
        + presets.projection_candidate_ratios(s.state)
        + tuple(service.target_interval_set(s.target_spec, s.state.domain_basis))
    )
    return service.unchanged_ratios_of_tuning(s.state, retuning, candidates)


def targets_in_use(s: Solve) -> bool:
    if not s.settings.get("projection"):
        return True
    if not s.manual_tuning:
        return True
    if len(unchanged_ratios(s)) < s.state.r:
        return True
    displayed = effective_generator_tuning(s)
    if displayed is None:
        return True
    try:
        optimum = optimum_generator_tuning(s)
    except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
        _log.debug("optimum solve failed; treating displayed tuning as optimal: %r", exc)
        return True
    return len(displayed) == len(optimum) and all(
        abs(a - b) < 1e-6 for a, b in zip(displayed, optimum, strict=False)
    )


def displayed_projection_scheme_name(s: Solve) -> str | None:
    return presets.identify_established_projection(s.state, unchanged_ratios(s))
