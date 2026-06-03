"""Diamond-monotone and diamond-tradeoff generator tuning ranges.

For a rank-``r`` temperament there is generally a *range* of valid generator
tunings over the odd-limit tonality diamond, not a single optimum. Both ranges
are normalized by holding the octave (2/1) pure, which pins the period generator
and leaves the remaining generator(s) free to vary. Each range is returned as a
``(low, high)`` pair of cents per generator.
"""

from __future__ import annotations

from itertools import combinations
from typing import Literal

import numpy as np
from scipy.optimize import linprog

from rtt.dimensions import get_d
from rtt.dual import mapping_matrix
from rtt.temperament import Temperament
from rtt.tuning import get_just_tuning_map, resolve_target_intervals

Mode = Literal["monotone", "tradeoff"]


def get_generator_tuning_range(
    t: Temperament, mode: Mode, target_spec: str = "OLD"
) -> tuple[tuple[float, float], ...] | None:
    """The ``(low, high)`` cents range of each generator, octave held pure.

    ``None`` (monotone only) means no such tuning exists for this temperament."""
    d = get_d(t)
    mapping = np.array(mapping_matrix(t), dtype=float)  # r x d
    r = mapping.shape[0]
    just = np.array(get_just_tuning_map(t), dtype=float)  # d

    diamond = np.array(resolve_target_intervals(target_spec, t, d), dtype=float)  # k x d
    coords = diamond @ mapping.T  # k x r (each diamond interval in generator coords)
    just_sizes = diamond @ just  # k

    octave = np.zeros(d)
    octave[0] = 1.0
    octave_coords = mapping @ octave  # r
    octave_just = float(just @ octave)  # 1200

    if mode == "monotone":
        return _monotone_range(coords, just_sizes, octave_coords, octave_just, r)
    if mode == "tradeoff":
        return _tradeoff_range(coords, just_sizes, octave_coords, octave_just, r)
    raise ValueError(f"unknown mode: {mode!r}")


def _monotone_range(
    coords: np.ndarray,
    just_sizes: np.ndarray,
    octave_coords: np.ndarray,
    octave_just: float,
    r: int,
) -> tuple[tuple[float, float], ...] | None:
    """The diamond-monotone range: the tunings under which the tempered diamond
    intervals keep their JI size order. Sorting the diamond (plus 1/1) by just
    size, each consecutive step must temper non-negatively — a polytope whose
    extent along each generator is a linear program, octave held pure.

    Returns ``None`` when no diamond-monotone tuning exists — the polytope is
    empty because some consonance can't keep its place (e.g. it tempers out)."""
    all_coords = np.vstack([np.zeros(r), coords])  # prepend 1/1 (the size floor)
    all_sizes = np.concatenate([[0.0], just_sizes])
    steps = np.diff(all_coords[np.argsort(all_sizes)], axis=0)  # (k, r): upper - lower
    a_ub, b_ub = -steps, np.zeros(len(steps))  # each step tempers >= 0
    a_eq, b_eq = octave_coords.reshape(1, r), np.array([octave_just])
    bounds = [(None, None)] * r

    def solve(direction: np.ndarray):
        return linprog(direction, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)

    ranges = []
    for i, unit in enumerate(np.eye(r)):
        low, high = solve(unit), solve(-unit)
        if not (low.success and high.success):
            return None  # the monotone polytope is empty (or unbounded)
        ranges.append((float(low.x[i]), float(high.x[i])))
    return tuple(ranges)


def _tradeoff_range(
    coords: np.ndarray,
    just_sizes: np.ndarray,
    octave_coords: np.ndarray,
    octave_just: float,
    r: int,
) -> tuple[tuple[float, float], ...] | None:
    """The diamond-tradeoff range: the extreme tunings hold the octave plus
    ``r-1`` diamond consonances purely. Each such pure tuning is a vertex; the
    range per generator is the span of the vertices.

    Returns ``None`` when no vertex pins a tuning — a degenerate temperament whose
    octave tempers out (so no tuning holds it pure) has none, like the empty
    monotone polytope. The caller draws a placeholder rather than I-beams."""
    vertices = []
    for combo in combinations(range(len(coords)), r - 1):
        a = np.vstack([octave_coords, *(coords[i] for i in combo)])  # r x r
        b = np.array([octave_just, *(just_sizes[i] for i in combo)])  # r
        if abs(np.linalg.det(a)) < 1e-9:
            continue  # the chosen intervals don't pin a unique tuning
        vertices.append(np.linalg.solve(a, b))
    if not vertices:
        return None  # no pure-octave tuning exists (the octave tempers out)
    v = np.array(vertices)  # m x r
    return tuple((float(v[:, i].min()), float(v[:, i].max())) for i in range(r))
