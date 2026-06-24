from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from nicegui import helpers, ui

from rtt.app import settings as show_settings
from rtt.app.building import PageBuilder
from rtt.app.editing import EditController
from rtt.app.editor import Editor
from rtt.app.gestures import GestureController
from rtt.app.page_assets import (
    _BUSY_JS,
    _CHAPTER_KEY,
    _DARK_FRAME,
    _DARK_KEY,
    _LOAD_FAILED,
    _OPTION_HOVER_DELEGATION,
    _STORAGE_SECRET,
    _STORE_KEY,
    _TOOLTIP_DISMISS_JS,
    _decode_state,
    _doc_store,
)
from rtt.app.reconciler import _Reconciler
from rtt.app.rendering import Renderer

_log = logging.getLogger(__name__)

# NiceGUI's User test simulation hands the test no reference to the _Page object (only its ui
# elements), so tests that must reach the live page (e.g. the renderer's _on_viewport) have no other
# way to it; appended only under the simulation.
_SIMULATED_PAGES: list = []


class _Page:
    def __init__(self, state: str | None = None) -> None:
        loaded_from_url = self._load_document(state)
        self.gestures = GestureController(self.editor, self)
        self.rec = _Reconciler(self.editor, self.gestures)
        self.renderer = Renderer(self.editor, self.rec, self.gestures, self)
        self.edits = EditController(self.editor, self.rec, self.gestures, self)
        self.builder = PageBuilder(self)
        self.builder._setup_page_head()
        self._init_page_client(loaded_from_url)
        self.edits._build_edit_specs()
        self.edits._build_vector_list_specs()
        self._wire_reconciler()
        self.builder._build_layout()
        self.renderer.render()
        self.apply_chapter()
        if self.load_failed:
            ui.notify(
                _LOAD_FAILED, type="warning", position="top", multi_line=True, close_button=True
            )

    def _load_document(self, state: str | None) -> bool:
        self.dark_mode = bool(_doc_store().get(_DARK_KEY, False))

        self.apply_theme()

        self.chapter = self._clamp_chapter(
            _doc_store().get(_CHAPTER_KEY, show_settings.CHAPTER_DEFAULT)
        )

        self.editor = Editor()
        self.load_failed = False
        loaded_from_url = False
        if state:
            try:
                self.editor.load(_decode_state(state))
                loaded_from_url = True
            except Exception:
                _log.exception("shared URL state failed to load; falling back: %.200r", state)
        if not loaded_from_url:
            stored = _doc_store().get(_STORE_KEY)
            if stored:
                try:
                    self.editor.load(stored)
                except Exception:
                    _log.exception("stored document failed to load; using defaults: %.200r", stored)
                    self.load_failed = True
        self.building = False
        self.last_lay = None
        self.refs: dict = {}
        return loaded_from_url

    def _init_page_client(self, loaded_from_url: bool) -> None:
        # NiceGUI: capture this page's Client while the slot context is valid. render() can run from an
        # off-loop background task (_commit_render) where ui.run_javascript — which finds its client via
        # the current slot — would raise; client.run_javascript on the captured client needs no slot.
        self.page_client = ui.context.client
        self.page_client.on_disconnect(self._on_disconnect)
        if helpers.is_user_simulation():
            _SIMULATED_PAGES.append(self)
        ui.on("rtt_viewport", self.renderer._on_viewport, throttle=0.05)
        ui.run_javascript(_OPTION_HOVER_DELEGATION)
        ui.run_javascript(_TOOLTIP_DISMISS_JS)
        ui.run_javascript(_BUSY_JS)
        if loaded_from_url:
            ui.run_javascript("window.history.replaceState({}, '', window.location.pathname)")

    def _wire_reconciler(self) -> None:
        sources = (self.edits, self.edits.vectors, self.edits.tuning, self.gestures)
        self.rec._cb = SimpleNamespace(
            **{
                name: method
                for s in sources
                for name in dir(s)
                if getattr((method := getattr(s, name)), "_rtt_cb", False)
            }
        )

    def _dark_icon(self):
        return "light_mode" if self.dark_mode else "dark_mode"

    def apply_theme(self):
        body = ui.query("body")
        body.classes(add="rtt-dark") if self.dark_mode else body.classes(remove="rtt-dark")
        body.style(f"background:{_DARK_FRAME if self.dark_mode else '#fff'}")

    def on_dark_toggle(self):
        self.dark_mode = not self.dark_mode
        _doc_store()[_DARK_KEY] = self.dark_mode
        self.apply_theme()
        self.dark_btn.props(f"icon={self._dark_icon()}")

    def _clamp_chapter(self, v) -> int:
        try:
            v = int(v)
        except (TypeError, ValueError):
            return show_settings.CHAPTER_DEFAULT
        return min(show_settings.CHAPTER_STAR, max(show_settings.CHAPTER_MIN, v))

    def _chapter_reading(self, ch: int) -> str:
        label = "★" if ch >= show_settings.CHAPTER_STAR else str(ch)
        return f"{label}: {show_settings.CHAPTER_TITLES[ch]}"

    def apply_chapter(self):
        ch = self.chapter
        self.chapter_reading.set_text(self._chapter_reading(ch))
        self.chapter_reading.classes(add="rtt-chapter-reading-narrow") if len(
            show_settings.CHAPTER_TITLES[ch]
        ) >= 25 else self.chapter_reading.classes(remove="rtt-chapter-reading-narrow")

        def _gate(el, cls, hidden):
            el.classes(add=cls) if hidden else el.classes(remove=cls)

        for key, parts in self.tile_parts.items():
            for part in parts:
                _gate(part, "rtt-chap-invisible", show_settings.reveal_chapter(key) > ch)
        for key, row in self.show_rows.items():
            _gate(row, "rtt-chap-hidden", show_settings.reveal_chapter(key) > ch)
        if "audio_bank" in self.refs:
            _gate(self.refs["audio_bank"], "rtt-chap-invisible", ch < show_settings.CHAPTER_MIN)
        self.sync_show_availability()

    def available_keys(self):
        return [
            k for k in show_settings.IMPLEMENTED if show_settings.reveal_chapter(k) <= self.chapter
        ]

    def sync_show_availability(self):
        for key, box in self.boxes.items():
            disabled = (
                key not in show_settings.IMPLEMENTED
                or show_settings.reveal_chapter(key) > self.chapter
            )
            box.props("disable") if disabled else box.props(remove="disable")
            self.examples[key].classes(add="rtt-ex-disabled") if disabled else self.examples[
                key
            ].classes(remove="rtt-ex-disabled")
        states = [self.editor.settings[k] for k in self.available_keys()]
        was_building = self.building
        self.building = True
        try:
            self.select_all_box.value = bool(states) and all(states)
        finally:
            self.building = was_building
        self.select_all_box.classes(add="rtt-show-mixed") if (
            any(states) and not all(states)
        ) else self.select_all_box.classes(remove="rtt-show-mixed")

    def on_chapter_change(self, v):
        if self.building:
            return
        self.chapter = self._clamp_chapter(v)
        _doc_store()[_CHAPTER_KEY] = self.chapter
        self.editor.disable_hidden_settings(self.chapter)
        self.apply_chapter()
        self.renderer.render()

    def reset_everything(self):
        self.chapter = show_settings.CHAPTER_DEFAULT
        _doc_store()[_CHAPTER_KEY] = self.chapter
        self.edits.act(self.editor.reset)
        self.apply_chapter()

    def _on_disconnect(self):
        if self.edits.tuning.target_limit_commit is not None:
            self.edits.tuning.target_limit_commit.cancel()
        self.gestures.end_gesture()

    def col_tokens(self, name):
        idents = self.last_lay.identities if self.last_lay is not None else None
        return [tok for tok, _ in (idents or {}).get(name, [])]

    def token_index(self, cid, name):
        token = cid.split(":", 1)[1]
        for i, tok in enumerate(self.col_tokens(name)):
            if str(tok) == token:
                return i
        return None


