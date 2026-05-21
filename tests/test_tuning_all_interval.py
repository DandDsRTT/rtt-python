"""All-interval tuning schemes (tests.m 3133-3228): TOP (minimax-S), TE (minimax-ES),
CTE (held-octave minimax-ES), and their historical names. All-interval damage is
minimized over every interval, which by duality is an optimization over the primes at
the dual of the complexity norm power."""

from math import inf

import pytest

from rtt.parsing import parse_temperament_data
from rtt.tuning import (
    TuningSchemeSpec,
    optimize_generator_tuning_map,
    optimize_tuning_map,
)

TOL = 1e-3
TOL_TOP = 1e-2  # the library uses accuracy=2 for the minimax-S generator forms

TEMPERAMENTS = {
    "meantone": "[⟨1 1 0] ⟨0 1 4]}",
    "blackwood": "[⟨5 8 0] ⟨0 0 1]}",
    "dicot": "[⟨1 1 2] ⟨0 2 1]}",
    "augmented": "[⟨3 0 7] ⟨0 1 0]}",
    "mavila": "[⟨1 0 7] ⟨0 1 -3]}",
    "porcupine": "[⟨1 2 3] ⟨0 3 5]}",
    "srutal": "[⟨2 0 11] ⟨0 1 -2]}",
    "hanson": "[⟨1 0 1] ⟨0 6 5]}",
    "magic": "[⟨1 0 2] ⟨0 5 1]}",
    "negri": "[⟨1 2 2] ⟨0 -4 3]}",
    "tetracot": "[⟨1 1 1] ⟨0 4 9]}",
    "meantone7": "[⟨1 0 -4 -13] ⟨0 1 4 10]}",
    "magic7": "[⟨1 0 2 -1] ⟨0 5 1 12]}",
    "pajara": "[⟨2 3 5 6] ⟨0 1 -2 -2]}",
    "augene": "[⟨3 0 7 18] ⟨0 1 0 -2]}",
    "sensi": "[⟨1 -1 -1 -2] ⟨0 7 9 13]}",
    "sensamagic": "[⟨1 0 0 0] ⟨0 1 1 2] ⟨0 0 2 -1]}",
}


# minimax-S = TOP, generator tuning maps (the second generator written as in the source).
TOP_GENERATORS = {
    "meantone": (1201.70, 1201.70 - 504.13),
    "blackwood": (238.87, 238.86 * 11.0003 + 158.78),
    "dicot": (1207.66, 353.22),
    "augmented": (399.02, 399.018 * 5.00005 - 93.15),
    "mavila": (1206.55, 1206.55 + 685.03),
    "porcupine": (1196.91, 1034.59 - 1196.91),
    "srutal": (599.56, 599.56 * 3.99999 - 494.86),
    "hanson": (1200.29, 317.07),
    "magic": (1201.28, 380.80),
    "negri": (1201.82, 1201.82 - 1075.68),
    "tetracot": (1199.03, 176.11),
    "meantone7": (1201.70, 1201.70 * 2 - 504.13),
    "magic7": (1201.28, 380.80),
    "pajara": (598.45, 598.45 - 491.88),
    "augene": (399.02, 399.02 * 5 - 90.59),
    "sensi": (1198.39, 1198.39 - 755.23),
}


