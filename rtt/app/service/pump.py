from __future__ import annotations

import json
import math

from rtt.app.service.notation import pump_score

_STD_CENTS = (
    1200.0,
    1901.9550008653874,
    2786.3137138648344,
    3368.825906469125,
    4151.317942364757,
    4440.527661769311,
)

_P1 = (0,)
_P4 = (2, -1)
_P5 = (-1, 1)
_M3 = (-2, 0, 1)
_m3 = (1, 1, -1)
_P8 = (1,)
_M7 = (-3, 1, 1)
_H7 = (-2, 0, 0, 1)
_NEUTRAL3 = ((0, -2, 0, 0, 1), (-1, 3, 0, 0, -1), (4, 0, 0, 0, 0, -1))
_DIM5 = ((0, 0, -1, 1), (6, -2, -1), (-5, 2, 1))
_AUG5 = ((-4, 0, 2), (1, -2, 0, 1))
_MIN7 = ((-2, 0, 0, 1), (0, 2, -1), (4, -2))

_FIFTH_UP = (-1, 1, 0)
_FIFTH_DOWN = (1, -1, 0)
_RELATIVE_DOWN = (-1, -1, 1)
_RELATIVE_UP = (1, 1, -1)


def _pad(monzo, length) -> tuple[int, ...]:
    return tuple(monzo[i] if i < len(monzo) else 0 for i in range(length))


def _dot(monzo, cents_map) -> float:
    return sum(x * float(c) for x, c in zip(monzo, cents_map, strict=True))


def _add(a, b) -> tuple[int, ...]:
    n = max(len(a), len(b))
    return tuple((a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n))


def _reduce(cents, equave) -> float:
    return cents - equave * math.floor(cents / equave)


def _balance(cents, equave) -> float:
    return cents - equave * round(cents / equave)


def _is_standard_domain(just_map) -> bool:
    return all(
        abs(float(just_map[i]) - _STD_CENTS[i]) < 0.5
        for i in range(min(len(just_map), len(_STD_CENTS)))
    )


def _fits_domain(monzo, dimensionality) -> bool:
    return all(x == 0 for x in monzo[dimensionality:])


def _just_cents(monzo) -> float:
    return sum(monzo[i] * _STD_CENTS[i] for i in range(len(monzo)))


def _tempered_cents(monzo, tempered_map, is_standard) -> float:
    dimensionality = len(tempered_map)
    if is_standard and _fits_domain(monzo, dimensionality):
        return sum(
            monzo[i] * float(tempered_map[i]) for i in range(min(len(monzo), dimensionality))
        )
    return _just_cents(monzo)


def _resolve_interval(candidates, dimensionality, is_standard) -> tuple[int, ...]:
    if is_standard:
        for monzo in candidates:
            if _fits_domain(monzo, dimensionality):
                return monzo
    return candidates[0]


def _open_chords(prime_3, dimensionality):
    fifths = -prime_3
    move = _pad(_FIFTH_UP, dimensionality) if fifths > 0 else _pad(_FIFTH_DOWN, dimensionality)
    roots = [tuple(0 for _ in range(dimensionality))]
    for _ in range(abs(fifths)):
        roots.append(_add(roots[-1], move))
    return roots, ["open"] * len(roots)


def _triad_chords(prime_3, prime_5, dimensionality):
    fifth_up = _pad(_FIFTH_UP, dimensionality)
    fifth_down = _pad(_FIFTH_DOWN, dimensionality)
    relative_down = _pad(_RELATIVE_DOWN, dimensionality)
    relative_up = _pad(_RELATIVE_UP, dimensionality)
    thirds_target, fifths_target = -prime_3, -prime_5
    moves: list[tuple[tuple[int, ...], str]] = []
    quality = "major"
    for _ in range(abs(fifths_target)):
        if fifths_target > 0:
            if quality != "major":
                moves.append((fifth_up, "major"))
            moves.append((relative_down, "minor"))
            quality = "minor"
        else:
            if quality != "minor":
                moves.append((fifth_up, "minor"))
            moves.append((relative_up, "major"))
            quality = "major"
    residual = thirds_target - sum(monzo[1] for monzo, _ in moves)
    fifth = fifth_up if residual > 0 else fifth_down
    for _ in range(abs(residual)):
        moves.append((fifth, quality))
    roots = [tuple(0 for _ in range(dimensionality))]
    qualities = ["major"]
    for monzo, move_quality in moves:
        roots.append(_add(roots[-1], monzo))
        qualities.append(move_quality)
    last = len(roots) - 1
    qualities[last] = "major"
    if last - 1 >= 1 and moves[last - 1][0] in (fifth_up, fifth_down):
        qualities[last - 1] = "major"
    return roots, qualities


