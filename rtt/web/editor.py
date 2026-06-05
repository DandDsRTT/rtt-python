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
from fractions import Fraction

from rtt.web import service
from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.layout import Layout
from rtt.web.service import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app
# The rows/columns/tiles folded to strips on a fresh start and after Reset. Empty:
# nothing starts folded — the default view opens every row and column.
INITIAL_COLLAPSED: frozenset[str] = frozenset()
# One mouse-wheel notch over a generator-tuning-map cell nudges that generator by this many
# cents — a thousandth, the last digit the cell's 3-dp cents face shows (see service.cents).
_GENERATOR_NUDGE_CENTS = 0.001


def _same_cents_map(a, b) -> bool:
    """Whether two generator tunings are equal at DISPLAY precision — the cents the grid actually
    shows (:func:`service.cents`). Comparing what's shown (not bit-exact floats) means a tuning
    frozen or typed back at its displayed value reads as 'no deviation', mirroring how
    :func:`service.displayed_prescaler_name` compares prescaler diagonals."""
    return len(a) == len(b) and all(service.cents(x) == service.cents(y) for x, y in zip(a, b))


@dataclass(frozen=True)
class _Doc:
    """An immutable snapshot of the whole document — the unit of undo/redo, reset
    and persistence. Mutable collections are kept in immutable form (tuples, a
    frozenset, sorted setting items) so a stored snapshot can never be mutated in
    place; :meth:`Editor._restore` copies them back to the editor's working forms."""

    state: TemperamentState
    tuning_scheme: object  # a TuningSchemeSpec (the canonical representation; named via the renderer)
    target_family: str
    target_limit: int | None
    interest_vectors: tuple[tuple[int, ...], ...]
    held_vectors: tuple[tuple[int, ...], ...]
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
    state = service.from_mapping(INITIAL_MAPPING)
    return _Doc(
        state=state,
        # all-interval is OFF by default: the as-shipped scheme targets the displayed interval
        # list (the default TILT family) at unity weight, so the target-controls "all-interval"
        # checkbox starts unchecked. Held as a resolved spec — the canonical representation the
        # whole editor now uses — which the chooser names back via the renderer ("minimax-U").
        tuning_scheme=service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME),
        target_family=service.DEFAULT_TARGET_SPEC,
        target_limit=None,
        interest_vectors=(),
        held_vectors=(),
        range_mode="monotone",
        optimize_locked=False,
        # auto-optimize is OFF by default: the generator tuning starts FROZEN at the as-shipped
        # scheme's optimum, so the tuning shows correctly at startup but does NOT silently re-
        # optimize as the temperament/targets change (that auto-recompute is the optimize lock,
        # off here). A frozen value — not None, which means "auto" — keeps the button unlocked
        # and the state consistent; the user clicks optimize to retune.
        generator_tuning=service.tuning(state.mapping, service.DEFAULT_DOCUMENT_SCHEME).generator_map,
        custom_prescaler=None,
        target_override=None,
        settings=tuple(sorted(show_settings.defaults().items())),
        collapsed=INITIAL_COLLAPSED,
    )


