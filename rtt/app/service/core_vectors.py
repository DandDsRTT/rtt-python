from __future__ import annotations

import math
from fractions import Fraction

from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.generator_detempering import (
    get_generator_detempering,
    get_generator_preimages,
    maps_to_the_generator,
)
from rtt.library.math_utils import get_primes, pcv_to_quotient
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_quotient_list
from rtt.library.temperament import Temperament, Variance


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


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


def detempers_the_generator(mapping, index: int, vector) -> bool:
    return maps_to_the_generator(_to_matrix(mapping), index, tuple(int(x) for x in vector))


def next_generator_preimage(mapping, index: int, current, domain_basis=None) -> tuple[int, ...]:
    m = Temperament(_to_matrix(mapping), Variance.ROW, domain_basis)
    preimages = get_generator_preimages(m, index)
    current = tuple(int(x) for x in current)
    if current not in preimages:
        return preimages[0]
    return preimages[(preimages.index(current) + 1) % len(preimages)]


def comma_ratios(comma_basis, domain_basis=None) -> tuple[str, ...]:
    return _vectors_to_ratios(comma_basis, domain_basis)


RADICAL_SIGN = "√"


def _radical(quotient: Fraction, index: int) -> str:
    body = (
        str(quotient.numerator)
        if quotient.denominator == 1
        else f"{quotient.numerator}/{quotient.denominator}"
    )
    return body if index == 1 else f"{index}{RADICAL_SIGN}{body}"


def embedding_ratios(embedding_matrix, domain_basis=None) -> tuple[str, ...]:
    if embedding_matrix is None or not embedding_matrix:
        return ()
    elements = tuple(Fraction(e) for e in domain_basis) if domain_basis else None
    rank = len(embedding_matrix[0])
    ratios = []
    for j in range(rank):
        column = [Fraction(embedding_matrix[p][j]) for p in range(len(embedding_matrix))]
        index = 1
        for exponent in column:
            index = index * exponent.denominator // math.gcd(index, exponent.denominator)
        base = elements or tuple(Fraction(p) for p in get_primes(len(column)))
        quotient = Fraction(1)
        for element, exponent in zip(base, column, strict=False):
            quotient *= element ** int(exponent * index)
        ratios.append(_radical(quotient, index))
    return tuple(ratios)


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
