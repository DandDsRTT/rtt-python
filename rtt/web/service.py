"""The sole seam between the web UI and the RTT library.

Everything the front end needs is expressed here in plain tuples/ints/strings so
the UI never imports library types directly. A :class:`TemperamentState` bundles
a temperament's mapping and its dual comma basis (kept in sync) plus dimensions.
"""

from __future__ import annotations

from dataclasses import dataclass

from rtt.dimensions import get_d, get_n, get_r
from rtt.dual import dual
from rtt.formatting import to_ebk
from rtt.generator_detempering import get_generator_detempering
from rtt.math_utils import get_primes, pcv_to_quotient
from rtt.parsing import parse_quotient_list, parse_temperament_data
from rtt.target_intervals import (
    default_old_limit,
    default_tilt_limit,
    process_old,
    process_tilt,
)
from rtt.temperament import Temperament, Variance
from rtt.tuning import (
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
    resolve_tuning_scheme,
)
from rtt.tuning_ranges import get_generator_tuning_range

Matrix = tuple[tuple[int, ...], ...]

DEFAULT_TUNING_SCHEME = "minimax-S"  # systematic name for TOP (the as-shipped scheme)
DEFAULT_TARGET_SPEC = "TILT"  # the default target interval set family (tracks the domain)


@dataclass(frozen=True)
class Tuning:
    """The temperament-level tuning — prime maps and generator ranges, independent
    of any interval set."""

    generator_map: tuple[float, ...]  # cents, over the generators
    tuning_map: tuple[float, ...]  # cents, over the domain primes
    just_map: tuple[float, ...]  # cents, over the domain primes
    retuning_map: tuple[float, ...]  # tempered - just, over the primes
    monotone_generator_range: tuple[tuple[float, float], ...] | None  # per generator; None if none exists
    tradeoff_generator_range: tuple[tuple[float, float], ...]  # (low, high) cents per generator


@dataclass(frozen=True)
class IntervalSizes:
    """An interval set's sizes under a tuning; each list runs over the intervals.

    Used for every interval column (targets, commas, other intervals of interest):
    project the set once through the shared prime maps rather than recomputing the
    optimization per set."""

    tempered: tuple[float, ...]  # cents
    just: tuple[float, ...]  # cents
    errors: tuple[float, ...]  # tempered - just
    damage: tuple[float, ...]  # |error| (unity weight)


@dataclass(frozen=True)
class TemperamentState:
    mapping: Matrix
    comma_basis: Matrix
    d: int
    r: int
    n: int


def _to_matrix(rows) -> Matrix:
    return tuple(tuple(int(x) for x in row) for row in rows)


def _state(mapping: Matrix, comma_basis: Matrix) -> TemperamentState:
    m = Temperament(mapping, Variance.ROW)
    return TemperamentState(mapping, comma_basis, get_d(m), get_r(m), get_n(m))


def from_mapping(mapping) -> TemperamentState:
    """State whose source of truth is ``mapping``; comma basis is its dual."""
    mapping = _to_matrix(mapping)
    comma_basis = dual(Temperament(mapping, Variance.ROW)).matrix
    return _state(mapping, comma_basis)


def from_comma_basis(comma_basis) -> TemperamentState:
    """State whose source of truth is ``comma_basis``; mapping is its dual."""
    comma_basis = _to_matrix(comma_basis)
    mapping = dual(Temperament(comma_basis, Variance.COL)).matrix
    return _state(mapping, comma_basis)


def standard_primes(d: int) -> tuple[int, ...]:
    """The first ``d`` primes — the standard prime-limit domain basis (header labels)."""
    return get_primes(d)


def target_interval_set(spec: str, domain_basis) -> tuple[str, ...]:
    """Resolve a target interval set spec against a domain basis, as ratio strings.

    ``spec`` selects the family — a truncated integer-limit triangle (``"TILT"`` /
    ``"N-TILT"``) or an odd-limit diamond (``"OLD"`` / ``"N-OLD"``). With no explicit
    limit the set tracks the domain. ``"TILT"`` is the as-shipped default.
    """
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


def default_target_limit(family: str, domain_basis) -> int:
    """The limit a bare TILT/OLD family resolves to for this domain — the number the
    target chooser shows when no manual limit is set (so it never reads as 'auto')."""
    domain = tuple(domain_basis)
    return default_old_limit(domain) if "OLD" in family else default_tilt_limit(domain)


def _monzos_to_ratios(monzos) -> tuple[str, ...]:
    """Each monzo as a ``"num/den"`` ratio string (the shared rendering for
    generators and commas)."""
    ratios = []
    for monzo in monzos:
        quotient = pcv_to_quotient(monzo)
        ratios.append(f"{quotient.numerator}/{quotient.denominator}")
    return tuple(ratios)


