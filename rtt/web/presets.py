"""Curated preset lists for the three preset dropdowns.

Each is a small, hand-picked menu the UI offers as a quick way to set one of the
three things you actually *choose* (the rest of the grid is derived):

* :data:`TEMPERAMENTS_BY_LIMIT` — named temperaments grouped by prime limit, each
  given by its defining comma basis (vectors over the limit's primes). Loaded via
  :func:`rtt.web.service.from_comma_basis`, so the mapping is the canonical dual;
  the sign/form of the commas is irrelevant (they span the same nullspace). Keyed
  as ``"limit:name"`` so the same name (e.g. Miracle) can appear at several limits.
* :data:`TUNING_SCHEMES` — tuning-scheme names in the systematic naming scheme of
  D&D's Guide (and this library), e.g. ``minimax-S`` (the all-interval log-product
  scheme) or ``minimax-sopfr-S``.
* :data:`TARGET_SETS` — target interval set families the service can resolve
  against the current domain (see :func:`rtt.web.service.target_interval_set`); an
  optional numeric limit (the N in ``N-TILT`` / ``N-OLD``) overrides the default.

The temperament menu is the full rank-2 Middle Path catalogue (see
:data:`TEMPERAMENTS_BY_LIMIT` for provenance); the tuning-scheme and target menus
remain short curated starter lists.
"""

from __future__ import annotations

import functools

from rtt.web import service

# Systematic tuning-scheme names (the minimax family, which optimize to sensible
# all-interval tunings). The trailing comment names the interval complexity each is built
# on: minimax-S uses the plain log-product (lp); the rest use other complexities and so
# ride behind the alternative-complexity feature — see :func:`tuning_schemes`.
TUNING_SCHEMES: tuple[str, ...] = (
    "minimax-S",                      # lp (log-product)
    "minimax-ES",                     # E-lp (Euclidean log-product)
    "held-octave minimax-ES",         # E-lp, octave held just
    "destretched-octave minimax-ES",  # E-lp, octave destretched
    "minimax-E-copfr-S",              # E-copfr
    "minimax-sopfr-S",                # sopfr
    "minimax-lils-S",                 # lils
    "minimax-E-lils-S",               # E-lils
)


def tuning_schemes(include_alternatives: bool) -> tuple[str, ...]:
    """The tuning-scheme names the preset chooser offers. Every scheme whose interval complexity
    isn't the plain log-product (``lp``) is an alternative-complexity scheme, gated behind
    the alternative-complexity feature: with ``include_alternatives`` false only the
    strictly-lp schemes are offered, keeping the app log-product-only until that feature
    ships; with it true, the whole family."""
    if include_alternatives:
        return TUNING_SCHEMES
    return tuple(s for s in TUNING_SCHEMES if service.complexity_name_of(s) == "lp")


def prescaler_options(include_alternatives: bool) -> tuple[str, ...]:
    """The prescaler names the chooser offers (keys of :data:`rtt.web.service.PRESCALERS`).
    log-prime is the plain default; the others (identity = unweighted count, prime = sopfr) are
    alternative-complexity prescalers gated behind that feature — so with ``include_alternatives``
    false only log-prime is offered, keeping the app log-prime-only until that feature ships."""
    if include_alternatives:
        return tuple(service.PRESCALERS)
    return ("log-prime",)

TARGET_SETS: tuple[str, ...] = ("TILT", "OLD")

