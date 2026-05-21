from math import inf, log2, sqrt

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import (
    TuningSchemeSpec,
    complexity_name_traits,
    damage_name_traits,
    generator_tuning_map_from_t_and_tuning_map,
    get_complexity,
    get_dual_power,
    get_just_tuning_map,
    optimize_generator_tuning_map,
    optimize_tuning_map,
)
from rtt.temperament import Temperament, Variance

ROW = Variance.ROW
TOL = 1e-3

MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
PAJARA = "[⟨2 3 5 6] ⟨0 1 -2 -2]}"
BLACKWOOD = "[⟨5 8 0] ⟨0 0 1]}"
SRUTAL = "[⟨2 0 11] ⟨0 1 -2]}"
FIVE_OLD = "{2/1, 3/2, 4/3, 5/4, 8/5, 5/3, 6/5}"
SIX_TILT = "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5}"
TEN_TILT = (
    "{2/1, 3/1, 3/2, 4/3, 5/2, 5/3, 5/4, 6/5, 7/3, 7/4, "
    "7/5, 7/6, 8/3, 8/5, 9/4, 9/5, 9/7, 10/7}"
)

# (optimization_power, damage_weight_slope, log_prime_power [5a], norm_power [4], expected)
# Mirrors tests.m 2588-2624: meantone optimized over the sixTilt target-interval set
# across all three powers, three damage-weight slopes, and complexity-trait variants.
EXPLICIT_CASES = [
    (inf, "unityWeight", 1, 1, (1200.000, 696.578)),
    (inf, "simplicityWeight", 0, 1, (1202.390, 697.176)),
    (inf, "simplicityWeight", 0, 2, (1202.728, 697.260)),
    (inf, "simplicityWeight", 1, 1, (1201.699, 697.564)),
    (inf, "simplicityWeight", 1, 2, (1201.600, 697.531)),
    (inf, "complexityWeight", 0, 1, (1197.610, 694.786)),
    (inf, "complexityWeight", 0, 2, (1197.435, 694.976)),
    (inf, "complexityWeight", 1, 1, (1197.979, 694.711)),
    (inf, "complexityWeight", 1, 2, (1198.423, 695.209)),
    (2, "unityWeight", 1, 1, (1202.081, 697.099)),
    (2, "simplicityWeight", 0, 1, (1202.609, 697.329)),
    (2, "simplicityWeight", 0, 2, (1202.729, 697.210)),
    (2, "simplicityWeight", 1, 1, (1201.617, 697.379)),
    (2, "simplicityWeight", 1, 2, (1201.718, 697.214)),
    (2, "complexityWeight", 0, 1, (1200.813, 696.570)),
    (2, "complexityWeight", 0, 2, (1200.522, 696.591)),
    (2, "complexityWeight", 1, 1, (1201.489, 696.662)),
    (2, "complexityWeight", 1, 2, (1201.535, 696.760)),
    (1, "unityWeight", 1, 1, (1204.301, 697.654)),
    (1, "simplicityWeight", 0, 1, (1204.301, 697.654)),
    (1, "simplicityWeight", 0, 2, (1204.301, 697.654)),
    (1, "simplicityWeight", 1, 1, (1200.000, 696.578)),
    (1, "simplicityWeight", 1, 2, (1200.000, 696.578)),
    (1, "complexityWeight", 0, 1, (1200.000, 696.578)),
    (1, "complexityWeight", 0, 2, (1200.000, 696.578)),
    (1, "complexityWeight", 1, 1, (1204.301, 697.654)),
    (1, "complexityWeight", 1, 2, (1204.301, 697.654)),
]


@pytest.mark.parametrize("power, slope, log_prime_power, norm_power, expected", EXPLICIT_CASES)
def test_optimize_generator_tuning_map_explicit(
    power, slope, log_prime_power, norm_power, expected
):
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=power,
        target_intervals=SIX_TILT,
        damage_weight_slope=slope,
        complexity_log_prime_power=log_prime_power,
        complexity_norm_power=norm_power,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Minimax over a larger target set (pajara, 18 intervals) where the plain minimax
# optimum is non-unique: only the nested (lexicographic) minimax pins down these
# generators. Mirrors the exact (non-"quick") pajara cases from tests.m 2633-2645.
NESTED_MINIMAX_CASES = [
    ("unityWeight", 1, 0, (600.000, 108.128)),  # minimax-U
    ("simplicityWeight", 1, 0, (596.502, 106.708)),  # minimax-copfr-S
    ("complexityWeight", 1, 0, (600.581, 107.714)),  # minimax-copfr-C
]


