from __future__ import annotations

import logging
from fractions import Fraction

from rtt.app import service
from rtt.app.service.state import TemperamentState

_log = logging.getLogger(__name__)


class _StructureCommands:
    @property
    def basis_is_nonstandard(self) -> bool:
        return not service.is_standard_domain(self.state.domain_basis)

    @property
    def can_expand(self) -> bool:
        return service.is_standard_domain(self.state.domain_basis)

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

    def edit_mapping(self, mapping) -> None:
        state = self.state
        domain_basis = state.domain_basis if mapping and len(mapping[0]) == state.d else None
        self.apply_state(service.from_mapping(mapping, domain_basis))

    def edit_comma_basis(self, comma_basis, domain_basis=None) -> None:
        self.apply_state(service.from_comma_basis(comma_basis, domain_basis))

    def standardize_domain_in_place(self) -> None:
        state = self.state
        ratios = service.comma_ratios(state.comma_basis, state.domain_basis)
        self.pending.clear_drafts()
        self.state = service.standardize_to_prime_limit(state.domain_basis, ratios)
        self.settings["nonstandard_domain"] = False

    def exit_nonstandard_domain(self) -> None:
        if not self.basis_is_nonstandard:
            return
        self.snapshot()
        self.standardize_domain_in_place()

    def set_mapping_row(self, i: int, val) -> bool:
        rows = self.state.mapping
        if not 0 <= i < len(rows):
            return False
        matrix = [list(row) for row in rows]
        matrix[i] = [int(x) for x in val]
        if not service.is_proper_temperament(matrix):
            return False
        self.apply_state(service.from_mapping(matrix, self.state.domain_basis))
        return True

    def set_comma(self, c: int, vector) -> bool:
        state = self.state
        cols = state.comma_basis
        if not 0 <= c < len(cols):
            return False
        basis = [list(col) for col in cols]
        basis[c] = [int(x) for x in vector]
        domain_basis = state.domain_basis if len(basis[c]) == state.d else None
        new_state = service.from_comma_basis(basis, domain_basis)
        if new_state.n != len(basis) or not service.is_proper_temperament(new_state.mapping):
            return False
        self.apply_state(new_state)
        return True

    def canonicalize_mapping(self) -> None:
        self.edit_mapping(service.canonical_mapping(self.state.mapping))

    def set_mapping_form(self, form: str) -> None:
        state = self.state
        self.edit_mapping(service.mapping_in_form(state.mapping, form, state.domain_basis))
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
        state = self.state
        self.edit_comma_basis(service.canonical_comma_basis(state.comma_basis), state.domain_basis)

    def set_comma_basis_form(self, form: str) -> None:
        state = self.state
        self.edit_comma_basis(
            service.comma_basis_in_form(state.comma_basis, form, state.domain_basis),
            state.domain_basis,
        )
        self.preferred_form["comma_basis"] = form

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
        self.apply_state(state)
        return True

    def try_edit_comma_basis_text(self, text: str) -> bool:
        basis = service.parse_comma_basis(text)
        if basis is None:
            return False
        domain_basis = self.state.domain_basis if len(basis[0]) == self.state.d else None
        try:
            if not service.is_proper_temperament(
                service.from_comma_basis(basis, domain_basis).mapping
            ):
                return False
            self.edit_comma_basis(basis, domain_basis)
        except Exception:
            _log.exception("comma-basis edit failed on %r", basis)
            return False
        return True

    def expand(self) -> None:
        if not self.can_expand:
            return
        self.snapshot()
        self.pending.clear_drafts()
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        if not self.can_shrink:
            return
        self.snapshot()
        self.pending.clear_drafts()
        self.state = service.shrink_domain(self.state)

    def add_mapping_row(self) -> None:
        if not self.can_add_mapping_row:
            return
        self.pending.clear_drafts()
        self.pending.pending_mapping_row = [None] * self.state.d

    def set_pending_mapping_row(self, values) -> None:
        self.pending.pending_mapping_row = list(values)
        if any(v is None for v in values):
            return
        state = self.state
        extended = [list(row) for row in state.mapping] + [[int(v) for v in values]]
        if service.is_proper_temperament(extended):
            self.snapshot()
            self.state = service.from_mapping(extended, state.domain_basis)
            self.pending.pending_mapping_row = None

    def cancel_pending_mapping_row(self) -> None:
        self.pending.pending_mapping_row = None

    def remove_mapping_row(self, i: int) -> None:
        if not self.can_remove_mapping_row:
            return
        self.snapshot()
        self.pending.clear_drafts()
        self.state = service.remove_mapping_row(self.state, i)

    def add_mapping_row_to(self, source: int, target: int) -> None:
        r = len(self.state.mapping)
        if source == target or not (0 <= source < r and 0 <= target < r):
            return
        self.snapshot()
        self.pending.clear_drafts()
        if self.generator_tuning is not None and len(self.generator_tuning) == r:
            tuning = list(self.generator_tuning)
            tuning[source] -= tuning[target]
            self.generator_tuning = tuple(tuning)
        self.state = service.add_mapping_row_to(self.state, source, target)

    def add_comma_to(self, source: int, target: int) -> None:
        n = len(self.state.comma_basis)
        if source == target or not (0 <= source < n and 0 <= target < n):
            return
        self.snapshot()
        self.pending.clear_drafts()
        old_mapping = self.state.mapping
        self.state = service.add_comma_to(self.state, source, target)
        self.drop_stale_manual(old_mapping)

    def add_comma(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_comma = [None] * self.state.d

    def set_pending_comma(self, values) -> None:
        self.pending.pending_comma = list(values)
        if any(v is None for v in values):
            return
        new_comma = tuple(int(v) for v in values)
        state = self.state
        domain_basis = state.domain_basis if len(new_comma) == state.d else None
        extended = service.from_comma_basis((*self.real_comma_basis, new_comma), domain_basis)
        if extended.n > state.n:
            self.snapshot()
            self.state = extended
            self.pending.pending_comma = None

    def cancel_pending_comma(self) -> None:
        self.pending.pending_comma = None

    def remove_comma(self, index: int = -1) -> None:
        if self.state.n == 0:
            return
        self.snapshot()
        self.state = service.remove_comma(self.state, index)

    def add_element(self) -> None:
        self.pending.clear_drafts()
        self.pending.pending_element = ""

    def set_pending_element(self, text) -> None:
        self.pending.pending_element = "" if text is None else str(text)
        if service.can_add_domain_element(self.state, self.pending.pending_element):
            self.snapshot()
            self.state = service.add_domain_element(
                self.state, service.parse_domain_element(self.pending.pending_element)
            )
            self.pending.pending_element = None

    def remove_element(self) -> None:
        self.pending.pending_element = None

    def remove_domain_element(self, index: int) -> None:
        if not self.can_remove_domain_element:
            return
        self.snapshot()
        self.pending.clear_drafts()
        self.state = service.remove_domain_element(self.state, index)

    def set_domain_element(self, index: int, text) -> None:
        if not service.can_set_domain_element(self.state, index, str(text)):
            return
        self.snapshot()
        self.state = service.set_domain_element(
            self.state, index, service.parse_domain_element(str(text))
        )
