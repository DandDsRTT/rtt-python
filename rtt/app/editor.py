from __future__ import annotations

import functools
import logging
import math
import re
from collections import deque
from dataclasses import dataclass
from fractions import Fraction

from rtt.app import presets
from rtt.app import service
from rtt.app import settings as show_settings
from rtt.app import spreadsheet
from rtt.app.layout import Layout
from rtt.app.service import TemperamentState

_log = logging.getLogger(__name__)

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))
INITIAL_COLLAPSED: frozenset[str] = frozenset()
_GENERATOR_NUDGE_CENTS = 0.001


def _same_cents_map(a, b) -> bool:
    return len(a) == len(b) and all(service.cents(x) == service.cents(y) for x, y in zip(a, b))


@dataclass(frozen=True)
class _Doc:
    state: TemperamentState
    tuning_scheme: object
    target_family: str
    target_limit: int | None
    interest_vectors: tuple[tuple[int, ...], ...]
    held_vectors: tuple[tuple[int, ...], ...]
    range_mode: str
    generator_tuning: tuple[float, ...] | None
    manual_tuning: bool
    custom_prescaler: tuple | None
    custom_weights: tuple[float, ...] | None
    target_override: tuple[str, ...] | None
    projection_basis: tuple[str, ...]
    settings: tuple[tuple[str, bool], ...]
    collapsed: frozenset[str]
    preferred_form: tuple[tuple[str, str], ...]


def _prescaler_to_json(p):
    if p is None:
        return None
    return [list(row) for row in p] if isinstance(p[0], (tuple, list)) else list(p)


def _prescaler_from_json(p):
    if p is None:
        return None
    if p and isinstance(p[0], (list, tuple)):
        prescaler = tuple(tuple(float(x) for x in row) for row in p)
    else:
        prescaler = tuple(float(x) for x in p)
    return prescaler if _prescaler_is_solvable(prescaler) else None


def _prescaler_is_solvable(p) -> bool:
    if not p:
        return False
    is_matrix = isinstance(p[0], (tuple, list))
    if is_matrix:
        for i, row in enumerate(p):
            for j, x in enumerate(row):
                if not math.isfinite(x) or (i == j and x <= 0):
                    return False
        return True
    return all(math.isfinite(x) and x > 0 for x in p)


def _weights_to_json(w):
    return list(w) if w is not None else None


def _weights_from_json(w):
    if w is None:
        return None
    weights = tuple(float(x) for x in w)
    return weights if _weights_are_solvable(weights) else None


def _weights_are_solvable(w) -> bool:
    return bool(w) and all(math.isfinite(x) and x > 0 for x in w)


@functools.lru_cache(maxsize=1)
def _initial_doc() -> _Doc:
    state = service.from_mapping(INITIAL_MAPPING)
    return _Doc(
        state=state,
        tuning_scheme=service.resolve_tuning_scheme(service.DEFAULT_DOCUMENT_SCHEME),
        target_family=service.DEFAULT_TARGET_SPEC,
        target_limit=None,
        interest_vectors=(),
        held_vectors=(),
        range_mode="monotone",
        generator_tuning=None,
        manual_tuning=False,
        custom_prescaler=None,
        custom_weights=None,
        target_override=None,
        projection_basis=(),
        settings=tuple(sorted(show_settings.defaults().items())),
        collapsed=INITIAL_COLLAPSED,
        preferred_form=(),
    )


_UNDO_HISTORY_MAX = 500


