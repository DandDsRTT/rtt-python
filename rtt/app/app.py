from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from nicegui import helpers, ui

from rtt.app import settings as show_settings
from rtt.app.building import ChromeHandlers, PageBuilder
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
from rtt.app.page_chrome import PageChrome
from rtt.app.page_runtime import PageRuntime
from rtt.app.reconciler import _Reconciler, bind_callbacks
from rtt.app.rendering import Renderer

_log = logging.getLogger(__name__)

# NiceGUI's User test simulation hands the test no reference to the _Page object (only its ui
# elements), so tests that must reach the live page (e.g. the renderer's _on_viewport) have no other
# way to it; appended only under the simulation.
_SIMULATED_PAGES: list = []


class _Page:
    def __init__(self, state: str | None = None) -> None:
        self.runtime = PageRuntime()
        self.chrome = PageChrome()
        loaded_from_url = self._load_document(state)
        self.gestures = GestureController(self.editor, self.runtime)
        self.rec = _Reconciler(self.editor, self.gestures)
        self.renderer = Renderer(
            self.editor,
            self.rec,
            self.gestures,
            self.chrome,
            self.runtime,
            self.sync_show_availability,
        )
        self.edits = EditController(
            self.editor, self.rec, self.gestures, self.renderer, self.runtime
        )
        self.gestures.bind(self.rec, self.renderer, self.edits)
        self.builder = PageBuilder(
            self.editor,
            self.chrome,
            self.runtime,
            self.gestures,
            self.edits,
            self.renderer,
            ChromeHandlers(self.reset_everything, self.on_dark_toggle, self.on_chapter_change),
        )
        self.builder._setup_page_head()
        self._init_page_client(loaded_from_url)
        self.edits._build_edit_specs()
        self.edits._build_vector_list_specs()
        self._wire_reconciler()
        self.builder._build_layout()
        self.renderer.render()
        self.apply_chapter()
        if self.runtime.load_failed:
            ui.notify(
                _LOAD_FAILED, type="warning", position="top", multi_line=True, close_button=True
            )

    def _load_document(self, state: str | None) -> bool:
        self.runtime.dark_mode = bool(_doc_store().get(_DARK_KEY, False))
        self.apply_theme()
        self.runtime.set_chapter(_doc_store().get(_CHAPTER_KEY, show_settings.CHAPTER_DEFAULT))
        self.editor = Editor()
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
                    self.runtime.load_failed = True
        return loaded_from_url

    def _init_page_client(self, loaded_from_url: bool) -> None:
        # NiceGUI: capture this page's Client while the slot context is valid. render() can run from an
        # off-loop background task (_commit_render) where ui.run_javascript — which finds its client via
        # the current slot — would raise; client.run_javascript on the captured client needs no slot.
        self.runtime.bind_client(ui.context.client)
        self.runtime.page_client.on_disconnect(self._on_disconnect)
        if helpers.is_user_simulation():
            _SIMULATED_PAGES.append(self)
        ui.on("rtt_viewport", self.renderer._on_viewport, throttle=0.05)
        ui.run_javascript(_OPTION_HOVER_DELEGATION)
        ui.run_javascript(_TOOLTIP_DISMISS_JS)
        ui.run_javascript(_BUSY_JS)
        if loaded_from_url:
            ui.run_javascript("window.history.replaceState({}, '', window.location.pathname)")

    def _wire_reconciler(self) -> None:
        self.rec._cb = bind_callbacks(
            self.edits,
            self.edits.vectors,
            self.edits.tuning,
            self.edits.controls,
            self.gestures,
            self.gestures.combine,
            self.gestures.hover,
        )

    def apply_theme(self):
        body = ui.query("body")
        dark = self.runtime.dark_mode
        body.classes(add="rtt-dark") if dark else body.classes(remove="rtt-dark")
        body.style(f"background:{_DARK_FRAME if dark else '#fff'}")

    def on_dark_toggle(self):
        self.runtime.dark_mode = not self.runtime.dark_mode
        _doc_store()[_DARK_KEY] = self.runtime.dark_mode
        self.apply_theme()
        self.chrome.dark_button.props(f"icon={self.runtime.dark_icon()}")

    def apply_chapter(self):
        ch = self.runtime.chapter
        self.chrome.chapter_reading.set_text(self.runtime.chapter_reading())
        self.chrome.chapter_reading.classes(add="rtt-chapter-reading-narrow") if len(
            show_settings.CHAPTER_TITLES[ch]
        ) >= 25 else self.chrome.chapter_reading.classes(remove="rtt-chapter-reading-narrow")

        def _gate(el, cls, hidden):
            el.classes(add=cls) if hidden else el.classes(remove=cls)

        for key, parts in self.chrome.tile_parts.items():
            for part in parts:
                _gate(part, "rtt-chap-invisible", show_settings.reveal_chapter(key) > ch)
        for key, row in self.chrome.show_rows.items():
            _gate(row, "rtt-chap-hidden", show_settings.reveal_chapter(key) > ch)
        if "audio_bank" in self.chrome.refs:
            _gate(
                self.chrome.refs["audio_bank"],
                "rtt-chap-invisible",
                ch < show_settings.CHAPTER_MIN,
            )
        self.sync_show_availability()

    def sync_show_availability(self):
        for key, box in self.chrome.boxes.items():
            disabled = (
                key not in show_settings.IMPLEMENTED
                or show_settings.reveal_chapter(key) > self.runtime.chapter
            )
            box.props("disable") if disabled else box.props(remove="disable")
            self.chrome.examples[key].classes(
                add="rtt-ex-disabled"
            ) if disabled else self.chrome.examples[key].classes(remove="rtt-ex-disabled")
        for group_name, box in self.chrome.section_all.items():
            keys = self.runtime.available_in(show_settings.group_keys(group_name))
            states = [self.editor.settings[k] for k in keys]
            with self.runtime.building_guard():
                box.value = bool(states) and all(states)
            box.classes(add="rtt-show-mixed") if (any(states) and not all(states)) else box.classes(
                remove="rtt-show-mixed"
            )

    def on_chapter_change(self, v):
        if self.runtime.building:
            return
        self.runtime.set_chapter(v)
        _doc_store()[_CHAPTER_KEY] = self.runtime.chapter
        self.editor.disable_hidden_settings(self.runtime.chapter)
        self.apply_chapter()
        self.renderer.render()

    def reset_everything(self):
        self.runtime.set_chapter(show_settings.CHAPTER_DEFAULT)
        _doc_store()[_CHAPTER_KEY] = self.runtime.chapter
        self.edits.act(self.editor.reset)
        self.apply_chapter()

    def _on_disconnect(self):
        if self.edits.tuning.target_limit_commit is not None:
            self.edits.tuning.target_limit_commit.cancel()
        self.gestures.end_gesture()


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
