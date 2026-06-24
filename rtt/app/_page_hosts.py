from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from rtt.app.editing import EditController
    from rtt.app.layout import Layout
    from rtt.app.reconciler import _Reconciler
    from rtt.app.rendering import Renderer


class GestureHost(Protocol):
    rec: _Reconciler
    edits: EditController
    renderer: Renderer
    last_lay: Layout | None

    def token_index(self, cid: str, name: str) -> int | None: ...
