from __future__ import annotations

from fractions import Fraction
from math import log2

from rtt.library.math_utils import quotient_to_pcv

_PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)

_PRIME_FACTOR_COMMAS = {
    5: ((4, -4, 1), "accSagittal5CommaDown"),
    7: ((-6, 2, 0, 1), "accSagittal7CommaDown"),
    11: ((-5, 1, 0, 0, 1), "accSagittal11MediumDiesisUp"),
    13: ((1, -3, 0, 0, 0, 1), "accSagittal35LargeDiesisDown"),
    17: ((-12, 5, 0, 0, 0, 0, 1), "accSagittal17CommaUp"),
    19: ((-9, 3, 0, 0, 0, 0, 0, 1), "accSagittal19SchismaUp"),
    23: ((5, -6, 0, 0, 0, 0, 0, 0, 1), "accSagittal23CommaUp"),
    29: ((-8, 2, 0, 0, 0, 0, 0, 0, 0, 1), "accSagittal7v11CommaUp"),
    31: ((-5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1), "accSagittal49MediumDiesisDown"),
    37: ((-2, -2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1), "accSagittal5v13MediumDiesisUp"),
}

_COMMA_CENTS = {
    prime: abs(sum(e * 1200.0 * log2(p) for e, p in zip(monzo, _PRIMES, strict=False)))
    for prime, (monzo, _) in _PRIME_FACTOR_COMMAS.items()
}

_LETTER_BY_STEP = ("C", "D", "E", "F", "G", "A", "B")
_FIFTHS_FROM_C = {"F": -1, "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5}
_SHARPS_CAP = 2


def _flip(glyph: str) -> str:
    return glyph[: -len("Up")] + "Down" if glyph.endswith("Up") else glyph[: -len("Down")] + "Up"


def spell_monzo(monzo):
    residual = list(monzo)
    if len(residual) > len(_PRIMES):
        if any(residual[len(_PRIMES) :]):
            return None
        residual = residual[: len(_PRIMES)]
    residual += [0] * (len(_PRIMES) - len(residual))
    sagittals = []
    for slot, prime in enumerate(_PRIMES[2:], start=2):
        count = residual[slot]
        if not count:
            continue
        comma, glyph_toward_positive = _PRIME_FACTOR_COMMAS[prime]
        for position, exponent in enumerate(comma):
            residual[position] -= count * exponent
        symbol = glyph_toward_positive if count > 0 else _flip(glyph_toward_positive)
        sagittals.extend([(_COMMA_CENTS[prime], prime, symbol)] * abs(count))
    octaves, fifths = residual[0], residual[1]
    diatonic_steps = 11 * fifths + 7 * octaves
    letter = _LETTER_BY_STEP[diatonic_steps % 7]
    octave = 4 + (diatonic_steps - (diatonic_steps % 7)) // 7
    sharps = (fifths - _FIFTHS_FROM_C[letter]) // 7
    if abs(sharps) > _SHARPS_CAP:
        return None
    sagittals.sort(key=lambda entry: (entry[0], entry[1]))
    return {
        "p": f"{letter.lower()}/{octave}",
        "s": sharps,
        "g": tuple(symbol for _, _, symbol in sagittals),
    }


def _prime_monzo(vector, basis_monzos, width):
    monzo = [0] * width
    for count, basis_monzo in zip(vector, basis_monzos, strict=True):
        for position, exponent in enumerate(basis_monzo):
            monzo[position] += count * exponent
    return tuple(monzo)


def _cents(monzo) -> float:
    return sum(e * 1200.0 * log2(p) for e, p in zip(monzo, _PRIMES, strict=False))


def _octave_reduced(monzo):
    shift = -int(_cents(monzo) // 1200.0)
    return (monzo[0] + shift, *monzo[1:])


def _octave_balanced(monzo):
    shift = -round(_cents(monzo) / 1200.0)
    return (monzo[0] + shift, *monzo[1:])


def _ratio_text(monzo) -> str:
    ratio = Fraction(1)
    for exponent, prime in zip(monzo, _PRIMES, strict=False):
        ratio *= Fraction(prime) ** exponent
    return f"{ratio.numerator}/{ratio.denominator}"


def _super_ratio_text(monzo) -> str:
    return _ratio_text(monzo if _cents(monzo) >= 0 else tuple(-e for e in monzo))


def _widen(monzo, width):
    return tuple(monzo[i] if i < len(monzo) else 0 for i in range(max(width, len(monzo))))


def _sum(a, b):
    width = max(len(a), len(b))
    return tuple((a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(width))


def _diff(a, b):
    width = max(len(a), len(b))
    return tuple((a[i] if i < len(a) else 0) - (b[i] if i < len(b) else 0) for i in range(width))


def _spelled_tones(placed_root, offsets, width):
    spelled = []
    for offset in offsets:
        tone = spell_monzo(_sum(placed_root, _widen(offset, width)))
        if tone is None:
            return None
        spelled.append(tone)
    return spelled


def _chord_step(placed_root, mixed_offsets, type_offsets, width):
    if spell_monzo(placed_root) is None:
        return None
    tones = {"mixed": _spelled_tones(placed_root, mixed_offsets, width)}
    if tones["mixed"] is None:
        return None
    for name, offsets in type_offsets.items():
        spelled = _spelled_tones(placed_root, offsets, width)
        if spelled is not None:
            tones[name] = spelled
    return {"r": _ratio_text(placed_root), "tones": tones}


def pump_score(roots, chord_tone_offsets, type_offsets, domain_basis):
    try:
        basis = tuple(Fraction(element) for element in domain_basis)
    except (TypeError, ValueError):
        return None
    if not basis or basis[0] != 2 or not roots:
        return None
    basis_monzos = [tuple(quotient_to_pcv(element)) for element in basis]
    width = max(len(m) for m in basis_monzos)
    if width > len(_PRIMES) or any(len(root) != len(basis) for root in roots):
        return None
    placed = [_octave_reduced(_prime_monzo(root, basis_monzos, width)) for root in roots]
    chord_count = len(roots) - 1
    steps = []
    for k in range(chord_count):
        step = _chord_step(placed[k], chord_tone_offsets[k], type_offsets, width)
        if step is None:
            return None
        steps.append(step)
    tonic = _octave_balanced(_prime_monzo(roots[chord_count], basis_monzos, width))
    moves = [_ratio_text(_diff(placed[k + 1], placed[k])) for k in range(chord_count - 1)] + [
        _ratio_text(_diff(tonic, placed[chord_count - 1]))
    ]
    return {"comma": _super_ratio_text(tonic), "steps": steps, "moves": moves}
