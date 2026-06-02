"""Framework-free view-model for the temperament editor.

Holds the whole editor *document* — everything the user can change — and the
undo/redo history over it. The document bundles the temperament
(:class:`~rtt.web.service.TemperamentState`), the view selections shown over it
(tuning scheme, target interval set, intervals of interest, held intervals, range
mode, optimize lock) and the UI state (the Show settings and the folded
rows/columns/tiles). It is all one history: any change snapshots the whole
document, undo/redo swap snapshots, :meth:`Editor.reset` restores the defaults, and
:meth:`Editor.serialize`/:meth:`Editor.load` persist it across a page refresh. The
NiceGUI layer is thin glue over this; all of it is unit-testable without a UI.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass

from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.layout import Layout
from rtt.web.service import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app
# The rows/columns/tiles folded to strips in the as-shipped view (the mockup's
# default): the commas and "other intervals of interest" columns and the
# interval-vectors row. Reset returns to exactly this fold state.
INITIAL_COLLAPSED: frozenset[str] = frozenset({"col:commas", "col:interest", "row:vectors"})


@dataclass(frozen=True)
class _Doc:
    """An immutable snapshot of the whole document — the unit of undo/redo, reset
    and persistence. Mutable collections are kept in immutable form (tuples, a
    frozenset, sorted setting items) so a stored snapshot can never be mutated in
    place; :meth:`Editor._restore` copies them back to the editor's working forms."""

    state: TemperamentState
    tuning_scheme: object  # str (a named scheme) | TuningSchemeSpec (a control-refined one)
    target_family: str
    target_limit: int | None
    interest_monzos: tuple[tuple[int, ...], ...]
    held_monzos: tuple[tuple[int, ...], ...]
    range_mode: str
    optimize_locked: bool
    generator_tuning: tuple[float, ...] | None
    # The user's override for the complexity prescaler 𝐿's diagonal — d floats, one per
    # domain prime. ``None`` means "no override": every weighting calculation falls back to
    # the scheme's computed diagonal (log_prime / prime / identity, per the alt.-complexity
    # traits), so the bare prescaler tile shows that, and complexity / damage / tuning flow
    # from it as they always did. Once set, the override drives EVERY downstream consumer
    # (the prescaler tile's cells, the 𝐿·basis product tiles, complexity, weights, the
    # tuning solve and its derived retunings/damages) — the bare tile is the single source
    # of truth for the prescaler. Stored as a d-tuple (the diagonal) rather than the full
    # d×d matrix because 𝐿 IS conceptually diag(...); off-diagonal cells are pinned at 0.
    custom_prescaler: tuple[float, ...] | None
    target_override: tuple[str, ...] | None  # a typed explicit target list, overriding the TILT/OLD spec
    settings: tuple[tuple[str, bool], ...]
    collapsed: frozenset[str]


@functools.lru_cache(maxsize=1)
def _initial_doc() -> _Doc:
    """The default document — the state a fresh Editor and :meth:`Editor.reset` start
    from. Cached (and immutable) so the as-shipped baseline is computed once."""
    return _Doc(
        state=service.from_mapping(INITIAL_MAPPING),
        # all-interval is OFF by default: the as-shipped scheme targets the displayed interval
        # list (the default TILT family), so the target-controls "all-interval" checkbox starts
        # unchecked. It stays a named string ("TILT minimax-S") so the chooser still names it.
        tuning_scheme=f"{service.DEFAULT_TARGET_SPEC} {service.DEFAULT_TUNING_SCHEME}",
        target_family=service.DEFAULT_TARGET_SPEC,
        target_limit=None,
        interest_monzos=(),
        held_monzos=(),
        range_mode="monotone",
        optimize_locked=False,
        generator_tuning=None,
        custom_prescaler=None,
        target_override=None,
        settings=tuple(sorted(show_settings.defaults().items())),
        collapsed=INITIAL_COLLAPSED,
    )


