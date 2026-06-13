"""Framework-free view-model for the temperament editor.

Holds the whole editor *document* — everything the user can change — and the
undo/redo history over it. The document bundles the temperament
(:class:`~rtt.app.service.TemperamentState`), the view selections shown over it
(tuning scheme, target interval set, intervals of interest, held intervals, range
mode) and the UI state (the Show settings and the folded
rows/columns/tiles). It is all one history: any change snapshots the whole
document, undo/redo swap snapshots, :meth:`Editor.reset` restores the defaults, and
:meth:`Editor.serialize`/:meth:`Editor.load` persist it across a page refresh. The
NiceGUI layer is thin glue over this; all of it is unit-testable without a UI.
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass
from fractions import Fraction

from rtt.app import presets
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app.layout import Layout
from rtt.app.service import TemperamentState

_log = logging.getLogger(__name__)

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app
# The rows/columns/tiles folded to strips on a fresh start and after Reset. Empty:
# nothing starts folded — the default view opens every row and column.
INITIAL_COLLAPSED: frozenset[str] = frozenset()
# One mouse-wheel notch over a generator-tuning-map cell nudges that generator by this many
# cents — a thousandth, the last digit the cell's 3-dp cents face shows (see service.cents).
_GENERATOR_NUDGE_CENTS = 0.001


def _same_cents_map(a, b) -> bool:
    """Whether two generator tunings are equal at DISPLAY precision — the cents the grid actually
    shows (:func:`service.cents`). Comparing what's shown (not bit-exact floats) means a manual
    tuning typed back at its displayed value reads as 'no deviation', mirroring how
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
    # The MANUAL generator-tuning override (a typed/nudged generator, a picked established
    # projection, or a hand-edited unchanged basis / G / P), or None — the scheme-driven state,
    # where the grid recomputes the scheme's optimum on every change (optimization is always on;
    # there is no freeze-at-optimum state and no optimize button). A manual override deviates
    # deliberately: the established-scheme chooser shows "-" and the mean damage drops its min().
    generator_tuning: tuple[float, ...] | None
    # Whether the tuning is that manual hand-edit rather than scheme-driven. Tracks
    # ``generator_tuning is not None`` for the document, but also covers a transient manual
    # superspace 𝒈L (held outside the document) while one is active.
    # See :attr:`Editor.displayed_tuning_scheme_name`.
    manual_tuning: bool
    # The user's override for the complexity prescaler 𝐿's diagonal — d floats, one per
    # domain prime. ``None`` means "no override": every weighting calculation falls back to
    # the scheme's computed diagonal (log_prime / prime / identity, per the alt.-complexity
    # traits), so the bare prescaler tile shows that, and complexity / damage / tuning flow
    # from it as they always did. Once set, the override drives EVERY downstream consumer
    # (the prescaler tile's cells, the 𝐿·basis product tiles, complexity, weights, the
    # tuning solve and its derived retunings/damages) — the bare tile is the single source of
    # truth for the pretransformer. Stored as a d-tuple (the diagonal) while it stays diagonal; once
    # alt complexity makes the whole square editable and an off-diagonal cell is touched, it becomes
    # a full d×d matrix (a non-diagonal pretransformer).
    custom_prescaler: tuple | None
    target_override: tuple[str, ...] | None  # a typed explicit target list, overriding the TILT/OLD spec
    # The exact rational basis a DELIBERATE projection pin holds — the ratios the user established by
    # picking a projection or hand-editing U / P / G (all via Editor._hold_as_manual_tuning). It does
    # NOT live in the held column (a pin leaves that untouched); recording it here is what lets
    # :attr:`Editor.unchanged_ratios` recover the full unchanged basis even when those ratios aren't in
    # the candidate pool it otherwise tests (established-projection ratios — meantone only — plus the
    # target set plus the held column). Empty () when no projection is pinned (a scheme-driven or freely
    # hand-tuned generator map), so U/P/G then fall back to reading the basis off the tuning. Validated
    # against the live tuning downstream, so a stale entry is harmless — it only ever contributes ratios
    # the displayed tuning still holds exactly just.
    projection_basis: tuple[str, ...]
    settings: tuple[tuple[str, bool], ...]
    collapsed: frozenset[str]


def _prescaler_to_json(p):
    """A custom pretransformer override as a JSON-safe value: a flat list (a diagonal) or a list of
    rows (a non-diagonal matrix), or None — so a matrix override persists, not just a diagonal."""
    if p is None:
        return None
    return [list(row) for row in p] if isinstance(p[0], (tuple, list)) else list(p)


