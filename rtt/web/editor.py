"""Framework-free view-model for the temperament editor.

Holds the current :class:`~rtt.web.service.TemperamentState` plus undo/redo
stacks, and exposes the user actions (edit either matrix, expand/shrink the
domain, undo, redo). It also tracks the two view selections that the derived rows
are shown under — the tuning scheme and the target-interval set spec — which sit
outside undo because they are display choices, not temperament edits. The NiceGUI
layer is thin glue over this; all of it is unit-testable without a UI.
"""

from __future__ import annotations

from rtt.web import service
from rtt.web.service import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app


class Editor:
    def __init__(self) -> None:
        self.state: TemperamentState = service.from_mapping(INITIAL_MAPPING)
        # Display/analysis selections: which tuning scheme and target-interval set
        # the derived rows are shown under. Unlike the temperament itself, these are
        # view choices (like the Show toggles), so they live outside the undo stack.
        self.tuning_scheme: str = service.DEFAULT_TUNING_SCHEME
        self.target_spec: str = service.DEFAULT_TARGET_SPEC
        # "Other intervals of interest": a user-built set of intervals to watch,
        # held as monzos (edited like the comma basis — editable vector cells).
        # Display data the user curates, not part of the temperament, so (like the
        # tuning/target selections) it lives outside the undo stack.
        self.interest_monzos: list[tuple[int, ...]] = []
        self._undo_stack: list[TemperamentState] = []
        self._redo_stack: list[TemperamentState] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._redo_stack)

    @property
    def can_shrink(self) -> bool:
        """Whether the domain can lose a prime without collapsing to nothing."""
        return self.state.d > 1

    @property
    def can_remove_comma(self) -> bool:
        """Whether a comma can be dropped without emptying the basis."""
        return len(self.state.comma_basis) > 1

    def edit_mapping(self, mapping) -> None:
        self._snapshot()
        self.state = service.from_mapping(mapping)

    def edit_comma_basis(self, comma_basis) -> None:
        self._snapshot()
        self.state = service.from_comma_basis(comma_basis)

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

    def try_edit_mapping_text(self, text: str) -> bool:
        """Parse an EBK map string and apply it as a mapping edit. Returns False
        (leaving the state untouched) when the text is not a valid integer map, so
        the caller can flag the input rather than mangling the temperament."""
        matrix = service.parse_mapping(text)
        if matrix is None:
            return False
        try:
            self.edit_mapping(matrix)
        except Exception:
            return False
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

    def set_target_spec(self, spec: str) -> None:
        self.target_spec = spec

    def expand(self) -> None:
        self._snapshot()
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        self._snapshot()
        self.state = service.shrink_domain(self.state)

    def add_comma(self) -> None:
        self._snapshot()
        self.state = service.add_comma(self.state)

    def remove_comma(self) -> None:
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
