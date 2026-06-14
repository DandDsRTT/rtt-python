"""Manual (custom) per-target damage weights: a ``weights_override`` that bypasses the
slope-derived weights and drives the solve directly. Target-mode only — an all-interval scheme
minimaxes over the primes with structural simplicity weights and has no per-target weights, so it
ignores any override. A bad or stale (wrong-length / non-positive / non-finite) override falls back
to the slope-derived weights rather than mis-pairing or crashing the solver."""

from math import inf

import numpy as np
import pytest

from rtt.library.parsing import parse_temperament_data
from rtt.library.tuning import damage_weights, optimize_generator_tuning_map
from rtt.library.tuning_scheme_names import TuningSchemeSpec

TOL = 1e-3
MEANTONE = "[⟨1 1 0] ⟨0 1 4]}"
TARGETS = "{2/1, 3/2, 5/4}"
# the three targets above as prime-count vectors over the 5-limit domain
TARGET_VECTORS = ((1, 0, 0), (-1, 1, 0), (-2, 0, 1))
COMPLEXITY_SPEC = TuningSchemeSpec(
    optimization_power=inf, target_intervals=TARGETS, damage_weight_slope="complexityWeight"
)


def _t():
    return parse_temperament_data(MEANTONE)


def test_matching_override_returned_verbatim():
    """A length-matching, positive, finite override IS the weights — the slope is ignored."""
    override = (1.0, 2.0, 5.0)
    weights = damage_weights(TARGET_VECTORS, _t(), COMPLEXITY_SPEC, weights_override=override)
    assert list(weights) == pytest.approx(list(override))


def test_mismatched_length_override_falls_back_to_slope():
    """A wrong-length override (a stale one left over a target ±/reorder) is ignored, so the
    weights are the slope-derived complexities, not a mis-paired override."""
    derived = damage_weights(TARGET_VECTORS, _t(), COMPLEXITY_SPEC)
    too_short = damage_weights(TARGET_VECTORS, _t(), COMPLEXITY_SPEC, weights_override=(1.0, 2.0))
    assert list(too_short) == pytest.approx(list(derived))


@pytest.mark.parametrize("bad", [(1.0, 0.0, 3.0), (1.0, -2.0, 3.0), (1.0, float("inf"), 3.0)])
def test_non_positive_or_nonfinite_override_falls_back(bad):
    """A 0 / negative / non-finite weight would corrupt the solve, so it falls back to the slope."""
    derived = damage_weights(TARGET_VECTORS, _t(), COMPLEXITY_SPEC)
    got = damage_weights(TARGET_VECTORS, _t(), COMPLEXITY_SPEC, weights_override=bad)
    assert list(got) == pytest.approx(list(derived))


def test_override_reaches_the_solve():
    """Two different overrides yield two different generator tunings — proof the override threads
    all the way into the constrained solve, not just the displayed weight row."""
    t = _t()
    a = optimize_generator_tuning_map(t, COMPLEXITY_SPEC, weights_override=(1.0, 1.0, 1.0))
    b = optimize_generator_tuning_map(t, COMPLEXITY_SPEC, weights_override=(1.0, 100.0, 100.0))
    assert a != pytest.approx(b, abs=TOL)


def test_override_matches_a_handmade_unity_scheme():
    """An all-ones override over a complexity-weighted scheme reproduces the same scheme with a
    unity slope — the override genuinely replaces the slope's weights."""
    t = _t()
    overridden = optimize_generator_tuning_map(t, COMPLEXITY_SPEC, weights_override=(1.0, 1.0, 1.0))
    unity = optimize_generator_tuning_map(
        t, TuningSchemeSpec(optimization_power=inf, target_intervals=TARGETS,
                            damage_weight_slope="unityWeight"))
    assert overridden == pytest.approx(unity, abs=TOL)


def test_all_interval_ignores_override():
    """An all-interval scheme (empty target set) has no per-target weights — a weights_override
    must not change its result."""
    t = _t()
    plain = optimize_generator_tuning_map(t, "minimax-S")
    with_override = optimize_generator_tuning_map(t, "minimax-S", weights_override=(9.0, 0.1, 7.0))
    assert with_override == pytest.approx(plain, abs=TOL)