@pytest.mark.parametrize("name, expected", TOP_GENERATORS.items())
def test_top_minimax_s(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_generator_tuning_map(t, "minimax-S") == pytest.approx(expected, abs=TOL_TOP)


# minimax-ES = TE, tuning maps.
TE_TUNING_MAPS = {
    "meantone": (1201.397, 1898.446, 2788.196),
    "blackwood": (1194.308, 1910.892, 2786.314),
    "dicot": (1206.410, 1907.322, 2763.276),
    "augmented": (1197.053, 1901.955, 2793.123),
    "mavila": (1208.380, 1892.933, 2779.860),
    "porcupine": (1199.562, 1907.453, 2779.234),
    "srutal": (1198.823, 1903.030, 2787.467),
    "hanson": (1200.166, 1902.303, 2785.418),
    "magic": (1201.248, 1902.269, 2782.950),
    "negri": (1202.347, 1900.691, 2782.698),
    "tetracot": (1199.561, 1903.942, 2784.419),
    "meantone7": (1201.242, 1898.458, 2788.863, 3368.432),
    "magic7": (1201.082, 1903.476, 2782.860, 3367.259),
    "pajara": (1197.719, 1903.422, 2780.608, 3379.468),
    "augene": (1196.255, 1903.298, 2791.261, 3370.933),
    "sensi": (1199.714, 1903.225, 2789.779, 3363.173),
    "sensamagic": (1200.000, 1903.742, 2785.546, 3366.583),
}


@pytest.mark.parametrize("name, expected", TE_TUNING_MAPS.items())
def test_te_minimax_es(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_tuning_map(t, "minimax-ES") == pytest.approx(expected, abs=TOL)


# held-octave minimax-ES = CTE, generator tuning maps.
CTE_GENERATORS = {
    "meantone": (1200.000, 697.214),
    "blackwood": (240.000, 1200.000 * 2 + 386.314),
    "dicot": (1200.000, 354.664),
    "augmented": (400.000, 1200.000 + 701.955),
    "mavila": (1200.000, 1200.000 + 677.145),
    "porcupine": (1200.000, -164.166),
    "srutal": (600.000, 1200.000 + 705.136),
    "hanson": (1200.000, 317.059),
    "magic": (1200.000, 380.499),
    "negri": (1200.000, 125.396),
    "tetracot": (1200.000, 176.028),
    "meantone7": (1200.000, 1200.000 + 696.952),
    "magic7": (1200.000, 380.651),
    "pajara": (600.000, 600.000 * -1 + 708.356),
    "augene": (400.000, 1200.000 + 709.595),
    "sensi": (1200.000, 1200.000 - 756.683),
    "sensamagic": (1200.000, 1200.000 + 703.742, 440.902),
}


@pytest.mark.parametrize("name, expected", CTE_GENERATORS.items())
def test_cte_held_octave_minimax_es(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_generator_tuning_map(t, "held-octave minimax-ES") == pytest.approx(
        expected, abs=TOL
    )


def test_all_interval_explicit_specs():
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_generator_tuning_map(
        meantone,
        TuningSchemeSpec(optimization_power=inf, target_intervals="{}", damage_weight_slope="simplicityWeight"),
    ) == pytest.approx((1201.699, 697.564), abs=TOL)
    assert optimize_generator_tuning_map(
        meantone,
        TuningSchemeSpec(
            optimization_power=inf,
            target_intervals="{}",
            damage_weight_slope="simplicityWeight",
            complexity_norm_power=2,
        ),
    ) == pytest.approx((1201.397, 697.049), abs=TOL)
    pajara = parse_temperament_data(TEMPERAMENTS["pajara"])
    assert optimize_generator_tuning_map(pajara, "minimax-S") == pytest.approx(
        (598.447, 106.567), abs=TOL
    )
    assert optimize_generator_tuning_map(pajara, "minimax-ES") == pytest.approx(
        (598.859, 106.844), abs=TOL
    )


# Historical scheme names resolve to their systematic equivalents.
ORIGINAL_NAME_EQUIVALENCES = [
    ("TOP", "minimax-S"),
    ("T1", "minimax-S"),
    ("TOP-max", "minimax-S"),
    ("TIPTOP", "minimax-S"),
    ("Tenney", "minimax-S"),
    ("TE", "minimax-ES"),
    ("T2", "minimax-ES"),
    ("TOP-RMS", "minimax-ES"),
    ("Tenney-Euclidean", "minimax-ES"),
    ("CTE", "held-octave minimax-ES"),
    ("Constrained Tenney-Euclidean", "held-octave minimax-ES"),
    ("minimax", "held-octave OLD minimax-U"),
    ("least squares", "held-octave OLD miniRMS-U"),
]


@pytest.mark.parametrize("original, systematic", ORIGINAL_NAME_EQUIVALENCES)
def test_original_name_equivalences(original, systematic):
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_tuning_map(meantone, original) == pytest.approx(
        optimize_tuning_map(meantone, systematic), abs=TOL
    )