def generators(mapping) -> tuple[str, ...]:
    """Each generator as an approximate ratio string, e.g. ``('2/1', '2/3')``."""
    m = Temperament(_to_matrix(mapping), Variance.ROW)
    return _monzos_to_ratios(get_generator_detempering(m).matrix)


def comma_ratios(comma_basis) -> tuple[str, ...]:
    """Each comma in the basis as a ratio string, e.g. ``('80/81',)`` — the
    comma-column analogue of :func:`generators`. Rendered as-is (the canonical
    dual's sign), so the syntonic comma reads ``80/81`` (a descending interval)."""
    return _monzos_to_ratios(comma_basis)


def _monzos(ratios, d) -> tuple:
    """Parse a ratio list into monzos over the first ``d`` primes (``()`` if empty)."""
    return parse_quotient_list("{" + ", ".join(ratios) + "}", d)


def _over(prime_map, monzo):
    """Project a monzo through a prime map (their dot product)."""
    return sum(prime_map[p] * monzo[p] for p in range(len(prime_map)))


def _map_through(mapping, monzos) -> Matrix:
    """Map each monzo through ``M`` — columns of monzos taken to generator coords."""
    d = len(mapping[0])
    return tuple(
        tuple(sum(mapping[i][p] * monzo[p] for p in range(d)) for monzo in monzos)
        for i in range(len(mapping))
    )


def mapped_intervals(mapping, ratios) -> Matrix:
    """A ratio-string interval set mapped through ``M`` — the intervals in generator
    coords (r x m). Works for any such set (targets or other intervals of interest);
    the empty set yields one empty generator row per mapping row, keeping the shape."""
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _monzos(ratios, len(mapping[0])))


def mapped_commas(mapping, comma_basis) -> Matrix:
    """Each comma mapped through ``M`` — the comma basis in generator coords (r x nc).
    Every comma the temperament tempers out maps to zero: it vanishes."""
    mapping = _to_matrix(mapping)
    return _map_through(mapping, _to_matrix(comma_basis))


def target_interval_monzos(ratios, d: int) -> Matrix:
    """Each target interval as a monzo — its interval-vector form over the d primes."""
    return tuple(tuple(int(x) for x in monzo) for monzo in _monzos(ratios, d))


