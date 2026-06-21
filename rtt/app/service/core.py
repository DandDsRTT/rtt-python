from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.library.addition import _get_greatest_factor
from rtt.library.canonicalization import canonical_ca, canonical_ma
from rtt.library.comma_forms import minimal_ca, positive_ratio_ca
from rtt.library.generator_forms import (
    equave_reduced_ma,
    minimal_generator_ma,
    positive_generator_ma,
    positive_generator_shift_ma,
    standard_jip_octaves,
)
from rtt.library.dimensions import get_d, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    filter_target_intervals_for_nonstandard_domain_basis,
    get_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.formatting import strip_negative_zero
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.math_utils import equave_reduce, get_primes, pcv_to_quotient, quotient_to_pcv
from rtt.library.matrix_utils import Matrix
from rtt.library.dual import mapping_matrix
from rtt.library.parsing import parse_quotient_list
from rtt.library.symbolic_tuning import closed_form_generator_operator
from rtt.library.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import (
    damage_weights,
    get_complexity,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
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
    every_element_reached = all(any(row[p] for row in rows) for p in range(len(rows[0])))
    return every_element_reached


def greatest_factor(mapping) -> int:
    rows = _to_matrix(mapping)
    if not rows or not rows[0] or get_r(Temperament(rows, Variance.ROW)) < len(rows):
        return 1
    return abs(_get_greatest_factor(rows))


def is_enfactored(mapping) -> bool:
    return greatest_factor(mapping) > 1


def target_interval_set(spec: str, domain_basis) -> tuple[str, ...]:
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    if is_standard_prime_limit_domain_basis(domain):
        quotients = tuple(q for q in quotients if len(quotient_to_pcv(q)) <= len(domain))
    else:
        quotients = filter_target_intervals_for_nonstandard_domain_basis(quotients, domain)
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


def element_ratio(element) -> str:
    fraction = Fraction(element)
    return f"{fraction.numerator}/{fraction.denominator}"


def default_target_limit(family: str, domain_basis) -> int:
    domain = tuple(domain_basis)
    return default_old_limit(domain) if "OLD" in family else default_tilt_limit(domain)


def target_limit_problem(family: str | None, limit_value) -> str | None:
    no_manual_limit = not limit_value
    if no_manual_limit:
        return None
    try:
        number = float(limit_value)
    except (TypeError, ValueError):
        return "whole"
    if number != int(number):
        return "whole"
    if "OLD" in (family or "") and int(number) % 2 == 0:
        return "odd"
    return None


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
            for element, exponent in zip(elements, vector):
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


def canonical_mapping(mapping) -> Matrix:
    return _to_matrix(canonical_ma(_to_matrix(mapping)))


def canonical_comma_basis(comma_basis) -> Matrix:
    return _to_matrix(canonical_ca(_to_matrix(comma_basis)))


MAPPING_FORM_KEYS = (
    "canonical",
    "mingen",
    "equave-reduced",
    "positive-generator",
    "positive-generator-shift",
)
MAPPING_FORM_LABELS = {
    "canonical": "canonical",
    "mingen": "minimal-generator",
    "equave-reduced": "equave-reduced",
    "positive-generator": "positive-generator (flip)",
    "positive-generator-shift": "positive-generator (shift)",
}
_ALT_MAPPING_FORMS = {
    "mingen": minimal_generator_ma,
    "equave-reduced": equave_reduced_ma,
    "positive-generator": positive_generator_ma,
    "positive-generator-shift": positive_generator_shift_ma,
}


def _jip_octaves(mapping, domain_basis):
    t = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    return tuple(c / 1200.0 for c in get_just_tuning_map(t))


def mapping_in_form(mapping, form: str, domain_basis=None) -> Matrix:
    m = _to_matrix(mapping)
    if form == "canonical":
        return _to_matrix(canonical_ma(m))
    return _to_matrix(_ALT_MAPPING_FORMS[form](m, _jip_octaves(m, domain_basis)))


def identify_mapping_form(mapping, domain_basis=None) -> str | None:
    m = _to_matrix(mapping)
    for key in MAPPING_FORM_KEYS:
        if mapping_in_form(m, key, domain_basis) == m:
            return key
    return None


def resolve_mapping_form(mapping, preferred, domain_basis=None) -> str:
    m = _to_matrix(mapping)
    if preferred in MAPPING_FORM_KEYS and mapping_in_form(m, preferred, domain_basis) == m:
        return preferred
    return identify_mapping_form(m, domain_basis) or ""


COMMA_BASIS_FORM_KEYS = ("canonical", "positive-ratio", "minimal")
COMMA_BASIS_FORM_LABELS = {
    "canonical": "canonical",
    "positive-ratio": "positive-ratio",
    "minimal": "minimal",
}
_ALT_COMMA_BASIS_FORMS = {
    "positive-ratio": positive_ratio_ca,
    "minimal": minimal_ca,
}


def _comma_octaves(d: int, domain_basis=None):
    if domain_basis is None or is_standard_prime_limit_domain_basis(domain_basis):
        return standard_jip_octaves(d)
    return tuple(math.log2(float(Fraction(e))) for e in domain_basis)


def comma_basis_in_form(comma_basis, form: str, domain_basis=None) -> Matrix:
    cb = _to_matrix(comma_basis)
    if form == "canonical":
        return _to_matrix(canonical_ca(cb))
    d = len(cb[0]) if cb else (len(domain_basis) if domain_basis else 0)
    return _to_matrix(_ALT_COMMA_BASIS_FORMS[form](cb, _comma_octaves(d, domain_basis)))


def identify_comma_basis_form(comma_basis, domain_basis=None) -> str | None:
    cb = _to_matrix(comma_basis)
    for key in COMMA_BASIS_FORM_KEYS:
        if comma_basis_in_form(cb, key, domain_basis) == cb:
            return key
    return None


def resolve_comma_basis_form(comma_basis, preferred, domain_basis=None) -> str:
    cb = _to_matrix(comma_basis)
    if (
        preferred in COMMA_BASIS_FORM_KEYS
        and comma_basis_in_form(cb, preferred, domain_basis) == cb
    ):
        return preferred
    return identify_comma_basis_form(cb, domain_basis) or ""


def form_matrix(mapping) -> Matrix:
    m = _to_matrix(mapping)
    canon = canonical_ma(m)
    detemper = get_generator_detempering(Temperament(m, Variance.ROW)).matrix
    return tuple(
        tuple(
            sum(canon[i][p] * detemper[j][p] for p in range(len(m[0])))
            for j in range(len(detemper))
        )
        for i in range(len(canon))
    )


def inverse_form_matrix(mapping) -> Matrix:
    m = _to_matrix(mapping)
    canon = canonical_ma(m)
    canon_detemper = get_generator_detempering(Temperament(_to_matrix(canon), Variance.ROW)).matrix
    return tuple(
        tuple(
            sum(m[i][p] * canon_detemper[j][p] for p in range(len(m[0])))
            for j in range(len(canon_detemper))
        )
        for i in range(len(m))
    )


def mapping_from_form_matrix(mapping, form_rows) -> Matrix | None:
    m = _to_matrix(mapping)
    r = len(m)
    f = _to_matrix(form_rows)
    if len(f) != r or any(len(row) != r for row in f):
        return None
    try:
        fm = sp.Matrix([[sp.Integer(int(x)) for x in row] for row in f])
    except (TypeError, ValueError):
        return None
    if fm.det() not in (1, -1):
        return None
    canon = sp.Matrix([list(row) for row in canonical_ma(m)])
    new = fm * canon
    return tuple(tuple(int(new[i, j]) for j in range(new.cols)) for i in range(new.rows))


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
        raise ValueError(f'"{text}" is not a valid ratio.')
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
        parts = ([own] if own else []) + [r for r in held]
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
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
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
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def interval_sizes(tun: Tuning, ratios, domain_basis=None, weights=None) -> IntervalSizes:
    vectors = _interval_vectors(ratios, domain_basis, len(tun.tuning_map))
    tempered = tuple(_over(tun.tuning_map, m) for m in vectors)
    just = tuple(_over(tun.just_map, m) for m in vectors)
    errors = tuple(t_ - j for t_, j in zip(tempered, just))
    if weights is None:
        damage = tuple(abs(e) for e in errors)
    else:
        damage = tuple(abs(e) * w for e, w in zip(errors, weights))
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
            m,
            t,
            spec.complexity_norm_power,
            spec.complexity_log_prime_power,
            spec.complexity_prime_power,
            spec.complexity_size_factor,
            spec.nonprime_basis_approach,
            prescaler_override=prescaler_override,
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


@dataclass(frozen=True)
class ClosedFormTuning:
    primes: tuple[int, ...]
    generator_exponents: tuple[tuple[Fraction, ...], ...]
    tempered_matrix: tuple[tuple[Fraction, ...], ...]

    def generator_operand(self, generator: int, value: float) -> str | None:
        if not 0 <= generator < len(self.generator_exponents):
            return None
        return self._operand(self.generator_exponents[generator], value)

    def tempered_operand(self, vector, value: float) -> str | None:
        return self._operand(self._tempered_exponents(vector), value)

    def retune_operand(self, vector, value: float) -> str | None:
        d = len(self.primes)
        tempered = self._tempered_exponents(vector)
        padded = tuple((vector[p] if p < len(vector) else 0) for p in range(d))
        exponents = tuple(tempered[i] - padded[i] for i in range(d))
        return self._operand(exponents, value)

    def canonical_generator_operand(self, coefficients, value: float) -> str | None:
        d = len(self.primes)
        exponents = tuple(
            sum(coefficients[k] * self.generator_exponents[k][i] for k in range(len(coefficients)))
            for i in range(d)
        )
        return self._operand(exponents, value)

    def _tempered_exponents(self, vector):
        d = len(self.primes)
        padded = tuple((vector[p] if p < len(vector) else 0) for p in range(d))
        return tuple(
            sum(self.tempered_matrix[i][p] * padded[p] for p in range(d)) for i in range(d)
        )

    def _operand(self, exponents, value: float) -> str | None:
        if not _closed_form_matches(exponents, self.primes, value):
            return None
        return _power_product_operand(exponents, self.primes)


def _closed_form_matches(exponents, primes, value: float, tolerance: float = 1e-6) -> bool:
    closed = 1200 * sum(float(e) * math.log2(p) for e, p in zip(exponents, primes))
    return abs(closed - value) < tolerance


def _power_product_operand(exponents, primes) -> str:
    terms = []
    for prime, exponent in zip(primes, exponents):
        if exponent == 0:
            continue
        if exponent == 1:
            terms.append(str(prime))
        elif exponent.denominator == 1:
            terms.append(f"{prime}^{exponent.numerator}")
        else:
            terms.append(f"{prime}^({exponent.numerator}/{exponent.denominator})")
    if not terms:
        return "1"
    if len(terms) == 1 and "^" not in terms[0]:
        return terms[0]
    return "(" + "·".join(terms) + ")"


def closed_form_tuning(
    mapping,
    scheme: str = DEFAULT_TUNING_SCHEME,
    domain_basis=None,
    nonprime_approach: str = "",
    held=(),
    prescaler_override=None,
    targets=None,
    weights_override=None,
) -> ClosedFormTuning | None:
    if prescaler_override is not None or weights_override is not None:
        return None
    return _cached_closed_form(
        _to_matrix(mapping),
        scheme,
        _hashable(domain_basis),
        nonprime_approach,
        tuple(held),
        _hashable(targets),
    )


@lru_cache(maxsize=256)
def _cached_closed_form(
    mapping, scheme, domain_basis, nonprime_approach, held, targets
) -> ClosedFormTuning | None:
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
        parts = ([own] if own else []) + [r for r in held]
        spec = replace(spec, held_intervals="{" + ", ".join(parts) + "}")
    return closed_form_from_temperament(t, spec)


def closed_form_from_temperament(t, spec) -> ClosedFormTuning | None:
    operator = closed_form_generator_operator(t, spec)
    if operator is None:
        return None
    tempered = operator * sp.Matrix(mapping_matrix(t))
    primes = tuple(int(p) for p in get_domain_basis(t))
    return ClosedFormTuning(
        primes=primes,
        generator_exponents=tuple(
            tuple(_to_fraction(operator[i, k]) for i in range(operator.rows))
            for k in range(operator.cols)
        ),
        tempered_matrix=tuple(
            tuple(_to_fraction(tempered[i, p]) for p in range(tempered.cols))
            for i in range(tempered.rows)
        ),
    )


def _to_fraction(value) -> Fraction:
    rational = sp.Rational(value)
    return Fraction(int(rational.p), int(rational.q))


def cents(value, decimals: bool = True) -> str:
    if value is None:
        return "—"
    return strip_negative_zero(f"{value:.{3 if decimals else 0}f}")


def prescale_text(value: float, decimals: bool = True) -> str:
    return str(int(value)) if value == int(value) else cents(value, decimals)
