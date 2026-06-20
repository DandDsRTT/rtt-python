from __future__ import annotations

import functools

from rtt.app import service
from rtt.library import equal_temperament

TUNING_SCHEMES: tuple[str, ...] = (
    "minimax-S",
    "minimax-ES",
    "held-octave minimax-ES",
    "destretched-octave minimax-ES",
    "minimax-E-copfr-S",
    "minimax-sopfr-S",
    "minimax-lils-S",
    "minimax-E-lils-S",
)


def tuning_schemes(include_alternatives: bool) -> tuple[str, ...]:
    if include_alternatives:
        return TUNING_SCHEMES
    return tuple(s for s in TUNING_SCHEMES if service.complexity_name_of(s) == "lp")


def prescaler_options(include_alternatives: bool) -> tuple[str, ...]:
    if include_alternatives:
        return tuple(service.PRESCALERS)
    return ("log-prime",)

TARGET_SETS: tuple[str, ...] = ("TILT", "OLD")

TEMPERAMENTS_BY_LIMIT: tuple[tuple[int, tuple[tuple[str, tuple[tuple[int, ...], ...]], ...]], ...] = (
    (5, (
        ("Dicot", ((-3, -1, 2),)),
        ("Meantone", ((-4, 4, -1),)),
        ("Augmented", ((7, 0, -3),)),
        ("Mavila", ((-7, 3, 1),)),
        ("Porcupine", ((1, -5, 3),)),
        ("Blackwood", ((8, -5, 0),)),
        ("Diminished", ((3, 4, -4),)),
        ("Srutal", ((11, -4, -2),)),
        ("Magic", ((-10, -1, 5),)),
        ("Ripple", ((-1, 8, -5),)),
        ("Hanson", ((-6, -5, 6),)),
        ("Negri", ((-14, 3, 4),)),
        ("Tetracot", ((5, -9, 4),)),
        ("Superpyth", ((12, -9, 1),)),
        ("Helmholtz", ((-15, 8, 1),)),
        ("Sensi", ((2, 9, -7),)),
        ("Passion", ((18, -4, -5),)),
        ("Würschmidt", ((17, 1, -8),)),
        ("Compton", ((-19, 12, 0),)),
        ("Amity", ((9, -13, 5),)),
        ("Orson", ((-21, 3, 7),)),
        ("Father", ((4, -1, -1),)),
        ("Bug", ((0, 3, -2),)),
        ("Vishnu", ((23, 6, -14),)),
        ("Luna", ((38, -2, -15),)),
    )),
    (7, (
        ("Blacksmith", ((2, -3, 0, 1), (-4, -1, 0, 2))),
        ("Diminished", ((2, 2, -1, -1), (1, 0, 2, -2))),
        ("Dominant", ((2, 2, -1, -1), (6, -2, 0, -1))),
        ("August", ((2, 2, -1, -1), (7, 0, -3, 0))),
        ("Pajara", ((1, 0, 2, -2), (6, -2, 0, -1))),
        ("Semaphore", ((-4, -1, 0, 2), (-4, 4, -1, 0))),
        ("Septimal Meantone", ((-4, 4, -1, 0), (1, 2, -3, 1))),
        ("Injera", ((1, 0, 2, -2), (-4, 4, -1, 0))),
        ("Negri", ((-4, -1, 0, 2), (-5, 2, 2, -1))),
        ("Augene", ((6, -2, 0, -1), (1, 2, -3, 1))),
        ("Keemun", ((-4, -1, 0, 2), (1, 2, -3, 1))),
        ("Catler", ((-4, 4, -1, 0), (7, 0, -3, 0))),
        ("Hedgehog", ((1, 0, 2, -2), (0, -5, 1, 2))),
        ("Superpyth", ((6, -2, 0, -1), (0, -5, 1, 2))),
        ("Sensi", ((1, 2, -3, 1), (0, -5, 1, 2))),
        ("Lemba", ((1, 0, 2, -2), (-9, 1, 2, 1))),
        ("Porcupine", ((6, -2, 0, -1), (1, -5, 3, 0))),
        ("Flattone", ((-4, 4, -1, 0), (-9, 1, 2, 1))),
        ("Magic", ((-5, 2, 2, -1), (0, -5, 1, 2))),
        ("Doublewide", ((1, 0, 2, -2), (-5, -3, 3, 1))),
        ("Nautilus", ((-4, -1, 0, 2), (1, -5, 3, 0))),
        ("Beatles", ((6, -2, 0, -1), (1, -3, -2, 3))),
        ("Liese", ((-4, 4, -1, 0), (1, -3, -2, 3))),
        ("Mothra", ((-4, 4, -1, 0), (-10, 1, 0, 3))),
        ("Orwell", ((-5, 2, 2, -1), (6, 3, -1, -3))),
        ("Garibaldi", ((-5, 2, 2, -1), (0, -2, 5, -3))),
        ("Myna", ((1, 2, -3, 1), (6, 3, -1, -3))),
        ("Miracle", ((-5, 2, 2, -1), (-10, 1, 0, 3))),
        ("Ennealimmal", ((-5, -1, -2, 4), (-1, -7, 4, 1))),
        ("Marvel", ((-5, 2, 2, -1),)),
        ("Starling", ((1, 2, -3, 1),)),
    )),
    (11, (
        ("Miracle", ((-5, 2, 2, -1, 0), (-10, 1, 0, 3, 0), (-7, -1, 1, 1, 1))),
        ("Marvel", ((-5, 2, 2, -1, 0), (-7, -1, 1, 1, 1))),
    )),
    (13, (
        ("Marvel", ((-5, 2, 2, -1, 0, 0), (-7, -1, 1, 1, 1, 0), (-2, -4, 2, 0, 0, 1))),
    )),
)

