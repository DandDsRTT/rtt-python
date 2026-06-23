from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.library.addition import _get_greatest_factor
from rtt.library.dimensions import get_d, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.formatting import strip_negative_zero
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.math_utils import equave_reduce, get_primes, pcv_to_quotient
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_quotient_list
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    damage_weights,
    get_complexity,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    tuning_map_from_generators,
)
from rtt.library.tuning_ranges import get_generator_tuning_range as _get_generator_tuning_range
from rtt.library.tuning_scheme_names import resolve_tuning_scheme


def get_generator_tuning_range(t, mode):
    try:
        return _get_generator_tuning_range(t, mode)
    except (ValueError, IndexError):
        return None


DEFAULT_TUNING_SCHEME = "minimax-S"
DEFAULT_TARGET_SPEC = "TILT"
DEFAULT_DOCUMENT_SCHEME = f"{DEFAULT_TARGET_SPEC} minimax-U"


@dataclass(frozen=True)
class Tuning:
    generator_map: tuple[float, ...]
    tuning_map: tuple[float, ...]
    just_map: tuple[float, ...]
    retuning_map: tuple[float, ...]
    monotone_generator_range: tuple[tuple[float, float], ...] | None
    tradeoff_generator_range: tuple[tuple[float, float], ...] | None


@dataclass(frozen=True)
class IntervalSizes:
    tempered: tuple[float, ...]
    just: tuple[float, ...]
    errors: tuple[float, ...]
    damage: tuple[float, ...]


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


def _hashable(value):
    if value is None:
        return None
    return tuple(tuple(row) if isinstance(row, (tuple, list)) else row for row in value)


def _is_matrix(x) -> bool:
    return bool(x) and isinstance(x[0], (tuple, list))


def standard_primes(d: int) -> tuple[int, ...]:
    return get_primes(d)


def is_standard_domain(domain_basis) -> bool:
    return is_standard_prime_limit_domain_basis(tuple(domain_basis))


def domain_has_nonprimes(domain_basis) -> bool:
    for element in domain_basis:
        fraction = Fraction(element)
        if fraction.denominator != 1 or not sp.isprime(fraction.numerator):
            return True
    return False


def is_proper_temperament(mapping) -> bool:
    rows = _to_matrix(mapping)
    if not rows or not rows[0]:
        return False
    rank = get_r(Temperament(rows, Variance.ROW))
    if rank < len(rows):
        return False
    return all(any(row[p] for row in rows) for p in range(len(rows[0])))


def greatest_factor(mapping) -> int:
    rows = _to_matrix(mapping)
    if not rows or not rows[0] or get_r(Temperament(rows, Variance.ROW)) < len(rows):
        return 1
    return abs(_get_greatest_factor(rows))


def is_enfactored(mapping) -> bool:
    return greatest_factor(mapping) > 1


def element_ratio(element) -> str:
    fraction = Fraction(element)
    return f"{fraction.numerator}/{fraction.denominator}"


# CPython raises when stringifying an int past ~4300 digits (its int->str DoS guard), so a ratio
# component that large would crash the formatter; flag anything past this far-lower ceiling instead.
_OVER_COMPLEX_RATIO = "⋯"
_MAX_RATIO_DIGITS = 1000


def _ratio_too_complex(quotient) -> bool:
    bits = max(quotient.numerator.bit_length(), quotient.denominator.bit_length())
    return bits * 0.30103 > _MAX_RATIO_DIGITS


def _vectors_to_ratios(vectors, domain_basis=None) -> tuple[str, ...]:
    standard = domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis)
    elements = None if standard else tuple(Fraction(e) for e in domain_basis)
    ratios = []
    for vector in vectors:
        if standard:
            quotient = pcv_to_quotient(vector)
        else:
            quotient = Fraction(1)
            for element, exponent in zip(elements, vector, strict=False):
                quotient *= element**exponent
        if _ratio_too_complex(quotient):
            ratios.append(_OVER_COMPLEX_RATIO)
        else:
            ratios.append(f"{quotient.numerator}/{quotient.denominator}")
    return tuple(ratios)


