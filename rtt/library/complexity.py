from __future__ import annotations

from fractions import Fraction
from math import log2

import numpy as np

from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.temperament import Temperament
from rtt.library.tuning_scheme_names import ComplexitySpec


def get_complexity_prescaler(t: Temperament, spec: ComplexitySpec, override=None) -> list[float]:
    if override is not None:
        return override
    return _prescaler_diagonal(get_domain_basis(t), spec)


def _prescaler_diagonal(domain_basis, spec: ComplexitySpec) -> list[float]:
    diagonal = []
    for q in domain_basis:
        fraction = Fraction(q)
        base = (
            float(q)
            if spec.nonprime_basis_approach == "nonprime-based"
            else float(fraction.numerator * fraction.denominator)
        )
        weight = 1.0
        if spec.log_prime_power > 0:
            weight *= log2(base) ** spec.log_prime_power
        if spec.prime_power > 0:
            weight *= base**spec.prime_power
        diagonal.append(weight)
    return diagonal


def _should_lift_pcv_to_prime_basis(pcv, domain_basis, nonprime_basis_approach, prescaler_override):
    return (
        prescaler_override is None
        and nonprime_basis_approach != "nonprime-based"
        and len(pcv) == len(domain_basis)
        and not is_standard_prime_limit_domain_basis(domain_basis)
    )


def _lift_pcv_to_prime_basis(pcv, domain_basis):
    prime_basis = get_simplest_prime_only_basis(domain_basis)
    if tuple(prime_basis) == tuple(domain_basis):
        return pcv, domain_basis
    lift = express_quotients_in_domain_basis(domain_basis, prime_basis)
    lifted = tuple(
        sum(pcv[e] * lift[e][p] for e in range(len(lift))) for p in range(len(prime_basis))
    )
    return lifted, prime_basis


def _zero_rough_primes(pcv, domain_basis, complexity_rough):
    return tuple(
        0 if Fraction(q).denominator == 1 and Fraction(q).numerator < complexity_rough else x
        for q, x in zip(domain_basis, pcv, strict=False)
    )


def get_complexity(
    pcv: tuple, t: Temperament, spec: ComplexitySpec, prescaler_override=None
) -> float:
    domain_basis = get_domain_basis(t)
    if _should_lift_pcv_to_prime_basis(
        pcv, domain_basis, spec.nonprime_basis_approach, prescaler_override
    ):
        pcv, domain_basis = _lift_pcv_to_prime_basis(pcv, domain_basis)
    if spec.rough:
        pcv = _zero_rough_primes(pcv, domain_basis, spec.rough)
    prescaler = (
        prescaler_override
        if prescaler_override is not None
        else _prescaler_diagonal(domain_basis, spec)
    )
    if np.ndim(prescaler) == 2:
        transformed = list(np.asarray(prescaler, dtype=float) @ np.asarray(pcv, dtype=float))
    else:
        transformed = [w * x for w, x in zip(prescaler, pcv, strict=False)]
    if spec.size_factor != 0:
        transformed.append(spec.size_factor * sum(transformed))
    ord_ = np.inf if spec.norm_power == float("inf") else spec.norm_power
    return float(np.linalg.norm(transformed, ord_)) / (1 + spec.size_factor)
