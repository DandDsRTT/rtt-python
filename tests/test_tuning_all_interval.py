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


# destretched-octave minimax-ES = POTE, tuning maps (tests.m 2998-3014).
POTE_TUNING_MAPS = {
    "meantone": (1200.000, 1896.239, 2784.955),
    "blackwood": (1200.000, 1920.000, 2799.594),
    "dicot": (1200.000, 1897.189, 2748.594),
    "augmented": (1200.000, 1906.638, 2800.000),
    "mavila": (1200.000, 1879.806, 2760.582),
    "porcupine": (1200.000, 1908.149, 2780.248),
    "srutal": (1200.000, 1904.898, 2790.204),
    "hanson": (1200.000, 1902.039, 2785.033),
    "magic": (1200.000, 1900.292, 2780.058),
    "negri": (1200.000, 1896.980, 2777.265),
    "tetracot": (1200.000, 1904.639, 2785.438),
    "meantone7": (1200.000, 1896.495, 2785.980, 3364.949),
    "magic7": (1200.000, 1901.760, 2780.352, 3364.224),
    "pajara": (1200.000, 1907.048, 2785.905, 3385.905),
    "augene": (1200.000, 1909.257, 2800.000, 3381.486),
    "sensi": (1200.000, 1903.679, 2790.444, 3363.975),
    "sensamagic": (1200.000, 1903.742, 2785.546, 3366.583),
}


@pytest.mark.parametrize("name, expected", POTE_TUNING_MAPS.items())
def test_pote_destretched_octave_minimax_es(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_tuning_map(t, "POTE") == pytest.approx(expected, abs=TOL)


# destretched-octave minimax-S = POTOP (tests.m 3024-3035); some use looser accuracy.
POTOP_CASES = [
    ("[⟨1 -1 0 1] ⟨0 10 9 7]}", (1200.000, 310.196), TOL),
    ("[⟨1 2 6 2 10] ⟨0 -1 -9 2 -16]}", (1200.0, 490.4), 0.1),
    ("[⟨1 2 6 2 1] ⟨0 -1 -9 2 6]}", (1200.0, 490.9), 0.1),
    ("[⟨1 2 -3 2 1] ⟨0 -1 13 2 6]}", (1200.0, 491.9), 0.1),
    ("[⟨1 1 2 1] ⟨0 1 0 2] ⟨0 0 1 2]}", (1200.0, 700.391, 384.022), TOL),
    ("[⟨1 1 0] ⟨0 1 4]}", (1200.0, 696.58), 0.01),
    ("[⟨1 1 0 -3] ⟨0 1 4 10]}", (1200.0, 696.58), 0.01),
    # [7j]: the library's value is corrected (its 706.843 has more damage than this 709.184).
    ("[⟨2 2 7 8 14 5] ⟨0 1 -2 -2 -6 2]}", (600.000, 709.184), TOL),
]


@pytest.mark.parametrize("ebk, expected, tol", POTOP_CASES)
def test_potop_destretched_octave_minimax_s(ebk, expected, tol):
    t = parse_temperament_data(ebk)
    assert optimize_generator_tuning_map(t, "POTOP") == pytest.approx(expected, abs=tol)


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
    ("POTE", "destretched-octave minimax-ES"),
    ("POTOP", "destretched-octave minimax-S"),
]


@pytest.mark.parametrize("original, systematic", ORIGINAL_NAME_EQUIVALENCES)
def test_original_name_equivalences(original, systematic):
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_tuning_map(meantone, original) == pytest.approx(
        optimize_tuning_map(meantone, systematic), abs=TOL
    )


# Alternative-complexity all-interval families (tests.m 3470-3540), size factor 0 so they
# go through the ordinary (un-augmented) all-interval path. Each maps a (temperament -> tuning
# map) over the standard temperament set. A few use looser accuracy in the library (TOL_2).
TOL_2 = 1e-2

# minimax-E-copfr-S = "Frobenius" (tests.m 3472-3490).
FROBENIUS_TUNING_MAPS = {
    "meantone": (1202.6068, 1899.3482, 2786.9654),
    "blackwood": (1191.8899, 1907.0238, 2786.3137),
    "dicot": (1215.1441, 1907.0030, 2776.2177),
    "augmented": (1195.0446, 1901.9550, 2788.4374),
    "mavila": (1210.9365, 1897.2679, 2784.7514),
    "porcupine": (1198.5953, 1908.9787, 2782.0995),
    "srutal": (1198.4746, 1902.5097, 2786.5911),
    "hanson": (1200.5015, 1902.3729, 2785.8122),
    "magic": (1202.3503, 1902.1900, 2785.1386),
    "negri": (1203.2384, 1901.2611, 2785.3885),
    "tetracot": (1198.8664, 1903.9955, 2785.4068),
    "meantone7": (1201.3440, 1898.5615, 2788.8699, 3368.1428),
    "magic7": (1202.0285, 1904.1849, 2784.8940, 3368.0151),
    "pajara": (1196.6908, 1901.7292, 2778.3407, 3376.6861),
    "augene": (1195.2617, 1901.4887, 2788.9439, 3368.5928),
    "sensi": (1198.2677, 1904.0314, 2790.4025, 3364.8772),
    "sensamagic": (1200.0000, 1904.3201, 2785.8407, 3367.8799),
}


