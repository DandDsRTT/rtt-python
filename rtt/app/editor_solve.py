from __future__ import annotations

from dataclasses import dataclass

from rtt.app.service.state import TemperamentState


@dataclass(frozen=True)
class Solve:
    state: TemperamentState
    tuning_scheme: object
    nonprime_basis_approach: str
    custom_prescaler: tuple | None
    custom_weights: tuple[float, ...] | None
    held_vectors: tuple[tuple[int, ...], ...]
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
        target_override=doc.target_override,
        generator_tuning=doc.generator_tuning,
        manual_tuning=doc.manual_tuning,
        projection_basis=doc.projection_basis,
        superspace_generator_tuning=doc.pending.superspace_generator_tuning,
        target_spec=doc.target_spec,
        settings=dict(doc.settings),
    )