@pytest.mark.parametrize("slope, norm_power, log_prime_power, expected", NESTED_MINIMAX_CASES)
def test_optimize_generator_tuning_map_nested_minimax(
    slope, norm_power, log_prime_power, expected
):
    t = parse_temperament_data(PAJARA)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals=TEN_TILT,
        damage_weight_slope=slope,
        complexity_norm_power=norm_power,
        complexity_log_prime_power=log_prime_power,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Sweeping the interval-complexity norm power (trait 4) for a minimax simplicity-weighted
# meantone tuning. Mirrors tests.m 2800-2806.
NORM_POWER_CONTINUUM = [
    (inf, (1201.191, 697.405)),
    (5.00, (1201.381, 697.460)),
    (3.00, (1201.513, 697.503)),
    (2.00, (1201.600, 697.531)),
    (1.50, (1201.648, 697.547)),
    (1.25, (1201.673, 697.556)),
    (1.00, (1201.699, 697.564)),
]


@pytest.mark.parametrize("norm_power, expected", NORM_POWER_CONTINUUM)
def test_optimize_generator_tuning_map_norm_power_continuum(norm_power, expected):
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals=SIX_TILT,
        damage_weight_slope="simplicityWeight",
        complexity_norm_power=norm_power,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Sweeping the optimization power (trait 2) for a unity-weighted blackwood tuning.
# Mirrors tests.m 2787-2793; powers other than inf/2/1 use the general power-sum method.
POWER_CONTINUUM = [
    (inf, (240.000, 2795.336)),
    (5.00, (239.174, 2787.898)),
    (3.00, (238.745, 2784.044)),
    (2.00, (238.408, 2781.006)),
    (1.50, (238.045, 2777.737)),
    (1.25, (237.793, 2775.471)),
    (1.00, (237.744, 2775.036)),
]


