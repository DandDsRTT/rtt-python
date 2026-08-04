from __future__ import annotations

from rtt.app import editor_codec as codec
from rtt.app.editor_state import initial_doc_at


class _SessionCommands:
    def open_at(self, chapter: int) -> None:
        self.restore(initial_doc_at(chapter))

    def reset(self, chapter: int) -> None:
        if not self.can_reset(chapter):
            return
        self.snapshot()
        self.open_at(chapter)

    def serialize(self) -> dict:
        return codec.serialize(self)

    def load(self, data: dict) -> bool:
        document = codec.load(data)
        if document is None:
            return False
        self.restore(document)
        self.reconcile_custom_weights()
        self.history.clear()
        return True

    def capture_for_preview(self) -> tuple:
        undo, redo = self.history.capture_stacks()
        transients = (*self.pending.capture(), self.nonprime_basis_approach)
        return (self.capture(), undo, redo, transients)

    def restore_for_preview(self, token: tuple) -> None:
        document, undo, redo, transients = token
        self.restore(document)
        self.history.restore_stacks(undo, redo)
        *pending_token, nonprime = transients
        self.pending.restore(tuple(pending_token))
        self.nonprime_basis_approach = nonprime
