from math import log2

import sympy as sp

from rtt.library.domain_basis import get_domain_basis
from rtt.library.dual import mapping_matrix
from rtt.library.symbolic_tuning import (
    closed_form_generator_operator,
    has_rational_closed_form,
)
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import optimize_generator_tuning_map, optimize_tuning_map
from rtt.library.tuning_scheme_names import resolve_tuning_scheme

MEANTONE_5 = ((1, 1, 0), (0, 1, 4))
BASIS_5 = ("2", "3", "5")
MEANTONE_7 = ((1, 1, 0, -3), (0, 1, 4, 10))
BASIS_7 = ("2", "3", "5", "7")
ET12_5 = ((12, 19, 28),)


def _symbolic_generators(t, name):
    operator = closed_form_generator_operator(t, name)
    primes = [int(p) for p in get_domain_basis(t)]
    just = sp.Matrix([[1200 * sp.log(p, 2) for p in primes]])
    generators = just * operator
    return [float(sp.N(generators[0, k])) for k in range(operator.cols)]


def _symbolic_tuning(t, name):
    operator = closed_form_generator_operator(t, name)
    primes = [int(p) for p in get_domain_basis(t)]
    just = sp.Matrix([[1200 * sp.log(p, 2) for p in primes]])
    tuning = just * operator * sp.Matrix(mapping_matrix(t))
    return [float(sp.N(tuning[0, p])) for p in range(len(primes))]


def _is_rational_operator(operator):
    return all(
        operator[i, k].is_rational
        for i in range(operator.rows)
        for k in range(operator.cols)
    )


CLOSED_FORM_CASES = [
    (MEANTONE_5, BASIS_5, "miniRMS-U"),
    (MEANTONE_5, BASIS_5, "held-octave miniRMS-U"),
    (MEANTONE_5, BASIS_5, "{2, 3/2} miniRMS-U"),
    (MEANTONE_5, BASIS_5, "{2, 3/2, 5/4} miniRMS-U"),
    (MEANTONE_7, BASIS_7, "miniRMS-U"),
    (MEANTONE_7, BASIS_7, "held-octave miniRMS-U"),
    (MEANTONE_7, BASIS_7, "{2, 3/2, 7/4} miniRMS-U"),
    (ET12_5, BASIS_5, "miniRMS-U"),
    (ET12_5, BASIS_5, "held-octave miniRMS-U"),
]


def test_closed_form_generators_equal_numeric_optimizer():
    for mapping, basis, name in CLOSED_FORM_CASES:
        t = Temperament(mapping, Variance.ROW, basis)
        numeric = optimize_generator_tuning_map(t, resolve_tuning_scheme(name))
        symbolic = _symbolic_generators(t, name)
        assert len(symbolic) == len(numeric)
        for s, n in zip(symbolic, numeric):
            assert abs(s - n) < 1e-9, (name, s, n)


def test_closed_form_tuning_map_equals_numeric_optimizer():
    for mapping, basis, name in CLOSED_FORM_CASES:
        t = Temperament(mapping, Variance.ROW, basis)
        numeric = optimize_tuning_map(t, resolve_tuning_scheme(name))
        symbolic = _symbolic_tuning(t, name)
        for s, n in zip(symbolic, numeric):
            assert abs(s - n) < 1e-9, (name, s, n)


def test_closed_form_operator_is_exactly_rational():
    for mapping, basis, name in CLOSED_FORM_CASES:
        t = Temperament(mapping, Variance.ROW, basis)
        operator = closed_form_generator_operator(t, name)
        assert operator is not None
        assert _is_rational_operator(operator)


NO_CLOSED_FORM_CASES = [
    "miniRMS-S",
    "miniRMS-ES",
    "minimax-U",
    "minimax-S",
    "destretched-octave miniRMS-U",
    "{2, 3/2} miniRMS-S",
]


def test_no_closed_form_for_minimax_weighted_and_destretched():
    t = Temperament(MEANTONE_5, Variance.ROW, BASIS_5)
    for name in NO_CLOSED_FORM_CASES:
        assert closed_form_generator_operator(t, name) is None, name


def test_no_closed_form_for_nonprime_domain():
    # a non-prime domain element (here 9 = 3²) breaks the prime-power-product form, so no
    # tidy closed form — even though the optimum is still an exact rational solution
    t = Temperament(MEANTONE_5, Variance.ROW, ("2", "9", "5"))
    assert closed_form_generator_operator(t, "miniRMS-U") is None
    assert not has_rational_closed_form(resolve_tuning_scheme("miniRMS-U"), t)


def test_closed_form_for_non_consecutive_prime_domain():
    # a prime-only basis that skips a prime (2.3.7, no 5) still yields an exact prime-power
    # closed form — this is what the superspace tuning rows rely on (their primes can skip)
    t = Temperament(((1, 1, 0), (0, 1, 4)), Variance.ROW, ("2", "3", "7"))
    operator = closed_form_generator_operator(t, "miniRMS-U")
    assert operator is not None and _is_rational_operator(operator)
    primes = [int(p) for p in get_domain_basis(t)]
    just = sp.Matrix([[1200 * sp.log(p, 2) for p in primes]])
    symbolic = [float(sp.N((just * operator)[0, k])) for k in range(operator.cols)]
    numeric = optimize_generator_tuning_map(t, resolve_tuning_scheme("miniRMS-U"))
    for s, n in zip(symbolic, numeric):
        assert abs(s - n) < 1e-9


def test_held_octave_makes_octave_pure():
    t = Temperament(MEANTONE_5, Variance.ROW, BASIS_5)
    tuning = _symbolic_tuning(t, "held-octave miniRMS-U")
    assert abs(tuning[0] - 1200.0) < 1e-9