def generators(mapping, domain_basis=None) -> tuple[str, ...]:
    m = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return _vectors_to_ratios(get_generator_detempering(m).matrix, domain_basis)


def generator_detempering(mapping) -> Matrix:
    m = Temperament(_to_matrix(mapping), Variance.ROW)
    return _to_matrix(get_generator_detempering(m).matrix)


def comma_ratios(comma_basis, domain_basis=None) -> tuple[str, ...]:
    return _vectors_to_ratios(comma_basis, domain_basis)


def _vectors(ratios, d) -> tuple:
    return parse_quotient_list("{" + ", ".join(ratios) + "}", d)


def _interval_vectors(ratios, domain_basis, d) -> tuple:
    ratios = tuple("1/1" if r == _OVER_COMPLEX_RATIO else r for r in ratios)
    if domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis):
        return _vectors(ratios, d)
    return express_quotients_in_domain_basis(
        tuple(Fraction(r) for r in ratios), tuple(domain_basis)
    )


def _over(prime_map, vector):
    return sum(prime_map[p] * vector[p] for p in range(len(prime_map)))


def _map_through(mapping, vectors) -> Matrix:
    d = len(mapping[0])
    return tuple(
        tuple(sum(mapping[i][p] * vector[p] for p in range(d)) for vector in vectors)
        for i in range(len(mapping))
    )


def mapped_intervals(mapping, ratios, domain_basis=None) -> Matrix:
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _interval_vectors(ratios, domain_basis, len(mapping[0])))


def mapped_commas(mapping, comma_basis) -> Matrix:
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _to_matrix(comma_basis))


def target_interval_vectors(ratios, d: int, domain_basis=None) -> Matrix:
    return tuple(
        tuple(int(x) for x in vector) for vector in _interval_vectors(ratios, domain_basis, d)
    )


def _domain_label(d: int, domain_basis=None) -> str:
    standard = domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis)
    return ".".join(str(e) for e in (standard_primes(d) if standard else domain_basis))


def interval_vector(ratio: str, d: int, domain_basis=None) -> tuple[int, ...]:
    text = str(ratio).strip()
    try:
        target = Fraction(text)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f'"{text}" is not a valid ratio.') from None
    if target <= 0:
        raise ValueError(f'"{text}" is not a positive ratio.')
    vectors = _interval_vectors((text,), domain_basis, d)
    vector = tuple(int(x) for x in vectors[0]) if len(vectors) == 1 and len(vectors[0]) == d else ()
    if not vector or Fraction(_vectors_to_ratios((vector,), domain_basis)[0]) != target:
        raise ValueError(f'"{text}" is outside the {_domain_label(d, domain_basis)} domain.')
    return vector


def equave_quotient(domain_basis=None) -> Fraction:
    return Fraction(domain_basis[0]) if domain_basis else Fraction(2)


def equave_reduce_vector(vector, domain_basis=None) -> tuple[int, ...]:
    v = tuple(int(x) for x in vector)
    q = Fraction(comma_ratios((v,), domain_basis)[0])
    reduced = equave_reduce(q, equave_quotient(domain_basis))
    return v if reduced == q else interval_vector(str(reduced), len(v), domain_basis)


def transformed_vector(vector, op: str, domain_basis=None) -> tuple[int, ...] | None:
    v = tuple(int(x) for x in vector)
    if op == "reciprocate":
        new_v = tuple(-x for x in v)
    else:
        new_v = tuple(int(x) for x in equave_reduce_vector(v, domain_basis))
    return None if new_v == v else new_v


def interval_op_availability(ratio: str, domain_basis=None) -> tuple[bool, bool]:
    try:
        q = Fraction(str(ratio))
    except (ValueError, ZeroDivisionError):
        return (False, False)
    if q <= 0:
        return (False, False)
    return (equave_reduce(q, equave_quotient(domain_basis)) != q, q != 1)


def transform_ratio(ratio: str, op: str, domain_basis=None) -> str | None:
    try:
        q = Fraction(str(ratio))
    except (ValueError, ZeroDivisionError):
        return None
    if q <= 0:
        return None
    new = (1 / q) if op == "reciprocate" else equave_reduce(q, equave_quotient(domain_basis))
    if new == q:
        return None
    return str(new.numerator) if new.denominator == 1 else f"{new.numerator}/{new.denominator}"


