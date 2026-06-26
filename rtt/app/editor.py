from __future__ import annotations

from rtt.app import editor_layout
from rtt.app.editor_document import Document
from rtt.app.editor_state import INITIAL_MAPPING

__all__ = ["INITIAL_MAPPING", "Editor"]


class Editor(Document):
    @property
    def superspace_generator_tuning(self) -> tuple[float, ...] | None:
        return self.pending.superspace_generator_tuning

    @property
    def pending_comma(self) -> list[int | None] | None:
        return self.pending.pending_comma

    @pending_comma.setter
    def pending_comma(self, value) -> None:
        self.pending.pending_comma = value

    @property
    def pending_interest(self) -> list[int | None] | None:
        return self.pending.pending_interest

    @property
    def pending_held(self) -> list[int | None] | None:
        return self.pending.pending_held

    @property
    def pending_target(self) -> list[int | None] | None:
        return self.pending.pending_target

    @property
    def pending_element(self) -> str | None:
        return self.pending.pending_element

    @property
    def pending_mapping_row(self) -> list[int | None] | None:
        return self.pending.pending_mapping_row

    @pending_mapping_row.setter
    def pending_mapping_row(self, value) -> None:
        self.pending.pending_mapping_row = value

    @property
    def undo_count(self) -> int:
        return self.history.undo_count

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def layout(self, prev_ids=None, preview_remove=None):
        return editor_layout.build(self, prev_ids, preview_remove)
