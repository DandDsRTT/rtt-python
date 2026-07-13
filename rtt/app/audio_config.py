from __future__ import annotations

WAVE_COUNT = 4
MODE_COUNT = 4

_BOOLS: tuple[str, ...] = ("hold", "root", "muted")
_RANGES: dict[str, tuple[int, int]] = {"pump_size": (1, 4), "pump_tempo": (30, 150)}

AUDIO_DEFAULTS: dict[str, int] = {
    "wave": 0,
    "mode": 0,
    "hold": 0,
    "root": 0,
    "muted": 0,
    "pump_size": 1,
    "pump_tempo": 75,
}

KEYS: tuple[str, ...] = tuple(AUDIO_DEFAULTS)


def defaults() -> dict[str, int]:
    return dict(AUDIO_DEFAULTS)


def _clamp(value, low: int, high: int, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(low, min(high, number))


def from_persisted(stored) -> dict[str, int]:
    data = stored if isinstance(stored, dict) else {}
    result = {
        "wave": _clamp(data.get("wave"), 0, WAVE_COUNT - 1, 0),
        "mode": _clamp(data.get("mode"), 0, MODE_COUNT - 1, 0),
    }
    for key in _BOOLS:
        result[key] = 1 if data.get(key) else 0
    for key, (low, high) in _RANGES.items():
        result[key] = _clamp(data.get(key), low, high, AUDIO_DEFAULTS[key])
    return result