def comma_pump_chords(comma):
    dimensionality = len(comma)
    prime_3 = comma[1] if dimensionality > 1 else 0
    prime_5 = comma[2] if dimensionality > 2 else 0
    seventh = dimensionality > 3 and comma[3] != 0
    if prime_5 == 0:
        roots, qualities = _open_chords(prime_3, dimensionality)
    else:
        roots, qualities = _triad_chords(prime_3, prime_5, dimensionality)
    return roots, qualities, seventh


def _mixed_offsets(quality, seventh) -> tuple[tuple[int, ...], ...]:
    top = _H7 if seventh else _P8
    if quality == "open":
        return _P1, _P5, _P8, (_H7 if seventh else _add(_P8, _P5))
    return _P1, (_M3 if quality == "major" else _m3), _P5, top


def _type_specs(dimensionality, is_standard) -> dict:
    neutral = _resolve_interval(_NEUTRAL3, dimensionality, is_standard)
    diminished = _resolve_interval(_DIM5, dimensionality, is_standard)
    augmented = _resolve_interval(_AUG5, dimensionality, is_standard)
    minor_seventh = _resolve_interval(_MIN7, dimensionality, is_standard)
    return {
        "fifth": (_P1, _P5),
        "fourth": (_P1, _P4),
        "major third": (_P1, _M3),
        "minor third": (_P1, _m3),
        "neutral third": (_P1, neutral),
        "major": (_P1, _M3, _P5),
        "minor": (_P1, _m3, _P5),
        "neutral": (_P1, neutral, _P5),
        "diminished": (_P1, _m3, diminished),
        "augmented": (_P1, _M3, augmented),
        "dominant seventh": (_P1, _M3, _P5, _H7),
        "major seventh": (_P1, _M3, _P5, _M7),
        "minor seventh": (_P1, _m3, _P5, minor_seventh),
    }


def _type_table(just_map, tempered_map) -> dict:
    is_standard = _is_standard_domain(just_map)
    specs = _type_specs(len(just_map), is_standard)
    return {
        name: {
            "ji": [_just_cents(monzo) for monzo in monzos],
            "t": [_tempered_cents(monzo, tempered_map, is_standard) for monzo in monzos],
        }
        for name, monzos in specs.items()
    }


def pump_payload(comma, just_map, tempered_map, domain_basis=None) -> str:
    dimensionality = len(comma)
    if (
        dimensionality == 0
        or len(just_map) != dimensionality
        or len(tempered_map) != dimensionality
        or not any(comma)
    ):
        return ""
    equave_just, equave_tempered = float(just_map[0]), float(tempered_map[0])
    if equave_just <= 0 or equave_tempered <= 0:
        return ""
    if abs(_balance(_dot(comma, tempered_map), equave_tempered)) > 1e-6:
        return ""
    oriented = comma if _dot(comma, just_map) >= 0 else tuple(-x for x in comma)
    roots, qualities, seventh = comma_pump_chords(oriented)
    if len(roots) < 2:
        return ""
    is_standard = _is_standard_domain(just_map)
    returning_tonic = roots[-1]
    chord_roots, chord_qualities = roots[:-1], qualities[:-1]
    just_tones, tempered_tones = [], []
    for quality in chord_qualities:
        offsets = _mixed_offsets(quality, seventh)
        just_tones.append([_just_cents(monzo) for monzo in offsets])
        tempered_tones.append(
            [_tempered_cents(monzo, tempered_map, is_standard) for monzo in offsets]
        )
    payload = {
        "ji": [_reduce(_dot(root, just_map), equave_just) for root in chord_roots],
        "t": [_reduce(_dot(root, tempered_map), equave_tempered) for root in chord_roots],
        "cji": just_tones,
        "ct": tempered_tones,
        "q": chord_qualities,
        "types": _type_table(just_map, tempered_map),
        "dji": _balance(_dot(returning_tonic, just_map), equave_just),
        "dt": _balance(_dot(returning_tonic, tempered_map), equave_tempered),
        "eji": equave_just,
        "et": equave_tempered,
    }
    if domain_basis is not None:
        score = pump_score(
            roots,
            [_mixed_offsets(quality, seventh) for quality in chord_qualities],
            _type_specs(dimensionality, is_standard),
            domain_basis,
        )
        if score is not None:
            payload["score"] = score
    return json.dumps(payload, separators=(",", ":"))
