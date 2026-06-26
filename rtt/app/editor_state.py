from __future__ import annotations

import functools
import math
from dataclasses import dataclass

from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app.service.state import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))
INITIAL_COLLAPSED: frozenset[str] = frozenset()


def _same_cents_map(a, b) -> bool:
    return len(a) == len(b) and all(
        service.cents(x) == service.cents(y) for x, y in zip(a, b, strict=False)
    )


def blank_draft(state: TemperamentState) -> list[None]:
    return [None] * state.d


def comma_ratios_in_domain(state: TemperamentState, vectors):
    return service.comma_ratios(vectors, state.domain_basis)


@dataclass(frozen=True)
class _Doc:
    state: TemperamentState
    tuning_scheme: object
    target_family: str
    target_limit: int | None
    interest_vectors: tuple[tuple[int, ...], ...]
    held_vectors: tuple[tuple[int, ...], ...]
    range_mode: str
    generator_tuning: tuple[float, ...] | None
    manual_tuning: bool
    custom_prescaler: tuple | None
    custom_weights: tuple[float, ...] | None
    target_override: tuple[str, ...] | None
    projection_basis: tuple[str, ...]
    settings: tuple[tuple[str, bool], ...]
    collapsed: frozenset[str]
    preferred_form: tuple[tuple[str, str], ...]


def prescaler_is_solvable(p) -> bool:
    if not p:
        return False
    is_matrix = isinstance(p[0], (tuple, list))
    if is_matrix:
        for i, row in enumerate(p):
            for j, x in enumerate(row):
                if not math.isfinite(x) or (i == j and x <= 0):
                    return False
        return True
    return all(math.isfinite(x) and x > 0 for x in p)


def weights_are_solvable(w) -> bool:
    return bool(w) and all(math.isfinite(x) and x > 0 for x in w)


@functools.lru_cache(maxsize=1)
def initial_doc() -> _Doc:
    state = service.from_mapping(INITIAL_MAPPING)
    return _Doc(
        state=state,
        tuning_scheme=service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME),
        target_family=service.DEFAULT_TARGET_SPEC,
        target_limit=None,
        interest_vectors=(),
        held_vectors=(),
        range_mode="monotone",
        generator_tuning=None,
        manual_tuning=False,
        custom_prescaler=None,
        custom_weights=None,
        target_override=None,
        projection_basis=(),
        settings=tuple(sorted(show_settings.defaults().items())),
        collapsed=INITIAL_COLLAPSED,
        preferred_form=(),
    )
