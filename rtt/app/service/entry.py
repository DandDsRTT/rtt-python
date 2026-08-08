from __future__ import annotations

import math

from rtt.app.service import outcome
from rtt.app.service.core_intervals import interval_vector
from rtt.app.service.core_vectors import detempers_the_generator
from rtt.app.service.outcome import Outcome, Reason

_ITALIC_G = "\U0001d454"
_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _generator_symbol(index: int) -> str:
    return _ITALIC_G + str(index + 1).translate(_SUBSCRIPTS)


def resolve_ratio_edit(raw, d: int, domain_basis=None) -> Outcome:
    if raw in ("", "?/?"):
        return outcome.RERENDER
    try:
        vector = interval_vector(raw, d, domain_basis)
    except ValueError as exc:
        return outcome.reject(str(exc))
    return outcome.accept(vector)


def resolve_detempering_edit(state, index: int, raw) -> Outcome:
    resolved = resolve_ratio_edit(raw, state.dimensionality, state.domain_basis)
    if resolved.effect is not outcome.Effect.ACCEPT:
        return resolved
    if not detempers_the_generator(state.mapping, index, resolved.value):
        return outcome.reject(f"“{raw}” doesn’t map to exactly one of {_generator_symbol(index)}")
    return resolved


def _parse(raw) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def custom_prescaler_entry(raw, on_diagonal: bool) -> Outcome:
    value = _parse(raw)
    if value is None:
        return outcome.IGNORE
    if not math.isfinite(value) or (on_diagonal and value <= 0):
        return outcome.reject(reason=Reason.INVALID_PRESCALER)
    return outcome.accept(value)


def parse_power(raw, minimum: float = 0.0) -> float | None:
    text = str(raw).strip().lower()
    if text in ("∞", "inf", "max", "minimax"):
        return float("inf")
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value) or value <= 0 or value < minimum:
        return None
    return value


def custom_weights(raws) -> Outcome:
    weights = []
    for raw in raws:
        value = _parse(raw)
        if value is None:
            return outcome.IGNORE
        if not math.isfinite(value) or value <= 0:
            return outcome.reject(reason=Reason.INVALID_WEIGHT)
        weights.append(value)
    return outcome.accept(tuple(weights))
