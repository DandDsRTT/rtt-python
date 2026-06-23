from __future__ import annotations


class PendingEdits:
    def __init__(self) -> None:
        self.pending_comma: list[int | None] | None = None
        self.pending_interest: list[int | None] | None = None
        self.pending_held: list[int | None] | None = None
        self.pending_target: list[int | None] | None = None
        self.pending_mapping_row: list[int | None] | None = None
        self.pending_element: str | None = None
        self.superspace_generator_tuning: tuple[float, ...] | None = None
        self.nudging_generator: int | None = None

    def clear_drafts(self) -> None:
        self.pending_comma = None
        self.pending_interest = None
        self.pending_held = None
        self.pending_target = None
        self.pending_mapping_row = None
        self.pending_element = None

    def reset(self) -> None:
        self.clear_drafts()
        self.nudging_generator = None
        self.superspace_generator_tuning = None

    def capture(self) -> tuple:
        return (
            self.pending_comma,
            self.pending_interest,
            self.pending_held,
            self.pending_target,
            self.pending_element,
            self.pending_mapping_row,
            self.nudging_generator,
            self.superspace_generator_tuning,
        )

    def restore(self, token: tuple) -> None:
        (
            self.pending_comma,
            self.pending_interest,
            self.pending_held,
            self.pending_target,
            self.pending_element,
            self.pending_mapping_row,
            self.nudging_generator,
            self.superspace_generator_tuning,
        ) = token
