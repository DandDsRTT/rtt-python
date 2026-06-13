"""The :class:`TemperamentState` bundle, its constructors, and the state edit operations.

A state bundles a temperament's mapping and its dual comma basis (kept in sync) plus
dimensions; the edit operations (domain walking, comma/mapping-row add/remove, domain
basis element editing, unimodular drag ops) each return a fresh state."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import sympy as sp

from rtt.library.dimensions import get_d, get_n, get_r
from rtt.library.domain_basis import (
    express_quotients_in_domain_basis,
    get_domain_basis,
    get_simplest_prime_only_basis,
    is_standard_prime_limit_domain_basis,
)
from rtt.library.dual import dual
from rtt.library.formatting import to_ebk
from rtt.library.matrix_utils import Matrix
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

from rtt.app.service.core import _to_matrix, is_standard_domain, standard_primes


@dataclass(frozen=True)
class TemperamentState:
    mapping: Matrix
    comma_basis: Matrix
    d: int
    r: int
    n: int
    domain_basis: tuple  # the d basis elements (ints / Fractions); standard primes by default


def _state(mapping: Matrix, comma_basis: Matrix, domain_basis=None) -> TemperamentState:
    m = Temperament(mapping, Variance.ROW, domain_basis)
    return TemperamentState(
        mapping, comma_basis, get_d(m), get_r(m), get_n(m), tuple(get_domain_basis(m))
    )


def from_mapping(mapping, domain_basis=None) -> TemperamentState:
    """State whose source of truth is ``mapping``; comma basis is its dual.

    ``domain_basis`` (a tuple of basis elements, possibly nonprime) names a
    nonstandard domain; ``None`` is the standard prime limit."""
    mapping = _to_matrix(mapping)
    comma_basis = dual(Temperament(mapping, Variance.ROW, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def from_comma_basis(comma_basis, domain_basis=None) -> TemperamentState:
    """State whose source of truth is ``comma_basis``; mapping is its dual."""
    comma_basis = _to_matrix(comma_basis)
    mapping = dual(Temperament(comma_basis, Variance.COL, domain_basis)).matrix
    return _state(mapping, comma_basis, domain_basis)


def from_temperament_data(ebk: str) -> TemperamentState:
    """State parsed from an EBK string, honouring an optional domain-basis prefix
    (e.g. ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"``). A map string is taken as the mapping,
    a vector string as the comma basis; the dual is computed as usual."""
    t = parse_temperament_data(ebk)
    if t.variance is Variance.ROW:
        return from_mapping(t.matrix, t.domain_basis)
    return from_comma_basis(t.matrix, t.domain_basis)


def mapping_ebk(state: TemperamentState) -> str:
    """The temperament's mapping as an EBK string — the editable dual the grid shows and
    the form persistence stores. A nonstandard domain prefixes its basis (e.g.
    ``"2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"``) so the string parses back to the same
    temperament via :func:`parse_mapping_state`."""
    ebk = to_ebk(Temperament(state.mapping, Variance.ROW, state.domain_basis))
    if not is_standard_prime_limit_domain_basis(state.domain_basis):
        ebk = ".".join(str(e) for e in state.domain_basis) + " " + ebk
    return ebk


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim the last component off each comma, then re-dual.
    Trimming can collapse commas that were independent into dependent ones over the smaller domain —
    leaving more comma vectors than the new nullity, which would violate d = r + n and show phantom
    comma columns. So keep only a maximal independent subset (each comma that still raises the
    nullity), preserving the surviving commas' values; an emptied set is full rank — just intonation
    over the smaller domain."""
    independent: list[tuple[int, ...]] = []
    for comma in (c[:-1] for c in state.comma_basis):
        trial = independent + [comma]
        if from_comma_basis(tuple(trial)).n == len(trial):  # this comma adds a new nullity dimension
            independent.append(comma)
    if not independent:
        return just_intonation(standard_primes(state.d - 1))  # nothing tempered survives the trim
    return from_comma_basis(tuple(independent))


def can_shrink_domain(state: TemperamentState) -> bool:
    """Whether the domain − applies to ``state``: a standard prime limit (the prime-walk control
    doesn't fit a nonstandard subgroup) with a prime to spare (a domain keeps at least one prime).
    Dropping the top prime may leave a lower prime tempered to a unison — a degenerate result — but
    that is allowed, just as tempering one out via the comma + is; such states render and tune. The
    single source of truth for both the editor's shrink guard and the renderer's decision to show
    the − (so the button appears exactly when a click would shrink)."""
    return is_standard_domain(state.domain_basis) and state.d > 1


def just_intonation(domain_basis) -> TemperamentState:
    """The untempered temperament over a domain — nothing tempered out, every basis element its
    own generator (the identity mapping), so nullity 0. The endpoint both the comma − (removing the
    last comma) and the mapping + (un-tempering it) arrive at. Built from the identity mapping
    rather than by dualizing an empty comma basis, which can't recover the dimension d — and which
    keeps a nonstandard domain that re-dualing would lose."""
    d = len(domain_basis)
    identity = tuple(tuple(int(row == col) for col in range(d)) for row in range(d))
    return from_mapping(identity, domain_basis)


def remove_comma(state: TemperamentState, index: int = -1) -> TemperamentState:
    """Drop comma ``index`` (the last by default) from the basis, then re-dual — raising
    rank as nullity falls (the temperament tempers out one fewer comma). An arbitrary index
    is the comma-space twin of :func:`remove_mapping_row`, reached by dragging a comma column
    out of the basis (un-tempering it). Adding a comma is the Editor's job (it stages a
    pending draft and commits it once valid), not a service primitive, since an arbitrary
    blank comma would be dependent and re-rank nothing. Removing the SOLE comma un-tempers
    everything — just intonation over the domain (see :func:`just_intonation`)."""
    basis = state.comma_basis
    i = index % len(basis)  # normalize, so the -1 default drops the last comma
    remaining = basis[:i] + basis[i + 1:]
    return from_comma_basis(remaining) if remaining else just_intonation(state.domain_basis)


def remove_mapping_row(state: TemperamentState, i: int) -> TemperamentState:
    """Drop mapping row ``i`` (a generator), keeping the remaining rows as-is and
    re-dualing the comma basis: rank falls, nullity rises, dimensionality held
    (−r, +n). The row-space dual of :func:`remove_comma` (which drops a comma to
    raise rank). Callers guard against removing the sole row. Adding a mapping row
    is the comma-space :func:`remove_comma` reached from the mapping (+r, −n)."""
    kept = state.mapping[:i] + state.mapping[i + 1:]
    return from_mapping(kept)


def add_mapping_row(state: TemperamentState) -> TemperamentState:
    """Add a generator by un-tempering a comma — the row-space face of :func:`remove_comma`:
    dropping the last comma and re-dualing IS adding a generator (+r, −n, dimensionality held).
    Re-dualing (rather than splicing the comma in as a raw row) keeps the generators simple: a raw
    comma row detempers to an astronomically complex ratio. Un-tempering the LAST comma leaves
    just intonation over the d primes. Callers guard on there being a comma (nullity > 0)."""
    return remove_comma(state)  # drop the last comma — the same primitive, viewed from the mapping


# ── domain basis element editing (chapter-9 nonstandard-domain input) ────────────────────────
# When the nonstandard-domain box is on the domain elements are typeable: an element can be
# relabelled in place (a basis relabel that leaves the mapping coordinates untouched) and a new
# element can be added (held just — its own new generator). Both demand the basis stay
# multiplicatively INDEPENDENT, or it names fewer than d directions and d = r + n breaks.

def _as_basis_element(value):
    """Normalize a domain basis element to the storage convention: a bare ``int`` when it is
    integral (a prime/integer like ``7``), else a ``Fraction`` (a nonprime like ``13/5``)."""
    fraction = Fraction(value)
    return fraction.numerator if fraction.denominator == 1 else fraction


def parse_domain_element(text):
    """Parse a typed domain basis element — a positive rational ``≠ 1`` such as ``"7"`` or
    ``"13/5"``. Returns the normalized element (int / Fraction) or ``None`` if it is not a valid
    positive rational (blank, non-numeric, ``≤ 0``, or the unison ``1``, which spans nothing)."""
    try:
        fraction = Fraction(str(text).strip())
    except (ValueError, ZeroDivisionError):
        return None
    if fraction <= 0 or fraction == 1:
        return None
    return _as_basis_element(fraction)


def is_independent_domain_basis(domain_basis) -> bool:
    """Whether the basis elements are multiplicatively independent — no element is a product of
    integer powers of the others, so the d elements really span a d-dimensional domain. A
    dependent basis (e.g. ``2.3.9``, where ``9 = 3²``) is degenerate: it names fewer than d
    independent directions, breaking ``d = r + n``. Tested by the rank of the elements' vectors over
    their simplest prime-only superspace (rank == d iff independent)."""
    elements = tuple(Fraction(e) for e in domain_basis)
    if not elements:
        return False
    superspace = get_simplest_prime_only_basis(tuple(domain_basis))
    vectors = express_quotients_in_domain_basis(elements, superspace)
    return sp.Matrix(vectors).rank() == len(elements)


def can_set_domain_element(state: TemperamentState, index: int, element) -> bool:
    """Whether relabelling basis element ``index`` to ``element`` yields a valid domain — a positive
    rational ``≠ 1`` that leaves the whole basis multiplicatively independent."""
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    trial = state.domain_basis[:index] + (_as_basis_element(parsed),) + state.domain_basis[index + 1:]
    return is_independent_domain_basis(trial)


def set_domain_element(state: TemperamentState, index: int, element) -> TemperamentState:
    """Relabel basis element ``index`` to ``element`` — a pure basis relabel: the mapping
    coordinates are unchanged, they now read over the new element. Callers guard with
    :func:`can_set_domain_element`."""
    new_basis = state.domain_basis[:index] + (_as_basis_element(element),) + state.domain_basis[index + 1:]
    return from_mapping(state.mapping, new_basis)


def can_add_domain_element(state: TemperamentState, element) -> bool:
    """Whether ``element`` can be added to the domain — a positive rational ``≠ 1`` independent of
    the existing basis (a dependent addition would name no new direction)."""
    parsed = parse_domain_element(element) if isinstance(element, str) else element
    if parsed is None:
        return False
    return is_independent_domain_basis(tuple(state.domain_basis) + (_as_basis_element(parsed),))


def add_domain_element(state: TemperamentState, element) -> TemperamentState:
    """Enlarge the domain by one basis element, held just: the element becomes its OWN new
    generator (a unit row), tuned pure, while every existing generator keeps its columns and gains a
    0 over the new element. ``d → d+1``, ``r → r+1``, nullity preserved (``n = d − r``) — the
    superspace 'extra prime held just' construction in the domain-enlarging direction. Callers guard
    with :func:`can_add_domain_element`."""
    new_basis = tuple(state.domain_basis) + (_as_basis_element(element),)
    extended = tuple(tuple(row) + (0,) for row in state.mapping)       # existing gens, 0 over the new element
    new_generator = tuple(0 for _ in range(state.d)) + (1,)            # the new element's own pure generator
    return from_mapping(extended + (new_generator,), new_basis)


def can_remove_domain_element(state: TemperamentState) -> bool:
    """Whether a domain basis element can be removed: a domain keeps at least one element, so the
    only bar is ``d == 1``. Unlike :func:`can_shrink_domain` (the standard prime-walk −, which is
    confined to a standard limit and only drops the TOP prime), this gates the nonstandard-domain
    per-element −, which removes ANY element of ANY basis — removing an element from a
    multiplicatively independent basis always leaves an independent one, so no further check."""
    return state.d > 1


def remove_domain_element(state: TemperamentState, index: int) -> TemperamentState:
    """Drop basis element ``index`` from the domain: trim its component off each comma and off the
    basis, then re-dual over the reduced basis. The arbitrary-index, nonstandard-aware generalization
    of :func:`shrink_domain` (which always drops the last component, re-dualing to a standard limit).
    As there, trimming can collapse independent commas into dependent ones, so keep only a maximal
    independent subset (each comma that still raises the nullity over the reduced basis); an emptied
    set is just intonation over the smaller domain. Inverts :func:`add_domain_element` for the element
    it just added (whose comma column is all-zero, so trimming it recovers the prior state). Callers
    guard with :func:`can_remove_domain_element`."""
    i = index % state.d
    new_basis = state.domain_basis[:i] + state.domain_basis[i + 1:]
    independent: list[tuple[int, ...]] = []
    for comma in (c[:i] + c[i + 1:] for c in state.comma_basis):
        trial = independent + [comma]
        if from_comma_basis(tuple(trial), new_basis).n == len(trial):  # raises the nullity over the reduced basis
            independent.append(comma)
    if not independent:
        return just_intonation(new_basis)  # nothing tempered survives the trim
    return from_comma_basis(tuple(independent), new_basis)


def add_mapping_row_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    """Add generator row ``source`` into row ``target`` (the row dropped onto): ``target``'s
    mapping row becomes ``row[target] + row[source]``. A unimodular row operation, so the
    temperament (its comma basis, rank and nullity) is untouched — only the generator basis
    changes, re-expressing the same tuning over a different generating set. The dragged
    generator's ratio shifts (e.g. the octave dropped onto the fifth becomes a fourth) while the
    target's stays put; callers transform any frozen generator tuning to hold the sound. Callers
    guard ``source != target`` (adding a row to itself would double it, enfactoring the mapping)."""
    rows = [list(row) for row in state.mapping]
    rows[target] = [t + s for t, s in zip(rows[target], rows[source])]
    return from_mapping(rows, state.domain_basis)


def add_comma_to(state: TemperamentState, source: int, target: int) -> TemperamentState:
    """Add comma ``source`` into comma ``target`` (the comma dropped onto): ``target``'s vector
    becomes ``comma[target] + comma[source]``. The dual of :func:`add_mapping_row_to` — a
    unimodular column operation on the comma basis, so the temperament (its mapping, rank and
    nullity) is untouched; only which intervals name the nullspace changes. The mapping is the
    comma basis's dual and is unaffected, so unlike the row op no tuning transform is needed.
    Callers guard ``source != target`` (adding a comma to itself would double it)."""
    commas = [list(comma) for comma in state.comma_basis]
    commas[target] = [t + s for t, s in zip(commas[target], commas[source])]
    return from_comma_basis(commas, state.domain_basis)