TEMPERAMENT_COMMAS: dict[str, tuple[tuple[int, ...], ...]] = {
    f"{limit}:{name}": commas
    for limit, group in TEMPERAMENTS_BY_LIMIT
    for name, commas in group
}


_DIVIDER_PREFIX = "hdr:"


def is_divider(value: str) -> bool:
    return value.startswith(_DIVIDER_PREFIX)


def temperament_options() -> dict[str, str]:
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
        options[f"{limit}:{name}"] = name.lower()
    return options


def tuning_scheme_options(all_interval: bool, include_alternatives: bool, weighting: bool) -> dict[str, str]:
    families = tuning_schemes(include_alternatives)
    if all_interval:
        return {name: name for name in families}
    return {
        variant: f"T {variant}"
        for name in families
        for variant in service.weight_slope_variants(name, weighting)
    }


ESTABLISHED_PROJECTIONS: dict[str, dict[str, tuple[str, ...]]] = {
    "5:Meantone": {
        "Pythagorean": ("2/1", "3/2"),
        "1/7-comma": ("2/1", "135/128"),
        "1/6-comma": ("2/1", "45/32"),
        "1/5-comma": ("2/1", "15/8"),
        "2/9-comma": ("2/1", "75/64"),
        "1/4-comma": ("2/1", "5/4"),
        "2/7-comma": ("2/1", "25/24"),
        "1/3-comma": ("2/1", "6/5"),
    },
}


def projection_candidate_ratios(state) -> tuple[str, ...]:
    seen: dict[str, None] = {}
    for ratios in ESTABLISHED_PROJECTIONS.get(identify(state), {}).values():
        for ratio in ratios:
            seen.setdefault(ratio, None)
    return tuple(seen)


def established_projections(state) -> dict[str, tuple[str, ...]]:
    candidates = ESTABLISHED_PROJECTIONS.get(identify(state), {})
    return {name: ratios for name, ratios in candidates.items()
            if service.tuning_projection(state, ratios) is not None}


def projection_options(state) -> dict[str, str]:
    return {name: name for name in established_projections(state)}


def projection_held_ratios(state, name: str | None) -> tuple[str, ...] | None:
    return established_projections(state).get(name) if name else None


def identify_established_projection(state, held_ratios) -> str | None:
    current = service.tuning_projection(state, held_ratios)
    if current is None:
        return None
    return next((name for name, ratios in established_projections(state).items()
                 if service.tuning_projection(state, ratios) == current), None)


@functools.lru_cache(maxsize=1)
def _signature_to_value() -> dict[tuple[tuple[int, ...], ...], str]:
    return {
        service.from_mapping(service.from_comma_basis(commas).mapping).comma_basis: value
        for value, commas in TEMPERAMENT_COMMAS.items()
    }


def identify(state) -> str | None:
    signature = service.from_mapping(state.mapping).comma_basis
    return _signature_to_value().get(signature)



