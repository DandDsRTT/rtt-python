from __future__ import annotations

import itertools
from fractions import Fraction

from rtt.library.dimensions import get_nullity
from rtt.library.domain_basis import get_domain_basis
from rtt.library.dual import dual
from rtt.library.matrix_utils import (
    Matrix,
    matrix_multiply,
    smith_normal_form_with_transforms,
    transpose,
)
from rtt.library.temperament import Temperament, Variance

GENERATOR_PREIMAGE_COUNT = 12
_COMBINATION_RADIUS_BY_NULLITY = {1: 6, 2: 3, 3: 2}
_COMBINATION_RADIUS_WHEN_MANY_COMMAS = 1


def get_generator_detempering(t: Temperament) -> Temperament:
    mapping = t if t.variance is Variance.ROW else dual(t)
    left, snf, right = smith_normal_form_with_transforms(mapping.matrix)
    detempering = matrix_multiply(matrix_multiply(right, transpose(snf)), left)
    return Temperament(transpose(detempering), Variance.COL)


def maps_to_the_generator(mapping: Matrix, index: int, vector) -> bool:
    if not mapping or len(vector) != len(mapping[0]):
        return False
    return all(
        sum(row[e] * vector[e] for e in range(len(row))) == int(i == index)
        for i, row in enumerate(mapping)
    )


def _quotient(vector, domain_basis) -> Fraction:
    quotient = Fraction(1)
    for element, exponent in zip(domain_basis, vector, strict=False):
        quotient *= Fraction(element) ** int(exponent)
    return quotient


def _product_complexity(vector, domain_basis) -> int:
    quotient = _quotient(vector, domain_basis)
    return quotient.numerator * quotient.denominator


def get_generator_preimages(
    t: Temperament, index: int, count: int = GENERATOR_PREIMAGE_COUNT
) -> tuple[tuple[int, ...], ...]:
    mapping = t if t.variance is Variance.ROW else dual(t)
    detempered = get_generator_detempering(mapping).matrix[index]
    nullity = get_nullity(mapping)
    commas = dual(mapping).matrix if nullity else ()
    domain_basis = get_domain_basis(mapping)
    radius = _COMBINATION_RADIUS_BY_NULLITY.get(nullity, _COMBINATION_RADIUS_WHEN_MANY_COMMAS)
    preimages = {
        tuple(
            int(entry) + sum(coefficients[j] * commas[j][e] for j in range(nullity))
            for e, entry in enumerate(detempered)
        )
        for coefficients in itertools.product(range(-radius, radius + 1), repeat=nullity)
    }
    ordered = sorted(
        preimages, key=lambda vector: (_product_complexity(vector, domain_basis), vector)
    )
    return tuple(ordered[:count])
