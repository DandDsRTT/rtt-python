from __future__ import annotations

from fractions import Fraction

from rtt.app import editor_layout, service
from rtt.app.editor_document import Document
from rtt.app.editor_state import INITIAL_MAPPING

__all__ = ["INITIAL_MAPPING", "Editor"]

DEV_MAX_DOMAIN_BASIS = (2, Fraction(7, 3), 5)
DEV_MAX_MAPPING = ((1, 3, 1), (0, 2, -1))
DEV_MAX_HELD = (1, 0, 0)
DEV_MAX_INTEREST = (0, 0, 1)
DEV_PROJECTION_MAPPING = ((1, 1, 0), (0, 1, 4))
DEV_PROJECTION_NAME = "1/4-comma"


class Editor(Document):
    def maximize_for_dev(self) -> None:
        self.apply_state(service.from_mapping(DEV_MAX_MAPPING, DEV_MAX_DOMAIN_BASIS))
        self.set_held_vectors([DEV_MAX_HELD])
        self.set_interest_vectors([DEV_MAX_INTEREST])
        self.set_weight_slope("complexity-weight")
        self.set_diminuator_replaced(True)
        self.settings["terminology"] = "both"
        self.set_all_show(True)

    def maximize_projection_for_dev(self) -> None:
        self.apply_state(service.from_mapping(DEV_PROJECTION_MAPPING))
        self.settings["terminology"] = "both"
        self.set_all_show(True)
        self.settings["nonstandard_domain"] = False
        self.set_established_projection(DEV_PROJECTION_NAME)

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
    def pending_generator(self) -> list[int | None] | None:
        return self.pending.pending_generator

    @pending_generator.setter
    def pending_generator(self, value) -> None:
        self.pending.pending_generator = value

    @property
    def undo_count(self) -> int:
        return self.history.undo_count

    @property
    def can_undo(self) -> bool:
        return self.history.can_undo

    @property
    def can_redo(self) -> bool:
        return self.history.can_redo

    def layout(self, previous_ids=None, preview_remove=None):
        return editor_layout.build(self, previous_ids, preview_remove)
