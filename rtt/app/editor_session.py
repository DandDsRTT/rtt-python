from __future__ import annotations

from rtt.app import editor_codec as codec
from rtt.app.editor_state import initial_doc


class _SessionCommands:
    def reset(self) -> None:
        if not self.can_reset:
            return
        self.snapshot()
        self.restore(initial_doc())

    def serialize(self) -> dict:
        return codec.serialize(self)

    def load(self, data: dict) -> None:
        doc = codec.load(data)
        if doc is None:
            return
        self.restore(doc)
        self.reconcile_custom_weights()
        self.history.clear()

    def capture_for_preview(self) -> tuple:
        undo, redo = self.history.capture_stacks()
        transients = (*self.pending.capture(), self.nonprime_basis_approach)
        return (self.capture(), undo, redo, transients)

    def restore_for_preview(self, token: tuple) -> None:
        doc, undo, redo, transients = token
        self.restore(doc)
        self.history.restore_stacks(undo, redo)
        *pending_token, nonprime = transients
        self.pending.restore(tuple(pending_token))
        self.nonprime_basis_approach = nonprime
