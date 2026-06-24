from __future__ import annotations

from fractions import Fraction

from rtt.app.service.core import standard_primes
from rtt.app.service.core_vectors import (
    _interval_vectors,
    _vectors_to_ratios,
    comma_ratios,
)
from rtt.library.domain_basis import is_standard_prime_limit_domain_basis
from rtt.library.math_utils import equave_reduce


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