# prime limit -> ((name, comma basis), ...). A comma basis of nc vectors over the
# limit's d primes makes a rank-(d - nc) temperament. Every basis is verified to
# temper out its commas in test_web_presets.
#
# Provenance / selection criteria (this was previously an undocumented hand-picked
# starter menu — "popular temperaments"):
#   * The 5- and 7-limit groups are the complete rank-2 tables of Paul Erlich's "A
#     Middle Path Between Just Intonation and the Equal Temperaments" (Xenharmonikon 18,
#     2006): Table 1 (5-limit) and Table 2 (7-limit). Erlich's "main sequence" is every
#     rank-2 temperament under a combined badness bound (complexity/12 + damage/10 < 1
#     at 5-limit, complexity/24 + damage/10 < 1 at 7-limit), plus the few he calls out
#     as "exotemperaments" (high damage, want custom timbres) and "bonus temperaments"
#     (near-JI microtemperaments). Names are modernized to the current canonical ones
#     (Erlich's Dimipent / Negripent / Sensipent / Cynder / ... -> Diminished / Negri /
#     Sensi / Mothra / ...).
#   * "A Middle Path" Part 2 (11-limit and beyond) was never published, so the 11- and
#     13-limit groups are not from it: they hold notable higher-rank temperaments
#     (Miracle, Marvel) carried over from the original list. Marvel and Starling at
#     7-limit are likewise notable rank-3 temperaments, outside Erlich's rank-2 tables.
TEMPERAMENTS_BY_LIMIT: tuple[tuple[int, tuple[tuple[str, tuple[tuple[int, ...], ...]], ...]], ...] = (
    (5, (
        # --- main sequence ---
        ("Dicot", ((-3, -1, 2),)),                          # 25/24
        ("Meantone", ((-4, 4, -1),)),                       # 81/80
        ("Augmented", ((7, 0, -3),)),                       # 128/125
        ("Mavila", ((-7, 3, 1),)),                          # 135/128
        ("Porcupine", ((1, -5, 3),)),                       # 250/243
        ("Blackwood", ((8, -5, 0),)),                       # 256/243
        ("Diminished", ((3, 4, -4),)),                      # 648/625
        ("Srutal", ((11, -4, -2),)),                        # 2048/2025
        ("Magic", ((-10, -1, 5),)),                         # 3125/3072
        ("Ripple", ((-1, 8, -5),)),                         # 6561/6250
        ("Hanson", ((-6, -5, 6),)),                         # 15625/15552
        ("Negri", ((-14, 3, 4),)),                          # 16875/16384
        ("Tetracot", ((5, -9, 4),)),                        # 20000/19683
        ("Superpyth", ((12, -9, 1),)),                      # 20480/19683
        ("Helmholtz", ((-15, 8, 1),)),                      # 32805/32768
        ("Sensi", ((2, 9, -7),)),                           # 78732/78125
        ("Passion", ((18, -4, -5),)),                       # 262144/253125
        ("Würschmidt", ((17, 1, -8),)),                     # 393216/390625
        ("Compton", ((-19, 12, 0),)),                       # 531441/524288
        ("Amity", ((9, -13, 5),)),                          # 1600000/1594323
        ("Orson", ((-21, 3, 7),)),                          # 2109375/2097152
        # --- exotemperaments (high damage; want custom timbres) ---
        ("Father", ((4, -1, -1),)),                         # 16/15
        ("Bug", ((0, 3, -2),)),                             # 27/25
        # --- bonus temperaments (very accurate, near-JI) ---
        ("Vishnu", ((23, 6, -14),)),                        # 6115295232/6103515625
        ("Luna", ((38, -2, -15),)),                         # 274877906944/274658203125
    )),
    (7, (
        # --- main sequence ---
        ("Blacksmith", ((2, -3, 0, 1), (-4, -1, 0, 2))),    # 28/27, 49/48
        ("Diminished", ((2, 2, -1, -1), (1, 0, 2, -2))),    # 36/35, 50/49
        ("Dominant", ((2, 2, -1, -1), (6, -2, 0, -1))),     # 36/35, 64/63
        ("August", ((2, 2, -1, -1), (7, 0, -3, 0))),        # 36/35, 128/125
        ("Pajara", ((1, 0, 2, -2), (6, -2, 0, -1))),        # 50/49, 64/63
        ("Semaphore", ((-4, -1, 0, 2), (-4, 4, -1, 0))),    # 49/48, 81/80
        ("Septimal Meantone", ((-4, 4, -1, 0), (1, 2, -3, 1))),  # 81/80, 126/125
        ("Injera", ((1, 0, 2, -2), (-4, 4, -1, 0))),        # 50/49, 81/80
        ("Negri", ((-4, -1, 0, 2), (-5, 2, 2, -1))),        # 49/48, 225/224
        ("Augene", ((6, -2, 0, -1), (1, 2, -3, 1))),        # 64/63, 126/125
        ("Keemun", ((-4, -1, 0, 2), (1, 2, -3, 1))),        # 49/48, 126/125
        ("Catler", ((-4, 4, -1, 0), (7, 0, -3, 0))),        # 81/80, 128/125
        ("Hedgehog", ((1, 0, 2, -2), (0, -5, 1, 2))),       # 50/49, 245/243
        ("Superpyth", ((6, -2, 0, -1), (0, -5, 1, 2))),     # 64/63, 245/243
        ("Sensi", ((1, 2, -3, 1), (0, -5, 1, 2))),          # 126/125, 245/243
        ("Lemba", ((1, 0, 2, -2), (-9, 1, 2, 1))),          # 50/49, 525/512
        ("Porcupine", ((6, -2, 0, -1), (1, -5, 3, 0))),     # 64/63, 250/243
        ("Flattone", ((-4, 4, -1, 0), (-9, 1, 2, 1))),      # 81/80, 525/512
        ("Magic", ((-5, 2, 2, -1), (0, -5, 1, 2))),         # 225/224, 245/243
        ("Doublewide", ((1, 0, 2, -2), (-5, -3, 3, 1))),    # 50/49, 875/864
        ("Nautilus", ((-4, -1, 0, 2), (1, -5, 3, 0))),      # 49/48, 250/243
        ("Beatles", ((6, -2, 0, -1), (1, -3, -2, 3))),      # 64/63, 686/675
        ("Liese", ((-4, 4, -1, 0), (1, -3, -2, 3))),        # 81/80, 686/675
        ("Mothra", ((-4, 4, -1, 0), (-10, 1, 0, 3))),       # 81/80, 1029/1024
        ("Orwell", ((-5, 2, 2, -1), (6, 3, -1, -3))),       # 225/224, 1728/1715
        ("Garibaldi", ((-5, 2, 2, -1), (0, -2, 5, -3))),    # 225/224, 3125/3087
        ("Myna", ((1, 2, -3, 1), (6, 3, -1, -3))),          # 126/125, 1728/1715
        ("Miracle", ((-5, 2, 2, -1), (-10, 1, 0, 3))),      # 225/224, 1029/1024
        # --- bonus temperaments (very accurate, near-JI) ---
        ("Ennealimmal", ((-5, -1, -2, 4), (-1, -7, 4, 1))),  # 2401/2400, 4375/4374
        # --- notable rank-3 (the Middle Path tables are rank-2 only) ---
        ("Marvel", ((-5, 2, 2, -1),)),                      # 225/224 (rank 3)
        ("Starling", ((1, 2, -3, 1),)),                     # 126/125 (rank 3)
    )),
    (11, (
        ("Miracle", ((-5, 2, 2, -1, 0), (-10, 1, 0, 3, 0), (-7, -1, 1, 1, 1))),  # 225/224, 1029/1024, 385/384
        # --- notable rank-3 (the Middle Path tables are rank-2 only) ---
        ("Marvel", ((-5, 2, 2, -1, 0), (-7, -1, 1, 1, 1))),  # 225/224, 385/384 (rank 3)
    )),
    (13, (
        # --- notable rank-3 (the Middle Path tables are rank-2 only) ---
        ("Marvel", ((-5, 2, 2, -1, 0, 0), (-7, -1, 1, 1, 1, 0), (-2, -4, 2, 0, 0, 1))),  # 225/224, 385/384, 325/324 (rank 3)
    )),
)

