from __future__ import annotations

from itertools import combinations
from typing import Literal

import numpy as np
from scipy.optimize import linprog

from rtt.library.dimensions import get_d
from rtt.library.dual import mapping_matrix
from rtt.library.temperament import Temperament
from rtt.library.tuning import get_just_tuning_map, resolve_target_intervals

Mode = Literal["monotone", "tradeoff"]


def get_generator_tuning_range(
    t: Temperament, mode: Mode, target_spec: str = "OLD"
) -> tuple[tuple[float, float], ...] | None:
    d = get_d(t)
    mapping = np.array(mapping_matrix(t), dtype=float)
    r = mapping.shape[0]
    just = np.array(get_just_tuning_map(t), dtype=float)

    diamond = np.array(resolve_target_intervals(target_spec, t, d), dtype=float)
    coords = diamond @ mapping.T
    just_sizes = diamond @ just

    octave = np.zeros(d)
    octave[0] = 1.0
    octave_coords = mapping @ octave
    octave_just = float(just @ octave)

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
    all_coords = np.vstack([np.zeros(r), coords])
    all_sizes = np.concatenate([[0.0], just_sizes])
    steps = np.diff(all_coords[np.argsort(all_sizes)], axis=0)
    a_ub, b_ub = -steps, np.zeros(len(steps))
    a_eq, b_eq = octave_coords.reshape(1, r), np.array([octave_just])
    bounds = [(None, None)] * r

    def solve(direction: np.ndarray):
        return linprog(direction, A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)

    ranges = []
    for i, unit in enumerate(np.eye(r)):
        low, high = solve(unit), solve(-unit)
        if not (low.success and high.success):
            return None
        ranges.append((float(low.x[i]), float(high.x[i])))
    return tuple(ranges)


def _tradeoff_range(
    coords: np.ndarray,
    just_sizes: np.ndarray,
    octave_coords: np.ndarray,
    octave_just: float,
    r: int,
) -> tuple[tuple[float, float], ...] | None:
    combos = np.array(list(combinations(range(len(coords)), r - 1)), dtype=np.intp)
    if combos.size == 0 and r > 1:
        return None
    chunk = 500_000
    vertices = []
    for start in range(0, len(combos), chunk):
        idx = combos[start : start + chunk]
        a = np.empty((len(idx), r, r))
        a[:, 0] = octave_coords
        a[:, 1:] = coords[idx]
        b = np.empty((len(idx), r))
        b[:, 0] = octave_just
        b[:, 1:] = just_sizes[idx]
        keep = np.abs(np.linalg.det(a)) >= 1e-9
        if keep.any():
            vertices.append(np.linalg.solve(a[keep], b[keep, :, None])[:, :, 0])
    if not vertices:
        return None
    v = np.vstack(vertices)
    return tuple((float(v[:, i].min()), float(v[:, i].max())) for i in range(r))