def _prescaler_from_json(p):
    """Rebuild a custom pretransformer override from :func:`_prescaler_to_json`: a tuple diagonal, or
    a tuple-of-tuples matrix when the saved value is a list of rows. The inverse of the above."""
    if p is None:
        return None
    if p and isinstance(p[0], (list, tuple)):
        return tuple(tuple(float(x) for x in row) for row in p)
    return tuple(float(x) for x in p)


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
        # optimization is always on: no manual override, so the grid recomputes the scheme's
        # optimum on every change — the tuning is never stale against what's on screen
        generator_tuning=None,
        manual_tuning=False,
        custom_prescaler=None,
        target_override=None,
        projection_basis=(),  # no deliberate projection pinned by default — U/P/G read off the tuning
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
        # green-outlined column the user fills in. The comma's draft commits once it is a
        # comma independent of the basis (re-ranking the mapping); the interval-list drafts
        # (interest, held, target) commit once every component is filled.
        self.pending_comma: list[int | None] | None = None
        self.pending_interest: list[int | None] | None = None
        self.pending_held: list[int | None] | None = None
        self.pending_target: list[int | None] | None = None
        # A generator being added but not yet complete: the ROW mirror of pending_comma — a draft
        # mapping row (d components, each an int or None while blank) the user types a new generator
        # into. It renders as a blank, green-outlined ROW across the mapping band (matching the green
        # draft COLUMNS the interval lists grow), and like them lives OUTSIDE the document — no
        # undo/redo/restore. It commits once the row, appended to the mapping, is a proper temperament
        # (independent of the existing rows, re-ranking +r/−n — see set_pending_mapping_row).
        self.pending_mapping_row: list[int | None] | None = None
        # the chapter-9 domain basis element draft (nonstandard-domain box on): a green ?/? column
        # the user types a rational into. None = no draft; "" / a partial ratio = being typed. It
        # commits once the text is a valid, independent addition (added held just — see
        # service.add_domain_element); like the other drafts it lives outside undo until then.
        self.pending_element: str | None = None
        # The generator a wheel nudge is currently fine-tuning, so consecutive notches on it
        # coalesce into one undo step (see nudge_generator_tuning_component). Transient, like the
        # drafts: any snapshot or document restore clears it, ending the gesture.
        self._nudging_generator: int | None = None
        # The chapter-9 nonstandard-domain-approach selection: "" (neutral — read a nonprime
        # element as a formal prime, the library default), "prime-based" (read the temperament
        # in its prime superspace), or "nonprime-based" (honor the basis as given). It's an
        # analysis selection parallel to the tuning scheme, but OUTSIDE undo — like the Show
        # toggles and the range mode, this is a view choice, not a document edit. The radio is
        # hidden when the domain has no nonprime elements, so the field resets to "" on a domain
        # change that flips :func:`service.domain_has_nonprimes` False (see the state setter).
        self.nonprime_basis_approach: str = ""
        # The manual SUPERSPACE generator tuning 𝒈L (rL cents), set only in the prime-based
        # approach over a nonprime domain: there the optimization lives in the prime superspace, so
        # 𝒈L is the editable generator map and the on-domain 𝒈 is its (read-only) projection. None
        # = auto (the prime-based optimum). A view-ish field like nonprime_basis_approach (not in
        # the undo document); cleared on any approach change, domain change, scheme pick,
        # back-to-scheme, or restore.
        self.superspace_generator_tuning: tuple[float, ...] | None = None
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
            generator_tuning=self.generator_tuning,
            manual_tuning=self.manual_tuning,
            custom_prescaler=self.custom_prescaler,
            target_override=self.target_override,
            projection_basis=self.projection_basis,
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
        self.generator_tuning = doc.generator_tuning
        self.manual_tuning = doc.manual_tuning
        self.custom_prescaler = doc.custom_prescaler
        self.target_override = doc.target_override
        self.projection_basis = doc.projection_basis
        self.settings = dict(doc.settings)
        self.collapsed = set(doc.collapsed)
        self._clear_pending()  # a draft never survives a document restore
        self._nudging_generator = None  # nor does an in-progress wheel gesture (undo/redo/reset/load)
        self.superspace_generator_tuning = None  # a manual 𝒈L doesn't survive a document restore either

    def capture_for_preview(self) -> tuple:
        """Snapshot the WHOLE editor — document plus undo/redo history — so a hypothetical edit can
        be applied (through the normal edit methods, which would otherwise push an undo step) for a
        live preview, then fully reverted via :meth:`restore_for_preview`, leaving no trace. The
        drag-to-combine drop preview uses this to show the would-be result while hovering, without
        committing it or polluting the undo history.

        "No trace" includes the transients OUTSIDE the document: the pending drafts,
        ``_nudging_generator`` (wheel-undo coalescing) and ``superspace_generator_tuning``, which
        :meth:`_restore` wipes, plus ``nonprime_basis_approach``, which a hypothetical op can mutate
        through the state setter's side effect (and _restore never resets). Without carrying them, a
        mere hover preview destroys an open draft column or silently commits the hovered approach."""
        transients = (self.pending_comma, self.pending_interest, self.pending_held,
                      self.pending_target, self.pending_element, self.pending_mapping_row,
                      self._nudging_generator, self.superspace_generator_tuning,
                      self.nonprime_basis_approach)
        return (self._capture(), list(self._undo_stack), list(self._redo_stack), transients)

    def restore_for_preview(self, token: tuple) -> None:
        """Revert to a :meth:`capture_for_preview` snapshot — document, history, and transients."""
        doc, undo, redo, transients = token
        self._restore(doc)
        self._undo_stack[:] = undo
        self._redo_stack[:] = redo
        (self.pending_comma, self.pending_interest, self.pending_held, self.pending_target,
         self.pending_element, self.pending_mapping_row, self._nudging_generator,
         self.superspace_generator_tuning, self.nonprime_basis_approach) = transients

    def _clear_pending(self) -> None:
        """Discard every in-progress draft. Called whenever the document or domain shifts
        out from under the drafts (restore/undo/redo, a temperament edit, a domain ±) —
        each draft's length is tied to the current d, so a domain change invalidates it."""
        self.pending_comma = None
        self.pending_interest = None
        self.pending_held = None
        self.pending_target = None
        self.pending_element = None
        self.pending_mapping_row = None

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
        # the chapter-9 approach radio is hidden when the domain carries no nonprime element, so
        # a domain change that flips has-nonprimes False clears the selection back to neutral —
        # an invisible control would otherwise keep an off-screen non-default state. A move
        # between two nonprime domains keeps the chosen mode.
        if not service.domain_has_nonprimes(new_state.domain_basis):
            self.nonprime_basis_approach = ""
        # a manual 𝒈L is over the superspace mapping M_L, so any temperament or domain edit makes it
        # stale (rL / M_L change); drop it, as a domain change drops the stale on-domain generators.
        # A pinned projection's basis is likewise tied to this temperament/domain — drop it too so a
        # stale basis can't masquerade as the new temperament's unchanged intervals.
        if (new_state.mapping != self._state.mapping
                or new_state.domain_basis != self._state.domain_basis):
            self.superspace_generator_tuning = None
            self.projection_basis = ()
        self._state = new_state

    @property
    def _real_comma_basis(self) -> tuple[tuple[int, ...], ...]:
        """The committed comma basis with the full-rank zero-comma placeholder dropped — the basis a
        new comma must EXTEND. At full rank (``n == 0``) ``state.comma_basis`` holds a trivial
        ``((0,…,0),)`` by convention; appending the first real comma beside it would commit a phantom
        ``1/1`` comma column (violating ``d = r + n``), so callers extend ``()`` instead. Mirrors the
        ``comma_basis if n else ()`` read that ``plain_text_values`` / the spreadsheet already use."""
        return self.state.comma_basis if self.state.n else ()

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

    def layout(self, prev_ids=None, preview_remove=None) -> Layout:
        """Build the rendered spreadsheet model for the current document — the single
        source of how the editor's state maps to the grid. The page render and the render
        tests both go through here rather than re-spelling spreadsheet.build's arguments.

        ``prev_ids`` is the previous render's interval-column identities (``Layout.identities``):
        threading it through lets a within-list reorder keep each column's id-token so the
        reconciler glides it. Omitted (the default) numbers the columns by index — a fresh build.

        ``preview_remove`` is a − hover's transient rank-removal preview (``("comma", idx)`` /
        ``("row", idx)``) — a pure view overlay, not document state, so it rides as a layout
        argument rather than on the editor."""
        return spreadsheet.build(
            self.state, self.settings, self.collapsed, self.tuning_scheme, self.target_spec,
            interest=self.interest_vectors, range_mode=self.range_mode,
            pending_comma=self.pending_comma, held_vectors=self.held_vectors,
            generator_tuning=self.effective_generator_tuning(),
            target_override=self.target_override,
            custom_prescaler=self.custom_prescaler,
            tuning_optimized=self.tuning_is_optimized,
            pending_interest=self.pending_interest,
            pending_held=self.pending_held,
            pending_target=self.pending_target,
            pending_element=self.pending_element,
            pending_mapping_row=self.pending_mapping_row,
            nonprime_approach=self.nonprime_basis_approach,
            superspace_generator_tuning=self.superspace_generator_tuning,
            displayed_tuning_name=self.displayed_tuning_scheme_name,
            held_basis_ratios=self.unchanged_ratios,
            displayed_projection_name=self.displayed_projection_scheme_name,
            targets_in_use=self.targets_in_use,
            prev_ids=prev_ids, preview_remove=preview_remove)

    @property
    def can_expand(self) -> bool:
        """Whether the domain + applies: only a standard prime limit walks to the next
        prime (a nonstandard subgroup isn't a prime sequence, so the control is inert)."""
        return service.is_standard_domain(self.state.domain_basis)

    @property
    def basis_is_nonstandard(self) -> bool:
        """Whether the current domain basis is a nonstandard subgroup (not the first d
        primes) — the state the "nonstandard domain" Show toggle exists to represent, so it
        can't be turned off until the basis is back to a standard prime limit."""
        return not service.is_standard_domain(self.state.domain_basis)

    @property
    def can_shrink(self) -> bool:
        """Whether the domain − applies — see :func:`service.can_shrink_domain`, the shared
        predicate the renderer gates the − button on too (so it never shows while inert)."""
        return service.can_shrink_domain(self.state)

    @property
    def can_remove_domain_element(self) -> bool:
        """Whether the nonstandard-domain per-element − applies — any element of any basis can go,
        down to the last one (see :func:`service.can_remove_domain_element`). The shared predicate
        the renderer gates each element's − on, so it never shows while inert (``d == 1``)."""
        return service.can_remove_domain_element(self.state)

    @property
    def can_add_mapping_row(self) -> bool:
        """Whether the mapping + applies: it un-tempers a comma into a new generator, so it
        needs a comma to un-temper (nullity > 0; at full rank there is nothing tempered)."""
        return self.state.n > 0

    @property
    def can_remove_mapping_row(self) -> bool:
        """Whether the mapping − is live: a generator to spare (never down to rank 0)."""
        return self.state.r > 1

    def _apply(self, state: TemperamentState) -> None:
        """Make a temperament edit: snapshot for undo, abandon any pending drafts, set state, and
        drop a now-stale manual generator tuning (see :meth:`_drop_stale_manual_tuning`)."""
        self._snapshot()
        self._clear_pending()
        old_mapping = self._state.mapping
        self.state = state
        self._drop_stale_manual_tuning(old_mapping)

    def _drop_stale_manual_tuning(self, old_mapping) -> None:
        """A manual generator tuning is a tuple of cents read against a SPECIFIC generator basis. A
        temperament edit that reshapes the mapping — choose-form / canonicalize, picking a preset,
        dragging a comma — keeps the rank but changes which generators those cents describe, so the
        frozen tuple would be silently reinterpreted into nonsense (negative or thousands-of-cents
        primes) while the chooser still named the scheme. Drop it back to scheme-driven, so the grid
        recomputes the optimum for the new form. The two ops that CAN preserve the sounding tuning —
        :meth:`add_mapping_row_to` and :meth:`flip_generator` — transform the cents themselves and
        re-assert the manual tuning after, so they don't lose it here."""
        if self.generator_tuning is not None and self.state.mapping != old_mapping:
            self.generator_tuning = None
            self.manual_tuning = False

    def edit_mapping(self, mapping) -> None:
        # keep a nonstandard domain when the new matrix is the same width (a cell edit, choose-form
        # or sign flip is the same temperament-or-domain), mirroring try_edit_comma_basis_text /
        # set_pending_comma — else from_mapping silently rebuilds the standard prime limit and
        # reverts the temperament's basis (e.g. 2.3.13/5 -> 2.3.5).
        domain_basis = self.state.domain_basis if mapping and len(mapping[0]) == self.state.d else None
        self._apply(service.from_mapping(mapping, domain_basis))

    def edit_comma_basis(self, comma_basis, domain_basis=None) -> None:
        self._apply(service.from_comma_basis(comma_basis, domain_basis))

    def _standardize_domain_in_place(self) -> None:
        """Re-express the temperament over the simplest standard prime limit covering every prime
        the (nonstandard) basis uses, and drop the "nonstandard domain" setting — the state mutation
        shared by the direct toggle and select-none. Snapshots are the caller's job (each does one)."""
        ratios = service.comma_ratios(self.state.comma_basis, self.state.domain_basis)
        self._clear_pending()
        self.state = service.standardize_to_prime_limit(self.state.domain_basis, ratios)
        self.settings["nonstandard_domain"] = False

    def exit_nonstandard_domain(self) -> None:
        """Leave a live nonstandard domain (the way to turn the "nonstandard domain" toggle off):
        convert it to the simplest standard prime limit that contains every prime it used, then drop
        the toggle — one undoable step. A no-op on an already-standard basis. The state setter forgets
        the held intervals / intervals of interest / target list, which were vectors over the old
        basis (a different dimension), reverting them to the new domain's defaults."""
        if not self.basis_is_nonstandard:
            return
        self._snapshot()
        self._standardize_domain_in_place()

    def set_mapping_row(self, i: int, val) -> bool:
        """Replace mapping row ``i`` with ``val`` (a curated ET's val over the current domain)
        and commit it — the per-sub-row ET picker's action. Stored verbatim like a cell edit
        (not canonicalized), so the row reads as the chosen ET. Returns False, leaving the
        state untouched, when the replacement isn't a proper temperament (a dependent/zero row
        or an unreached element) — the picker then toasts and reverts. Preserves a nonstandard
        domain. One undo snapshot."""
        rows = self.state.mapping
        if not 0 <= i < len(rows):
            return False
        matrix = [list(row) for row in rows]
        matrix[i] = [int(x) for x in val]
        if not service.is_proper_temperament(matrix):
            return False
        self._apply(service.from_mapping(matrix, self.state.domain_basis))
        return True

    def set_comma(self, c: int, vector) -> bool:
        """Replace comma-basis column ``c`` with ``vector`` (a curated comma over the current
        domain) and commit it — the per-sub-column comma picker's action. Stored verbatim, so
        the column reads as the chosen comma. Returns False, leaving the state untouched, when
        the replacement would drop the nullity (the new comma is dependent on the others) or
        yield an improper dual mapping — the picker then toasts and reverts. Preserves a
        nonstandard domain (mirroring :meth:`set_pending_comma`). One undo snapshot."""
        cols = self.state.comma_basis
        if not 0 <= c < len(cols):
            return False
        basis = [list(col) for col in cols]
        basis[c] = [int(x) for x in vector]
        domain_basis = self.state.domain_basis if len(basis[c]) == self.state.d else None
        state = service.from_comma_basis(basis, domain_basis)
        # the dual stays proper even for a dependent column (it just drops a comma), so also
        # require the nullity to survive — a replacement must keep all nc commas independent.
        if state.n != len(basis) or not service.is_proper_temperament(state.mapping):
            return False
        self._apply(state)
        return True

    def canonicalize_mapping(self) -> None:
        """Re-store the mapping in canonical form (the mapping box's ``<choose form>``
        control) — an undoable edit, so an equivalent generating set can be normalized."""
        self.edit_mapping(service.canonical_mapping(self.state.mapping))

    def canonicalize_comma_basis(self) -> None:
        """Re-store the comma basis in canonical form (the comma-basis box's
        ``<choose form>`` control) — an undoable edit, like :meth:`canonicalize_mapping`. Passes the
        current domain basis so reforming a nonstandard temperament doesn't reset it to standard
        primes (the dual of canonical_mapping's domain-preserving edit_mapping)."""
        self.edit_comma_basis(
            service.canonical_comma_basis(self.state.comma_basis), self.state.domain_basis)

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
        """Begin a blank interval-of-interest draft (a green, blank column the user fills in),
        mirroring add_comma. Not part of the document and not undoable until it commits."""
        self._clear_pending()  # one draft at a time: opening this discards any other
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
        """Begin a blank held interval draft — the held intervals column's + control,
        mirroring :meth:`add_interest`."""
        self._clear_pending()  # one draft at a time: opening this discards any other
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

    def _optimum_tuning(self) -> service.Tuning:
        """The scheme's current optimal Tuning — the single solve behind every editor-side reference
        to "the optimum" (the scheme name, the optimized flag, a stale tuning's reseed, the
        projection's retuning). It threads the SAME arguments the grid's own solve does
        (``spreadsheet.build``): the document's ``domain_basis`` and ch9 ``nonprime_basis_approach``
        (so a nonstandard subgroup optimizes over ITS elements, not the standard primes — else
        barbados freezes an 822 ¢ "octave"), the held intervals expressed in that basis (so a held
        13/5 isn't read as 5/1), and the custom prescaler override (so a hand-edited complexity
        diagonal reaches the optimum and ``min(⟪𝐝⟫ₚ)`` names a genuinely minimized value)."""
        held = service.comma_ratios(self.held_vectors, self.state.domain_basis) if self.held_vectors else ()
        return service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, held=held,
            prescaler_override=self.custom_prescaler, targets=self.target_override)

    def _optimum_generator_tuning(self) -> tuple[float, ...]:
        """The scheme's current optimal generator tuning, respecting any held intervals and a
        typed target-list override (so re-optimizing tracks the displayed target intervals, not
        just the named TILT/OLD set). See :meth:`_optimum_tuning` for the threaded arguments."""
        return self._optimum_tuning().generator_map

    def back_to_scheme(self) -> None:
        """The projection / generator-embedding tiles' "back to scheme" button: leave a picked or
        hand-edited tuning and hand the wheel back to the scheme + target list. The tuning returns
        to the scheme's target-driven optimum (recomputed on every change, as always), so the
        target list comes back and the projection reverts to a read-only identification of
        the resulting tuning. A no-op (no undo step) when the tuning is already scheme-driven."""
        if not self.manual_tuning:
            return  # already the scheme's optimum — nothing to hand back
        self._snapshot()
        self.generator_tuning = None
        self.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()  # the wheel is handed back to the scheme — no pinned projection

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        """The generator tuning the grid should display: None (recompute the scheme's optimum
        every render — optimization is always on) until a manual override deviates; then the
        hand-edited / projection-picked map, until back_to_scheme or a scheme pick hands the
        wheel back.

        In the prime-based superspace, a manual 𝒈L drives the on-domain maps too: the editable map
        is 𝒈L (over the superspace generators), so the on-domain 𝒈 is its projection — every
        on-domain map then tracks the edited 𝒈L while 𝒈 itself stays read-only."""
        if self.superspace_generator_tuning is not None \
                and self.nonprime_basis_approach == "prime-based" \
                and service.domain_has_nonprimes(self.state.domain_basis):
            return service.project_superspace_generators_to_domain(self.state, self.superspace_generator_tuning)
        return self.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        """The ESTABLISHED scheme's systematic name, or None — for which the tuning chooser shows
        "-". The chooser tracks the scheme the user has established (a weight slope, optimization
        power or named pick). "-" only when the *displayed* tuning genuinely leaves the bare scheme —
        a hand-edited generator (:attr:`manual_tuning`), or a held interval pulling the (always-
        optimized) tuning off the bare scheme — or when the scheme has no systematic name (an
        unnameable optimization power or complexity). Compared at DISPLAY precision (the shown
        cents), mirroring :attr:`displayed_prescaler_name`."""
        # the optimum WITH held intervals (what the grid would show if optimized) vs the BARE optimum
        # WITHOUT them — over the SAME displayed target list either way. With no held interval the two
        # coincide, so skip the second solve. Both run over the document's domain basis / ch9 approach
        # / custom prescaler (as the grid does), so the name doesn't compare against a standard-primes
        # optimum the grid never shows.
        bare = service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, prescaler_override=self.custom_prescaler,
            targets=self.target_override).generator_map
        held_optimum = self._optimum_generator_tuning() if self.held_vectors else bare
        override = self.effective_generator_tuning()
        displayed = (override if override is not None and len(override) == len(self.state.mapping)
                     else held_optimum)
        if not _same_cents_map(displayed, held_optimum):
            # the displayed tuning is NOT the current optimum — a manual override leaves the
            # scheme ("-"); one typed back at the optimum's displayed cents reads as no deviation
            if self.manual_tuning:
                return None
        elif not _same_cents_map(held_optimum, bare):
            # the displayed tuning IS the optimum, but a held interval pulls that optimum off the
            # bare scheme the chooser lists (the established schemes carry no held constraints).
            return None
        # the chooser lists base names (its label T-prefixes a target-based scheme), so drop any
        # target prefix here — a target-based "TILT minimax-S" shows as the "minimax-S" entry
        return service.base_scheme_name(self.tuning_scheme)

    @property
    def tuning_is_optimized(self) -> bool:
        """Whether the grid's displayed generator tuning sits at the scheme's optimum — so the
        mean damage shown IS the minimized value and its symbol wraps in min(). True while the
        tuning is scheme-driven (optimization is always on, so the grid shows the optimum);
        False as soon as a manual generator edit pulls it off. Compared at DISPLAY precision like
        :attr:`displayed_tuning_scheme_name`, but against the optimum that HOLDS any held intervals
        — so only a hand-edit drops the min(), whereas a held interval, which leaves the BARE
        scheme, drops the scheme NAME but not the min()."""
        override = self.effective_generator_tuning()
        if override is None or len(override) != len(self.state.mapping):
            return True  # scheme-driven (or a stale-length override) → the grid shows the optimum
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
        """Hold a typed manual generator tuning (the editable generator tuning map): parse a
        cents map of exactly r values and hold it as the manual override. False (state
        untouched) when it is not r cents values, so the caller can flag the input rather
        than mangling the tuning."""
        gens = service.parse_cents_map(text, len(self.state.mapping))
        if gens is None:
            return False
        self._snapshot()
        self.generator_tuning = gens
        self.manual_tuning = True  # a typed tuning is a hand-edit — it leaves the established scheme
        self.projection_basis = ()  # a free cents map need not be a rational projection — drop the pin
        return True

    def _override_generator(self, i: int, transform, *, snapshot: bool = True) -> None:
        """Hold a manual generator tuning with component ``i`` replaced by
        ``transform(current[i])``, seeding the rest from the manual override or, when the tuning
        is scheme-driven, the current optimum. Backs the editable cell (set to a typed value)
        and the wheel nudge (step it). ``snapshot=False`` extends the current undo step instead
        of opening a new one — how a continuous wheel gesture coalesces its notches."""
        # a manual override whose length no longer matches the rank (a domain ± or comma/mapping
        # edit since it was set) is stale — seed from the optimum instead, as the grid does, so
        # editing the new generator's cell can't index past the stale shorter tuning
        override = self.effective_generator_tuning()
        base = list(override if override is not None and len(override) == len(self.state.mapping)
                    else self._optimum_generator_tuning())
        if not 0 <= i < len(base):
            return  # a stale-LONGER frozen tuning (a rank-reducing edit since it was set) can offer a
            # component index past the new rank; ignore it rather than IndexError. The live grid only
            # renders r cells, so this guards an API/fuzzer path, not a normal edit.
        base[i] = float(transform(base[i]))
        if snapshot:
            self._snapshot()
        self.generator_tuning = tuple(base)
        self.manual_tuning = True  # editing one generator is a hand-edit — it leaves the scheme
        self.projection_basis = ()  # nudging one generator breaks the pinned projection — drop it

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        """Override one generator's tuning (one editable generator-tuning-map cell)."""
        self._override_generator(i, lambda _current: cents)

    def _optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        """The prime-based superspace optimum 𝒈L — the seed a manual 𝒈L edit starts from."""
        return service.superspace_tuning(self.state, self.tuning_scheme, "prime-based").generator_map

    def set_superspace_generator_tuning_text(self, text: str) -> bool:
        """Hold a typed manual superspace generator tuning 𝒈L (the prime-based approach's editable
        generator map): parse a cents map of exactly rL values and hold it as the manual override.
        False (state untouched) when it is not rL cents values, so the caller can flag the
        input. The on-domain 𝒈 follows as 𝒈L's projection (see effective_generator_tuning)."""
        gens = service.parse_cents_map(text, service.superspace_rank(self.state))
        if gens is None:
            return False
        self._snapshot()
        self.superspace_generator_tuning = gens
        self.manual_tuning = True
        return True

    def set_superspace_generator_tuning_component(self, i: int, cents: float) -> None:
        """Override one superspace generator's tuning (one editable 𝒈L cell), seeding the rest from
        the manual 𝒈L or, when none is held, the prime-based superspace optimum."""
        manual = self.superspace_generator_tuning
        rL = service.superspace_rank(self.state)
        base = list(manual if manual is not None and len(manual) == rL
                    else self._optimum_superspace_generator_tuning())
        base[i] = float(cents)
        self._snapshot()
        self.superspace_generator_tuning = tuple(base)
        self.manual_tuning = True

    def nudge_superspace_generator_tuning_component(self, i: int, steps: int) -> None:
        """Wheel fine-adjust one superspace generator 𝒈L cell by ``steps`` thousandths of a cent
        (the prime-based shift's counterpart of the on-domain genmap nudge), seeding from the manual
        𝒈L or the superspace optimum and rounding to the 3 dp the cell shows."""
        rL = service.superspace_rank(self.state)
        manual = self.superspace_generator_tuning
        base = list(manual if manual is not None and len(manual) == rL
                    else self._optimum_superspace_generator_tuning())
        self.set_superspace_generator_tuning_component(
            i, round(round(base[i], 3) + steps * _GENERATOR_NUDGE_CENTS, 3))

    def flip_generator(self, i: int) -> None:
        """Reverse generator ``i``'s direction — the +/− sign on its generator-tuning-map cell.
        A generator and its mapping row are the same quantity, so negating the generator negates
        mapping row ``i`` too; with the row and the generator's tuned size both flipped, the prime
        tuning map 𝒕 = 𝒈𝑀 is unchanged — the generator just points the other way (e.g. a fifth
        becomes a descending fourth's worth). A scheme-driven tuning re-optimizes and flips the
        generator's size on its own; a manual override has its component negated
        here so 𝒕 holds. One undoable edit (the mapping edit's snapshot covers both halves)."""
        override = self.effective_generator_tuning()
        mapping = [list(row) for row in self.state.mapping]
        mapping[i] = [-x for x in mapping[i]]
        self.edit_mapping(mapping)  # snapshots; negating a row is the same temperament (and drops the
        # frozen tuning as stale — we re-assert the sound-preserving transform of it just below)
        if override is not None and len(override) == len(mapping):
            flipped = list(override)
            flipped[i] = -flipped[i]
            self.generator_tuning = tuple(flipped)
            self.manual_tuning = True  # _apply dropped the manual flag; this IS still a manual tuning

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

    @staticmethod
    def _valid_domain_basis(state: TemperamentState) -> bool:
        """Whether a parsed state's domain basis is well-formed enough to render and solve: one
        element per matrix column, each a positive non-unit rational, and the set multiplicatively
        independent. A typed mapping prefix can violate any of these — ``0.5`` (a zero element),
        ``1.3`` (the unit 1), ``2.4`` (4 = 2², dependent), or ``2.3.7`` over a 2-wide matrix (a
        length mismatch) — and the matrix itself still parses, so without this guard the bad domain
        commits and the NEXT render raises (a non-positive input, a non-invertible basis, or a ragged
        broadcast). Positivity/unit are checked before independence, which can't size a 0/1 element."""
        basis = state.domain_basis
        if not state.mapping or len(basis) != len(state.mapping[0]):
            return False
        try:
            elements = [Fraction(e) for e in basis]
        except (TypeError, ValueError, ZeroDivisionError):
            return False
        if any(e <= 0 or e == 1 for e in elements):
            return False
        return service.is_independent_domain_basis(basis)

    def try_edit_mapping_text(self, text: str) -> bool:
        """Parse an EBK map string (honouring a domain-basis prefix, so a nonstandard
        temperament can be typed in) and apply it. Returns False (leaving the state
        untouched) when the text is not a valid integer map, or its domain-basis prefix is
        malformed (:meth:`_valid_domain_basis`), so the caller can flag the input rather than
        mangling the temperament or committing a state that crashes the next render."""
        state = service.parse_mapping_state(text)
        if state is None or not service.is_proper_temperament(state.mapping):
            return False  # unparseable, or a degenerate temperament (the caller toasts and reverts)
        if not self._valid_domain_basis(state):
            return False  # a malformed domain prefix (0/1/dependent element, or wrong length)
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
            # parse gates already rejected every malformed basis, so reaching here is a bug,
            # not bad input — log it loudly instead of letting it masquerade as a red box
            _log.exception("comma-basis edit failed on %r", basis)
            return False
        return True

    def try_edit_projection_text(self, text: str) -> bool:
        """Parse an EBK map string as the projection P and apply it — the editable P plain-text band,
        the only P edit path now that the gridded cells are read-only (a single cell can't keep P
        idempotent). False (state untouched) when the text isn't a parseable d×d rational map OR isn't
        a valid tempering projection (rejected by :meth:`set_projection_matrix`), so the caller reddens
        the box and toasts why."""
        matrix = service.parse_projection(text)
        if matrix is None:
            return False
        return self.set_projection_matrix(matrix)

    def try_edit_embedding_text(self, text: str) -> bool:
        """Parse an EBK vector string as the generator embedding G and apply it — the editable G
        plain-text band. False when it isn't a parseable d×r rational vector list OR isn't a valid
        embedding (𝑀𝐺 ≠ 𝐼, rejected by :meth:`set_embedding_matrix`)."""
        matrix = service.parse_embedding(text, self.state.d, len(self.state.mapping))
        if matrix is None:
            return False
        return self.set_embedding_matrix(matrix)

    def set_tuning_scheme(self, name: str) -> None:
        """Apply a systematic scheme name from the established-tuning-scheme chooser, preserving
        the current target mode: all-interval when the scheme currently targets every interval,
        else over the displayed target list (the chooser's T-prefixed entries). Picking a scheme
        establishes it outright: any manual tuning override is dropped, so the grid retunes to the
        picked scheme's optimum (optimization is always on) and the chooser names it. Undoable."""
        self._snapshot()
        target = "{}" if service.is_all_interval(self.tuning_scheme) else self.target_spec
        # set the target set as a structured trait (not by gluing a prefix onto the name) so a
        # held-/destretched- modifier in the name survives — string concatenation would hide it
        self.tuning_scheme = service.scheme_with_targets(name, target)
        # the pick is a deliberate "use this scheme": with no optimize button to apply it over a
        # manual tuning, the pick itself hands the wheel back (else it would be a dead control)
        self.generator_tuning = None
        self.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()  # a scheme pick hands the wheel back — no pinned projection

    def set_established_projection(self, name: str | None) -> None:
        """Apply an established projection / embedding from that chooser: set the generator tuning
        TO the named rational tuning (e.g. 1/3-comma's 𝒈), as a deliberate tuning choice. It does
        NOT touch the held column — only the user decides which intervals they deliberately hold;
        picking a named tuning just sets 𝒈, and the unchanged basis U, P and G then follow from the
        tuning itself (the intervals it holds at zero damage). Because 𝒈 now departs from the named
        scheme's optimum, the established-scheme chooser reads "-". A no-op when ``name`` isn't a
        current option. Undoable."""
        ratios = presets.projection_held_ratios(self.state, name)
        if ratios is None:
            return
        self._hold_as_manual_tuning(ratios)

    def _hold_as_manual_tuning(self, ratios) -> None:
        """Freeze the generator tuning at the rational tuning that holds ``ratios`` (a full
        projection), WITHOUT writing the held column — the shared core of picking an established
        projection and hand-editing the unchanged basis / G / P. Undoable."""
        self._snapshot()
        # thread the domain basis / ch9 approach / custom prescaler (as the grid's solve does), so a
        # held nonprime ratio like 13/5 is read over the domain — not parsed over the prime series
        # (which raised an uncaught ValueError) — and the residual optimization uses the right just map
        self.generator_tuning = service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, held=tuple(ratios),
            prescaler_override=self.custom_prescaler, targets=self.target_override,
        ).generator_map
        self.superspace_generator_tuning = None
        self.manual_tuning = True  # a deliberate tuning override (not the scheme optimum)
        # remember the exact basis this pin holds, so unchanged_ratios recovers the FULL unchanged
        # basis (hence targets_in_use / P / G / U) even when these ratios aren't in its candidate pool
        self.projection_basis = tuple(ratios)

    def set_unchanged_basis(self, ratios) -> None:
        """Apply a hand-edited unchanged interval basis (the editable U cells) — set the tuning to the
        rational projection that holds those intervals, exactly like picking an established projection
        but with your own basis. A no-op when they don't form a valid FULL rational projection, so an
        in-progress or degenerate edit is rejected and reverts on re-render. Undoable."""
        if service.tuning_projection(self.state, tuple(ratios)) is None:
            return  # not a valid full-rank rational projection — reject the edit
        self._hold_as_manual_tuning(ratios)

    def set_projection_matrix(self, projection) -> bool:
        """Apply a hand-edited projection matrix P (the editable P tile): recover its unchanged basis
        (the eigenvalue-1 eigenvectors) and retune to it, like editing U. Returns False (so the caller
        can toast why) when the edit isn't a valid rational tempering projection of this temperament.
        Undoable."""
        U = service.unchanged_basis_from_projection(self.state, projection)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.state.domain_basis))
        return True

    def set_embedding_matrix(self, embedding) -> bool:
        """Apply a hand-edited generator embedding G (the editable G tile): recover its unchanged basis
        (its column space) and retune to it. Returns False (so the caller can toast why) when G isn't a
        valid embedding (M·G ≠ I). Undoable."""
        U = service.unchanged_basis_from_embedding(self.state, embedding)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.state.domain_basis))
        return True

    def _displayed_retuning_map(self) -> tuple[float, ...] | None:
        """The per-prime retuning (tempered − just sizes, in cents) of the tuning the grid is
        actually showing — a hand-edited/established manual 𝒈 if there is one, else the scheme's
        live optimum. Its zeros are the intervals held unchanged, which is what drives U/P/G.
        ``None`` when it can't be measured (a stale manual 𝒈 from before a dimension change, or a
        nonstandard mixed basis the solver can't size) — the projection then simply dashes out.

        A manual 𝒈 that rounds to the optimum at DISPLAY precision is treated AS the optimum here, so
        the projection identification agrees with the scheme-name / optimized flag (which already
        compare at display precision): retyping or wheel-nudging the tuning back to its shown 3-dp
        cents then keeps P/G/U and the projection name, rather than dashing them while the scheme
        chooser still reads the optimum."""
        try:
            generators = self.effective_generator_tuning()
            if generators is not None and len(generators) == self.state.r:
                optimum = self._optimum_tuning()  # the held-/target-/basis-aware solve the grid uses
                if not _same_cents_map(generators, optimum.generator_map):
                    return service.tuning_from_generators(
                        self.state.mapping, generators, self.state.domain_basis).retuning_map
                return optimum.retuning_map  # a manual 𝒈 indistinguishable from the optimum at display precision
            # scheme-driven, or a stale-length manual 𝒈 from before a dimension change
            return self._optimum_tuning().retuning_map
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("_displayed_retuning_map dashed: %r", exc)
            return None

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        """The intervals the DISPLAYED tuning holds unchanged, as ratio strings — read off the
        tuning itself (the candidates it leaves at zero damage), not off the held column, so e.g.
        the default minimax-U meantone reports {2/1, 5/4} (it IS quarter-comma). This is what drives
        the projection P/G and the unchanged basis U; fewer than r ⇒ not a full rational projection,
        and the rest dash.

        Candidate ORDER matters: the basis representatives chosen for U are the first independent
        unchanged candidates found. The held column comes FIRST — an interval the user deliberately
        holds is unchanged by construction, so it must itself appear in U (overriding an auto-picked
        representative of the same direction); this is ch3's "anything in the held interval basis
        will always be in the unchanged interval basis too". Only AFTER the held intervals do we
        fall back to the established-projection bases (clean representatives like 5/4 over 5/2 for
        the directions the optimizer holds on its own) and then the target interval set. With no
        held column the order is unchanged, so the default still reports {2/1, 5/4}."""
        retuning = self._displayed_retuning_map()
        if retuning is None:  # the tuning can't be measured — nothing known unchanged, all dashes
            return ()
        # The held column leads the candidate pool: an interval the user deliberately holds is
        # unchanged by construction, so it must itself be U's representative for its direction
        # (overriding an auto-pick). Next comes the exact basis a deliberate pin holds — without it a
        # projection whose ratios aren't an established/target/held candidate (a hand-edited U/P/G, or
        # any pick on a temperament with no established projections) reads as under-rank, wrongly
        # keeping the target column up and dashing P/G/U. Held and the pin lead in different scenarios
        # (an optimization-time hold vs a manual pin) so they rarely coincide; when they do, the
        # explicit hold wins the representative slot while the count stays the same (order doesn't
        # change the rank). Each candidate is still validated against the live tuning below, so
        # listing one never forces a ratio the tuning doesn't actually hold.
        held = tuple(service.comma_ratios(self.held_vectors, self.state.domain_basis)) if self.held_vectors else ()
        candidates = (held
                      + self.projection_basis
                      + presets.projection_candidate_ratios(self.state)
                      + tuple(service.target_interval_set(self.target_spec, self.state.domain_basis)))
        return service.unchanged_ratios_of_tuning(self.state, retuning, candidates)

    @property
    def targets_in_use(self) -> bool:
        """Whether the target interval list is actually computing the displayed tuning. The targets
        only do their job — minimizing damage to pin the generators — when the displayed tuning IS
        the scheme's target-driven optimum. Once you specify a projection (pick one, or edit U/G/P)
        whose tuning deviates from that optimum, the targets play no role, so the whole target column
        is hidden (ch3's h + k ≥ r: pin a full projection and there's nothing left for targets to do;
        a tuning that still equals the optimum — e.g. the default, which lands on 1/4-comma — keeps
        it). The targets only drop away once a FULL rational projection (r unchanged intervals) pins
        the tuning AWAY from the optimum; an under-rank tuning (a partial projection, or a hand-edit
        holding fewer than r rational intervals) still needs the targets to fix the rest (ch3
        h + k ≥ r), so they stay. True too when the optimum can't be measured, so we never hide
        spuriously."""
        if not self.settings.get("projection"):
            return True  # the target-list-hiding is a projection-feature behaviour — with the
            # projection box off there's no projection in play, so the target list always shows
        if not self.manual_tuning:
            return True  # scheme-driven: the targets produce the displayed optimum
        if len(self.unchanged_ratios) < self.state.r:
            return True  # under-rank: the targets still pin the unconstrained generators
        displayed = self.effective_generator_tuning()  # a full projection — does it equal the optimum?
        if displayed is None:
            return True
        try:
            optimum = self._optimum_generator_tuning()
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("optimum solve failed; treating displayed tuning as optimal: %r", exc)
            return True
        return len(displayed) == len(optimum) and all(abs(a - b) < 1e-6 for a, b in zip(displayed, optimum))

    @property
    def displayed_projection_scheme_name(self) -> str | None:
        """The established-projection / -embedding chooser's value: the named tuning the displayed
        tuning realises (matched by projection), or ``None`` (the placeholder) when the tuning isn't
        a full rational projection or matches no named tuning. Mirrors
        :attr:`displayed_tuning_scheme_name` for the projection presets."""
        return presets.identify_established_projection(self.state, self.unchanged_ratios)

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

    def set_nonprime_basis_approach(self, approach: str) -> None:
        """Set the chapter-9 nonstandard-domain-approach radio: ``""`` (neutral),
        ``"prime-based"`` (read the temperament in its prime superspace) or ``"nonprime-based"``
        (honor the basis as given). An analysis selection, not a document edit, so it does not
        snapshot — like the Show toggles and range mode. Rejects any other value (the radio
        only offers these three) so the field can't drift off contract."""
        if approach not in ("", "prime-based", "nonprime-based"):
            raise ValueError(f"unknown nonprime basis approach: {approach!r}")
        self.nonprime_basis_approach = approach
        # a manual 𝒈L only exists in the prime-based superspace; any approach switch drops it
        self.superspace_generator_tuning = None
        # dropping the only manual tuning drops the manual flag too: if no on-domain manual 𝒈 remains,
        # the tuning reverts to the scheme optimum, so leaving manual_tuning True would strand the
        # back-to-scheme button lit with nothing to revert (back_to_scheme / the scheme pick both
        # clear it alongside 𝒈L). A manual on-domain 𝒈 still set keeps the flag.
        if self.generator_tuning is None:
            self.manual_tuning = False

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
        """Begin a blank target interval draft — the target list's + control, mirroring
        :meth:`add_interest`. Off in all-interval (the control is hidden there)."""
        self._clear_pending()  # one draft at a time: opening this discards any other
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
    # "unchanged" is a COPY source only: the unchanged interval basis U is derived (read off the
    # tuning), so dragging one of its intervals to another list copies it there without removing it
    # from U, and nothing can be dropped INTO U (see _move_feasible / _take_from).
    MOVE_LISTS = ("targets", "held", "interest", "commas", "unchanged")

    def _list_vectors(self, name: str) -> list[tuple[int, ...]]:
        """The named interval list as vectors over the domain — the currency a move reads."""
        if name == "targets":
            return [tuple(v) for v in service.target_interval_vectors(
                self._current_targets(), self.state.d, self.state.domain_basis)]
        if name == "held":
            return [tuple(v) for v in self.held_vectors]
        if name == "interest":
            return [tuple(v) for v in self.interest_vectors]
        if name == "unchanged":  # the derived unchanged interval basis U (None for a dashed column)
            return list(service.unchanged_interval_basis(self.state, self.unchanged_ratios) or ())
        return [tuple(v) for v in self.state.comma_basis]  # commas

    def _peek_vector(self, name: str, i: int) -> tuple[int, ...] | None:
        vectors = self._list_vectors(name)
        return vectors[i] if 0 <= i < len(vectors) else None

    def _move_feasible(self, src: str, dst: str, vector: tuple[int, ...]) -> bool:
        if src not in self.MOVE_LISTS or dst not in self.MOVE_LISTS:
            return False
        if dst == "unchanged":
            return False  # U is derived from the tuning — nothing can be dropped INTO it
        if "targets" in (src, dst) and service.is_all_interval(self.tuning_scheme):
            return False  # the target list is auto Tₚ = I there, not a user-curated set
        if src == "commas" and self.state.n == 0:
            return False  # nothing tempered: no real comma to drag out (parity with the comma −)
        if dst == "commas":  # tempering the interval out must genuinely raise the nullity
            domain_basis = self.state.domain_basis if len(vector) == self.state.d else None
            extended = service.from_comma_basis(self._real_comma_basis + (tuple(vector),), domain_basis)
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
        elif name == "unchanged":
            pass  # U is derived — a drag COPIES the interval out; it stays held (nothing removed)
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
            domain_basis = self.state.domain_basis if len(vector) == self.state.d else None
            self.state = service.from_comma_basis(self._real_comma_basis + (tuple(vector),), domain_basis)

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
        if src_list == dst_list and (src_list in ("commas", "unchanged") or src_idx == dst_idx):
            return False  # dropping a column on itself is a no-op; a commas/unchanged reorder is
            # unobservable (the dual canonicalizes the comma order; U is a derived, unordered basis)
        self._snapshot()
        if "commas" in (src_list, dst_list):
            self._clear_pending()  # a rank change invalidates the per-list drafts
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)  # land at the dropped-on column's index (insert clamps)
        return True

    def set_range_mode(self, mode: str) -> None:
        self._snapshot()
        self.range_mode = mode

    def _reset_to_basic_tuning(self) -> None:
        """Drop the advanced tuning knobs back to basic minimax-lp — the lp interval complexity
        (which also clears any custom prescaler) and the minimax power 𝑝 = ∞. Called when alt.
        complexity is turned off, since those knobs are reachable only with it on; the caller has
        already snapshotted, so the reset shares that one undo step with the toggle that fired it."""
        self.tuning_scheme = service.scheme_with_power(
            service.scheme_with_complexity(self.tuning_scheme, "lp"), float("inf"))
        self.custom_prescaler = None

    def set_show(self, key: str, value: bool) -> None:
        """Set one Show toggle (which parts of the grid are visible) — an undoable change. The
        sub-control hierarchy (:data:`show_settings.SUBCONTROLS`) is kept consistent both ways:
        selecting a sub-control also selects every layer it refines (a refinement can't show
        without its base — equivalences needs symbols, mnemonics needs names), and deselecting a
        toggle deselects every sub-control nested under it (so a hidden parent never strands its
        sub-controls' content or panel rows on screen). Turning alt. complexity off (directly or by
        deselecting a parent like weighting) also resets the tuning to basic minimax-lp."""
        self._snapshot()
        had_alt_complexity = self.settings["alt_complexity"]
        self.settings[key] = value
        if value:
            for parent in show_settings.ancestors_of(key):
                self.settings[parent] = True
        else:
            for child in show_settings.subcontrols_of(key):
                self.settings[child] = False
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self._reset_to_basic_tuning()

    def set_all_show(self, value: bool, keys=None) -> None:
        """The settings panel's select-all/none: turn the given Show toggles on (``True``) or off
        (``False``) at once. ``keys`` defaults to every *implemented* toggle; the panel narrows it
        to the ones the chapter slider has revealed (an unrevealed toggle is disabled, so select-all
        leaves it alone). The not-yet-built toggles are left at their defaults either way."""
        keys = show_settings.IMPLEMENTED if keys is None else keys
        self._snapshot()
        had_alt_complexity = self.settings["alt_complexity"]
        for key in keys:
            self.settings[key] = value
        # turning "nonstandard domain" off via select-none leaves the nonstandard basis the same way
        # the direct toggle does — convert it to the simplest standard prime limit (the setting stays
        # off) rather than stranding its content with nowhere to show.
        if not value and "nonstandard_domain" in keys and self.basis_is_nonstandard:
            self._standardize_domain_in_place()
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self._reset_to_basic_tuning()

    def disable_hidden_settings(self, chapter: int) -> None:
        """Turn OFF every Show toggle the guide-chapter slider has hidden (its reveal chapter is past
        ``chapter``), so a hidden layer's content drops out of the grid — the slider doesn't merely
        hide the control, it disables the setting. A view-driven prune (the slider is a viewing
        preference, not a document edit), so it is NOT snapshotted for undo; raising the slider
        re-reveals the control but leaves it off for the user to turn back on. Turning off every
        unrevealed key together keeps the sub-control hierarchy consistent (a child's reveal chapter
        is never before its parent's), and resets to basic tuning if alt. complexity was hidden away."""
        had_alt_complexity = self.settings["alt_complexity"]
        for key in self.settings:
            if self.settings[key] and show_settings.reveal_chapter(key) > chapter:
                self.settings[key] = False
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self._reset_to_basic_tuning()

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
        """Begin a pending mapping row: a blank green draft row the user types a new generator into,
        the ROW mirror of :meth:`add_comma`. It is NOT part of the temperament (the mapping is
        unchanged) and not an undoable edit until it commits — see :meth:`set_pending_mapping_row`.
        Gated like before on there being a comma to un-temper (nullity > 0): at full rank no
        independent generator can be added holding the d primes, so the + does not open a draft."""
        if not self.can_add_mapping_row:
            return  # full rank: no independent generator to add (n = 0)
        self._clear_pending()  # one draft at a time: opening this discards any other
        self.pending_mapping_row = [None] * self.state.d

    def set_pending_mapping_row(self, values) -> None:
        """Hold the draft generator's typed components. Once all d are filled and the row, appended
        to the mapping, is a proper temperament — independent of the existing rows, so it genuinely
        adds a generator (+r, −n) — commit it (re-dualing the comma basis) and clear the draft. An
        incomplete or dependent draft is kept as-is (shown pending), changing nothing. The row-space
        twin of :meth:`set_pending_comma`; like it, commits directly (no :meth:`_clear_pending`, which
        would wipe the very draft mid-edit)."""
        self.pending_mapping_row = list(values)
        if any(v is None for v in values):
            return  # still being typed in
        extended = [list(row) for row in self.state.mapping] + [[int(v) for v in values]]
        if service.is_proper_temperament(extended):  # an independent new row re-ranks the temperament
            self._snapshot()
            self.state = service.from_mapping(extended, self.state.domain_basis)
            self.pending_mapping_row = None

    def cancel_pending_mapping_row(self) -> None:
        """Discard the draft mapping row without committing (the draft row's − control). Not an
        undoable edit — the row was never committed. A no-op when there is no draft."""
        self.pending_mapping_row = None

    def remove_mapping_row(self, i: int) -> None:
        if not self.can_remove_mapping_row:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.remove_mapping_row(self.state, i)

    def add_mapping_row_to(self, source: int, target: int) -> None:
        """Drag generator row ``source`` onto a DIFFERENT row ``target``: add the dragged row into
        the dropped-on one (``row[target] += row[source]``). A generator-basis change that holds the
        temperament and the sounding tuning — see :func:`service.add_mapping_row_to`. A manual
        generator tuning is transformed so the pitches are preserved (the dragged generator's size
        loses the target's); a scheme-driven tuning (None) just re-solves the same optimum.
        ``source == target`` is a no-op (dropping a row on itself is not a meaningful operation)."""
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
        :func:`service.add_comma_to`); the mapping is the comma basis's canonical dual. When the
        displayed mapping is ALREADY that dual the mapping is unchanged, so no tuning transform is
        needed; but the editor accepts any proper form (e.g. an ET-pair mapping), and re-dualing then
        rewrites the mapping to canonical — a generator-basis change that would silently reinterpret a
        frozen tuning. So drop a now-stale manual tuning (:meth:`_drop_stale_manual_tuning`) rather
        than leave it pointing at the old generators. ``source == target`` is a no-op."""
        n = len(self.state.comma_basis)
        if source == target or not (0 <= source < n and 0 <= target < n):
            return
        self._snapshot()
        self._clear_pending()
        old_mapping = self.state.mapping
        self.state = service.add_comma_to(self.state, source, target)
        self._drop_stale_manual_tuning(old_mapping)

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
        self._clear_pending()  # one draft at a time: opening this discards any other
        self.pending_comma = [None] * self.state.d

    def set_pending_comma(self, values) -> None:
        """Hold the draft comma's edited components. Once all are filled and the comma
        is independent of the basis (so it genuinely raises the nullity), commit it —
        re-dualing to a mapping with one fewer row — and clear the draft. An
        incomplete or dependent draft is kept as-is (shown pending), changing nothing."""
        self.pending_comma = list(values)
        if any(v is None for v in values):
            return  # still being typed in
        new_comma = tuple(int(v) for v in values)
        # keep a nonstandard domain when the draft's length matches d, mirroring
        # try_edit_comma_basis_text — else from_comma_basis would silently rebuild the
        # standard prime limit and revert the temperament's basis (e.g. 2.3.13/5 -> 2.3.5).
        domain_basis = self.state.domain_basis if len(new_comma) == self.state.d else None
        extended = service.from_comma_basis(self._real_comma_basis + (new_comma,), domain_basis)
        if extended.n > self.state.n:  # an independent new comma re-ranks the temperament
            self._snapshot()
            self.state = extended
            self.pending_comma = None

    def add_element(self) -> None:
        """Begin a pending domain basis element: a blank green ?/? draft column. Not part of the
        domain (d unchanged) and not an undoable edit until it commits — see set_pending_element."""
        self._clear_pending()  # one draft at a time: opening this discards any other
        self.pending_element = ""

    def set_pending_element(self, text) -> None:
        """Hold the draft element's typed text. Once it parses to a valid, independent addition
        (a positive rational ≠ 1, multiplicatively independent of the basis), commit it — the new
        element added held just, its own pure generator (d → d+1, r → r+1) — and clear the draft.
        An incomplete or invalid draft is kept as-is (shown pending), changing nothing."""
        self.pending_element = "" if text is None else str(text)
        if service.can_add_domain_element(self.state, self.pending_element):
            self._snapshot()
            self.state = service.add_domain_element(self.state, service.parse_domain_element(self.pending_element))
            self.pending_element = None

    def remove_element(self) -> None:
        """Cancel the pending domain basis element draft (the green ?/? column's −). Not an undoable
        edit — the draft was never committed. A no-op when there is no draft."""
        self.pending_element = None

    def remove_domain_element(self, index: int) -> None:
        """Drop domain basis element ``index`` (its per-element − with the nonstandard-domain box on):
        an undoable structural edit that re-duals over the reduced basis (see
        :func:`service.remove_domain_element`). Changing d invalidates any length-d draft, so clear it
        like :meth:`shrink` does. A no-op down at the last element (``can_remove_domain_element``)."""
        if not self.can_remove_domain_element:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.remove_domain_element(self.state, index)

    def set_domain_element(self, index: int, text) -> None:
        """Relabel domain basis element ``index`` to the typed ``text`` — a pure basis relabel that
        leaves the mapping coordinates untouched. Commits only a valid, independent relabel (a
        positive rational ≠ 1 keeping the basis independent); an invalid edit is a no-op (the cell
        reverts to the live element on the next render)."""
        if not service.can_set_domain_element(self.state, index, str(text)):
            return
        self._snapshot()
        self.state = service.set_domain_element(self.state, index, service.parse_domain_element(str(text)))

    def cancel_pending_comma(self) -> None:
        """Discard the pending comma draft without committing (the draft column's −).
        Not an undoable edit — the draft was never part of the temperament."""
        self.pending_comma = None

    def remove_comma(self, index: int = -1) -> None:
        """Un-temper comma ``index`` (the last by default) — re-dualing to a mapping with one
        more row (−n, +r). Each comma carries its own −, so ANY one is removable, down to and
        including the last (which leaves just intonation, nullity 0). A no-op with nothing
        tempered; the + adds a comma back."""
        if self.state.n == 0:
            return  # nothing tempered: no comma to un-temper (the + adds one back)
        self._snapshot()
        self.state = service.remove_comma(self.state, index)

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
            "generator_tuning": list(self.generator_tuning) if self.generator_tuning is not None else None,
            "manual_tuning": self.manual_tuning,
            "custom_prescaler": _prescaler_to_json(self.custom_prescaler),
            "target_override": list(self.target_override) if self.target_override is not None else None,
            "projection_basis": list(self.projection_basis),
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
            # a saved tuning is honoured only as a MANUAL override; a doc saved by an older build
            # with a non-manual frozen tuning (the retired freeze-at-optimum state) re-optimizes.
            # The flag is coupled to the honoured tuning: a doc saved while a manual superspace 𝒈L
            # was active carries manual_tuning=true with no generator_tuning (𝒈L is transient and
            # never persists), and honouring the orphaned flag would light the back-to-scheme
            # button over a scheme-driven grid.
            generator_tuning=tuple(data["generator_tuning"])
            if data.get("generator_tuning") is not None and data.get("manual_tuning") else None,
            manual_tuning=bool(data.get("manual_tuning") and data.get("generator_tuning") is not None),
            custom_prescaler=_prescaler_from_json(data.get("custom_prescaler")),
            target_override=tuple(data["target_override"])
            if data.get("target_override") is not None else None,
            projection_basis=tuple(data.get("projection_basis", ()) or ()),
            settings=tuple(sorted(show_settings.from_persisted(data.get("settings", {})).items())),
            collapsed=frozenset(data.get("collapsed", INITIAL_COLLAPSED)),
        )
        self._restore(doc)
        self._undo_stack.clear()
        self._redo_stack.clear()
