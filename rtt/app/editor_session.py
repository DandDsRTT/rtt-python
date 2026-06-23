from __future__ import annotations

from rtt.app import editor_codec as codec
from rtt.app.editor_document import Document, initial_doc


class SessionOps:
    def __init__(self, doc: Document) -> None:
        self.doc = doc
        self.history = doc.history
        self.pending = doc.pending

    def undo(self) -> None:
        self.doc.undo()

    def redo(self) -> None:
        self.doc.redo()

    def reset(self) -> None:
        if not self.doc.can_reset:
            return
        self.doc.snapshot()
        self.doc.restore(initial_doc())

    def serialize(self) -> dict:
        return codec.serialize(self.doc)

    def load(self, data: dict) -> None:
        doc = codec.load(data)
        if doc is None:
            return
        self.doc.restore(doc)
        self.doc.reconcile_custom_weights()
        self.history.clear()

    def capture_for_preview(self) -> tuple:
        undo, redo = self.history.capture_stacks()
        transients = (*self.pending.capture(), self.doc.nonprime_basis_approach)
        return (self.doc.capture(), undo, redo, transients)

    def restore_for_preview(self, token: tuple) -> None:
        doc, undo, redo, transients = token
        self.doc.restore(doc)
        self.history.restore_stacks(undo, redo)
        *pending_token, nonprime = transients
        self.pending.restore(tuple(pending_token))
        self.doc.nonprime_basis_approach = nonprime
