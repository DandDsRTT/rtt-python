from __future__ import annotations

import math
from dataclasses import dataclass, replace
from fractions import Fraction
from functools import lru_cache

import sympy as sp

from rtt.app.service.core import DEFAULT_TUNING_SCHEME, _hashable, _to_matrix
from rtt.library.domain_basis import get_domain_basis
from rtt.library.dual import mapping_matrix
from rtt.library.symbolic_tuning import closed_form_generator_operator
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning_scheme_names import resolve_tuning_scheme


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
    closed = 1200 * sum(float(e) * math.log2(p) for e, p in zip(exponents, primes, strict=False))
    return abs(closed - value) < tolerance


def _power_product_operand(exponents, primes) -> str:
    terms = []
    for prime, exponent in zip(primes, exponents, strict=False):
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
        parts = ([own] if own else []) + list(held)
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
