from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nicegui import Client
    from nicegui.element import Element

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


class RenderHost(Protocol):
    last_lay: Layout | None
    building: bool
    page_client: Client
    grid_pane: Element
    board: Element
    colhead: Element
    colhead_inner: Element
    corner: Element
    gridbody: Element
    rowband: Element
    show_frozen: Element
    show_scroll: Element
    chapter_slider: Element
    cell_parents: dict[str, Element]
    refs: dict[str, Element]
    boxes: dict[str, Element]
    tile_parts: dict[str, list[Element]]
    chapter: int
    load_failed: bool

    def sync_show_availability(self) -> None: ...


class EditHost(Protocol):
    renderer: Renderer
    building: bool
    last_lay: Layout | None
    page_client: Client

    def token_index(self, cid: str, name: str) -> int | None: ...

    def col_tokens(self, name: str) -> list: ...

    def available_keys(self) -> list[str]: ...