def tuning(mapping, scheme: str = DEFAULT_TUNING_SCHEME) -> Tuning:
    """The temperament's prime maps and generator ranges (cents) under ``scheme`` —
    no interval set."""
    t = Temperament(_to_matrix(mapping), Variance.ROW)
    tempered = optimize_tuning_map(t, scheme)
    just = get_just_tuning_map(t)
    return Tuning(
        generator_map=optimize_generator_tuning_map(t, scheme),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


def optimization_power(scheme: str = DEFAULT_TUNING_SCHEME) -> float:
    """The optimization power ``p`` the tuning scheme minimizes: the order of the Lp
    norm taken over the damages — ∞ for a minimax scheme, 2 for least-squares
    (miniRMS), 1 for miniaverage."""
    return resolve_tuning_scheme(scheme).optimization_power


def interval_sizes(tun: Tuning, ratios) -> IntervalSizes:
    """Project an interval set through ``tun`` — its tempered/just sizes, error, damage."""
    monzos = _monzos(ratios, len(tun.tuning_map))
    tempered = tuple(_over(tun.tuning_map, m) for m in monzos)
    just = tuple(_over(tun.just_map, m) for m in monzos)
    errors = tuple(t_ - j for t_, j in zip(tempered, just))
    return IntervalSizes(tempered, just, errors, tuple(abs(e) for e in errors))


def plain_text_values(
    state: TemperamentState,
    scheme: str = DEFAULT_TUNING_SCHEME,
    target_spec: str = DEFAULT_TARGET_SPEC,
) -> dict[tuple[str, str], str]:
    """Each value group's natural plain-text form, keyed by its ``(row, column)``
    tile (the same vocabulary the spreadsheet layout uses). The grid and this text
    show the same numbers two ways — the EBK string is the inline notation."""
    primes = standard_primes(state.d)
    targets = target_interval_set(target_spec, primes)
    commas = comma_ratios(state.comma_basis)
    mapped = mapped_intervals(state.mapping, targets)
    mapped_comma = mapped_commas(state.mapping, state.comma_basis)
    target_monzos = target_interval_monzos(targets, state.d)
    tun = tuning(state.mapping, scheme)  # prime maps, shared by both interval sets
    target_sizes = interval_sizes(tun, targets)
    comma_sizes = interval_sizes(tun, commas)  # comma sizes, like the grid's commas column
    # Keyed by the tile each value group occupies. The interval-vectors row holds the
    # monzo lists (close ⟩); the mapping row holds the mapping (a list of maps, close ])
    # and the mapped lists (generator-coordinate vectors, close }). The editable duals
    # are the mapping (mapping/primes) and the comma basis (vectors/commas). The
    # quantities-row ratios get a per-column plain text in the layout, not here; the
    # generators (mapping/quantities) carry no plain-text form.
    return {
        ("quantities", "primes"): ".".join(str(p) for p in primes),
        ("vectors", "commas"): _ket_list(state.comma_basis, "⟩"),
        ("vectors", "targets"): _ket_list(target_monzos, "⟩"),
        ("mapping", "primes"): to_ebk(Temperament(state.mapping, Variance.ROW)),
        ("mapping", "commas"): _ket_list(zip(*mapped_comma), "}"),
        ("mapping", "targets"): _ket_list(zip(*mapped), "}"),
        ("tuning", "gens"): _cents_genmap(tun.generator_map),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(comma_sizes.tempered),
        ("tuning", "targets"): _cents_list(target_sizes.tempered),
        ("just", "primes"): _cents_map(tun.just_map),
        ("just", "commas"): _cents_list(comma_sizes.just),
        ("just", "targets"): _cents_list(target_sizes.just),
        ("retune", "primes"): _cents_map(tun.retuning_map),
        ("retune", "commas"): _cents_list(comma_sizes.errors),
        ("retune", "targets"): _cents_list(target_sizes.errors),
        ("damage", "targets"): _cents_list(target_sizes.damage),
    }


def _ket_list(vectors, close: str) -> str:
    """A bracketed list of column vectors: ``[[1 0 0⟩ [0 1 0⟩]`` for monzos (close
    ``⟩``), ``[[1 0} [0 1}]`` for generator-coordinate vectors (close ``}``). The
    outer ``[ ]`` wraps the whole list (even a single vector)."""
    return "[" + " ".join("[" + " ".join(str(x) for x in v) + close for v in vectors) + "]"


def cents(value: float) -> str:
    """A cents quantity at the 3-dp the grid and plain-text views share, so the
    two displays always agree."""
    return f"{value:.3f}"


def _cents_map(values) -> str:
    """A tuning covector over the primes: ``⟨1200.000 1901.955 …]``."""
    return "⟨" + " ".join(cents(v) for v in values) + "]"


def _cents_list(values) -> str:
    """A tuning list over the targets: ``[1200.000 1901.955 …]``."""
    return "[" + " ".join(cents(v) for v in values) + "]"


def _cents_genmap(values) -> str:
    """The generator tuning map: ``{1201.699 697.564]`` — curly open, square close,
    per the mockup (distinct from the primes' covector ``⟨ … ]``)."""
    return "{" + " ".join(cents(v) for v in values) + "]"


def _int_matrix_or_none(matrix) -> Matrix | None:
    """A rectangular all-integer matrix, or None — the validity gate for an edited
    plain-text mapping/comma-basis string (Fractions, decimals, blanks, or a ragged
    shape are rejected so the caller can flag the input rather than apply it)."""
    if not matrix or not all(matrix):
        return None
    width = len(matrix[0])
    rows = []
    for row in matrix:
        if len(row) != width:
            return None
        if any(isinstance(x, bool) or not isinstance(x, int) for x in row):
            return None
        rows.append(tuple(row))
    return tuple(rows)


def parse_mapping(text: str) -> Matrix | None:
    """Read an EBK *map* string (e.g. ``[⟨1 1 0] ⟨0 1 4]}``) back to a mapping
    matrix, or None if it is unparseable, the wrong variance (a vector, not a map),
    or not an integer matrix. The inverse of the ``("mapping", "primes")`` plain text."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.ROW:
        return None
    return _int_matrix_or_none(t.matrix)


def parse_comma_basis(text: str) -> Matrix | None:
    """Read an EBK *vector* string (e.g. ``[4 -4 1⟩``) back to a comma basis, or
    None if unparseable, the wrong variance (a map, not a vector), or non-integer.
    The inverse of the ``("vectors", "commas")`` plain text."""
    try:
        t = parse_temperament_data(text)
    except Exception:
        return None
    if t.variance is not Variance.COL:
        return None
    return _int_matrix_or_none(t.matrix)


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim each comma, then re-dual."""
    shrunk = tuple(comma[:-1] for comma in state.comma_basis)
    return from_comma_basis(shrunk)


def remove_comma(state: TemperamentState) -> TemperamentState:
    """Drop the last comma from the basis, then re-dual — raising rank as nullity
    falls (the temperament tempers out one fewer comma). Adding a comma is the
    Editor's job (it stages a pending draft and commits it once valid), not a service
    primitive, since an arbitrary blank comma would be dependent and re-rank nothing.
    Callers guard against removing the sole comma."""
    return from_comma_basis(state.comma_basis[:-1])