@pytest.mark.parametrize("power, expected", POWER_CONTINUUM)
def test_optimize_generator_tuning_map_power_continuum(power, expected):
    t = parse_temperament_data(BLACKWOOD)
    spec = TuningSchemeSpec(
        optimization_power=power,
        target_intervals=SIX_TILT,
        damage_weight_slope="unityWeight",
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Section "fully by tuningSchemeSystematicName" (tests.m 2633-2677): pajara optimized
# over tenTilt, scheme given as a single systematic-name string. The 6 minimax E/quick
# cases (minimax-E-copfr-S/-S/-ES/-E-copfr-C/-C/-EC) are omitted pending review — the
# library's published values there are provably suboptimal (lower-max-damage proof in the
# mismatch report); judgment suspended.
PAJARA_SYSTEMATIC = [
    ("minimax-U", (600.000, 108.128)),
    ("minimax-copfr-S", (596.502, 106.708)),
    ("minimax-copfr-C", (600.581, 107.714)),
    ("miniRMS-U", (598.247, 106.830)),
    ("miniRMS-copfr-S", (598.488, 106.799)),
    ("miniRMS-E-copfr-S", (598.346, 106.837)),
    ("miniRMS-S", (599.020, 106.492)),
    ("miniRMS-ES", (598.882, 106.594)),
    ("miniRMS-copfr-C", (598.518, 106.789)),
    ("miniRMS-E-copfr-C", (598.655, 106.720)),
    ("miniRMS-C", (597.875, 107.083)),
    ("miniRMS-EC", (597.804, 107.013)),
    ("miniaverage-U", (598.914, 105.214)),
    ("miniaverage-copfr-S", (598.914, 105.214)),
    ("miniaverage-E-copfr-S", (598.914, 105.214)),
    ("miniaverage-S", (598.914, 105.214)),
    ("miniaverage-ES", (598.914, 105.214)),
    ("miniaverage-copfr-C", (598.914, 105.214)),
    ("miniaverage-E-copfr-C", (598.914, 105.214)),
    ("miniaverage-C", (598.603, 106.145)),
    ("miniaverage-EC", (598.603, 106.145)),
]


@pytest.mark.parametrize("scheme_name, expected", PAJARA_SYSTEMATIC)
def test_optimize_generator_tuning_map_systematic_name(scheme_name, expected):
    t = parse_temperament_data(PAJARA)
    assert optimize_generator_tuning_map(
        t, f"{TEN_TILT} {scheme_name}"
    ) == pytest.approx(expected, abs=TOL)


# Section "by damageSystematicName" (tests.m 2684-2720): srutal over sixTilt, damage
# scheme named (slope + complexity) with explicit power. The single L1 tie
# (power 1, copfr-S-damage) is omitted — same total damage, alternate optimal vertex.
SRUTAL_DAMAGE = [
    (inf, "U-damage", (600.000, 1905.214)),
    (inf, "copfr-S-damage", (599.425, 1903.105)),
    (inf, "E-copfr-S-damage", (599.362, 1902.875)),
    (inf, "S-damage", (599.555, 1903.365)),
    (inf, "ES-damage", (599.577, 1903.449)),
    (inf, "copfr-C-damage", (600.752, 1907.971)),
    (inf, "E-copfr-C-damage", (600.863, 1908.379)),
    (inf, "C-damage", (600.413, 1906.917)),
    (inf, "EC-damage", (600.296, 1906.485)),
    (2, "U-damage", (599.131, 1902.390)),
    (2, "copfr-S-damage", (599.219, 1902.515)),
    (2, "E-copfr-S-damage", (599.156, 1902.381)),
    (2, "S-damage", (599.431, 1903.058)),
    (2, "ES-damage", (599.363, 1902.960)),
    (2, "copfr-C-damage", (599.232, 1902.839)),
    (2, "E-copfr-C-damage", (599.247, 1902.882)),
    (2, "C-damage", (599.159, 1902.609)),
    (2, "EC-damage", (599.116, 1902.444)),
    (1, "U-damage", (598.914, 1901.955)),
    (1, "E-copfr-S-damage", (598.914, 1901.955)),
    (1, "S-damage", (599.111, 1901.955)),
    (1, "ES-damage", (598.914, 1901.955)),
    (1, "copfr-C-damage", (598.914, 1901.955)),
    (1, "E-copfr-C-damage", (598.914, 1901.955)),
    (1, "C-damage", (598.914, 1901.955)),
    (1, "EC-damage", (598.914, 1901.955)),
]


@pytest.mark.parametrize("power, damage_name, expected", SRUTAL_DAMAGE)
def test_optimize_generator_tuning_map_damage_name(power, damage_name, expected):
    t = parse_temperament_data(SRUTAL)
    spec = TuningSchemeSpec(
        optimization_power=power, target_intervals=SIX_TILT, **damage_name_traits(damage_name)
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Section "by intervalComplexitySystematicName" (tests.m 2727-2763): blackwood over sixTilt,
# explicit power + slope, complexity named separately ("" = none, for unityWeight). The single
# minimax E-complexity case (power inf, simplicity) is omitted — library used a "quick"
# approximation with higher max damage; judgment suspended.
BLACKWOOD_COMPLEXITY = [
    (inf, "unityWeight", "", (240.000, 2795.336)),
    (inf, "simplicityWeight", "copfr-complexity", (238.612, 2784.926)),
    (inf, "simplicityWeight", "copfr-E-complexity", (238.445, 2783.722)),
    (inf, "simplicityWeight", "complexity", (238.867, 2785.650)),
    (inf, "complexityWeight", "copfr-complexity", (241.504, 2811.877)),
    (inf, "complexityWeight", "copfr-E-complexity", (241.702, 2812.251)),
    (inf, "complexityWeight", "complexity", (241.209, 2808.887)),
    (inf, "complexityWeight", "E-complexity", (240.981, 2805.237)),
    (2, "unityWeight", "", (238.408, 2781.006)),
    (2, "simplicityWeight", "copfr-complexity", (238.316, 2781.797)),
    (2, "simplicityWeight", "copfr-E-complexity", (238.248, 2781.458)),
    (2, "simplicityWeight", "complexity", (238.779, 2784.026)),
    (2, "simplicityWeight", "E-complexity", (238.712, 2783.815)),
    (2, "complexityWeight", "copfr-complexity", (238.916, 2784.540)),
    (2, "complexityWeight", "copfr-E-complexity", (239.047, 2784.702)),
    (2, "complexityWeight", "complexity", (238.642, 2783.284)),
    (2, "complexityWeight", "E-complexity", (238.583, 2782.365)),
    (1, "unityWeight", "", (237.744, 2775.036)),
    (1, "simplicityWeight", "copfr-complexity", (237.744, 2775.036)),
    (1, "simplicityWeight", "E-complexity", (237.744, 2775.036)),
    (1, "complexityWeight", "complexity", (237.744, 2775.036)),
]


@pytest.mark.parametrize("power, slope, complexity_name, expected", BLACKWOOD_COMPLEXITY)
def test_optimize_generator_tuning_map_complexity_name(power, slope, complexity_name, expected):
    t = parse_temperament_data(BLACKWOOD)
    traits = complexity_name_traits(complexity_name) if complexity_name else {}
    spec = TuningSchemeSpec(
        optimization_power=power, target_intervals=SIX_TILT, damage_weight_slope=slope, **traits
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx(expected, abs=TOL)


# Held-intervals (trait 0, tests.m 2813-2853): named intervals tuned exactly justly.
@pytest.mark.parametrize("held", ["octave", "2", "2/1", "{2}", "{2/1}"])
def test_held_octave_synonyms_dict(held):
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=1,
        target_intervals=FIVE_OLD,
        damage_weight_slope="unityWeight",
        held_intervals=held,
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1200.000, 696.578), abs=TOL)


@pytest.mark.parametrize("held", ["octave", "2", "2/1", "{2}", "{2/1}"])
def test_held_octave_synonyms_name(held):
    t = parse_temperament_data(MEANTONE)
    name = f"held-{held} {FIVE_OLD} miniaverage-U"
    assert optimize_generator_tuning_map(t, name) == pytest.approx((1200.000, 696.578), abs=TOL)


def test_held_two_intervals():
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=1,
        target_intervals=FIVE_OLD,
        damage_weight_slope="unityWeight",
        held_intervals="{2/1, 3/2}",
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1200.000, 701.955), abs=TOL)
    name = f"held-{{2/1, 3/2}} {FIVE_OLD} miniaverage-U"
    assert optimize_generator_tuning_map(t, name) == pytest.approx((1200.000, 701.955), abs=TOL)