@ui.page("/")
def index(state: str | None = None) -> None:
    _Page(state)


def _reload_excludes(worktrees: Path) -> str:
    excludes = [".*", ".py[cod]", ".sw.*", "~*"]
    if worktrees.is_dir():
        excludes.append(str(worktrees))
    return ", ".join(excludes)


def main() -> None:
    hosted_port = os.environ.get("PORT")
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    elif hosted_port:
        port = int(hosted_port)
    else:
        port = 8137
    # NiceGUI: a remote favicon URL makes /favicon.ico → get_favicon_response() raise ValueError, so
    # every hit on /favicon.ico 500s; a LOCAL file routes it to a working FileResponse (is_file gate).
    favicon = str(Path(__file__).parent / "assets" / "favicon.png")
    run_kwargs = {
        "title": "D&D's RTT App",
        "favicon": favicon,
        "show": False,
        "port": port,
        "storage_secret": os.environ.get("STORAGE_SECRET", _STORAGE_SECRET),
        # NiceGUI: a few paths still build synchronously (the initial page, a one-off cache-warming
        # hover preview, a drag preview); give the websocket heartbeat headroom so a brief sync build
        # can't trip the "lost connection" reload that NiceGUI's default 3 s reconnect timeout caused.
        "reconnect_timeout": 30.0,
    }
    if hosted_port:
        run_kwargs.update(host="0.0.0.0", reload=False)
    else:
        worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
        # uvicorn reload watches only *.py by default; include *.css / *.js so an assets-only edit
        # hot-reloads on its own instead of waiting for some unrelated .py file to change.
        run_kwargs.update(
            reload=True,
            uvicorn_reload_includes="*.py,*.css,*.js",
            uvicorn_reload_excludes=_reload_excludes(worktrees),
        )
    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__"}:
    main()
