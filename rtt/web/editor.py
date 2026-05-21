"""Framework-free view-model for the temperament editor.

Holds the current :class:`~rtt.web.service.TemperamentState` and an undo stack,
and exposes the user actions (edit either matrix, expand/shrink the domain, undo).
The NiceGUI layer is thin glue over this; all of it is unit-testable without a UI.
"""

from __future__ import annotations

from rtt.web import service
from rtt.web.service import TemperamentState

INITIAL_MAPPING = ((1, 1, 0), (0, 1, 4))  # meantone, matching the original app


class Editor:
    def __init__(self) -> None:
        self.state: TemperamentState = service.from_mapping(INITIAL_MAPPING)
        self._undo_stack: list[TemperamentState] = []

    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    @property
    def can_shrink(self) -> bool:
        """Whether the domain can lose a prime without collapsing to nothing."""
        return self.state.d > 1

    def edit_mapping(self, mapping) -> None:
        self._snapshot()
        self.state = service.from_mapping(mapping)

    def edit_comma_basis(self, comma_basis) -> None:
        self._snapshot()
        self.state = service.from_comma_basis(comma_basis)

    def expand(self) -> None:
        self._snapshot()
        self.state = service.expand_domain(self.state)

    def shrink(self) -> None:
        self._snapshot()
        self.state = service.shrink_domain(self.state)

    def undo(self) -> None:
        if self._undo_stack:
            self.state = self._undo_stack.pop()

    def _snapshot(self) -> None:
        self._undo_stack.append(self.state)