@pytest.mark.parametrize("name, expected", FROBENIUS_TUNING_MAPS.items())
def test_frobenius_minimax_e_copfr_s(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_tuning_map(t, "minimax-E-copfr-S") == pytest.approx(expected, abs=TOL)


def test_frobenius_original_name():
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_generator_tuning_map(meantone, "Frobenius") == pytest.approx(
        optimize_generator_tuning_map(meantone, "minimax-E-copfr-S"), abs=TOL
    )


# minimax-sopfr-S = "BOP"/"Benedetti" (tests.m 3494-3517). tetracot and magic7 use accuracy 2.
BOP_TUNING_MAPS = {
    "meantone": ((1201.7205, 1899.3742, 2790.6150), TOL),
    "blackwood": ((1194.179, 1910.686, 2786.314), TOL),
    "dicot": ((1207.4392, 1913.1138, 2767.7157), TOL),
    "augmented": ((1197.1684, 1901.9550, 2793.3928), TOL),
    "mavila": ((1206.5842, 1892.0787, 2769.8533), TOL),
    "porcupine": ((1196.9271, 1906.5643, 2778.6315), TOL),
    "srutal": ((1199.1112, 1903.2881, 2788.5356), TOL),
    "hanson": ((1200.2845, 1902.3817, 2785.6025), TOL),
    "magic": ((1201.2339, 1903.8058, 2783.2290), TOL),
    "negri": ((1201.7937, 1899.2645, 2781.8295), TOL),
    "tetracot": ((1199.0293, 1903.4111, 2783.8883), TOL_2),
    "meantone7": ((1201.721, 1899.374, 2790.615, 3371.376), TOL),
    "magic7": ((1201.2340, 1903.8044, 2783.2288, 3367.8966), TOL_2),
    "pajara": ((1197.3094, 1902.8073, 2779.5873, 3378.2420), TOL),
    "augene": ((1197.168, 1904.326, 2793.393, 3374.358), TOL),
    "sensi": ((1198.5891, 1903.5233, 2789.8411, 3363.8876), TOL),
    "sensamagic": ((1200.0000, 1903.2071, 2784.2269, 3365.9043), TOL),
}


@pytest.mark.parametrize("name, expected_tol", BOP_TUNING_MAPS.items())
def test_bop_minimax_sopfr_s(name, expected_tol):
    expected, tol = expected_tol
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_tuning_map(t, "minimax-sopfr-S") == pytest.approx(expected, abs=tol)


@pytest.mark.parametrize("original", ["BOP", "Benedetti"])
def test_bop_original_names(original):
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_generator_tuning_map(meantone, original) == pytest.approx(
        optimize_generator_tuning_map(meantone, "minimax-sopfr-S"), abs=TOL
    )


# minimax-E-sopfr-S = "BE"/"Benedetti-Euclidean" (tests.m 3521-3540).
BE_TUNING_MAPS = {
    "meantone": (1201.4768, 1898.6321, 2788.6213),
    "blackwood": (1193.9975, 1910.3960, 2786.3137),
    "dicot": (1205.8488, 1906.3416, 2761.9439),
    "augmented": (1197.2692, 1901.9550, 2793.6282),
    "mavila": (1208.5464, 1893.7139, 2778.683),
    "porcupine": (1199.5668, 1906.8283, 2778.1916),
    "srutal": (1198.8183, 1902.9219, 2787.6566),
    "hanson": (1200.1533, 1902.2425, 2785.3554),
    "magic": (1201.1456, 1902.2128, 2782.7337),
    "negri": (1202.2630, 1900.8639, 2782.2726),
    "tetracot": (1199.5499, 1903.7780, 2784.0631),
    "meantone7": (1201.3847, 1898.6480, 2789.0531, 3368.4787),
    "magic7": (1200.9990, 1903.1832, 2782.6345, 3366.6407),
    "pajara": (1197.9072, 1903.2635, 2781.9626, 3380.9162),
    "augene": (1196.4076, 1903.1641, 2791.6178, 3372.1175),
    "sensi": (1199.7904, 1902.7978, 2789.2516, 3362.3687),
    "sensamagic": (1200.0000, 1903.3868, 2785.5183, 3365.7078),
}


@pytest.mark.parametrize("name, expected", BE_TUNING_MAPS.items())
def test_be_minimax_e_sopfr_s(name, expected):
    t = parse_temperament_data(TEMPERAMENTS[name])
    assert optimize_tuning_map(t, "minimax-E-sopfr-S") == pytest.approx(expected, abs=TOL)


@pytest.mark.parametrize("original", ["BE", "Benedetti-Euclidean"])
def test_be_original_names(original):
    meantone = parse_temperament_data(TEMPERAMENTS["meantone"])
    assert optimize_generator_tuning_map(meantone, original) == pytest.approx(
        optimize_generator_tuning_map(meantone, "minimax-E-sopfr-S"), abs=TOL
    )
