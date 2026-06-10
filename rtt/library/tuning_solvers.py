"""Low-level optimum-generator solvers: given the tempered/just target rows as plain
numpy arrays, find the generators minimizing the chosen Lp norm of the damages. These are
temperament-agnostic — no scheme, no Temperament, just linear algebra and linear programs —
so the optimization orchestration in rtt.library.tuning calls :func:`solve_optimum` as a black box."""

from __future__ import annotations

import numpy as np
from scipy.optimize import linprog, minimize


def solve_optimum(
    tempered: np.ndarray, just: np.ndarray, power: float, rank: int
) -> np.ndarray:
    """Solve for the generators minimizing the ``power``-norm of (tempered·g − just)."""
    if power == 2:
        generators, *_ = np.linalg.lstsq(tempered, just, rcond=None)
        return generators
    if power == float("inf"):
        return _minimax(tempered, just, rank)
    if power == 1:
        return _minisum(tempered, just, rank)
    return _power_sum(tempered, just, power)


def _power_sum(tempered: np.ndarray, just: np.ndarray, power: float) -> np.ndarray:
    """Minimize the sum of damages raised to ``power`` (the optimum for a finite power
    other than 1, 2, or ∞), starting from the least-squares solution."""
    initial = np.linalg.lstsq(tempered, just, rcond=None)[0]
    result = minimize(
        lambda generators: np.sum(np.abs(tempered @ generators - just) ** power),
        initial,
        method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 100000},
    )
    return result.x


def _minimax(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Nested (lexicographic) minimax: minimize the largest absolute damage, then the
    next-largest, and so on, until the generators are uniquely pinned down.

    A plain minimax leaves the generators under-determined whenever several targets
    can share the maximum damage. We resolve that the way Wolfram's coinciding-damage
    method does: solve for the minimax level δ, freeze every target whose damage is
    forced to ±δ across the whole optimal set, then re-minimax the rest below δ.
    """
    active = list(range(len(just)))
    frozen_rows: list[np.ndarray] = []  # tempered rows pinned to an exact damage
    frozen_values: list[float] = []  # the value each pinned row's tempering must hit
    generators = np.zeros(rank)
    while active:
        delta, generators = _capped_minimax(
            tempered, just, rank, active, frozen_rows, frozen_values
        )
        locked = _targets_locked_at_delta(
            tempered, just, rank, active, frozen_rows, frozen_values, delta
        )
        if not locked:
            break
        for index, value in locked:
            frozen_rows.append(tempered[index])
            frozen_values.append(value)
            active.remove(index)
        if np.linalg.matrix_rank(np.vstack(frozen_rows)) >= rank:
            break
    return generators


def _capped_minimax(
    tempered: np.ndarray,
    just: np.ndarray,
    rank: int,
    active: list[int],
    frozen_rows: list[np.ndarray],
    frozen_values: list[float],
) -> tuple[float, np.ndarray]:
    """Minimize δ (variables ``[generators, δ]``) so every active target's damage is
    ≤ δ while the already-frozen targets stay pinned to their exact damage."""
    cost = np.concatenate([np.zeros(rank), [1.0]])
    a_ub, b_ub = [], []
    for i in active:
        a_ub.append(np.concatenate([tempered[i], [-1.0]]))
        b_ub.append(just[i])
        a_ub.append(np.concatenate([-tempered[i], [-1.0]]))
        b_ub.append(-just[i])
    a_eq = [np.concatenate([row, [0.0]]) for row in frozen_rows] or None
    bounds = [(None, None)] * rank + [(0, None)]
    result = linprog(
        cost,
        A_ub=np.array(a_ub),
        b_ub=np.array(b_ub),
        A_eq=np.array(a_eq) if a_eq else None,
        b_eq=np.array(frozen_values) if frozen_values else None,
        bounds=bounds,
    )
    return result.x[-1], result.x[:rank]


def _targets_locked_at_delta(
    tempered: np.ndarray,
    just: np.ndarray,
    rank: int,
    active: list[int],
    frozen_rows: list[np.ndarray],
    frozen_values: list[float],
    delta: float,
    tol: float = 1e-7,
) -> list[tuple[int, float]]:
    """Which active targets have damage forced to exactly ±δ across the whole optimal
    set (and so must be frozen there before re-minimaxing the rest). Returns each such
    target's index paired with the tempering value its row must hit."""
    a_ub, b_ub = [], []
    for j in active:
        a_ub.append(tempered[j])
        b_ub.append(just[j] + delta)
        a_ub.append(-tempered[j])
        b_ub.append(-just[j] + delta)
    a_ub, b_ub = np.array(a_ub), np.array(b_ub)
    a_eq = np.array(frozen_rows) if frozen_rows else None
    b_eq = np.array(frozen_values) if frozen_values else None
    bounds = [(None, None)] * rank
    scale = max(1.0, abs(delta))
    locked = []
    for i in active:
        low = linprog(tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if abs((tempered[i] @ low.x - just[i]) - delta) <= tol * scale:
            locked.append((i, just[i] + delta))
            continue
        high = linprog(-tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if abs((tempered[i] @ high.x - just[i]) + delta) <= tol * scale:
            locked.append((i, just[i] - delta))
    return locked


def _minisum(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Minimize the sum of absolute damages via a linear program (a slack per target)."""
    k = len(just)
    cost = np.concatenate([np.zeros(rank), np.ones(k)])  # minimize Σ slack
    identity = np.eye(k)
    a_ub = np.vstack(
        [np.hstack([tempered, -identity]), np.hstack([-tempered, -identity])]
    )
    b_ub = np.concatenate([just, -just])
    bounds = [(None, None)] * rank + [(0, None)] * k
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
    return result.x[:rank]