class Editor:
    def __init__(self) -> None:
        self._undo_stack: deque[_Doc] = deque(maxlen=_UNDO_HISTORY_MAX)
        self._redo_stack: deque[_Doc] = deque(maxlen=_UNDO_HISTORY_MAX)
        self.pending_comma: list[int | None] | None = None
        self.pending_interest: list[int | None] | None = None
        self.pending_held: list[int | None] | None = None
        self.pending_target: list[int | None] | None = None
        self.pending_mapping_row: list[int | None] | None = None
        self.pending_element: str | None = None
        self._nudging_generator: int | None = None
        self.nonprime_basis_approach: str = ""
        self.superspace_generator_tuning: tuple[float, ...] | None = None
        self.preferred_form: dict[str, str] = {}
        self._restore(_initial_doc())


    def _capture(self) -> _Doc:
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
            custom_weights=self.custom_weights,
            target_override=self.target_override,
            projection_basis=self.projection_basis,
            settings=tuple(sorted(self.settings.items())),
            collapsed=frozenset(self.collapsed),
            preferred_form=tuple(sorted(self.preferred_form.items())),
        )

    def _restore(self, doc: _Doc) -> None:
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
        self.custom_weights = doc.custom_weights
        self.target_override = doc.target_override
        self.projection_basis = doc.projection_basis
        self.settings = dict(doc.settings)
        self.collapsed = set(doc.collapsed)
        self.preferred_form = dict(doc.preferred_form)
        self._clear_pending()
        self._nudging_generator = None
        self.superspace_generator_tuning = None

    def capture_for_preview(self) -> tuple:
        transients = (self.pending_comma, self.pending_interest, self.pending_held,
                      self.pending_target, self.pending_element, self.pending_mapping_row,
                      self._nudging_generator, self.superspace_generator_tuning,
                      self.nonprime_basis_approach)
        return (self._capture(), list(self._undo_stack), list(self._redo_stack), transients)

    def restore_for_preview(self, token: tuple) -> None:
        doc, undo, redo, transients = token
        self._restore(doc)
        # deque has no slice assignment; clear + extend keeps the maxlen cap (the snapshot
        # came from a capped stack, so this never overfills, but extend would trim if it did)
        self._undo_stack.clear()
        self._undo_stack.extend(undo)
        self._redo_stack.clear()
        self._redo_stack.extend(redo)
        (self.pending_comma, self.pending_interest, self.pending_held, self.pending_target,
         self.pending_element, self.pending_mapping_row, self._nudging_generator,
         self.superspace_generator_tuning, self.nonprime_basis_approach) = transients

    def _clear_pending(self) -> None:
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
        if new_state.d != self._state.d:
            self.target_limit = None
            self.target_override = None
            self.held_vectors = []
            self.interest_vectors = []
            self.custom_prescaler = None
            self._invalidate_custom_weights()
        if not service.domain_has_nonprimes(new_state.domain_basis):
            self.nonprime_basis_approach = ""
        if (new_state.mapping != self._state.mapping
                or new_state.domain_basis != self._state.domain_basis):
            self.superspace_generator_tuning = None
            self.projection_basis = ()
        self._state = new_state

    @property
    def _real_comma_basis(self) -> tuple[tuple[int, ...], ...]:
        return self.state.comma_basis if self.state.n else ()

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def can_reset(self) -> bool:
        return self._capture() != _initial_doc()

    @property
    def target_spec(self) -> str:
        if self.target_limit is not None:
            return f"{self.target_limit}-{self.target_family}"
        return self.target_family

    def layout(self, prev_ids=None, preview_remove=None) -> Layout:
        return spreadsheet.build(
            self.state, self.settings, self.collapsed,
            tuning_scheme=self.tuning_scheme, target_spec=self.target_spec,
            interest=self.interest_vectors, range_mode=self.range_mode,
            pending_comma=self.pending_comma, held_vectors=self.held_vectors,
            generator_tuning=self.effective_generator_tuning(),
            target_override=self.target_override,
            custom_prescaler=self.custom_prescaler,
            custom_weights=self.custom_weights,
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
            mapping_form=self.preferred_form.get("mapping"),
            comma_basis_form=self.preferred_form.get("comma_basis"),
            prev_ids=prev_ids, preview_remove=preview_remove)

    @property
    def can_expand(self) -> bool:
        return service.is_standard_domain(self.state.domain_basis)

    @property
    def basis_is_nonstandard(self) -> bool:
        return not service.is_standard_domain(self.state.domain_basis)

    @property
    def can_shrink(self) -> bool:
        return service.can_shrink_domain(self.state)

    @property
    def can_remove_domain_element(self) -> bool:
        return service.can_remove_domain_element(self.state)

    @property
    def can_add_mapping_row(self) -> bool:
        return self.state.n > 0

    @property
    def can_remove_mapping_row(self) -> bool:
        return self.state.r > 1

    def _apply(self, state: TemperamentState) -> None:
        self._snapshot()
        self._clear_pending()
        old_mapping = self._state.mapping
        self.state = state
        self._drop_stale_manual_tuning(old_mapping)

    def _drop_stale_manual_tuning(self, old_mapping) -> None:
        if self.generator_tuning is not None and self.state.mapping != old_mapping:
            self.generator_tuning = None
            self.manual_tuning = False

    def edit_mapping(self, mapping) -> None:
        domain_basis = self.state.domain_basis if mapping and len(mapping[0]) == self.state.d else None
        self._apply(service.from_mapping(mapping, domain_basis))

    def edit_comma_basis(self, comma_basis, domain_basis=None) -> None:
        self._apply(service.from_comma_basis(comma_basis, domain_basis))

    def _standardize_domain_in_place(self) -> None:
        ratios = service.comma_ratios(self.state.comma_basis, self.state.domain_basis)
        self._clear_pending()
        self.state = service.standardize_to_prime_limit(self.state.domain_basis, ratios)
        self.settings["nonstandard_domain"] = False

    def exit_nonstandard_domain(self) -> None:
        if not self.basis_is_nonstandard:
            return
        self._snapshot()
        self._standardize_domain_in_place()

    def set_mapping_row(self, i: int, val) -> bool:
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
        cols = self.state.comma_basis
        if not 0 <= c < len(cols):
            return False
        basis = [list(col) for col in cols]
        basis[c] = [int(x) for x in vector]
        domain_basis = self.state.domain_basis if len(basis[c]) == self.state.d else None
        state = service.from_comma_basis(basis, domain_basis)
        if state.n != len(basis) or not service.is_proper_temperament(state.mapping):
            return False
        self._apply(state)
        return True

    def canonicalize_mapping(self) -> None:
        self.edit_mapping(service.canonical_mapping(self.state.mapping))

    def set_mapping_form(self, form: str) -> None:
        self.edit_mapping(service.mapping_in_form(self.state.mapping, form, self.state.domain_basis))
        self.preferred_form["mapping"] = form

    def edit_form_matrix(self, form_rows) -> bool:
        new = service.mapping_from_form_matrix(self.state.mapping, form_rows)
        if new is None:
            return False
        self.edit_mapping(new)
        self.preferred_form["mapping"] = ""
        return True

    def try_edit_form_matrix_text(self, text: str) -> bool:
        rows = service.parse_form_matrix(text)
        if rows is None:
            return False
        return self.edit_form_matrix(rows)

    def canonicalize_comma_basis(self) -> None:
        self.edit_comma_basis(
            service.canonical_comma_basis(self.state.comma_basis), self.state.domain_basis)

    def set_comma_basis_form(self, form: str) -> None:
        self.edit_comma_basis(
            service.comma_basis_in_form(self.state.comma_basis, form, self.state.domain_basis),
            self.state.domain_basis)
        self.preferred_form["comma_basis"] = form

    def _feed_draft(self, values, commit) -> list[int | None] | None:
        draft = list(values)
        if any(v is None for v in draft):
            return draft
        self._snapshot()
        commit(tuple(int(v) for v in draft))
        return None

    def add_interest(self) -> None:
        self._clear_pending()
        self.pending_interest = [None] * self.state.d

    def set_pending_interest(self, values) -> None:
        self.pending_interest = self._feed_draft(values, self.interest_vectors.append)

    def cancel_pending_interest(self) -> None:
        self.pending_interest = None

    def remove_interest(self, i: int) -> None:
        self._snapshot()
        del self.interest_vectors[i]

    def set_interest_vectors(self, vectors) -> None:
        self._snapshot()
        self.interest_vectors = [tuple(int(x) for x in m) for m in vectors]

    def add_held(self) -> None:
        self._clear_pending()
        self.pending_held = [None] * self.state.d

    def set_pending_held(self, values) -> None:
        self.pending_held = self._feed_draft(values, self.held_vectors.append)

    def cancel_pending_held(self) -> None:
        self.pending_held = None

    def remove_held(self, i: int) -> None:
        self._snapshot()
        del self.held_vectors[i]

    def set_held_vectors(self, vectors) -> None:
        self._snapshot()
        self.held_vectors = [tuple(int(x) for x in m) for m in vectors]

    def _optimum_tuning(self) -> service.Tuning:
        held = service.comma_ratios(self.held_vectors, self.state.domain_basis) if self.held_vectors else ()
        return service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, held=held,
            prescaler_override=self.custom_prescaler, targets=self.target_override,
            weights_override=self.custom_weights)

    def _optimum_generator_tuning(self) -> tuple[float, ...]:
        return self._optimum_tuning().generator_map

    def back_to_scheme(self) -> None:
        if not self.manual_tuning:
            return
        self._snapshot()
        self.generator_tuning = None
        self.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()

    def effective_generator_tuning(self) -> tuple[float, ...] | None:
        if self.superspace_generator_tuning is not None \
                and self.nonprime_basis_approach == "prime-based" \
                and service.domain_has_nonprimes(self.state.domain_basis):
            return service.project_superspace_generators_to_domain(self.state, self.superspace_generator_tuning)
        return self.generator_tuning

    @property
    def displayed_tuning_scheme_name(self) -> str | None:
        bare = service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, prescaler_override=self.custom_prescaler,
            targets=self.target_override, weights_override=self.custom_weights).generator_map
        held_optimum = self._optimum_generator_tuning() if self.held_vectors else bare
        override = self.effective_generator_tuning()
        displayed = (override if override is not None and len(override) == len(self.state.mapping)
                     else held_optimum)
        if not _same_cents_map(displayed, held_optimum):
            if self.manual_tuning:
                return None
        elif not _same_cents_map(held_optimum, bare):
            return None
        return service.base_scheme_name(self.tuning_scheme)

    @property
    def tuning_is_optimized(self) -> bool:
        override = self.effective_generator_tuning()
        if override is None or len(override) != len(self.state.mapping):
            return True
        return _same_cents_map(override, self._optimum_generator_tuning())

    @property
    def displayed_prescaler_name(self) -> str | None:
        return service.displayed_prescaler_name(
            self.state.mapping, self.tuning_scheme, self.custom_prescaler)

    def set_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, len(self.state.mapping))
        if gens is None:
            return False
        self._snapshot()
        self.generator_tuning = gens
        self.manual_tuning = True
        self.projection_basis = ()
        return True

    def _override_generator(self, i: int, transform, *, snapshot: bool = True) -> None:
        override = self.effective_generator_tuning()
        base = list(override if override is not None and len(override) == len(self.state.mapping)
                    else self._optimum_generator_tuning())
        if not 0 <= i < len(base):
            return
        base[i] = float(transform(base[i]))
        if snapshot:
            self._snapshot()
        self.generator_tuning = tuple(base)
        self.manual_tuning = True
        self.projection_basis = ()

    def set_generator_tuning_component(self, i: int, cents: float) -> None:
        self._override_generator(i, lambda _current: cents)

    def _optimum_superspace_generator_tuning(self) -> tuple[float, ...]:
        return service.superspace_tuning(self.state, self.tuning_scheme, "prime-based").generator_map

    def set_superspace_generator_tuning_text(self, text: str) -> bool:
        gens = service.parse_cents_map(text, service.superspace_rank(self.state))
        if gens is None:
            return False
        self._snapshot()
        self.superspace_generator_tuning = gens
        self.manual_tuning = True
        return True

    def set_superspace_generator_tuning_component(self, i: int, cents: float) -> None:
        manual = self.superspace_generator_tuning
        rL = service.superspace_rank(self.state)
        base = list(manual if manual is not None and len(manual) == rL
                    else self._optimum_superspace_generator_tuning())
        base[i] = float(cents)
        self._snapshot()
        self.superspace_generator_tuning = tuple(base)
        self.manual_tuning = True

    def nudge_superspace_generator_tuning_component(self, i: int, steps: int) -> None:
        rL = service.superspace_rank(self.state)
        manual = self.superspace_generator_tuning
        base = list(manual if manual is not None and len(manual) == rL
                    else self._optimum_superspace_generator_tuning())
        self.set_superspace_generator_tuning_component(
            i, round(round(base[i], 3) + steps * _GENERATOR_NUDGE_CENTS, 3))

    def flip_generator(self, i: int) -> None:
        override = self.effective_generator_tuning()
        mapping = [list(row) for row in self.state.mapping]
        mapping[i] = [-x for x in mapping[i]]
        self.edit_mapping(mapping)
        if override is not None and len(override) == len(mapping):
            flipped = list(override)
            flipped[i] = -flipped[i]
            self.generator_tuning = tuple(flipped)
            self.manual_tuning = True

    def nudge_generator_tuning_component(self, i: int, steps: int) -> None:
        self._override_generator(
            i, lambda current: round(round(current, 3) + steps * _GENERATOR_NUDGE_CENTS, 3),
            snapshot=self._nudging_generator != i)
        self._nudging_generator = i

    @staticmethod
    def _valid_domain_basis(state: TemperamentState) -> bool:
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
        state = service.parse_mapping_state(text)
        if state is None or not service.is_proper_temperament(state.mapping):
            return False
        if not self._valid_domain_basis(state):
            return False
        self._apply(state)
        return True

    def try_edit_comma_basis_text(self, text: str) -> bool:
        basis = service.parse_comma_basis(text)
        if basis is None:
            return False
        domain_basis = self.state.domain_basis if len(basis[0]) == self.state.d else None
        try:
            if not service.is_proper_temperament(service.from_comma_basis(basis, domain_basis).mapping):
                return False
            self.edit_comma_basis(basis, domain_basis)
        except Exception:
            _log.exception("comma-basis edit failed on %r", basis)
            return False
        return True

    def try_edit_projection_text(self, text: str) -> bool:
        matrix = service.parse_projection(text)
        if matrix is None:
            return False
        return self.set_projection_matrix(matrix)

    def try_edit_embedding_text(self, text: str) -> bool:
        matrix = service.parse_embedding(text, self.state.d, len(self.state.mapping))
        if matrix is None:
            return False
        return self.set_embedding_matrix(matrix)

    def set_tuning_scheme(self, name: str) -> None:
        self._snapshot()
        target = "{}" if service.is_all_interval(self.tuning_scheme) else self.target_spec
        self.tuning_scheme = service.scheme_with_targets(name, target)
        self.generator_tuning = None
        self.superspace_generator_tuning = None
        self.manual_tuning = False
        self.projection_basis = ()

    def set_established_projection(self, name: str | None) -> None:
        ratios = presets.projection_held_ratios(self.state, name)
        if ratios is None:
            return
        self._hold_as_manual_tuning(ratios)

    def _hold_as_manual_tuning(self, ratios) -> None:
        self._snapshot()
        self.generator_tuning = service.tuning(
            self.state.mapping, self.tuning_scheme, self.state.domain_basis,
            self.nonprime_basis_approach, held=tuple(ratios),
            prescaler_override=self.custom_prescaler, targets=self.target_override,
            weights_override=self.custom_weights,
        ).generator_map
        self.superspace_generator_tuning = None
        self.manual_tuning = True
        self.projection_basis = tuple(ratios)

    def set_unchanged_basis(self, ratios) -> None:
        if service.tuning_projection(self.state, tuple(ratios)) is None:
            return
        self._hold_as_manual_tuning(ratios)

    def set_projection_matrix(self, projection) -> bool:
        U = service.unchanged_basis_from_projection(self.state, projection)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.state.domain_basis))
        return True

    def set_embedding_matrix(self, embedding) -> bool:
        U = service.unchanged_basis_from_embedding(self.state, embedding)
        if U is None:
            return False
        self.set_unchanged_basis(service.comma_ratios(U, self.state.domain_basis))
        return True

    def _displayed_retuning_map(self) -> tuple[float, ...] | None:
        try:
            generators = self.effective_generator_tuning()
            if generators is not None and len(generators) == self.state.r:
                optimum = self._optimum_tuning()
                if not _same_cents_map(generators, optimum.generator_map):
                    return service.tuning_from_generators(
                        self.state.mapping, generators, self.state.domain_basis).retuning_map
                return optimum.retuning_map
            return self._optimum_tuning().retuning_map
        except (ValueError, ArithmeticError, IndexError, TypeError) as exc:
            _log.debug("_displayed_retuning_map dashed: %r", exc)
            return None

    @property
    def unchanged_ratios(self) -> tuple[str, ...]:
        retuning = self._displayed_retuning_map()
        if retuning is None:
            return ()
        held = tuple(service.comma_ratios(self.held_vectors, self.state.domain_basis)) if self.held_vectors else ()
        candidates = (held
                      + self.projection_basis
                      + presets.projection_candidate_ratios(self.state)
                      + tuple(service.target_interval_set(self.target_spec, self.state.domain_basis)))
        return service.unchanged_ratios_of_tuning(self.state, retuning, candidates)

    @property
    def targets_in_use(self) -> bool:
        if not self.settings.get("projection"):
            return True
        if not self.manual_tuning:
            return True
        if len(self.unchanged_ratios) < self.state.r:
            return True
        displayed = self.effective_generator_tuning()
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
        return presets.identify_established_projection(self.state, self.unchanged_ratios)

    def set_complexity_prescaler(self, prescaler: str) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_prescaler(self.tuning_scheme, prescaler)
        self.custom_prescaler = None
        self._turn_off_custom_weights()

    def set_complexity_norm_power(self, power: float) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_complexity_norm_power(self.tuning_scheme, power)

    def set_optimization_power(self, power: float) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_power(self.tuning_scheme, power)

    def set_weight_slope(self, slope: str) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)
        self._turn_off_custom_weights()

    def set_nonprime_basis_approach(self, approach: str) -> None:
        if approach not in ("", "prime-based", "nonprime-based"):
            raise ValueError(f"unknown nonprime basis approach: {approach!r}")
        self.nonprime_basis_approach = approach
        self.superspace_generator_tuning = None
        if self.generator_tuning is None:
            self.manual_tuning = False

    def set_complexity_name(self, name: str) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_complexity(self.tuning_scheme, name)
        self.custom_prescaler = None
        self._turn_off_custom_weights()

    def set_custom_prescaler_entry(self, i: int, j: int, value: float) -> None:
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
        diag = service.parse_prescaler_diagonal(text, self.state.d)
        if diag is None:
            return False
        self._snapshot()
        self.custom_prescaler = diag
        return True

    def set_diminuator_replaced(self, replaced: bool) -> None:
        self._snapshot()
        self.tuning_scheme = service.scheme_with_diminuator(self.tuning_scheme, replaced)

    def set_all_interval(self, all_interval: bool) -> None:
        self._snapshot()
        slope = "simplicity-weight" if all_interval else "unity-weight"
        scheme = service.scheme_with_weight_slope(self.tuning_scheme, slope)
        self.tuning_scheme = service.scheme_with_targets(
            scheme, "{}" if all_interval else self.target_spec)
        self._reconcile_custom_weights()

    def _reconcile_custom_weights(self) -> None:
        applies = self.settings["custom_weights"] and not service.is_all_interval(self.tuning_scheme)
        if applies and self.custom_weights is None:
            self.custom_weights = tuple(self._displayed_target_weights())
        elif not applies:
            self.custom_weights = None

    def _displayed_target_weights(self) -> tuple[float, ...]:
        return tuple(service.interval_weights(
            self.state.mapping, self.tuning_scheme, self._current_targets(),
            prescaler_override=self.custom_prescaler, domain_basis=self.state.domain_basis))

    def set_custom_weight_entry(self, i: int, value: float) -> None:
        self._snapshot()
        if self.custom_weights is None:
            self.custom_weights = tuple(self._displayed_target_weights())
            self.settings["custom_weights"] = True
        weights = list(self.custom_weights)
        if 0 <= i < len(weights):
            weights[i] = float(value)
            self.custom_weights = tuple(weights)

    def set_custom_weights(self, weights) -> None:
        weights = tuple(float(w) for w in weights)
        if not _weights_are_solvable(weights):
            return
        self._snapshot()
        self.custom_weights = weights
        self.settings["custom_weights"] = True

    def _invalidate_custom_weights(self) -> None:
        self.custom_weights = None
        self._reconcile_custom_weights()

    def _turn_off_custom_weights(self) -> None:
        self.settings["custom_weights"] = False
        self.custom_weights = None

    def set_target_spec(self, spec: str) -> None:
        self._snapshot()
        match = re.match(r"(\d*)-?(TILT|OLD)", spec)
        n, family = (match.group(1), match.group(2)) if match else ("", self.target_family)
        self.target_family = family
        self.target_limit = int(n) if n else None
        self.target_override = None
        self._invalidate_custom_weights()
        if not service.is_all_interval(self.tuning_scheme):
            self.tuning_scheme = service.scheme_with_targets(self.tuning_scheme, self.target_spec)

    def set_target_override_text(self, text: str) -> bool:
        vectors = service.parse_comma_basis(text)
        if vectors is None:
            return False
        self._snapshot()
        self.target_override = service.comma_ratios(vectors, self.state.domain_basis)
        self._invalidate_custom_weights()
        return True

    def set_target_override_vectors(self, vectors) -> None:
        self._snapshot()
        self.target_override = service.comma_ratios(
            [tuple(int(x) for x in m) for m in vectors], self.state.domain_basis)
        self._invalidate_custom_weights()

    def _current_targets(self) -> list[str]:
        if self.target_override is not None:
            return list(self.target_override)
        return list(service.target_interval_set(self.target_spec, self.state.domain_basis))

    def add_target(self) -> None:
        self._clear_pending()
        self.pending_target = [None] * self.state.d

    def set_pending_target(self, values) -> None:
        def commit(vector):
            targets = self._current_targets()
            targets.append(service.comma_ratios([vector], self.state.domain_basis)[0])
            self.target_override = tuple(targets)
            self._invalidate_custom_weights()
        self.pending_target = self._feed_draft(values, commit)

    def cancel_pending_target(self) -> None:
        self.pending_target = None

    def remove_target(self, i: int) -> None:
        targets = self._current_targets()
        del targets[i]
        self._snapshot()
        self.target_override = tuple(targets)
        self._invalidate_custom_weights()

    MOVE_LISTS = ("targets", "held", "interest", "commas", "unchanged")

    def _list_vectors(self, name: str) -> list[tuple[int, ...]]:
        if name == "targets":
            return [tuple(v) for v in service.target_interval_vectors(
                self._current_targets(), self.state.d, self.state.domain_basis)]
        if name == "held":
            return [tuple(v) for v in self.held_vectors]
        if name == "interest":
            return [tuple(v) for v in self.interest_vectors]
        if name == "unchanged":
            return list(service.unchanged_interval_basis(self.state, self.unchanged_ratios) or ())
        return [tuple(v) for v in self.state.comma_basis]

    def _peek_vector(self, name: str, i: int) -> tuple[int, ...] | None:
        vectors = self._list_vectors(name)
        return vectors[i] if 0 <= i < len(vectors) else None

    def _move_feasible(self, src: str, dst: str, vector: tuple[int, ...]) -> bool:
        if src not in self.MOVE_LISTS or dst not in self.MOVE_LISTS:
            return False
        if dst == "unchanged":
            return False
        if "targets" in (src, dst) and service.is_all_interval(self.tuning_scheme):
            return False
        if src == "commas" and self.state.n == 0:
            return False
        if dst == "commas":
            domain_basis = self.state.domain_basis if len(vector) == self.state.d else None
            extended = service.from_comma_basis(self._real_comma_basis + (tuple(vector),), domain_basis)
            if extended.n <= self.state.n:
                return False
        return True

    def _take_from(self, name: str, i: int) -> None:
        if name == "targets":
            targets = self._current_targets()
            del targets[i]
            self.target_override = tuple(targets)
        elif name == "held":
            del self.held_vectors[i]
        elif name == "interest":
            del self.interest_vectors[i]
        elif name == "unchanged":
            pass
        else:
            self.state = service.remove_comma(self.state, i)

    def _put_into(self, name: str, i: int, vector: tuple[int, ...]) -> None:
        if name == "targets":
            targets = self._current_targets()
            targets.insert(i, service.comma_ratios([vector], self.state.domain_basis)[0])
            self.target_override = tuple(targets)
        elif name == "held":
            self.held_vectors.insert(i, tuple(vector))
        elif name == "interest":
            self.interest_vectors.insert(i, tuple(vector))
        else:
            domain_basis = self.state.domain_basis if len(vector) == self.state.d else None
            self.state = service.from_comma_basis(self._real_comma_basis + (tuple(vector),), domain_basis)

    def move_interval(self, src_list: str, src_idx: int, dst_list: str, dst_idx: int) -> bool:
        vector = self._peek_vector(src_list, src_idx)
        if vector is None or not self._move_feasible(src_list, dst_list, vector):
            return False
        if src_list == dst_list and (src_list in ("commas", "unchanged") or src_idx == dst_idx):
            return False
        self._snapshot()
        if "commas" in (src_list, dst_list):
            self._clear_pending()
        if "targets" in (src_list, dst_list):
            self._invalidate_custom_weights()
        self._take_from(src_list, src_idx)
        self._put_into(dst_list, dst_idx, vector)
        return True

    def set_range_mode(self, mode: str) -> None:
        self._snapshot()
        self.range_mode = mode

    def _reset_to_basic_tuning(self) -> None:
        self.tuning_scheme = service.scheme_with_power(
            service.scheme_with_complexity(self.tuning_scheme, "lp"), float("inf"))
        self.custom_prescaler = None

    def set_show(self, key: str, value: bool) -> None:
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
        self._reconcile_custom_weights()

    def set_all_show(self, value: bool, keys=None) -> None:
        keys = show_settings.IMPLEMENTED if keys is None else keys
        self._snapshot()
        had_alt_complexity = self.settings["alt_complexity"]
        for key in keys:
            self.settings[key] = value
        if not value and "nonstandard_domain" in keys and self.basis_is_nonstandard:
            self._standardize_domain_in_place()
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self._reset_to_basic_tuning()
        self._reconcile_custom_weights()

    def disable_hidden_settings(self, chapter: int) -> None:
        had_alt_complexity = self.settings["alt_complexity"]
        for key in self.settings:
            if self.settings[key] and show_settings.reveal_chapter(key) > chapter:
                self.settings[key] = False
        if had_alt_complexity and not self.settings["alt_complexity"]:
            self._reset_to_basic_tuning()
        self._reconcile_custom_weights()

    def toggle_collapsed(self, item: str) -> None:
        self._snapshot()
        self.collapsed.discard(item) if item in self.collapsed else self.collapsed.add(item)

    def set_collapsed(self, items) -> None:
        self._snapshot()
        self.collapsed = set(items)

    def reset(self) -> None:
        if not self.can_reset:
            return
        self._snapshot()
        self._restore(_initial_doc())

    def expand(self) -> None:
        if not self.can_expand:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        if not self.can_shrink:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.shrink_domain(self.state)

    def add_mapping_row(self) -> None:
        if not self.can_add_mapping_row:
            return
        self._clear_pending()
        self.pending_mapping_row = [None] * self.state.d

    def set_pending_mapping_row(self, values) -> None:
        self.pending_mapping_row = list(values)
        if any(v is None for v in values):
            return
        extended = [list(row) for row in self.state.mapping] + [[int(v) for v in values]]
        if service.is_proper_temperament(extended):
            self._snapshot()
            self.state = service.from_mapping(extended, self.state.domain_basis)
            self.pending_mapping_row = None

    def cancel_pending_mapping_row(self) -> None:
        self.pending_mapping_row = None

    def remove_mapping_row(self, i: int) -> None:
        if not self.can_remove_mapping_row:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.remove_mapping_row(self.state, i)

    def add_mapping_row_to(self, source: int, target: int) -> None:
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
        n = len(self.state.comma_basis)
        if source == target or not (0 <= source < n and 0 <= target < n):
            return
        self._snapshot()
        self._clear_pending()
        old_mapping = self.state.mapping
        self.state = service.add_comma_to(self.state, source, target)
        self._drop_stale_manual_tuning(old_mapping)

    def _combine_interval_vectors(self, vectors: list, source: int, target: int) -> None:
        if source == target or not (0 <= source < len(vectors) and 0 <= target < len(vectors)):
            return
        self._snapshot()
        vectors[target] = tuple(a + b for a, b in zip(vectors[target], vectors[source]))

    def add_interest_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.interest_vectors, source, target)

    def add_held_to(self, source: int, target: int) -> None:
        self._combine_interval_vectors(self.held_vectors, source, target)

    def add_target_to(self, source: int, target: int) -> None:
        targets = self._current_targets()
        if source == target or not (0 <= source < len(targets) and 0 <= target < len(targets)):
            return
        product = Fraction(targets[source]) * Fraction(targets[target])
        self._snapshot()
        targets[target] = f"{product.numerator}/{product.denominator}"
        self.target_override = tuple(targets)
        self._invalidate_custom_weights()

    def add_comma(self) -> None:
        self._clear_pending()
        self.pending_comma = [None] * self.state.d

    def set_pending_comma(self, values) -> None:
        self.pending_comma = list(values)
        if any(v is None for v in values):
            return
        new_comma = tuple(int(v) for v in values)
        domain_basis = self.state.domain_basis if len(new_comma) == self.state.d else None
        extended = service.from_comma_basis(self._real_comma_basis + (new_comma,), domain_basis)
        if extended.n > self.state.n:
            self._snapshot()
            self.state = extended
            self.pending_comma = None

    def add_element(self) -> None:
        self._clear_pending()
        self.pending_element = ""

    def set_pending_element(self, text) -> None:
        self.pending_element = "" if text is None else str(text)
        if service.can_add_domain_element(self.state, self.pending_element):
            self._snapshot()
            self.state = service.add_domain_element(self.state, service.parse_domain_element(self.pending_element))
            self.pending_element = None

    def remove_element(self) -> None:
        self.pending_element = None

    def remove_domain_element(self, index: int) -> None:
        if not self.can_remove_domain_element:
            return
        self._snapshot()
        self._clear_pending()
        self.state = service.remove_domain_element(self.state, index)

    def set_domain_element(self, index: int, text) -> None:
        if not service.can_set_domain_element(self.state, index, str(text)):
            return
        self._snapshot()
        self.state = service.set_domain_element(self.state, index, service.parse_domain_element(str(text)))

    def cancel_pending_comma(self) -> None:
        self.pending_comma = None

    def remove_comma(self, index: int = -1) -> None:
        if self.state.n == 0:
            return
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
        self._redo_stack.clear()
        self._nudging_generator = None

    def serialize(self) -> dict:
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
            "custom_weights": _weights_to_json(self.custom_weights),
            "target_override": list(self.target_override) if self.target_override is not None else None,
            "projection_basis": list(self.projection_basis),
            "settings": dict(self.settings),
            "collapsed": sorted(self.collapsed),
        }

    def load(self, data: dict) -> None:
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
            generator_tuning=tuple(data["generator_tuning"])
            if data.get("generator_tuning") is not None and data.get("manual_tuning") else None,
            manual_tuning=bool(data.get("manual_tuning") and data.get("generator_tuning") is not None),
            custom_prescaler=_prescaler_from_json(data.get("custom_prescaler")),
            custom_weights=_weights_from_json(data.get("custom_weights")),
            target_override=tuple(data["target_override"])
            if data.get("target_override") is not None else None,
            projection_basis=tuple(data.get("projection_basis", ()) or ()),
            settings=tuple(sorted(show_settings.from_persisted(data.get("settings", {})).items())),
            collapsed=frozenset(data.get("collapsed", INITIAL_COLLAPSED)),
            preferred_form=(),
        )
        self._restore(doc)
        self._reconcile_custom_weights()
        self._undo_stack.clear()
        self._redo_stack.clear()
