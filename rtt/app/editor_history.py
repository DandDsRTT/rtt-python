from __future__ import annotations

from collections import deque

_UNDO_HISTORY_MAX = 500


class History:
    def __init__(self) -> None:
        self.undo_stack: deque = deque(maxlen=_UNDO_HISTORY_MAX)
        self.redo_stack: deque = deque(maxlen=_UNDO_HISTORY_MAX)

    @property
    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    @property
    def undo_count(self) -> int:
        return len(self.undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def record(self, snapshot) -> None:
        self.undo_stack.append(snapshot)
        self.redo_stack.clear()

    def pop_undo(self):
        return self.undo_stack.pop()

    def pop_redo(self):
        return self.redo_stack.pop()

    def push_undo(self, snapshot) -> None:
        self.undo_stack.append(snapshot)

    def push_redo(self, snapshot) -> None:
        self.redo_stack.append(snapshot)

    def clear(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def capture_stacks(self) -> tuple[list, list]:
        return list(self.undo_stack), list(self.redo_stack)

    def restore_stacks(self, undo: list, redo: list) -> None:
        self.undo_stack.clear()
        self.undo_stack.extend(undo)
        self.redo_stack.clear()
        self.redo_stack.extend(redo)