def tuning(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    domain_basis=None,
    nonprime_approach: str = "",
    held=(),
    prescaler_override=None,
    targets=None,
    weights_override=None,
) -> Tuning:
    return _cached_tuning(
        _to_matrix(mapping),
        scheme,
        _hashable(domain_basis),
        nonprime_approach,
        tuple(held),
        _hashable(prescaler_override),
        _hashable(targets),
        _hashable(weights_override),
    )


@lru_cache(maxsize=256)
def _cached_tuning(
    mapping,
    scheme,
    domain_basis,
    nonprime_approach,
    held,
    prescaler_override,
    targets,
    weights_override,
) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
    spec = resolve_tuning_scheme(scheme)
    if targets is not None and (spec.target_intervals or "").strip() not in ("{}", ""):
        if targets:
            spec = replace(spec, target_intervals="{" + ", ".join(targets) + "}")
        else:
            spec = replace(
                spec,
                target_intervals="1-OLD" if "OLD" in (spec.target_intervals or "") else "1-TILT",
            )
    if nonprime_approach:
        spec = replace(spec, nonprime_basis_approach=nonprime_approach)
    if held:
        own = (spec.held_intervals or "").strip().strip("{}").strip()
        parts = ([own] if own else []) + list(held)
        spec = replace(spec, held_intervals="{" + ", ".join(parts) + "}")
    gmap = optimize_generator_tuning_map(
        t, spec, prescaler_override=prescaler_override, weights_override=weights_override
    )
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, gmap))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=gmap,
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just, strict=False)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def tuning_from_generators(mapping, generators, domain_basis=None) -> Tuning:
    return _cached_tuning_from_generators(
        _to_matrix(mapping), tuple(float(g) for g in generators), _hashable(domain_basis)
    )


@lru_cache(maxsize=256)
def _cached_tuning_from_generators(mapping, generators, domain_basis) -> Tuning:
    t = Temperament(mapping, Variance.ROW, domain_basis)
    tempered = tuple(float(x) for x in tuning_map_from_generators(t, generators))
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=tuple(generators),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just, strict=False)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def interval_sizes(tun: Tuning, ratios, domain_basis=None, weights=None) -> IntervalSizes:
    vectors = _interval_vectors(ratios, domain_basis, len(tun.tuning_map))
    tempered = tuple(_over(tun.tuning_map, m) for m in vectors)
    just = tuple(_over(tun.just_map, m) for m in vectors)
    errors = tuple(t_ - j for t_, j in zip(tempered, just, strict=False))
    if weights is None:
        damage = tuple(abs(e) for e in errors)
    else:
        damage = tuple(abs(e) * w for e, w in zip(errors, weights, strict=False))
    return IntervalSizes(tempered, just, errors, damage)


def _temperament_spec_vectors(mapping, scheme, ratios, domain_basis=None):
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return t, resolve_tuning_scheme(scheme), _interval_vectors(ratios, domain_basis, get_d(t))


def interval_complexities(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    ratios=(),
    prescaler_override=None,
    domain_basis=None,
) -> tuple[float, ...]:
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        get_complexity(
            m, t, replace(spec.complexity, rough=0), prescaler_override=prescaler_override
        )
        for m in vectors
    )


def interval_weights(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    ratios=(),
    prescaler_override=None,
    domain_basis=None,
    weights_override=None,
) -> tuple[float, ...]:
    t, spec, vectors = _temperament_spec_vectors(mapping, scheme, ratios, domain_basis)
    return tuple(
        float(w)
        for w in damage_weights(
            vectors,
            t,
            spec,
            prescaler_override=prescaler_override,
            weights_override=weights_override,
        )
    )


def cents(value, decimals: bool = True) -> str:
    if value is None:
        return "—"
    return strip_negative_zero(f"{value:.{3 if decimals else 0}f}")


def prescale_text(value: float, decimals: bool = True) -> str:
    return str(int(value)) if value == int(value) else cents(value, decimals)
