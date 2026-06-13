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
    """Solve for the generators minimizing the ``power``-norm of (tempered·g − just).

    An underdetermined system (the target rows not spanning the generator space) leaves the free
    directions at 0 here; :func:`rtt.library.tuning._default_free_generators_to_just` then defaults
    them to the just tuning rather than to 0 cents (a benign no-op when fully determined)."""
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
        if low.success and abs((tempered[i] @ low.x - just[i]) - delta) <= tol * scale:
            locked.append((i, just[i] + delta))
            continue
        high = linprog(-tempered[i], A_ub=a_ub, b_ub=b_ub, A_eq=a_eq, b_eq=b_eq, bounds=bounds)
        if high.success and abs((tempered[i] @ high.x - just[i]) + delta) <= tol * scale:
            locked.append((i, just[i] - delta))
    return locked


def _minisum(tempered: np.ndarray, just: np.ndarray, rank: int) -> np.ndarray:
    """Minimize the sum of absolute damages (p = 1 / miniaverage).

    A plain LP returns *an* optimal vertex, but the optimum is often a tied range of vertices,
    and the LP lands on an arbitrary endpoint. The true miniaverage tuning is the limit of the
    p-norm optimum as p → 1⁺ (tuning-fundamentals MUST-GET-RIGHT 12 / units MUST-GET-RIGHT 8:
    the power-limit schedule), which is the *interior* of the tied range, not an endpoint —
    the p = 1 counterpart of the nested tie-break the p = ∞ path already does.

    The uniqueness check is only a fast-path that skips the power limit when the optimum is clearly
    a single point; it never asserts uniqueness it can't certify (an LP that fails to converge —
    e.g. under heavy parallel load — counts as *not* unique). So the power limit also runs whenever
    uniqueness is uncertain, and the snap-back below makes that harmless: a power limit seeded at a
    determined optimum doesn't move it at all (verified ~0 cents), while a genuinely tied optimum is
    pulled a meaningful distance into the range's interior. Snapping back to the exact LP vertex
    when the move is negligible keeps determined miniaverage tunings bit-stable regardless of which
    branch ran."""
    generators, optimum = _minisum_lp(tempered, just, rank)
    if _minisum_optimum_is_unique(tempered, just, rank, optimum):
        return generators
    refined = _power_limit(tempered, just, generators)
    if float(np.max(np.abs(refined - generators))) < 1e-3:
        return generators  # a determined optimum after all: the LP vertex is exact, don't drift it
    return refined


def _minisum_lp(tempered: np.ndarray, just: np.ndarray, rank: int) -> tuple[np.ndarray, float]:
    """The minisum LP (a slack per target): the optimal generators and the minimized Σ damage."""
    k = len(just)
    cost = np.concatenate([np.zeros(rank), np.ones(k)])  # minimize Σ slack
    identity = np.eye(k)
    a_ub = np.vstack(
        [np.hstack([tempered, -identity]), np.hstack([-tempered, -identity])]
    )
    b_ub = np.concatenate([just, -just])
    bounds = [(None, None)] * rank + [(0, None)] * k
    result = linprog(cost, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
    if not result.success:
        raise ValueError(f"miniaverage linear program did not converge: {result.message}")
    return result.x[:rank], float(result.fun)


def _minisum_optimum_is_unique(
    tempered: np.ndarray, just: np.ndarray, rank: int, optimum: float, tol: float = 1e-6
) -> bool:
    """Whether the minisum optimum is *certainly* a single point (vs. a tied range). For each
    generator, push it as low and as high as possible while the total damage stays at the optimum:
    any coordinate with a nonzero achievable range means the optimum is non-unique.

    Conservative on purpose: this only ever returns ``True`` (skip the power-limit tie-break) when
    every probe LP converged and pinned every coordinate. A probe LP that fails to converge (which
    can happen transiently under heavy parallel CPU load) returns ``False`` — *not unique* — so the
    caller falls through to the power limit + snap-back rather than wrongly certifying a tied
    optimum as unique. Wrongly running the tie-break on a determined optimum is harmless (it snaps
    back); wrongly skipping it on a tied one is not."""
    k = len(just)
    identity = np.eye(k)
    a_ub = np.vstack([
        np.hstack([tempered, -identity]),
        np.hstack([-tempered, -identity]),
        np.concatenate([np.zeros(rank), np.ones(k)]),  # Σ damage ≤ optimum (within tol)
    ])
    b_ub = np.concatenate([just, -just, [optimum + tol]])
    bounds = [(None, None)] * rank + [(0, None)] * k
    for axis in range(rank):
        direction = np.zeros(rank + k)
        direction[axis] = 1.0
        low = linprog(direction, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
        high = linprog(-direction, A_ub=a_ub, b_ub=b_ub, bounds=bounds)
        if not (low.success and high.success):
            return False  # can't certify uniqueness → let the power limit + snap-back decide
        if (high.x[axis] - low.x[axis]) > 1e-4:
            return False
    return True


def _power_limit(
    tempered: np.ndarray, just: np.ndarray, start: np.ndarray, steps: int = 14
) -> np.ndarray:
    """The p → 1⁺ limit of the p-norm optimum: minimize the (scaled) sum of damages**p for
    p = 1 + 2⁻ᵏ stepping toward 1, each step seeded from the last (units MUST-GET-RIGHT 8's
    power-limit schedule). Resolves a tied p = 1 optimum to its unique interior limit; the
    scaling keeps the powered damages from under/overflowing as p approaches 1."""
    generators = np.array(start, dtype=float)
    scale = max(float(np.max(np.abs(tempered @ generators - just))), 1.0)
    for k in range(1, steps + 1):
        power = 1.0 + 2.0 ** -k
        result = minimize(
            lambda g: float(np.sum((np.abs(tempered @ g - just) / scale) ** power)),
            generators,
            method="Nelder-Mead",
            options={"xatol": 1e-10, "fatol": 1e-14, "maxiter": 20000},
        )
        generators = result.x
    return generators
