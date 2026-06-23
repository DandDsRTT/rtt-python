from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class EntryResolution:
    value: object
    problem: str | None


def _parse(raw) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def custom_prescaler_entry(raw, on_diagonal: bool) -> EntryResolution:
    value = _parse(raw)
    if value is None:
        return EntryResolution(None, "skip")
    if not math.isfinite(value) or (on_diagonal and value <= 0):
        return EntryResolution(None, "invalid")
    return EntryResolution(value, None)


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


def custom_weights(raws) -> EntryResolution:
    weights = []
    for raw in raws:
        value = _parse(raw)
        if value is None:
            return EntryResolution(None, "skip")
        if not math.isfinite(value) or value <= 0:
            return EntryResolution(None, "invalid")
        weights.append(value)
    return EntryResolution(tuple(weights), None)