# chooser value ``"limit:name"`` -> comma basis, for loading and matching.
TEMPERAMENT_COMMAS: dict[str, tuple[tuple[int, ...], ...]] = {
    f"{limit}:{name}": commas
    for limit, group in TEMPERAMENTS_BY_LIMIT
    for name, commas in group
}


# prefix marking a temperament-chooser value as a rank-and-limit section divider header
# rather than a pickable preset (the chooser renders these as disabled, non-selectable rows).
_DIVIDER_PREFIX = "hdr:"


def is_divider(value: str) -> bool:
    """Whether a temperament-chooser value is an inert section divider header
    (see :func:`temperament_options`) rather than a pickable preset."""
    return value.startswith(_DIVIDER_PREFIX)


def temperament_options() -> dict[str, str]:
    """Ordered ``{value: label}`` for the temperament chooser: the temperaments grouped
    by rank then prime limit, each group headed by a ``"rank R, L-limit"`` divider row and
    its members shown lowercase. Groups are ordered by rank first, then limit, so every
    rank-2 group precedes the rank-3 ones. A temperament's rank is ``d - nc`` for its
    ``nc`` commas over the limit's ``d`` primes (``d`` = the comma vectors' length). The
    divider rows carry the :data:`_DIVIDER_PREFIX` so the chooser renders them disabled —
    they read as section headers without being pickable values (see :func:`is_divider`).
    The chooser styles each header as a centred row with rules flanking it (CSS in the
    popup), so no decorative dashes are baked into the text."""
    # (rank, limit, name) for every preset; a *stable* sort by (rank, limit) keeps each
    # group's authored order (Erlich's complexity order) within it.
    entries = sorted(
        ((len(commas[0]) - len(commas), limit, name)
         for limit, group in TEMPERAMENTS_BY_LIMIT
         for name, commas in group),
        key=lambda e: (e[0], e[1]),
    )
    options: dict[str, str] = {}
    current: tuple[int, int] | None = None
    for rank, limit, name in entries:
        if (rank, limit) != current:
            current = (rank, limit)
            options[f"{_DIVIDER_PREFIX}{rank}:{limit}"] = f"rank {rank}, {limit}-limit"
        # the value key keeps the canonical proper-name casing (the stable id shared with
        # TEMPERAMENT_COMMAS / identify); only the shown label is lowercased
        options[f"{limit}:{name}"] = name.lower()
    return options


