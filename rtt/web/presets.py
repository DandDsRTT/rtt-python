"""Curated preset lists for the three "preselect" dropdowns.

Each is a small, hand-picked menu the UI offers as a quick way to set one of the
three things you actually *choose* (the rest of the grid is derived):

* :data:`TEMPERAMENTS_BY_LIMIT` — named temperaments grouped by prime limit, each
  given by its defining comma basis (monzos over the limit's primes). Loaded via
  :func:`rtt.web.service.from_comma_basis`, so the mapping is the canonical dual;
  the sign/form of the commas is irrelevant (they span the same nullspace). Keyed
  as ``"limit:name"`` so the same name (e.g. Miracle) can appear at several limits.
* :data:`TUNING_SCHEMES` — tuning-scheme names in the systematic naming scheme of
  D&D's Guide (and this library), e.g. ``minimax-S`` (the all-interval log-product
  scheme) or ``minimax-sopfr-S``.
* :data:`TARGET_SETS` — target interval set families the service can resolve
  against the current domain (see :func:`rtt.web.service.target_interval_set`); an
  optional numeric limit (the N in ``N-TILT`` / ``N-OLD``) overrides the default.

These are deliberately short starter menus; the design intends a fuller curated
list later.
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
    """The tuning-scheme names the preselect offers. Every scheme whose interval complexity
    isn't the plain log-product (``lp``) is an alternative-complexity scheme, gated behind
    the alternative-complexity feature: with ``include_alternatives`` false only the
    strictly-lp schemes are offered, keeping the app log-product-only until that feature
    ships; with it true, the whole family."""
    if include_alternatives:
        return TUNING_SCHEMES
    return tuple(s for s in TUNING_SCHEMES if service.complexity_name_of(s) == "lp")

TARGET_SETS: tuple[str, ...] = ("TILT", "OLD")

# prime limit -> ((name, comma basis), ...). A comma basis of nc monzos over the
# limit's d primes makes a rank-(d - nc) temperament. Commas given as the standard
# defining ones for each name (verified to temper out in test_web_presets).
TEMPERAMENTS_BY_LIMIT: tuple[tuple[int, tuple[tuple[str, tuple[tuple[int, ...], ...]], ...]], ...] = (
    (5, (
        ("Meantone", ((-4, 4, -1),)),                            # 81/80
        ("Porcupine", ((1, -5, 3),)),                            # 250/243
        ("Augmented", ((7, 0, -3),)),                            # 128/125
        ("Diminished", ((3, 4, -4),)),                           # 648/625
        ("Blackwood", ((8, -5, 0),)),                            # 256/243
        ("Mavila", ((-7, 3, 1),)),                               # 135/128
        ("Magic", ((-10, -1, 5),)),                              # 3125/3072
        ("Hanson", ((-6, -5, 6),)),                              # 15625/15552
        ("Tetracot", ((5, -9, 4),)),                             # 20000/19683
        ("Helmholtz", ((-15, 8, 1),)),                           # 32805/32768
        ("Würschmidt", ((17, 1, -8),)),                          # 393216/390625
    )),
    (7, (
        ("Septimal Meantone", ((-4, 4, -1, 0), (1, 2, -3, 1))),  # 81/80, 126/125
        ("Miracle", ((-5, 2, 2, -1), (-10, 1, 0, 3))),           # 225/224, 1029/1024
        ("Pajara", ((1, 0, 2, -2), (6, -2, 0, -1))),             # 50/49, 64/63
        ("Augene", ((7, 0, -3, 0), (6, -2, 0, -1))),             # 128/125, 64/63
        ("Marvel", ((-5, 2, 2, -1),)),                           # 225/224 (rank 3)
        ("Starling", ((1, 2, -3, 1),)),                          # 126/125 (rank 3)
    )),
    (11, (
        ("Miracle", ((-5, 2, 2, -1, 0), (-10, 1, 0, 3, 0), (-7, -1, 1, 1, 1))),  # +385/384
        ("Marvel", ((-5, 2, 2, -1, 0), (-7, -1, 1, 1, 1))),      # 225/224, 385/384 (rank 3)
    )),
    (13, (
        ("Marvel", ((-5, 2, 2, -1, 0, 0), (-7, -1, 1, 1, 1, 0), (-2, -4, 2, 0, 0, 1))),  # +325/324
    )),
)

# chooser value ``"limit:name"`` -> comma basis, for loading and matching.
TEMPERAMENT_COMMAS: dict[str, tuple[tuple[int, ...], ...]] = {
    f"{limit}:{name}": commas
    for limit, group in TEMPERAMENTS_BY_LIMIT
    for name, commas in group
}


# prefix marking a temperament-chooser value as a prime-limit divider header rather
# than a pickable preset (the chooser renders these as disabled, non-selectable rows).
_DIVIDER_PREFIX = "hdr:"


def is_divider(value: str) -> bool:
    """Whether a temperament-chooser value is an inert prime-limit divider header
    (see :func:`temperament_options`) rather than a pickable preset."""
    return value.startswith(_DIVIDER_PREFIX)


def temperament_options() -> dict[str, str]:
    """Ordered ``{value: label}`` for the temperament chooser: a divider row before
    each prime-limit group, then the temperaments in it. The divider rows carry the
    :data:`_DIVIDER_PREFIX` so the chooser renders them disabled — they read as group
    headers without being pickable values (see :func:`is_divider`)."""
    options: dict[str, str] = {}
    for limit, group in TEMPERAMENTS_BY_LIMIT:
        options[f"{_DIVIDER_PREFIX}{limit}"] = f"── {limit}-limit ──"
        for name, _ in group:
            options[f"{limit}:{name}"] = name
    return options


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