CURATED_COMMAS: tuple[tuple[str, str], ...] = (
    ("father", "16/15"),
    ("bug", "27/25"),
    ("dicot", "25/24"),
    ("mavila", "135/128"),
    ("blackwood", "256/243"),
    ("porcupine", "250/243"),
    ("syntonic", "81/80"),
    ("diaschisma", "2048/2025"),
    ("magic", "3125/3072"),
    ("lesser diesis", "128/125"),
    ("greater diesis", "648/625"),
    ("negri", "16875/16384"),
    ("tetracot", "20000/19683"),
    ("superpyth", "20480/19683"),
    ("kleisma", "15625/15552"),
    ("amity", "1600000/1594323"),
    ("ripple", "6561/6250"),
    ("semicomma", "2109375/2097152"),
    ("schisma", "32805/32768"),
    ("sensipent", "78732/78125"),
    ("würschmidt", "393216/390625"),
    ("passion", "262144/253125"),
    ("Pythagorean", "531441/524288"),
    ("Archytas'", "64/63"),
    ("septimal diesis", "36/35"),
    ("jubilisma", "50/49"),
    ("slendro diesis", "49/48"),
    ("marvel", "225/224"),
    ("starling", "126/125"),
    ("sensamagic", "245/243"),
    ("keema", "875/864"),
    ("gamelisma", "1029/1024"),
    ("orwellisma", "1728/1715"),
    ("hemifamity", "5120/5103"),
    ("octagar", "4000/3969"),
    ("hemimean", "3136/3125"),
    ("porwell", "6144/6125"),
    ("cataharry", "19683/19600"),
    ("ragisma", "4375/4374"),
    ("breedsma", "2401/2400"),
    ("alpharabian", "33/32"),
    ("rastma", "243/242"),
    ("ptolemisma", "100/99"),
    ("mothwellsma", "99/98"),
    ("biyatisma", "121/120"),
    ("valinorsma", "176/175"),
    ("keenanisma", "385/384"),
    ("werckisma", "441/440"),
    ("swetisma", "540/539"),
    ("pentacircle", "896/891"),
    ("kalisma", "9801/9800"),
    ("grossma", "144/143"),
    ("dhanvantarisma", "169/168"),
    ("tridecimal", "1053/1024"),
    ("island", "676/675"),
    ("marveltwin", "325/324"),
    ("minthma", "352/351"),
    ("ratwolfsma", "351/350"),
    ("small tridecimal", "105/104"),
    ("mynucuma", "196/195"),
    ("squbema", "729/728"),
    ("animist", "364/363"),
    ("ibnsinma", "2080/2079"),
    ("tridecimal schisma", "4096/4095"),
)

_MAX_UNIFORM_MAP_EDO = 72
_NOTABLE_EDOS_ABOVE_72: tuple[int, ...] = (
    80, 87, 94, 99, 103, 111, 118, 130, 140, 152, 159, 171, 183, 190, 198, 207,
    217, 224, 270, 282, 311,
)


def _fmt_components(components) -> str:
    return " ".join(str(int(x)) for x in components)


@functools.lru_cache(maxsize=64)
def _commas_in_domain(domain_basis: tuple) -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    d = len(domain_basis)
    out: list[tuple[str, str, tuple[int, ...]]] = []
    for name, ratio in CURATED_COMMAS:
        try:
            vector = service.interval_vector(ratio, d, domain_basis)
        except ValueError:
            continue
        out.append((name, ratio, vector))
    return tuple(out)


@functools.lru_cache(maxsize=64)
def _ets_in_domain(domain_basis: tuple) -> tuple[tuple[str, tuple[int, ...]], ...]:
    out = [
        (equal_temperament.wart_name(n, warts), val)
        for n, warts, val in equal_temperament.uniform_maps(domain_basis, _MAX_UNIFORM_MAP_EDO)
    ]
    out += [
        (equal_temperament.wart_name(n), equal_temperament.patent_val(n, domain_basis))
        for n in _NOTABLE_EDOS_ABOVE_72
    ]
    return tuple(out)


def comma_options(domain_basis) -> dict[str, str]:
    return {
        ratio: f"{name.lower()}  {ratio}  [{_fmt_components(vector)}⟩"
        for name, ratio, vector in _commas_in_domain(tuple(domain_basis))
    }


def et_options(domain_basis) -> dict[str, str]:
    return {
        value: f"{value}  ⟨{_fmt_components(val)}]"
        for value, val in _ets_in_domain(tuple(domain_basis))
    }


def identify_comma(vector, domain_basis) -> str | None:
    target = tuple(int(x) for x in vector)
    negated = tuple(-x for x in target)
    for _name, ratio, curated in _commas_in_domain(tuple(domain_basis)):
        if curated == target or curated == negated:
            return ratio
    return None


def identify_et(val, domain_basis) -> str | None:
    target = tuple(int(x) for x in val)
    for value, curated in _ets_in_domain(tuple(domain_basis)):
        if curated == target:
            return value
    return None


def comma_value_to_vector(value: str, domain_basis) -> tuple[int, ...]:
    return service.interval_vector(value, len(domain_basis), domain_basis)


def et_value_to_val(value: str, domain_basis) -> tuple[int, ...]:
    n, warts = equal_temperament.parse_wart_name(value)
    return equal_temperament.warted_val(n, warts, domain_basis)