class Editor:
    def __init__(self) -> None:
        self._undo_stack: list[_Doc] = []
        self._redo_stack: list[_Doc] = []
        # A comma being added but not yet valid: a draft monzo (d components, each an
        # int or None while blank). It is NOT part of the document — the mapping is
        # untouched, and a draft does not survive undo/redo/reset/load — until it is
        # filled in with a comma independent of the basis, at which point it commits.
        self.pending_comma: list[int | None] | None = None
        self._restore(_initial_doc())

    # --- the document: capture / restore (the unit of undo, reset, persistence) ---

    def _capture(self) -> _Doc:
        """Freeze the current document into a snapshot."""
        return _Doc(
            state=self._state,
            tuning_scheme=self.tuning_scheme,
            target_family=self.target_family,
            target_limit=self.target_limit,
            interest_monzos=tuple(self.interest_monzos),
            held_monzos=tuple(self.held_monzos),
            range_mode=self.range_mode,
            optimize_locked=self.optimize_locked,
            generator_tuning=self.generator_tuning,
            custom_prescaler=self.custom_prescaler,
            target_override=self.target_override,
            settings=tuple(sorted(self.settings.items())),
            collapsed=frozenset(self.collapsed),
        )

    def _restore(self, doc: _Doc) -> None:
        """Make ``doc`` the live document, copying its immutable collections back to
        the editor's working (mutable) forms. Sets ``_state`` directly so the state
        setter's weakly-held-limit side effect does not fire on an undo/redo."""
        self._state = doc.state
        self.tuning_scheme = doc.tuning_scheme
        self.target_family = doc.target_family
        self.target_limit = doc.target_limit
        self.interest_monzos = [tuple(m) for m in doc.interest_monzos]
        self.held_monzos = [tuple(m) for m in doc.held_monzos]
        self.range_mode = doc.range_mode
        self.optimize_locked = doc.optimize_locked
        self.generator_tuning = doc.generator_tuning
        self.custom_prescaler = doc.custom_prescaler
        self.target_override = doc.target_override
        self.settings = dict(doc.settings)
        self.collapsed = set(doc.collapsed)
        self.pending_comma = None  # a draft never survives a document restore

    @property
    def state(self) -> TemperamentState:
        return self._state

    @state.setter
    def state(self, new_state: TemperamentState) -> None:
        # a domain (d) change forgets the weakly-held manual target limit and any typed
        # target list, so the set reverts to the new domain's default — and does not
        # resurrect if d comes back
        if new_state.d != self._state.d:
            self.target_limit = None
            self.target_override = None
        self._state = new_state

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def can_reset(self) -> bool:
        """Whether the document differs from the as-shipped defaults — i.e. whether
        the reset control has anything to restore."""
        return self._capture() != _initial_doc()

    @property
    def target_spec(self) -> str:
        """The active target spec: ``"N-family"`` when a manual limit is set, else the
        bare family (so the set tracks the domain's default). A domain change clears the
        manual limit (see the state setter), so it never resurrects."""
        if self.target_limit is not None:
            return f"{self.target_limit}-{self.target_family}"
        return self.target_family

    def layout(self) -> Layout:
        """Build the rendered spreadsheet model for the current document — the single
        source of how the editor's state maps to the grid. The page render and the render
        tests both go through here rather than re-spelling spreadsheet.build's arguments."""
        return spreadsheet.build(
            self.state, self.settings, self.collapsed, self.tuning_scheme, self.target_spec,
            interest=self.interest_monzos, range_mode=self.range_mode,
            pending_comma=self.pending_comma, held_monzos=self.held_monzos,
            generator_tuning=self.effective_generator_tuning(),
            target_override=self.target_override,
            custom_prescaler=self.custom_prescaler,
            optimize_locked=self.optimize_locked)

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
        self._snapshot()
        self.interest_monzos.append((0,) * self.state.d)

    def remove_interest(self, i: int) -> None:
        """Drop the i-th interval of interest (each one carries its own − control)."""
        self._snapshot()
        del self.interest_monzos[i]

    def set_interest_monzos(self, monzos) -> None:
        """Replace the interest set from the edited vector cells."""
        self._snapshot()
        self.interest_monzos = [tuple(int(x) for x in m) for m in monzos]

    def add_held(self) -> None:
        """Append a blank held interval (a zero monzo = 1/1) for the user to fill in —
        the held intervals column's + control, mirroring add_interest."""
        self._snapshot()
        self.held_monzos.append((0,) * self.state.d)

    def remove_held(self, i: int) -> None:
        """Drop the i-th held interval (each one carries its own − control)."""
        self._snapshot()
        del self.held_monzos[i]

    def set_held_monzos(self, monzos) -> None:
        """Replace the held interval set from the edited vector cells."""
        self._snapshot()
        self.held_monzos = [tuple(int(x) for x in m) for m in monzos]

    def _optimum_generator_tuning(self) -> tuple[float, ...]:
        """The scheme's current optimal generator tuning, respecting any held intervals."""
        held = service.comma_ratios(self.held_monzos) if self.held_monzos else ()
        return service.tuning(self.state.mapping, self.tuning_scheme, held=held).generator_map

    def optimize(self) -> None:
        """The optimize button's single click: freeze the generator tuning at the scheme's
        current optimum (respecting any held intervals). With the lock off, the frozen tuning
        then stays put as the temperament/scheme change, until optimized again. Idempotent —
        re-optimizing to the same tuning (e.g. the extra clicks a double-click fires) does not
        push a redundant undo step."""
        optimum = self._optimum_generator_tuning()
        if optimum == self.generator_tuning:
            return
        self._snapshot()
        self.generator_tuning = optimum

    def toggle_optimize_lock(self) -> None:
        """The optimize button's double click: toggle auto-optimize. Locked on, the tuning
        recomputes to the optimum on every change; unlocking freezes it at the current optimum."""
        self._snapshot()
        self.optimize_locked = not self.optimize_locked
        # auto: recompute the optimum on every change (None); unlocking freezes at it now
        self.generator_tuning = None if self.optimize_locked else self._optimum_generator_tuning()

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        """The generator tuning the grid should display: None (recompute the optimum) while
        the lock is on or nothing has been frozen yet; else the frozen manual tuning."""
        return None if self.optimize_locked else self.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        """The named scheme the grid's *displayed* tuning realises, or None — for which the
        tuning chooser shows "-". None when the scheme is a control-refined spec (no name), or
        when a manual generator-tuning override is in effect and deviates from the scheme's
        optimum (the user hand-edited the generator tuning map), so the shown tuning no longer
        matches the selected scheme. A frozen tuning still equal to the optimum, or a stale
        override the grid ignores (its generator count no longer fits the mapping), keeps the
        scheme's name — those still show the scheme's own tuning."""
        if not isinstance(self.tuning_scheme, str):
            return None
        override = self.effective_generator_tuning()
        if (override is not None and len(override) == len(self.state.mapping)
                and override != self._optimum_generator_tuning()):
            return None
        # the chooser lists base names (its label T-prefixes a target-based scheme), so drop any
        # target prefix here — a target-based "TILT minimax-S" shows as the "minimax-S" entry
        return service.base_scheme_name(self.tuning_scheme)

    def set_generator_tuning_text(self, text: str) -> bool:
        """Freeze a typed manual generator tuning (the editable generator tuning map): parse a
        cents map of exactly r values and hold it, turning auto-optimize off (a manual tuning
        and auto-optimize are mutually exclusive). False (state untouched) when it is not r
        cents values, so the caller can flag the input rather than mangling the tuning."""
        gens = service.parse_cents_map(text, len(self.state.mapping))
        if gens is None:
            return False
        self._snapshot()
        self.optimize_locked = False
        self.generator_tuning = gens
        return True

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        """Override one generator's tuning (one editable generator-tuning-map cell), seeding
        the rest from the frozen tuning or, when none is frozen, the current optimum. Turns
        auto-optimize off, like a typed tuning."""
        base = self.effective_generator_tuning() or self._optimum_generator_tuning()
        new = list(base)
        new[i] = float(cents)
        self._snapshot()
        self.optimize_locked = False
        self.generator_tuning = tuple(new)

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

    def set_tuning_scheme(self, name: str) -> None:
        """Apply a systematic scheme name from the established-tuning-scheme chooser, preserving
        the current target mode: all-interval when the scheme currently targets every interval,
        else over the displayed target list (the chooser's T-prefixed entries). Drops any manual
        generator-tuning override so the grid snaps to the chosen scheme's optimum — re-selecting
        a scheme after hand-editing the tuning re-applies it. Undoable."""
        self._snapshot()
        self.tuning_scheme = name if service.is_all_interval(self.tuning_scheme) \
            else f"{self.target_spec} {name}"  # keep it a named string so the chooser can name it
        self.generator_tuning = None

    def set_complexity_prescaler(self, prescaler: str) -> None:
        """Swap the complexity prescaler (the alt.-complexity control in box 𝐋), which
        re-weights damage and so retunes. Holds the refined scheme as a resolved spec
        (the service/layout take a spec anywhere a scheme name is taken). Also CLEARS
        any custom-prescaler override — picking a named preset is the user's reset path,
        snapping the bare prescaler tile back to the scheme's computed diagonal."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_prescaler(self.tuning_scheme, prescaler)
        self.custom_prescaler = None

    def set_complexity_euclidean(self, euclidean: bool) -> None:
        """Switch the complexity norm between Euclidean (q=2) and taxicab (q=1) — the
        alt.-complexity control in box 𝒄 — which likewise re-weights and retunes."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_norm(self.tuning_scheme, euclidean)

    def set_optimization_power(self, power: float) -> None:
        """Set the optimization power 𝑝 (the editable field in the optimization box): ∞ for
        minimax, 2 for miniRMS, 1 for miniaverage. Re-solves the tuning under the new Lp norm."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_power(self.tuning_scheme, power)

    def set_weight_slope(self, slope: str) -> None:
        """Swap the damage-weight slope (the weight box's chooser in box 𝒘) — whether each
        target's weight is its complexity, 1, or 1/complexity — which retunes accordingly."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)

    def set_complexity_name(self, name: str) -> None:
        """Set the whole complexity shape from the predefined-complexities master chooser (box
        𝒄) — prescaler, size factor and norm at once, overriding the box 𝐋/𝒄 fine controls —
        which re-weights and retunes. Also CLEARS the custom-prescaler override: every named
        complexity carries its own prescaler trait, so a preset pick is the user's reset path
        away from a hand-edited diagonal back to the named complexity's computed diagonal."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_complexity(self.tuning_scheme, name)
        self.custom_prescaler = None

    def set_custom_prescaler_entry(self, i: int, value: float) -> None:
        """Edit one diagonal entry of the prescaler 𝐿 — the bare prescaler tile's editable
        cells call this on every change. The first edit *seeds* the override from the current
        scheme's diagonal (so the d-1 other cells keep their displayed values rather than
        snapping to silent zeros); subsequent edits mutate the seeded tuple."""
        self._snapshot()
        if self.custom_prescaler is None:
            seed = service.complexity_prescaler(self.state.mapping, self.tuning_scheme)
            self.custom_prescaler = tuple(seed)
        diag = list(self.custom_prescaler)
        diag[i] = float(value)
        self.custom_prescaler = tuple(diag)

    def set_custom_prescaler_text(self, text: str) -> bool:
        """Freeze a typed manual prescaler diagonal — the bare prescaler 𝐿 tile's editable
        plain-text dual. Parses the d×d covariant matrix the tile renders (with off-diagonal
        zeros) and stores its diagonal as the override, replacing any prior cell-by-cell
        edits in one step. False (state untouched) when the text isn't a valid d×d matrix
        with all off-diagonal entries zero, so the caller can flag the input rather than
        mangling 𝐿. Distinct from :meth:`set_custom_prescaler_entry` (per-cell): this writes
        the WHOLE diagonal at once, the way a typed dual replaces the whole structure."""
        diag = service.parse_prescaler_diagonal(text, self.state.d)
        if diag is None:
            return False
        self._snapshot()
        self.custom_prescaler = diag
        return True

    def clear_custom_prescaler(self) -> None:
        """Drop the custom override — every weighting calculation reverts to the live
        scheme's computed diagonal. The Show-panel reset path uses :meth:`reset` (which
        clears the whole document); this is the targeted clear that the preset choosers
        and the bare prescaler tile's revert control rely on."""
        if self.custom_prescaler is None:
            return  # no-op so a redundant revert doesn't push an empty undo step
        self._snapshot()
        self.custom_prescaler = None

    def set_diminuator_replaced(self, replaced: bool) -> None:
        """Toggle the size factor (the box 𝐋 "replace diminuator" checkbox) — the integer-limit
        shear that turns lp into lils — which re-weights and retunes."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_diminuator(self.tuning_scheme, replaced)

    def set_all_interval(self, all_interval: bool) -> None:
        """Toggle the target-controls all-interval checkbox: checked targets every interval (the
        empty set — an all-interval scheme), unchecked targets the displayed interval list (the
        live target spec). Switches the scheme's target set accordingly (an undoable edit). A
        named scheme keeps its name (the target prefix is added/dropped) so the chooser can still
        name it; a control-refined spec stays a spec."""
        self._snapshot()
        base = service.base_scheme_name(self.tuning_scheme)
        if base is None:  # a refined spec has no name — keep the spec form
            self.tuning_scheme = service.scheme_with_targets(
                self.tuning_scheme, "{}" if all_interval else self.target_spec)
        else:
            self.tuning_scheme = base if all_interval else f"{self.target_spec} {base}"

    def set_target_spec(self, spec: str) -> None:
        """Set the target family and (optional) manual limit from a spec like ``"9-TILT"``
        or ``"OLD"``. A manual limit is weakly held — the next domain change forgets it.
        Choosing a scheme clears any typed target list (the chooser and the manual list are
        alternatives)."""
        self._snapshot()
        match = re.match(r"(\d*)-?(TILT|OLD)", spec)
        n, family = (match.group(1), match.group(2)) if match else ("", self.target_family)
        self.target_family = family
        self.target_limit = int(n) if n else None
        self.target_override = None
        # a target-based scheme tracks the displayed interval list: re-prefix it to the new
        # family/limit (an all-interval scheme ignores the list, so leave it untouched)
        base = service.base_scheme_name(self.tuning_scheme)
        if base is not None and not service.is_all_interval(self.tuning_scheme):
            self.tuning_scheme = f"{self.target_spec} {base}"

    def set_target_override_text(self, text: str) -> bool:
        """Set an explicit target interval list from a typed EBK vector string (the editable
        target interval list plain text). Stored as ratios, overriding the TILT/OLD spec until
        the spec is re-chosen or the domain changes. False (state untouched) when it is not a
        valid integer vector list, so the caller can flag the input."""
        monzos = service.parse_comma_basis(text)
        if monzos is None:
            return False
        self._snapshot()
        self.target_override = service.comma_ratios(monzos, self.state.domain_basis)
        return True

    def set_target_override_monzos(self, monzos) -> None:
        """Set the explicit target list from edited monzo columns (the editable target
        interval list cells), like :meth:`set_interest_monzos` — stored back as ratios."""
        self._snapshot()
        self.target_override = service.comma_ratios(
            [tuple(int(x) for x in m) for m in monzos], self.state.domain_basis)

    def set_range_mode(self, mode: str) -> None:
        self._snapshot()
        self.range_mode = mode

    def set_show(self, key: str, value: bool) -> None:
        """Set one Show toggle (which parts of the grid are visible) — an undoable change.
        Deselecting a toggle also deselects every sub-control nested under it, so a hidden
        parent never strands its sub-controls' content (or panel rows) on screen."""
        self._snapshot()
        self.settings[key] = value
        if not value:
            for child in show_settings.subcontrols_of(key):
                self.settings[child] = False

    def set_all_show(self, value: bool) -> None:
        """The settings panel's select-all/none: turn every *implemented* Show toggle on
        (``True``) or off (``False``) at once. The not-yet-built toggles are left at their
        defaults (the user can't toggle them individually either)."""
        self._snapshot()
        for key in show_settings.IMPLEMENTED:
            self.settings[key] = value

    def toggle_collapsed(self, item: str) -> None:
        """Fold or unfold one row, column, or tile (``"row:tuning"``, ``"col:targets"``,
        ``"tile:mapping:primes"``) — an undoable change to the expand/collapse state."""
        self._snapshot()
        self.collapsed.discard(item) if item in self.collapsed else self.collapsed.add(item)

    def set_collapsed(self, items) -> None:
        """Replace the whole set of folded ids (the master expand/collapse-all toggle
        computes the next set from the layout) — an undoable change."""
        self._snapshot()
        self.collapsed = set(items)

    def reset(self) -> None:
        """Restore the entire document to the as-shipped defaults — temperament values,
        view selections, Show settings and expand/collapse state — as one undoable action."""
        if not self.can_reset:
            return
        self._snapshot()
        self._restore(_initial_doc())

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
            self._redo_stack.append(self._capture())
            self._restore(self._undo_stack.pop())

    def redo(self) -> None:
        if self._redo_stack:
            self._undo_stack.append(self._capture())
            self._restore(self._redo_stack.pop())

    def _snapshot(self) -> None:
        self._undo_stack.append(self._capture())
        self._redo_stack.clear()  # a fresh action invalidates the redo history

    def serialize(self) -> dict:
        """The whole document as a JSON-safe dict, for persisting across a page refresh.
        The temperament rides as its (domain-prefixed) EBK string so a nonstandard domain
        round-trips; the tuning scheme is name-or-spec via the service (inf power encoded)."""
        return {
            "mapping_ebk": service.mapping_ebk(self._state),
            "tuning_scheme": service.scheme_to_json(self.tuning_scheme),
            "target_family": self.target_family,
            "target_limit": self.target_limit,
            "interest_monzos": [list(m) for m in self.interest_monzos],
            "held_monzos": [list(m) for m in self.held_monzos],
            "range_mode": self.range_mode,
            "optimize_locked": self.optimize_locked,
            "generator_tuning": list(self.generator_tuning) if self.generator_tuning is not None else None,
            "custom_prescaler": list(self.custom_prescaler) if self.custom_prescaler is not None else None,
            "target_override": list(self.target_override) if self.target_override is not None else None,
            "settings": dict(self.settings),
            "collapsed": sorted(self.collapsed),
        }

    def load(self, data: dict) -> None:
        """Restore a document previously produced by :meth:`serialize`. Unknown/missing
        keys — and any greyed, not-yet-live Show toggle — fall back to defaults (so an
        older saved state still loads, and a shelved feature can't be re-exposed by stale
        saved state); an unparseable temperament leaves the editor untouched. Builds the
        snapshot fully before swapping it in, so a malformed field can't leave a half-
        loaded state. A load is a fresh start, so it clears the undo/redo history."""
        state = service.parse_mapping_state(data["mapping_ebk"])
        if state is None:
            return
        doc = _Doc(
            state=state,
            tuning_scheme=service.scheme_from_json(data["tuning_scheme"]),
            target_family=data.get("target_family", service.DEFAULT_TARGET_SPEC),
            target_limit=data.get("target_limit"),
            interest_monzos=tuple(tuple(int(x) for x in m) for m in data.get("interest_monzos", ())),
            held_monzos=tuple(tuple(int(x) for x in m) for m in data.get("held_monzos", ())),
            range_mode=data.get("range_mode", "monotone"),
            optimize_locked=bool(data.get("optimize_locked", False)),
            generator_tuning=tuple(data["generator_tuning"])
            if data.get("generator_tuning") is not None else None,
            custom_prescaler=tuple(float(x) for x in data["custom_prescaler"])
            if data.get("custom_prescaler") is not None else None,
            target_override=tuple(data["target_override"])
            if data.get("target_override") is not None else None,
            settings=tuple(sorted(show_settings.from_persisted(data.get("settings", {})).items())),
            collapsed=frozenset(data.get("collapsed", INITIAL_COLLAPSED)),
        )
        self._restore(doc)
        self._undo_stack.clear()
        self._redo_stack.clear()