def tuning_scheme_options(all_interval: bool, include_alternatives: bool, weighting: bool) -> dict[str, str]:
    """The established-tuning-scheme chooser's ``{value: label}``. The offered complexity families
    are those of :func:`tuning_schemes` (so alternative-complexity schemes stay gated behind that
    feature). All-interval schemes are simplicity-weighted by construction, so the all-interval
    list is the bare canonical names. The target-based list instead offers each family's weight-slope
    variants (see :func:`rtt.web.service.weight_slope_variants`): all three (T minimax-S / -U / -C)
    with ``weighting`` on, or just the unity variant (T minimax-U) with it off — the simplicity and
    complexity slopes are reachable only through the weighting feature. Labels prefix an upright T (the
    target-list symbol) to mark optimizing over the target list, not every interval. The all-interval
    checkbox flips between the two lists."""
    families = tuning_schemes(include_alternatives)
    if all_interval:
        return {name: name for name in families}
    return {
        variant: f"T {variant}"
        for name in families
        for variant in service.weight_slope_variants(name, weighting)
    }


# Established rational projections / embeddings, keyed by temperament chooser value (see
# :func:`temperament_options`): the recognized rational tunings of each temperament, as
# ``{name: held ratio strings}``. A tuning belongs here only if it holds a FULL-RANK set of
# RATIONAL intervals exactly just (its unchanged-interval basis) — only then is it expressible
# as a rational projection ``P = GM`` and embedding ``G`` (the established-projection chooser
# drives P/G by the chosen tuning's held intervals; see :func:`rtt.web.service.tuning_projection`).
# Most temperaments have NO such established tuning — an OPTIMIZED tuning (minimax-S, minimax-ES …)
# generally holds nothing rational and has no rational projection — so the chooser is empty for
# them, and that is the common case.
#
# Provenance — every entry is computationally verified (idempotent rational P, full rank r,
# non-degenerate, holds exactly its stated intervals, and reproduces the named comma fraction to
# the digit). KEY POINT: a fractional-comma meantone IS a rational projection even though its
# FIFTH is an irrational root — because n fifths reach a RATIONAL interval ((3/2)ⁿ/(81/80)ᵐ for the
# m/n-comma tuning), and THAT is the held unchanged interval. The whole comma-fraction family
# therefore qualifies. Historical names: Pythagorean (0-comma, pure fifth); quarter-comma (Pietro
# Aron, 1523, pure 5/4); 2/7-comma (Zarlino, 1558); third-comma (Salinas, 1577, pure 6/5);
# 1/6-comma (Silbermann); 2/9-comma (Smith, soft attribution); 1/5- and 1/7-comma (standard
# comma-fraction names). Ordered by tempering amount (the fifth flattening from pure). No other
# preset temperament has a literature-named rational tuning (a thorough adversarial search found
# none; the projection is simply dashed out for them — the common case).
ESTABLISHED_PROJECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "5:Meantone": {
        "Pythagorean": ("2/1", "3/2"),       # 0-comma: pure fifth
        "1/7-comma": ("2/1", "135/128"),
        "1/6-comma": ("2/1", "45/32"),       # Silbermann
        "1/5-comma": ("2/1", "15/8"),
        "2/9-comma": ("2/1", "75/64"),       # Smith
        "quarter-comma": ("2/1", "5/4"),     # Aron: pure major third
        "2/7-comma": ("2/1", "25/24"),       # Zarlino
        "third-comma": ("2/1", "6/5"),       # Salinas: pure minor third
    },
}


