from __future__ import annotations

import numpy as np
from scipy.optimize import linprog, minimize


def solve_optimum(tempered: np.ndarray, just: np.ndarray, power: float, rank: int) -> np.ndarray:
    if power == 2:
        generators, *_ = np.linalg.lstsq(tempered, just, rcond=None)
        return generators
    if power == float("inf"):
        return _minimax(tempered, just, rank)
    if power == 1:
        return _minisum(tempered, just, rank)
    return _power_sum(tempered, just, power)


def _power_sum(tempered: np.ndarray, just: np.ndarray, power: float) -> np.ndarray:
    initial = np.linalg.lstsq(tempered, just, rcond=None)[0]
    result = minimize(
        lambda generators: np.sum(np.abs(tempered @ generators - just) ** power),
        initial,
        method="Nelder-Mead",
        options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 100000},
    )
    return result.x


def _minimax(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    active = list(range(len(just)))
    frozen_rows: list[np.ndarray] = []
    frozen_values: list[float] = []
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
    if not result.success:
        raise ValueError(f"minimax linear program did not converge: {result.message}")
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
        if low.success and abs((tempered[i] @ low.x - just[i]) - delta) <= tol * scale:
            locked.append((i, just[i] + delta))
            continue
        high = linprog(-tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if high.success and abs((tempered[i] @ high.x - just[i]) + delta) <= tol * scale:
            locked.append((i, just[i] - delta))
    return locked


def _minisum(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    generators, optimum = _minisum_lp(tempered, just, rank)
    if _minisum_optimum_is_unique(tempered, just, rank, optimum):
        return generators
    refined = _power_limit(tempered, just, generators)
    if float(np.max(np.abs(refined - generators))) < 1e-3:
        return generators
    return refined


def _minisum_lp(tempered: np.ndarray, just: np.ndarray, rank: int) -> tuple[np.ndarray, float]:
    k = len(just)
    cost = np.concatenate([np.zeros(rank), np.ones(k)])
    identity = np.eye(k)
    a_ub = np.vstack([np.hstack([tempered, -identity]), np.hstack([-tempered, -identity])])
    b_ub = np.concatenate([just, -just])
    bounds = [(None, None)] * rank + [(0, None)] * k
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
    if not result.success:
        raise ValueError(f"miniaverage linear program did not converge: {result.message}")
    return result.x[:rank], float(result.fun)


def _minisum_optimum_is_unique(
    tempered: np.ndarray, just: np.ndarray, rank: int, optimum: float, tol: float = 1e-6
) -> bool:
    k = len(just)
    identity = np.eye(k)
    a_ub = np.vstack(
        [
            np.hstack([tempered, -identity]),
            np.hstack([-tempered, -identity]),
            np.concatenate([np.zeros(rank), np.ones(k)]),
        ]
    )
    b_ub = np.concatenate([just, -just, [optimum + tol]])
    bounds = [(None, None)] * rank + [(0, None)] * k
    for axis in range(rank):
        direction = np.zeros(rank + k)
        direction[axis] = 1.0
        low = linprog(direction, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
        high = linprog(-direction, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
        if not (low.success and high.success):
            return False
        if (high.x[axis] - low.x[axis]) > 1e-4:
            return False
    return True


def _power_limit(
    tempered: np.ndarray, just: np.ndarray, start: np.ndarray, steps: int = 14
) -> np.ndarray:
    generators = np.array(start, dtype=float)
    scale = max(float(np.max(np.abs(tempered @ generators - just))), 1.0)
    for k in range(1, steps + 1):
        power = 1.0 + 2.0**-k
        result = minimize(
            lambda g: float(np.sum((np.abs(tempered @ g - just) / scale) ** power)),
            generators,
            method="Nelder-Mead",
            options={"xatol": 1e-10, "fatol": 1e-14, "maxiter": 20000},
        )
        generators = result.x
    return generators