def test_held_octave_with_target_single_free_generator():
    # tests.m 2872: the coinciding-damage edge where the held octave pins one generator,
    # leaving a single free one and a target (prime 5) whose damage is already locked.
    t = parse_temperament_data("[⟨3 0 7] ⟨0 1 0]}")
    assert optimize_generator_tuning_map(
        t, "held-octave {3/1, 5/1} minimax-U"
    ) == pytest.approx((400.000, 1901.955), abs=TOL)


def test_held_interval_minimax():
    t = parse_temperament_data(MEANTONE)
    spec = TuningSchemeSpec(
        optimization_power=inf,
        target_intervals=FIVE_OLD,
        damage_weight_slope="unityWeight",
        held_intervals="5/3",
    )
    assert optimize_generator_tuning_map(t, spec) == pytest.approx((1200.000, 694.786), abs=TOL)


def test_held_intervals_determine_tuning():
    # h = r: the held intervals alone pin the generators, no target set needed.
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, "held-{2/1, 5/4} minimax-U") == pytest.approx(
        (1200.000, 696.578), abs=TOL
    )


# Handling ETs (tests.m 2770-2780): a single-generator 53-ET, target = TILT (default
# integer limit from the domain basis), across all powers and weights.
ET_TILT = [
    ("TILT minimax-U", 22.644),
    ("TILT miniRMS-U", 22.650),
    ("TILT miniaverage-U", 22.642),
    ("TILT minimax-C", 22.638),
    ("TILT miniRMS-C", 22.657),
    ("TILT miniaverage-C", 22.662),
    ("TILT minimax-S", 22.647),
    ("TILT miniRMS-S", 22.644),
    ("TILT miniaverage-S", 22.642),
]


@pytest.mark.parametrize("scheme, expected", ET_TILT)
def test_optimize_et_tilt(scheme, expected):
    t = parse_temperament_data("[⟨53 84 123]}")
    assert optimize_generator_tuning_map(t, scheme) == pytest.approx((expected,), abs=TOL)


# Held-interval cases that use a TILT target (tests.m 2832-2838).
TILT_HELD = [
    ("held-octave TILT miniRMS-U", (1200.000, 696.274)),
    ("held-2 TILT miniRMS-U", (1200.000, 696.274)),
    ("held-2/1 TILT miniRMS-U", (1200.000, 696.274)),
    ("held-{2} TILT miniRMS-U", (1200.000, 696.274)),
    ("held-{2/1} TILT miniRMS-U", (1200.000, 696.274)),
    ("held-3/2 TILT miniRMS-U", (1209.926, 701.955)),
    ("held-5/4 TILT miniRMS-U", (1201.536, 697.347)),
]