def established_projections(state) -> dict[str, tuple[str, ...]]:
    """The current temperament's established rational tunings as ``{name: held ratios}`` (see
    :data:`ESTABLISHED_PROJECTIONS`), or ``{}`` when it matches no preset or has none. Only
    entries that actually form a rational projection for this mapping are kept — a degenerate
    hold (one interval mapping to a fraction of another's image) is dropped, never offered."""
    candidates = ESTABLISHED_PROJECTIONS.get(identify(state), {})
    return {name: ratios for name, ratios in candidates.items()
            if service.tuning_projection(state, ratios) is not None}


def projection_options(state) -> dict[str, str]:
    """The established-projection / established-embedding chooser's ``{value: label}``: the
    current temperament's named rational tunings (see :func:`established_projections`), value
    and label both the tuning name. Empty when the temperament has no established rational
    projection — the chooser then shows only its placeholder."""
    return {name: name for name in established_projections(state)}


def projection_held_ratios(state, name: str | None) -> tuple[str, ...] | None:
    """The rational held intervals of the established tuning ``name`` (a value from
    :func:`projection_options`) — the basis the chooser writes into the held column to re-solve
    the tuning — or ``None`` when ``name`` is not a current option."""
    return established_projections(state).get(name) if name else None


def identify_established_projection(state, held_ratios) -> str | None:
    """The named established tuning the current held basis realises — the chooser's displayed
    value — found by matching its projection. ``None`` (the placeholder) when the tuning isn't a
    full rational projection (``P`` dashed, so the held basis is under-rank) or matches no named
    tuning. ``held_ratios`` is the tuning's held-interval basis (scheme held + held column)."""
    current = service.tuning_projection(state, held_ratios)
    if current is None:
        return None
    return next((name for name, ratios in established_projections(state).items()
                 if service.tuning_projection(state, ratios) == current), None)


@functools.lru_cache(maxsize=1)
def _signature_to_value() -> dict[tuple[tuple[int, ...], ...], str]:
    """Each preset's canonical comma-basis signature -> its chooser value. The
    signature is form-independent (re-dualed through the mapping), so any equivalent
    entry of the same temperament matches."""
    return {
        service.from_mapping(service.from_comma_basis(commas).mapping).comma_basis: value
        for value, commas in TEMPERAMENT_COMMAS.items()
    }


def identify(state) -> str | None:
    """The chooser value (``"limit:name"``) whose temperament matches ``state``, by
    canonical comma basis, or None when the current temperament is not a preset."""
    signature = service.from_mapping(state.mapping).comma_basis
    return _signature_to_value().get(signature)