class Editor:
    def __init__(self) -> None:
        self._undo_stack: list[_Doc] = []
        self._redo_stack: list[_Doc] = []
        # An interval being added but not yet complete: a draft vector (d components, each
        # an int or None while blank), one per addable column. It is NOT part of the
        # document and does not survive undo/redo/reset/load; it renders as a blank,
        # red-outlined column the user fills in. The comma's draft commits once it is a
        # comma independent of the basis (re-ranking the mapping); the interval-list drafts
        # (interest, held, target) commit once every component is filled.
        self.pending_comma: list[int | None] | None = None
        self.pending_interest: list[int | None] | None = None
        self.pending_held: list[int | None] | None = None
        self.pending_target: list[int | None] | None = None
        # The generator a wheel nudge is currently fine-tuning, so consecutive notches on it
        # coalesce into one undo step (see nudge_generator_tuning_component). Transient, like the
        # drafts: any snapshot or document restore clears it, ending the gesture.
        self._nudging_generator: int | None = None
        self._restore(_initial_doc())

    # --- the document: capture / restore (the unit of undo, reset, persistence) ---

    def _capture(self) -> _Doc:
        """Freeze the current document into a snapshot."""
        return _Doc(
            state=self._state,
            tuning_scheme=self.tuning_scheme,
            target_family=self.target_family,
            target_limit=self.target_limit,
            interest_vectors=tuple(self.interest_vectors),
            held_vectors=tuple(self.held_vectors),
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
        self.interest_vectors = [tuple(m) for m in doc.interest_vectors]
        self.held_vectors = [tuple(m) for m in doc.held_vectors]
        self.range_mode = doc.range_mode
        self.optimize_locked = doc.optimize_locked
        self.generator_tuning = doc.generator_tuning
        self.custom_prescaler = doc.custom_prescaler
        self.target_override = doc.target_override
        self.settings = dict(doc.settings)
        self.collapsed = set(doc.collapsed)
        self._clear_pending()  # a draft never survives a document restore
        self._nudging_generator = None  # nor does an in-progress wheel gesture (undo/redo/reset/load)

    def capture_for_preview(self) -> tuple:
        """Snapshot the WHOLE editor — document plus undo/redo history — so a hypothetical edit can
        be applied (through the normal edit methods, which would otherwise push an undo step) for a
        live preview, then fully reverted via :meth:`restore_for_preview`, leaving no trace. The
        drag-to-combine drop preview uses this to show the would-be result while hovering, without
        committing it or polluting the undo history."""
        return (self._capture(), list(self._undo_stack), list(self._redo_stack))

    def restore_for_preview(self, token: tuple) -> None:
        """Revert to a :meth:`capture_for_preview` snapshot — document and history both."""
        doc, undo, redo = token
        self._restore(doc)
        self._undo_stack[:] = undo
        self._redo_stack[:] = redo

    def _clear_pending(self) -> None:
        """Discard every in-progress draft. Called whenever the document or domain shifts
        out from under the drafts (restore/undo/redo, a temperament edit, a domain ±) —
        each draft's length is tied to the current d, so a domain change invalidates it."""
        self.pending_comma = None
        self.pending_interest = None
        self.pending_held = None
        self.pending_target = None

    @property
    def state(self) -> TemperamentState:
        return self._state

    @state.setter
    def state(self, new_state: TemperamentState) -> None:
        # a domain (d) change forgets every dimension-specific selection — the weakly-held manual
        # target limit and typed target list, plus the held intervals, intervals of interest, and
        # any hand-edited prescaler diagonal (all d-length vectors / a d-diagonal). They revert to
        # the new domain's defaults rather than lingering at the old dimension, where they would
        # desync or crash the grid; they do not resurrect if d comes back.
        if new_state.d != self._state.d:
            self.target_limit = None
            self.target_override = None
            self.held_vectors = []
            self.interest_vectors = []
            self.custom_prescaler = None
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

    def layout(self, prev_ids=None) -> Layout:
        """Build the rendered spreadsheet model for the current document — the single
        source of how the editor's state maps to the grid. The page render and the render
        tests both go through here rather than re-spelling spreadsheet.build's arguments.

        ``prev_ids`` is the previous render's interval-column identities (``Layout.identities``):
        threading it through lets a within-list reorder keep each column's id-token so the
        reconciler glides it. Omitted (the default) numbers the columns by index — a fresh build."""
        return spreadsheet.build(
            self.state, self.settings, self.collapsed, self.tuning_scheme, self.target_spec,
            interest=self.interest_vectors, range_mode=self.range_mode,
            pending_comma=self.pending_comma, held_vectors=self.held_vectors,
            generator_tuning=self.effective_generator_tuning(),
            target_override=self.target_override,
            custom_prescaler=self.custom_prescaler,
            optimize_locked=self.optimize_locked,
            tuning_optimized=self.tuning_is_optimized,
            pending_interest=self.pending_interest,
            pending_held=self.pending_held,
            pending_target=self.pending_target,
            prev_ids=prev_ids)

    @property
    def can_expand(self) -> bool:
        """Whether the domain + applies: only a standard prime limit walks to the next
        prime (a nonstandard subgroup isn't a prime sequence, so the control is inert)."""
        return service.is_standard_domain(self.state.domain_basis)

    @property
    def can_shrink(self) -> bool:
        """Whether the domain − applies: a standard prime limit with a prime to spare, and only
        when the smaller temperament is still proper (dropping the top prime can leave a lower
        prime tempered to a unison — a degenerate result the control then withholds)."""
        if not (self.can_expand and self.state.d > 1):
            return False
        try:
            return service.is_proper_temperament(service.shrink_domain(self.state).mapping)
        except Exception:
            return False

    @property
    def can_add_mapping_row(self) -> bool:
        """Whether the mapping + applies: it un-tempers a comma into a new generator, so it
        needs a comma to un-temper (nullity > 0; at full rank there is nothing tempered)."""
        return self.state.n > 0

    @property
    def can_remove_mapping_row(self) -> bool:
        """Whether the mapping − is live: a generator to spare (never down to rank 0)."""
        return self.state.r > 1

    @property
    def can_remove_comma(self) -> bool:
        """Whether the comma − is live: it cancels a pending draft, or (with none)
        drops a real comma without emptying the basis."""
        return self.pending_comma is not None or len(self.state.comma_basis) > 1

    def _apply(self, state: TemperamentState) -> None:
        """Make a temperament edit: snapshot for undo, abandon any pending drafts, set state."""
        self._snapshot()
        self._clear_pending()
        self.state = state

    def edit_mapping(self, mapping) -> None:
        self._apply(service.from_mapping(mapping))

    def edit_comma_basis(self, comma_basis, domain_basis=None) -> None:
        self._apply(service.from_comma_basis(comma_basis, domain_basis))

    def canonicalize_mapping(self) -> None:
        """Re-store the mapping in canonical form (the mapping box's ``<choose form>``
        control) — an undoable edit, so an equivalent generating set can be normalized."""
        self.edit_mapping(service.canonical_mapping(self.state.mapping))

    def canonicalize_comma_basis(self) -> None:
        """Re-store the comma basis in canonical form (the comma-basis box's
        ``<choose form>`` control) — an undoable edit, like :meth:`canonicalize_mapping`."""
        self.edit_comma_basis(service.canonical_comma_basis(self.state.comma_basis))

    def _feed_draft(self, values, commit) -> list[int | None] | None:
        """Drive an interval-list draft (interest / held / target): store the entered
        components, and once every one is filled, snapshot and hand the completed vector to
        ``commit`` (which folds it into the document). Returns the draft to keep pending
        (the values, still blank somewhere) or ``None`` once committed. The comma draft has
        its own commit gate (independence), so it does not route through here."""
        draft = list(values)
        if any(v is None for v in draft):
            return draft  # still being typed in
        self._snapshot()
        commit(tuple(int(v) for v in draft))
        return None

    def add_interest(self) -> None:
        """Begin a blank interval-of-interest draft (a red, blank column the user fills in),
        mirroring add_comma. Not part of the document and not undoable until it commits."""
        self.pending_interest = [None] * self.state.d

    def set_pending_interest(self, values) -> None:
        """Hold the draft's edited components; once all are filled, commit it (append the
        interval) and clear the draft — see :meth:`_feed_draft`."""
        self.pending_interest = self._feed_draft(values, self.interest_vectors.append)

    def cancel_pending_interest(self) -> None:
        """Discard the draft without committing (the draft column's − control)."""
        self.pending_interest = None

    def remove_interest(self, i: int) -> None:
        """Drop the i-th interval of interest (each one carries its own − control)."""
        self._snapshot()
        del self.interest_vectors[i]

    def set_interest_vectors(self, vectors) -> None:
        """Replace the interest set from the edited vector cells."""
        self._snapshot()
        self.interest_vectors = [tuple(int(x) for x in m) for m in vectors]

    def add_held(self) -> None:
        """Begin a blank held-interval draft — the held intervals column's + control,
        mirroring :meth:`add_interest`."""
        self.pending_held = [None] * self.state.d

    def set_pending_held(self, values) -> None:
        """Hold the draft's edited components; once all are filled, commit it (append the
        held interval) and clear the draft — see :meth:`_feed_draft`."""
        self.pending_held = self._feed_draft(values, self.held_vectors.append)

    def cancel_pending_held(self) -> None:
        """Discard the draft without committing (the draft column's − control)."""
        self.pending_held = None

    def remove_held(self, i: int) -> None:
        """Drop the i-th held interval (each one carries its own − control)."""
        self._snapshot()
        del self.held_vectors[i]

    def set_held_vectors(self, vectors) -> None:
        """Replace the held interval set from the edited vector cells."""
        self._snapshot()
        self.held_vectors = [tuple(int(x) for x in m) for m in vectors]

    def _optimum_generator_tuning(self) -> tuple[float, ...]:
        """The scheme's current optimal generator tuning, respecting any held intervals and a
        typed target-list override (so re-optimizing tracks the displayed target intervals, not
        just the named TILT/OLD set)."""
        held = service.comma_ratios(self.held_vectors) if self.held_vectors else ()
        return service.tuning(self.state.mapping, self.tuning_scheme, held=held,
                              targets=self.target_override).generator_map

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
        """The generator tuning the grid should display: None (recompute the optimum every
        render) while the auto-optimize lock is on; else the frozen tuning — the scheme's optimum
        by default (auto-optimize is off, so it does not auto-recompute as the temperament/targets
        change), a hand-edited map, or whatever the last Optimize froze."""
        return None if self.optimize_locked else self.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        """The named scheme the grid's *displayed* tuning realises, or None — for which the
        tuning chooser shows "-". None when the displayed generator tuning deviates from the BARE
        scheme's optimum (the established schemes the chooser lists carry no held constraints), or
        when the scheme has no systematic name (an unnameable optimization power or complexity).
        The displayed tuning is a valid frozen manual override, else the scheme's optimum WITH any
        held intervals folded in; so a hand-edited generator OR a held interval that pulls the
        tuning off the bare optimum both drop the name to "-". A stale override the grid ignores
        (its generator count no longer fits the mapping) falls back to that optimum, keeping the
        name when nothing else deviates. Compared at DISPLAY precision (the shown cents), mirroring
        :attr:`displayed_prescaler_name`, so a tuning frozen or typed at the displayed optimum reads
        as no deviation. A control-refined spec (e.g. a Euclidean-norm scheme) is named like any
        other now that the spec can be rendered, rather than dropping to "-" for lacking a string."""
        override = self.effective_generator_tuning()
        displayed = (override if override is not None and len(override) == len(self.state.mapping)
                     else self._optimum_generator_tuning())
        # the bare scheme's optimum over the SAME target set the grid shows (a typed target list is a
        # separate control, not a scheme deviation) but WITHOUT held constraints — so the comparison
        # isolates exactly the held-interval / manual-override deviations.
        bare = service.tuning(self.state.mapping, self.tuning_scheme,
                              targets=self.target_override).generator_map
        if not _same_cents_map(displayed, bare):
            return None
        # the chooser lists base names (its label T-prefixes a target-based scheme), so drop any
        # target prefix here — a target-based "TILT minimax-S" shows as the "minimax-S" entry
        return service.base_scheme_name(self.tuning_scheme)

    @property
    def tuning_is_optimized(self) -> bool:
        """Whether the grid's displayed generator tuning sits at the scheme's optimum — so the
        objective shown IS the minimized value and its symbol wraps in min(). True with auto-optimize
        on, with nothing frozen, or once optimized (the frozen tuning equals the current optimum);
        False as soon as a manual generator edit pulls it off. Compared at DISPLAY precision like
        :attr:`displayed_tuning_scheme_name`, but against the optimum that HOLDS any held intervals
        (holding then optimizing is still optimized) — so only a hand-edit drops the min(), whereas a
        held interval, which leaves the BARE scheme, drops the scheme NAME but not the min()."""
        override = self.effective_generator_tuning()
        if override is None or len(override) != len(self.state.mapping):
            return True  # auto-optimize on / nothing frozen / stale override → the grid shows the optimum
        return _same_cents_map(override, self._optimum_generator_tuning())

    @property
    def displayed_prescaler_name(self) -> str | None:
        """The named prescaler the grid's displayed 𝑋 diagonal realises, or None — for which the
        prescaler chooser shows "-". None when a custom-prescaler override deviates from the
        scheme's computed diagonal (the user hand-edited the bare prescaler tile). Mirrors
        :attr:`displayed_tuning_scheme_name` for the prescaler preset."""
        return service.displayed_prescaler_name(
            self.state.mapping, self.tuning_scheme, self.custom_prescaler)

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

    def _override_generator(self, i: int, transform, *, snapshot: bool = True) -> None:
        """Freeze a manual generator tuning with component ``i`` replaced by
        ``transform(current[i])``, seeding the rest from the frozen tuning or, when none is
        frozen, the current optimum. Turns auto-optimize off, like a typed tuning. Backs the
        editable cell (set to a typed value) and the wheel nudge (step it). ``snapshot=False``
        extends the current undo step instead of opening a new one — how a continuous wheel
        gesture coalesces its notches."""
        # a frozen tuning whose length no longer matches the rank (a domain ± or comma/mapping edit
        # since it was frozen) is stale — seed from the optimum instead, as the grid does, so editing
        # the new generator's cell can't index past the stale shorter tuning
        frozen = self.effective_generator_tuning()
        base = list(frozen if frozen is not None and len(frozen) == len(self.state.mapping)
                    else self._optimum_generator_tuning())
        base[i] = float(transform(base[i]))
        if snapshot:
            self._snapshot()
        self.optimize_locked = False
        self.generator_tuning = tuple(base)

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        """Override one generator's tuning (one editable generator-tuning-map cell)."""
        self._override_generator(i, lambda _current: cents)

    def flip_generator(self, i: int) -> None:
        """Reverse generator ``i``'s direction — the +/− sign on its generator-tuning-map cell.
        A generator and its mapping row are the same quantity, so negating the generator negates
        mapping row ``i`` too; with the row and the generator's tuned size both flipped, the prime
        tuning map 𝒕 = 𝒈𝑀 is unchanged — the generator just points the other way (e.g. a fifth
        becomes a descending fourth's worth). With auto-optimize on, the re-optimized tuning
        flips the generator's size on its own; a frozen manual tuning has its component negated
        here so 𝒕 holds. One undoable edit (the mapping edit's snapshot covers both halves)."""
        override = self.effective_generator_tuning()
        mapping = [list(row) for row in self.state.mapping]
        mapping[i] = [-x for x in mapping[i]]
        self.edit_mapping(mapping)  # snapshots; negating a row is the same temperament
        if override is not None and len(override) == len(mapping):
            flipped = list(override)
            flipped[i] = -flipped[i]
            self.generator_tuning = tuple(flipped)

    def nudge_generator_tuning_component(self, i: int, steps: int) -> None:
        """Fine-adjust one generator's tuning by ``steps`` thousandths of a cent — the hover-
        and-scroll-wheel nudge on a generator-tuning-map cell (one notch up = +0.001¢, down =
        −0.001¢). Rounds to the 3 dp the cell shows (:func:`service.cents`) so each notch moves the
        displayed thousandths digit by exactly ``steps``. Consecutive notches on the SAME generator
        share one undo step (one continuous scroll gesture = one undo, so a fine-tune doesn't bury
        the history); any other action resets the marker via _snapshot, and a notch on a different
        generator mismatches it — either way the next notch opens a fresh step."""
        self._override_generator(
            i, lambda current: round(round(current, 3) + steps * _GENERATOR_NUDGE_CENTS, 3),
            snapshot=self._nudging_generator != i)
        self._nudging_generator = i

    def try_edit_mapping_text(self, text: str) -> bool:
        """Parse an EBK map string (honouring a domain-basis prefix, so a nonstandard
        temperament can be typed in) and apply it. Returns False (leaving the state
        untouched) when the text is not a valid integer map, so the caller can flag the
        input rather than mangling the temperament."""
        state = service.parse_mapping_state(text)
        if state is None or not service.is_proper_temperament(state.mapping):
            return False  # unparseable, or a degenerate temperament (the caller toasts and reverts)
        self._apply(state)
        return True

    def try_edit_comma_basis_text(self, text: str) -> bool:
        """Parse an EBK vector string and apply it as a comma-basis edit; False
        (state untouched) when it is not a valid integer vector list, or its dual mapping is a
        degenerate temperament (e.g. tempering out a prime). A nonstandard domain on the
        current state is preserved when the parsed vectors' dimensionality matches d, so a
        comma-box edit doesn't silently revert the temperament to standard primes."""
        basis = service.parse_comma_basis(text)
        if basis is None:
            return False
        domain_basis = self.state.domain_basis if len(basis[0]) == self.state.d else None
        try:
            if not service.is_proper_temperament(service.from_comma_basis(basis, domain_basis).mapping):
                return False
            self.edit_comma_basis(basis, domain_basis)
        except Exception:
            return False
        return True

    def set_tuning_scheme(self, name: str) -> None:
        """Apply a systematic scheme name from the established-tuning-scheme chooser, preserving
        the current target mode: all-interval when the scheme currently targets every interval,
        else over the displayed target list (the chooser's T-prefixed entries). With auto-optimize
        off the generator tuning stays frozen — picking a scheme does NOT retune; the chooser shows
        "-" until the user clicks Optimize. (With the auto lock on, the grid recomputes anyway.)
        Undoable."""
        self._snapshot()
        target = "{}" if service.is_all_interval(self.tuning_scheme) else self.target_spec
        # set the target set as a structured trait (not by gluing a prefix onto the name) so a
        # held-/destretched- modifier in the name survives — string concatenation would hide it
        self.tuning_scheme = service.scheme_with_targets(name, target)

    def set_complexity_prescaler(self, prescaler: str) -> None:
        """Swap the complexity prescaler (the predefined-prescalers preset), which
        re-weights damage and so retunes. Holds the refined scheme as a resolved spec
        (the service/layout take a spec anywhere a scheme name is taken). Also CLEARS
        any custom-prescaler override — picking a named preset is the user's reset path,
        snapping the bare prescaler tile back to the scheme's computed diagonal."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_prescaler(self.tuning_scheme, prescaler)
        self.custom_prescaler = None

    def set_complexity_norm_power(self, power: float) -> None:
        """Set the interval-complexity norm power q (the editable q field in box 𝒄) — which Lq
        norm of each prescaled vector the complexity takes. Re-weights and retunes."""
        self._snapshot()
        self.tuning_scheme = service.scheme_with_complexity_norm_power(self.tuning_scheme, power)

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

    def set_custom_prescaler_entry(self, i: int, j: int, value: float) -> None:
        """Edit one entry (row ``i``, column ``j``) of the complexity pretransformer — the editable
        square's cells call this on every change. The first edit *seeds* the override from the
        scheme's diagonal (so untouched cells keep their displayed values rather than snapping to
        zeros). A diagonal edit on a still-diagonal override keeps it a flat d-tuple; an OFF-diagonal
        edit promotes it to a full d×d matrix (a non-diagonal pretransformer), filling the rest of
        the square from the seeded diagonal (zeros off it)."""
        self._snapshot()
        if self.custom_prescaler is None:
            self.custom_prescaler = tuple(service.complexity_prescaler(self.state.mapping, self.tuning_scheme))
        is_matrix = isinstance(self.custom_prescaler[0], (tuple, list))
        if i == j and not is_matrix:
            diag = list(self.custom_prescaler)
            diag[i] = float(value)
            self.custom_prescaler = tuple(diag)
        else:
            d = self.state.d
            rows = ([list(r) for r in self.custom_prescaler] if is_matrix
                    else [[self.custom_prescaler[r] if r == c else 0.0 for c in range(d)] for r in range(d)])
            rows[i][j] = float(value)
            self.custom_prescaler = tuple(tuple(r) for r in rows)

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
        live target spec). Switches the scheme's target set accordingly (an undoable edit). The
        weight slope flips with the mode: an all-interval scheme is simplicity-weighted by
        construction, while the target-based default is unity weight — so checking forces
        simplicity, unchecking forces unity."""
        self._snapshot()
        slope = "simplicity-weight" if all_interval else "unity-weight"
        # swap the slope and the target set as structured traits — no name surgery, so a
        # held-/destretched- modifier survives the toggle (a glued prefix would drop it)
        scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)
        self.tuning_scheme = service.scheme_with_targets(
            scheme, "{}" if all_interval else self.target_spec)

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
        # a target-based scheme tracks the displayed interval list: retarget it to the new
        # family/limit as a structured trait (an all-interval scheme ignores the list, so leave
        # it untouched). Setting the trait — not re-gluing a prefix — keeps any held-/destretched-
        # modifier intact.
        if not service.is_all_interval(self.tuning_scheme):
            self.tuning_scheme = service.scheme_with_targets(self.tuning_scheme, self.target_spec)

    def set_target_override_text(self, text: str) -> bool:
        """Set an explicit target interval list from a typed EBK vector string (the editable
        target interval list plain text). Stored as ratios, overriding the TILT/OLD spec until
        the spec is re-chosen or the domain changes. False (state untouched) when it is not a
        valid integer vector list, so the caller can flag the input."""
        vectors = service.parse_comma_basis(text)
        if vectors is None:
            return False
        self._snapshot()
        self.target_override = service.comma_ratios(vectors, self.state.domain_basis)
        return True

    def set_target_override_vectors(self, vectors) -> None:
        """Set the explicit target list from edited vector columns (the editable target
        interval list cells), like :meth:`set_interest_vectors` — stored back as ratios."""
        self._snapshot()
        self.target_override = service.comma_ratios(
            [tuple(int(x) for x in m) for m in vectors], self.state.domain_basis)

    def _current_targets(self) -> list[str]:
        """The live target list as ratio strings — the manual override if set, else the
        spec's resolved set. The basis the target ± controls edit from."""
        if self.target_override is not None:
            return list(self.target_override)
        return list(service.target_interval_set(self.target_spec, self.state.domain_basis))

    def add_target(self) -> None:
        """Begin a blank target-interval draft — the target list's + control, mirroring
        :meth:`add_interest`. Off in all-interval (the control is hidden there)."""
        self.pending_target = [None] * self.state.d

    def set_pending_target(self, values) -> None:
        """Hold the draft's edited components; once all are filled, commit it — materializing
        the spec set into a manual override and appending the new interval's ratio (like
        editing a target cell does) — and clear the draft. See :meth:`_feed_draft`."""
        def commit(vector):
            targets = self._current_targets()
            targets.append(service.comma_ratios([vector], self.state.domain_basis)[0])
            self.target_override = tuple(targets)
        self.pending_target = self._feed_draft(values, commit)

    def cancel_pending_target(self) -> None:
        """Discard the draft without committing (the draft column's − control)."""
        self.pending_target = None

    def remove_target(self, i: int) -> None:
        """Drop the i-th target (each carries its own − control), materializing the spec set
        into a manual override."""
        targets = self._current_targets()
        del targets[i]
        self._snapshot()
        self.target_override = tuple(targets)

    # --- drag-and-drop: move one interval column between or within the lists ---
    # The four interval lists are heterogeneous — targets ride as ratio strings off a
    # materialized override, held/interest as plain vector lists, commas as the temperament's
    # dual — so a move composes per-list take/put primitives over a common vector currency
    # rather than one generic list edit. A move is ONE undoable step: it snapshots once, reads
    # the moved vector BEFORE mutating, and removes from the source BEFORE inserting into the
    # destination (so a targets→commas move can't clobber the override it just wrote).
    MOVE_LISTS = ("targets", "held", "interest", "commas")

    def _list_vectors(self, name: str) -> list[tuple[int, ...]]:
        """The named interval list as vectors over the domain — the currency a move reads."""
        if name == "targets":
            return [tuple(v) for v in service.target_interval_vectors(
                self._current_targets(), self.state.d, self.state.domain_basis)]
        if name == "held":
            return [tuple(v) for v in self.held_vectors]
        if name == "interest":
            return [tuple(v) for v in self.interest_vectors]
        return [tuple(v) for v in self.state.comma_basis]  # commas

    def _peek_vector(self, name: str, i: int) -> tuple[int, ...] | None:
        vectors = self._list_vectors(name)
        return vectors[i] if 0 <= i < len(vectors) else None

    def _move_feasible(self, src: str, dst: str, vector: tuple[int, ...]) -> bool:
        if src not in self.MOVE_LISTS or dst not in self.MOVE_LISTS:
            return False
        if "targets" in (src, dst) and service.is_all_interval(self.tuning_scheme):
            return False  # the target list is auto Tₚ = I there, not a user-curated set
        if src == "commas" and len(self.state.comma_basis) <= 1:
            return False  # never empty the comma basis (parity with the comma −)
        if dst == "commas":  # tempering the interval out must genuinely raise the nullity
            extended = service.from_comma_basis(self.state.comma_basis + (tuple(vector),))
            if extended.n <= self.state.n:
                return False  # a dependent interval re-ranks nothing — reject the drop
        return True

    def _take_from(self, name: str, i: int) -> None:
        if name == "targets":  # mirror remove_target (materialize the spec, then drop i)
            targets = self._current_targets()
            del targets[i]
            self.target_override = tuple(targets)
        elif name == "held":
            del self.held_vectors[i]
        elif name == "interest":
            del self.interest_vectors[i]
        else:  # commas — re-dual the basis without comma i (un-temper it: −n, +r)
            self.state = service.remove_comma(self.state, i)

    def _put_into(self, name: str, i: int, vector: tuple[int, ...]) -> None:
        if name == "targets":  # mirror the target draft's commit (materialize, insert the ratio)
            targets = self._current_targets()
            targets.insert(i, service.comma_ratios([vector], self.state.domain_basis)[0])
            self.target_override = tuple(targets)
        elif name == "held":
            self.held_vectors.insert(i, tuple(vector))
        elif name == "interest":
            self.interest_vectors.insert(i, tuple(vector))
        else:  # commas — temper the interval out (+n, −r); the dual fixes the column order
            self.state = service.from_comma_basis(self.state.comma_basis + (tuple(vector),))

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        """Move interval ``src_idx`` of ``src_list`` so it LANDS AT index ``dst_idx`` of ``dst_list``
        — the drag-and-drop of an interval column: dropping it onto the column at ``dst_idx`` puts it
        in that column's place. (``dst_idx`` past the end appends — a drop on the list's +.) targets
        ↔ held ↔ interest are plain interval moves; a move into commas tempers the interval out
        (re-ranking the temperament), out of commas un-tempers it. Returns False (no change, no undo
        step) for an infeasible or no-op move; one undoable step otherwise.

        The dragged column lands exactly where it was dropped: remove it, then insert at ``dst_idx``
        in the now-shorter list. So dropping A onto its neighbour B swaps them (A takes B's index) —
        no off-by-one. Dropping a column on ITSELF is the only same-list no-op."""
        vector = self._peek_vector(src_list, src_idx)
        if vector is None or not self._move_feasible(src_list, dst_list, vector):
            return False
        if src_list == dst_list and (src_list == "commas" or src_idx == dst_idx):
            return False  # dropping a column on itself is a no-op; a commas reorder is unobservable
            # (the dual canonicalizes the column order)
        self._snapshot()
        if "commas" in (src_list, dst_list):
            self._clear_pending()  # a rank change invalidates the per-list drafts
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)  # land at the dropped-on column's index (insert clamps)
        return True

    def set_range_mode(self, mode: str) -> None:
        self._snapshot()
        self.range_mode = mode

    def set_show(self, key: str, value: bool) -> None:
        """Set one Show toggle (which parts of the grid are visible) — an undoable change. The
        sub-control hierarchy (:data:`show_settings.SUBCONTROLS`) is kept consistent both ways:
        selecting a sub-control also selects every layer it refines (a refinement can't show
        without its base — equivalences needs symbols, mnemonics needs names), and deselecting a
        toggle deselects every sub-control nested under it (so a hidden parent never strands its
        sub-controls' content or panel rows on screen)."""
        self._snapshot()
        self.settings[key] = value
        if value:
            for parent in show_settings.ancestors_of(key):
                self.settings[parent] = True
        else:
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
        self._clear_pending()  # each draft's length is tied to the old domain
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        if not self.can_shrink:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.shrink_domain(self.state)

    def add_mapping_row(self) -> None:
        if not self.can_add_mapping_row:
            return  # nothing tempered to un-temper into a new generator
        self._snapshot()
        self._clear_pending()
        self.state = service.add_mapping_row(self.state)

    def remove_mapping_row(self, i: int) -> None:
        if not self.can_remove_mapping_row:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.remove_mapping_row(self.state, i)

    def add_mapping_row_to(self, source: int, target: int) -> None:
        """Drag generator row ``source`` onto a DIFFERENT row ``target``: add the dragged row into
        the dropped-on one (``row[target] += row[source]``). A generator-basis change that holds the
        temperament and the sounding tuning — see :func:`service.add_mapping_row_to`. A frozen
        generator tuning is transformed so the pitches are preserved (the dragged generator's size
        loses the target's); auto-optimize (None) just re-solves the same optimum. ``source ==
        target`` is a no-op (dropping a row on itself is not a meaningful operation)."""
        r = len(self.state.mapping)
        if source == target or not (0 <= source < r and 0 <= target < r):
            return
        self._snapshot()
        self._clear_pending()
        if self.generator_tuning is not None and len(self.generator_tuning) == r:
            tuning = list(self.generator_tuning)
            tuning[source] -= tuning[target]
            self.generator_tuning = tuple(tuning)
        self.state = service.add_mapping_row_to(self.state, source, target)

    def add_comma_to(self, source: int, target: int) -> None:
        """Drag comma ``source`` onto a DIFFERENT comma ``target``: add the dragged comma into the
        dropped-on one (``comma[target] += comma[source]``). The interval-column twin of
        :meth:`add_mapping_row_to` — a comma-basis change that holds the temperament (see
        :func:`service.add_comma_to`); the mapping is unaffected, so no tuning transform. ``source ==
        target`` is a no-op."""
        n = len(self.state.comma_basis)
        if source == target or not (0 <= source < n and 0 <= target < n):
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.add_comma_to(self.state, source, target)

    def _combine_interval_vectors(self, vectors: list, source: int, target: int) -> None:
        """Add interval ``source`` into a DIFFERENT interval ``target`` in a vector list (intervals
        of interest / held intervals): the dropped-on vector becomes the two intervals' sum (their
        product). Snapshots only when it actually applies (a valid, distinct pair)."""
        if source == target or not (0 <= source < len(vectors) and 0 <= target < len(vectors)):
            return
        self._snapshot()
        vectors[target] = tuple(a + b for a, b in zip(vectors[target], vectors[source]))

    def add_interest_to(self, source: int, target: int) -> None:
        """Drag one interval of interest onto another to combine them into their product."""
        self._combine_interval_vectors(self.interest_vectors, source, target)

    def add_held_to(self, source: int, target: int) -> None:
        """Drag one held interval onto another to combine them into their product."""
        self._combine_interval_vectors(self.held_vectors, source, target)

    def add_target_to(self, source: int, target: int) -> None:
        """Drag one target interval onto another to combine them into their product, materializing
        the spec set into a manual override (like :meth:`remove_target`). Targets are ratio
        strings, so the product is taken directly (a ratio product is the intervals' vector sum)."""
        targets = self._current_targets()
        if source == target or not (0 <= source < len(targets) and 0 <= target < len(targets)):
            return
        product = Fraction(targets[source]) * Fraction(targets[target])
        self._snapshot()
        targets[target] = f"{product.numerator}/{product.denominator}"
        self.target_override = tuple(targets)

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
        if len(self.state.comma_basis) <= 1:
            return  # never empty the basis — self-guard like shrink / remove_mapping_row do
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
        self._nudging_generator = None  # a new undoable action ends any in-progress wheel gesture

    def serialize(self) -> dict:
        """The whole document as a JSON-safe dict, for persisting across a page refresh.
        The temperament rides as its (domain-prefixed) EBK string so a nonstandard domain
        round-trips; the tuning scheme is name-or-spec via the service (inf power encoded)."""
        return {
            "mapping_ebk": service.mapping_ebk(self._state),
            "tuning_scheme": service.scheme_to_json(self.tuning_scheme),
            "target_family": self.target_family,
            "target_limit": self.target_limit,
            "interest_vectors": [list(m) for m in self.interest_vectors],
            "held_vectors": [list(m) for m in self.held_vectors],
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
        state = service.parse_mapping_state(data.get("mapping_ebk", ""))
        if state is None:
            return
        doc = _Doc(
            state=state,
            tuning_scheme=service.scheme_from_json(
                data.get("tuning_scheme", service.DEFAULT_DOCUMENT_SCHEME)),
            target_family=data.get("target_family", service.DEFAULT_TARGET_SPEC),
            target_limit=data.get("target_limit"),
            interest_vectors=tuple(tuple(int(x) for x in m) for m in data.get("interest_vectors", ())),
            held_vectors=tuple(tuple(int(x) for x in m) for m in data.get("held_vectors", ())),
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
