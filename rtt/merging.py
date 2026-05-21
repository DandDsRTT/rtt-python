from __future__ import annotations

from rtt.canonicalization import canonical_form
from rtt.change_basis import change_domain_basis_for_c, change_domain_basis_for_m
from rtt.domain_basis import (
    domain_basis_intersection,
    domain_basis_merge,
    get_domain_basis,
)
from rtt.dual import dual
from rtt.temperament import Temperament, Variance


def map_merge(*temperaments: Temperament) -> Temperament:
    """The join: stack the temperaments' mappings and canonicalize.

    Inputs may be mappings or comma bases; the result is a mapping.
    """
    mappings = [t if t.variance is Variance.ROW else dual(t) for t in temperaments]
    basis = domain_basis_intersection(*(get_domain_basis(t) for t in temperaments))
    rebased = [change_domain_basis_for_m(m, basis) for m in mappings]
    stacked = tuple(row for m in rebased for row in m.matrix)
    return canonical_form(Temperament(stacked, Variance.ROW, basis))


def comma_merge(*temperaments: Temperament) -> Temperament:
    """The meet: stack the temperaments' comma bases and canonicalize.

    Inputs may be mappings or comma bases; the result is a comma basis.
    """
    comma_bases = [t if t.variance is Variance.COL else dual(t) for t in temperaments]
    basis = domain_basis_merge(*(get_domain_basis(t) for t in temperaments))
    rebased = [change_domain_basis_for_c(c, basis) for c in comma_bases]
    stacked = tuple(row for c in rebased for row in c.matrix)
    return canonical_form(Temperament(stacked, Variance.COL, basis))
