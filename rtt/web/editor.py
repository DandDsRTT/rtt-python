"""Framework-free view-model for the temperament editor.

Holds the current :class:`~rtt.web.service.TemperamentState` plus undo/redo
stacks, and exposes the user actions (edit either matrix, expand/shrink the
domain, undo, redo). It also tracks the two view selections that the derived rows
are shown under — the tuning scheme and the target interval set spec — which sit
outside undo because they are display choices, not temperament edits. The NiceGUI
layer is thin glue over this; all of it is unit-testable without a UI.
"""

from __future__ import annotations

import re

from rtt.web import service
from rtt.web.service import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app


class Editor:
    def __init__(self) -> None:
        self._state: TemperamentState = service.from_mapping(INITIAL_MAPPING)
        # Display/analysis selections: which tuning scheme and target interval set
        # the derived rows are shown under. Unlike the temperament itself, these are
        # view choices (like the Show toggles), so they live outside the undo stack.
        self.tuning_scheme: str = service.DEFAULT_TUNING_SCHEME
        # The target set is a family ("TILT"/"OLD") plus an optional manual limit N.
        # The limit is *weakly held*: any domain (d) change forgets it (see the state
        # setter), so the set reverts to the new domain's default rather than resurrecting.
        self.target_family: str = service.DEFAULT_TARGET_SPEC
        self.target_limit: int | None = None
        # "Other intervals of interest": a user-built set of intervals to watch,
        # held as monzos (edited like the comma basis — editable vector cells).
        # Display data the user curates, not part of the temperament, so (like the
        # tuning/target selections) it lives outside the undo stack.
        self.interest_monzos: list[tuple[int, ...]] = []
        # Held intervals: the optimization's held-just constraints, a user-built set of
        # monzos edited in the held-intervals column (like the intervals of interest). The
        # tuning holds each exactly just; a display/constraint choice, so outside undo.
        self.held_monzos: list[tuple[int, ...]] = []
        # Which generator tuning range the ranges chart shows — diamond-monotone or
        # diamond-tradeoff. A display choice like the two above, so it sits outside undo.
        self.range_mode: str = "monotone"
        # The optimize button's state. ``optimize_locked`` on = auto-optimize every change
        # (the always-optimal default behaviour). Off (single-click action) = the tuning is
        # frozen at ``generator_tuning`` (the last optimum) and stays put under edits until
        # re-optimized. ``generator_tuning`` is None until first frozen (so the load shows
        # the optimum). A display/constraint choice, so it lives outside the undo stack.
        self.optimize_locked: bool = False
        self.generator_tuning: tuple[float, ...] | None = None
        # A comma being added but not yet valid: a draft monzo (d components, each an
        # int or None while blank). It is NOT part of the temperament — the mapping is
        # untouched — until it is filled in with a comma independent of the basis, so
        # d = r + n always holds for the real commas; the draft is shown apart.
        self.pending_comma: list[int | None] | None = None
        self._undo_stack: list[TemperamentState] = []
        self._redo_stack: list[TemperamentState] = []

    @property
    def state(self) -> TemperamentState:
        return self._state

    @state.setter
    def state(self, new_state: TemperamentState) -> None:
        # a domain (d) change forgets the weakly-held manual target limit, so the set
        # reverts to the new domain's default — and does not resurrect if d comes back
        if new_state.d != self._state.d:
            self.target_limit = None
        self._state = new_state

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def target_spec(self) -> str:
        """The active target spec: ``"N-family"`` when a manual limit is set, else the
        bare family (so the set tracks the domain's default). A domain change clears the
        manual limit (see the state setter), so it never resurrects."""
        if self.target_limit is not None:
            return f"{self.target_limit}-{self.target_family}"
        return self.target_family

    @property
    def can_expand(self) -> bool:
        """Whether the domain + applies: only a standard prime limit walks to the next
        prime (a nonstandard subgroup isn't a prime sequence, so the control is inert)."""
        return service.is_standard_domain(self.state.domain_basis)

    @property
    def can_shrink(self) -> bool:
        """Whether the domain − applies: a standard prime limit with a prime to spare
        (a nonstandard subgroup isn't walked by the prime ± controls)."""
        return self.can_expand and self.state.d > 1

    @property
    def can_remove_comma(self) -> bool:
        """Whether the comma − is live: it cancels a pending draft, or (with none)
        drops a real comma without emptying the basis."""
        return self.pending_comma is not None or len(self.state.comma_basis) > 1

    def _apply(self, state: TemperamentState) -> None:
        """Make a temperament edit: snapshot for undo, abandon any comma draft, set state."""
        self._snapshot()
        self.pending_comma = None
        self.state = state

    def edit_mapping(self, mapping) -> None:
        self._apply(service.from_mapping(mapping))

    def edit_comma_basis(self, comma_basis) -> None:
        self._apply(service.from_comma_basis(comma_basis))

    def canonicalize_mapping(self) -> None:
        """Re-store the mapping in canonical form (the mapping box's ``<choose form>``
        control) — an undoable edit, so an equivalent generating set can be normalized."""
        self.edit_mapping(service.canonical_mapping(self.state.mapping))

    def canonicalize_comma_basis(self) -> None:
        """Re-store the comma basis in canonical form (the comma-basis box's
        ``<choose form>`` control) — an undoable edit, like :meth:`canonicalize_mapping`."""
        self.edit_comma_basis(service.canonical_comma_basis(self.state.comma_basis))

    def add_interest(self) -> None:
        """Append a blank interval of interest (a zero monzo = 1/1) for the user to
        edit, mirroring how add_comma seeds a blank comma."""
        self.interest_monzos.append((0,) * self.state.d)

    def remove_interest(self, i: int) -> None:
        """Drop the i-th interval of interest (each one carries its own − control)."""
        del self.interest_monzos[i]

    def set_interest_monzos(self, monzos) -> None:
        """Replace the interest set from the edited vector cells."""
        self.interest_monzos = [tuple(int(x) for x in m) for m in monzos]

    def add_held(self) -> None:
        """Append a blank held interval (a zero monzo = 1/1) for the user to fill in —
        the held-intervals column's + control, mirroring add_interest."""
        self.held_monzos.append((0,) * self.state.d)

    def remove_held(self, i: int) -> None:
        """Drop the i-th held interval (each one carries its own − control)."""
        del self.held_monzos[i]

    def set_held_monzos(self, monzos) -> None:
        """Replace the held-interval set from the edited vector cells."""
        self.held_monzos = [tuple(int(x) for x in m) for m in monzos]

    def optimize(self) -> None:
        """The optimize button's single click: freeze the generator tuning at the scheme's
        current optimum (respecting any held intervals). With the lock off, the frozen tuning
        then stays put as the temperament/scheme change, until optimized again."""
        held = service.comma_ratios(self.held_monzos) if self.held_monzos else ()
        self.generator_tuning = service.tuning(
            self.state.mapping, self.tuning_scheme, held=held
        ).generator_map

    def toggle_optimize_lock(self) -> None:
        """The optimize button's double click: toggle auto-optimize. Locked on, the tuning
        recomputes to the optimum on every change; unlocking freezes it at the current optimum."""
        self.optimize_locked = not self.optimize_locked
        if self.optimize_locked:
            self.generator_tuning = None  # auto: recompute the optimum on every change
        else:
            self.optimize()  # unlocking freezes at the current optimum

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        """The generator tuning the grid should display: None (recompute the optimum) while
        the lock is on or nothing has been frozen yet; else the frozen manual tuning."""
        return None if self.optimize_locked else self.generator_tuning

    def try_edit_mapping_text(self, text: str) -> bool:
        """Parse an EBK map string (honouring a domain-basis prefix, so a nonstandard
        temperament can be typed in) and apply it. Returns False (leaving the state
        untouched) when the text is not a valid integer map, so the caller can flag the
        input rather than mangling the temperament."""
        state = service.parse_mapping_state(text)
        if state is None:
            return False
        self._apply(state)
        return True

    def try_edit_comma_basis_text(self, text: str) -> bool:
        """Parse an EBK vector string and apply it as a comma-basis edit; False
        (state untouched) when it is not a valid integer vector list."""
        basis = service.parse_comma_basis(text)
        if basis is None:
            return False
        try:
            self.edit_comma_basis(basis)
        except Exception:
            return False
        return True

    def set_tuning_scheme(self, scheme: str) -> None:
        self.tuning_scheme = scheme

    def set_complexity_prescaler(self, prescaler: str) -> None:
        """Swap the complexity prescaler (the alt.-complexity control in box 𝐋), which
        re-weights damage and so retunes. Holds the refined scheme as a resolved spec
        (the service/layout take a spec anywhere a scheme name is taken)."""
        self.tuning_scheme = service.scheme_with_prescaler(self.tuning_scheme, prescaler)

    def set_complexity_euclidean(self, euclidean: bool) -> None:
        """Switch the complexity norm between Euclidean (q=2) and taxicab (q=1) — the
        alt.-complexity control in box 𝒄 — which likewise re-weights and retunes."""
        self.tuning_scheme = service.scheme_with_norm(self.tuning_scheme, euclidean)

    def set_optimization_power(self, power: float) -> None:
        """Set the optimization power 𝑝 (the editable field in the optimization box): ∞ for
        minimax, 2 for miniRMS, 1 for miniaverage. Re-solves the tuning under the new Lp norm."""
        self.tuning_scheme = service.scheme_with_power(self.tuning_scheme, power)

    def set_target_spec(self, spec: str) -> None:
        """Set the target family and (optional) manual limit from a spec like ``"9-TILT"``
        or ``"OLD"``. A manual limit is weakly held — the next domain change forgets it."""
        match = re.match(r"(\d*)-?(TILT|OLD)", spec)
        n, family = (match.group(1), match.group(2)) if match else ("", self.target_family)
        self.target_family = family
        self.target_limit = int(n) if n else None

    def set_range_mode(self, mode: str) -> None:
        self.range_mode = mode

    def expand(self) -> None:
        if not self.can_expand:
            return  # the prime walk doesn't apply to a nonstandard subgroup
        self._snapshot()
        self.pending_comma = None  # the draft's length is tied to the old domain
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        if not self.can_shrink:
            return
        self._snapshot()
        self.pending_comma = None
        self.state = service.shrink_domain(self.state)

    def add_comma(self) -> None:
        """Begin a pending comma: a blank draft column for the user to fill in. It is
        not part of the temperament (the mapping is unchanged) and not an undoable
        edit until it commits — see set_pending_comma."""
        self.pending_comma = [None] * self.state.d

    def set_pending_comma(self, values) -> None:
        """Hold the draft comma's edited components. Once all are filled and the comma
        is independent of the basis (so it genuinely raises the nullity), commit it —
        re-dualing to a mapping with one fewer row — and clear the draft. An
        incomplete or dependent draft is kept as-is (shown pending), changing nothing."""
        self.pending_comma = list(values)
        if any(v is None for v in values):
            return  # still being typed in
        extended = service.from_comma_basis(self.state.comma_basis + (tuple(int(v) for v in values),))
        if extended.n > self.state.n:  # an independent new comma re-ranks the temperament
            self._snapshot()
            self.state = extended
            self.pending_comma = None

    def remove_comma(self) -> None:
        if self.pending_comma is not None:
            self.pending_comma = None  # cancel the draft (not an undoable edit)
            return
        self._snapshot()
        self.state = service.remove_comma(self.state)

    def undo(self) -> None:
        if self._undo_stack:
            self._redo_stack.append(self.state)
            self.state = self._undo_stack.pop()

    def redo(self) -> None:
        if self._redo_stack:
            self._undo_stack.append(self.state)
            self.state = self._redo_stack.pop()

    def _snapshot(self) -> None:
        self._undo_stack.append(self.state)
        self._redo_stack.clear()  # a fresh action invalidates the redo history