@pytest.mark.parametrize("scheme, expected", TILT_HELD)
def test_held_tilt(scheme, expected):
    t = parse_temperament_data(MEANTONE)
    assert optimize_generator_tuning_map(t, scheme) == pytest.approx(expected, abs=TOL)


# "held-octave OLD minimax-U" (= the original "minimax"/Tenney-minimax), tests.m 2883-2901.
HELD_OCTAVE_OLD_GENERATORS = [
    ("[⟨1 2 3] ⟨0 3 5]}", (1200.000, -162.737)),  # porcupine
    ("[⟨1 0 2] ⟨0 5 1]}", (1200.000, 380.391)),  # magic
    ("[⟨1 1 1] ⟨0 4 9]}", (1200.000, 176.257)),  # tetracot
    ("[⟨1 0 -4 -13] ⟨0 1 4 10]}", (1200.000, 1896.578)),  # meantone7
    ("[⟨1 0 2 -1] ⟨0 5 1 12]}", (1200.000, 380.391)),  # magic7
    ("[⟨1 -1 -1 -2] ⟨0 7 9 13]}", (1200.000, 443.519)),  # sensi
]


@pytest.mark.parametrize("ebk, expected", HELD_OCTAVE_OLD_GENERATORS)
def test_held_octave_old_generators(ebk, expected):
    t = parse_temperament_data(ebk)
    assert optimize_generator_tuning_map(t, "held-octave OLD minimax-U") == pytest.approx(
        expected, abs=TOL
    )


def test_held_octave_old_augene():
    t = parse_temperament_data("[⟨3 0 7 18] ⟨0 1 0 -2]}")  # accuracy=1 in the library
    assert optimize_generator_tuning_map(t, "held-octave OLD minimax-U") == pytest.approx(
        (400.000, 1908.798), abs=0.1
    )


def test_held_octave_old_tuning_map():
    meantone = parse_temperament_data(MEANTONE)
    assert optimize_tuning_map(meantone, "held-octave OLD minimax-U") == pytest.approx(
        (1200.000, 1896.578, 2786.314), abs=TOL
    )
    sensamagic = parse_temperament_data("[⟨1 0 0 0] ⟨0 1 1 2] ⟨0 0 2 -1]}")
    assert optimize_tuning_map(sensamagic, "held-octave OLD minimax-U") == pytest.approx(
        (1200.000, 1901.955, 2781.584, 3364.096), abs=TOL
    )


def test_get_just_tuning_map_standard():
    t = Temperament(((12, 19, 28),), ROW, (2, 3, 5))
    expected = (1200 * log2(2), 1200 * log2(3), 1200 * log2(5))
    assert get_just_tuning_map(t) == pytest.approx(expected, abs=TOL)


def test_get_just_tuning_map_nonstandard_basis():
    t = Temperament(((1, 0, -4, 0), (0, 1, 2, 0), (0, 0, 0, 1)), ROW, (2, 9, 5, 21))
    expected = (1200 * log2(2), 1200 * log2(9), 1200 * log2(5), 1200 * log2(21))
    assert get_just_tuning_map(t) == pytest.approx(expected, abs=TOL)


@pytest.mark.parametrize(
    "norm_power, log_prime_power, expected",
    [
        (1, 0, 3),
        (2, 0, sqrt(3)),
        (1, 1, 1 + log2(3) + log2(5)),
    ],
)
def test_get_complexity(norm_power, log_prime_power, expected):
    dummy = Temperament(((1, 2, 3), (0, 5, 6)), ROW)
    result = get_complexity((1, 1, -1), dummy, norm_power, log_prime_power, 0, 0, "")
    assert result == pytest.approx(expected, abs=1e-9)


@pytest.mark.parametrize(
    "power, expected", [(1, float("inf")), (2, 2), (float("inf"), 1)]
)
def test_get_dual_power(power, expected):
    assert get_dual_power(power) == expected


def test_generator_tuning_map_from_t_and_tuning_map():
    meantone_m = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]}")
    quarter_comma_tuning_map = (1200.000, 1896.578, 2786.314)
    result = generator_tuning_map_from_t_and_tuning_map(
        meantone_m, quarter_comma_tuning_map
    )
    assert result == pytest.approx((1200.000, 696.578), abs=TOL)
