from __future__ import annotations

import math
from fractions import Fraction

import sympy as sp

from rtt.app.service.core_vectors import _to_matrix
from rtt.library.canonicalization import canonical_ca, canonical_ma
from rtt.library.comma_forms import minimal_ca, positive_ratio_ca
from rtt.library.domain_basis import is_standard_prime_limit_domain_basis
from rtt.library.generator_detempering import get_generator_detempering
from rtt.library.generator_forms import (
    equave_reduced_ma,
    minimal_generator_ma,
    positive_generator_ma,
    positive_generator_shift_ma,
    standard_jip_octaves,
)
from rtt.library.matrix_utils import Matrix
from rtt.library.temperament import Temperament, Variance
from rtt.library.tuning import get_just_tuning_map


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
