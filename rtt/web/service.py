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
from rtt.parsing import parse_quotient_list
from rtt.target_intervals import process_old, process_tilt
from rtt.temperament import Temperament, Variance
from rtt.tuning import (
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
)
from rtt.tuning_ranges import get_generator_tuning_range

Matrix = tuple[tuple[int, ...], ...]

DEFAULT_TUNING_SCHEME = "TOP"
DEFAULT_TARGET_SPEC = "TILT"  # the default target-interval set family (tracks the domain)


@dataclass(frozen=True)
class Tuning:
    generator_map: tuple[float, ...]  # cents, over the generators
    tuning_map: tuple[float, ...]  # cents, over the domain primes
    just_map: tuple[float, ...]  # cents, over the domain primes
    retuning_map: tuple[float, ...]  # tempered - just, over the primes
    tempered_targets: tuple[float, ...]  # cents, over the target intervals
    just_targets: tuple[float, ...]  # cents, over the target intervals
    target_errors: tuple[float, ...]  # tempered - just, over the targets
    target_damage: tuple[float, ...]  # |error| (unity weight), over the targets
    monotone_generator_range: tuple[tuple[float, float], ...] | None  # per generator; None if none exists
    tradeoff_generator_range: tuple[tuple[float, float], ...]  # (low, high) cents per generator


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
    """Resolve a target-interval set spec against a domain basis, as ratio strings.

    ``spec`` selects the family — a truncated integer-limit triangle (``"TILT"`` /
    ``"N-TILT"``) or an odd-limit diamond (``"OLD"`` / ``"N-OLD"``). With no explicit
    limit the set tracks the domain. ``"TILT"`` is the as-shipped default.
    """
    domain = tuple(domain_basis)
    quotients = process_old(spec, domain) if "OLD" in spec else process_tilt(spec, domain)
    return tuple(f"{q.numerator}/{q.denominator}" for q in quotients)


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


def mapped_target_intervals(mapping, ratios) -> Matrix:
    """Each target interval mapped through ``M`` — the targets in generator coords (r x k)."""
    mapping = _to_matrix(mapping)
    d = len(mapping[0])
    monzos = parse_quotient_list("{" + ", ".join(ratios) + "}", d)
    return tuple(
        tuple(sum(mapping[i][p] * monzo[p] for p in range(d)) for monzo in monzos)
        for i in range(len(mapping))
    )


def tuning(mapping, ratios, scheme: str = DEFAULT_TUNING_SCHEME) -> Tuning:
    """All tuning-row values (cents) for the temperament under ``scheme``."""
    t = Temperament(_to_matrix(mapping), Variance.ROW)
    d = get_d(t)
    tempered = optimize_tuning_map(t, scheme)
    just = get_just_tuning_map(t)
    monzos = parse_quotient_list("{" + ", ".join(ratios) + "}", d)

    def over(prime_map, monzo):
        return sum(prime_map[p] * monzo[p] for p in range(d))

    tempered_targets = tuple(over(tempered, m) for m in monzos)
    just_targets = tuple(over(just, m) for m in monzos)
    errors = tuple(t_ - j for t_, j in zip(tempered_targets, just_targets))
    return Tuning(
        generator_map=optimize_generator_tuning_map(t, scheme),
        tuning_map=tempered,
        just_map=just,
        retuning_map=tuple(t_ - j for t_, j in zip(tempered, just)),
        tempered_targets=tempered_targets,
        just_targets=just_targets,
        target_errors=errors,
        target_damage=tuple(abs(e) for e in errors),
        monotone_generator_range=get_generator_tuning_range(t, "monotone"),
        tradeoff_generator_range=get_generator_tuning_range(t, "tradeoff"),
    )


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
    gens = generators(state.mapping)
    mapped = mapped_target_intervals(state.mapping, targets)
    tun = tuning(state.mapping, targets, scheme)
    ctun = tuning(state.mapping, commas)  # comma sizes, like the grid's commas column
    return {
        ("quantities", "primes"): ".".join(str(p) for p in primes),
        ("quantities", "commas"): "{" + ", ".join(commas) + "}",
        ("quantities", "targets"): "{" + ", ".join(targets) + "}",
        ("mapping", "gens"): "[" + ", ".join(f"~{g}" for g in gens) + "]",
        ("mapping", "primes"): to_ebk(Temperament(state.mapping, Variance.ROW)),
        ("mapping", "commas"): to_ebk(Temperament(state.comma_basis, Variance.COL)),
        ("mapping", "targets"): _vector_list(mapped),
        ("tuning", "primes"): _cents_map(tun.tuning_map),
        ("tuning", "commas"): _cents_list(ctun.tempered_targets),
        ("tuning", "targets"): _cents_list(tun.tempered_targets),
        ("just", "primes"): _cents_map(tun.just_map),
        ("just", "commas"): _cents_list(ctun.just_targets),
        ("just", "targets"): _cents_list(tun.just_targets),
        ("retune", "primes"): _cents_map(tun.retuning_map),
        ("retune", "commas"): _cents_list(ctun.target_errors),
        ("retune", "targets"): _cents_list(tun.target_errors),
        ("damage", "commas"): _cents_list(ctun.target_damage),
        ("damage", "targets"): _cents_list(tun.target_damage),
    }


def _vector_list(matrix: Matrix) -> str:
    """A list of column vectors ``[[a b] [c d] …]`` — the mapped target-interval
    list, each target shown in generator coordinates."""
    cols = zip(*matrix)
    return "[" + " ".join("[" + " ".join(str(x) for x in col) + "]" for col in cols) + "]"


def _cents(value: float) -> str:
    return f"{value:.2f}"  # the 2-dp the grid shows, so text and grid agree


def _cents_map(values) -> str:
    """A tuning covector over the primes: ``⟨1200.00 1901.95 …]``."""
    return "⟨" + " ".join(_cents(v) for v in values) + "]"


def _cents_list(values) -> str:
    """A tuning list over the targets: ``[1200.00 1901.95 …]``."""
    return "[" + " ".join(_cents(v) for v in values) + "]"


def expand_domain(state: TemperamentState) -> TemperamentState:
    """Add the next prime to the domain: append a 0 to each comma, then re-dual."""
    expanded = tuple(comma + (0,) for comma in state.comma_basis)
    return from_comma_basis(expanded)


def shrink_domain(state: TemperamentState) -> TemperamentState:
    """Drop the highest prime from the domain: trim each comma, then re-dual."""
    shrunk = tuple(comma[:-1] for comma in state.comma_basis)
    return from_comma_basis(shrunk)


def add_comma(state: TemperamentState) -> TemperamentState:
    """Append a blank comma to the basis (a zero monzo) for the user to fill in,
    then re-dual. The zero comma is dependent, so rank holds until it is edited to
    an independent interval — at which point nullity rises and rank falls."""
    extended = state.comma_basis + ((0,) * state.d,)
    return from_comma_basis(extended)


def remove_comma(state: TemperamentState) -> TemperamentState:
    """Drop the last comma from the basis, then re-dual — the inverse of
    :func:`add_comma`. Raising rank as nullity falls (the temperament tempers out
    one fewer comma). Callers guard against removing the sole comma."""
    return from_comma_basis(state.comma_basis[:-1])
