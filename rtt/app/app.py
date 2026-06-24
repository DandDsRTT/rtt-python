from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import sys
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from html import escape as _escape
from pathlib import Path
from types import SimpleNamespace
from typing import ClassVar, NamedTuple

from nicegui import app, background_tasks, helpers, ui

from rtt.app import (
    ids,
    presets,
    service,
    spreadsheet,
    spreadsheet_constants,
    spreadsheet_text,
    tooltips,
)
from rtt.app import settings as show_settings
from rtt.app.building import PageBuilder
from rtt.app.editing import EditController
from rtt.app.editor import Editor
from rtt.app.gestures import GestureController
from rtt.app.marks import (
    BR_COLOR,
    PENDING_COLOR,
    ebk_svg,
)
from rtt.app.page_assets import (
    _ASSETS,
    _AUDIO_BANK,
    _AUDIO_GLYPHS,
    _AUDIO_JS,
    _BUSY_DELAY_MS,
    _BUSY_JS,
    _BUSY_SAFETY_MS,
    _CELL_BORDER,
    _CELL_BORDER_W,
    _CELL_FONT,
    _CELLUNIT_MAX_FONT,
    _CHAPTER_KEY,
    _CHROME_H,
    _CSS,
    _CSS_DARK_VARS,
    _CSS_VARS,
    _DARK_CELL,
    _DARK_FRAME,
    _DARK_KEY,
    _DARK_MARK,
    _DARK_MUTED,
    _DARK_TEXT,
    _DECIMAL_JS,
    _EBK_SQUARE,
    _EBK_SVG_KINDS,
    _FONT_FACE,
    _FRACTION_JS,
    _FREEZE_JS,
    _GENERAL_TILE_LINES,
    _GENSIGN_W,
    _GRIDVALUE_SPECS,
    _GROUP_EXIT_JS,
    _GUIDE_JS,
    _INT_WHEEL_JS,
    _INVALID_EMBEDDING,
    _INVALID_FORM,
    _INVALID_PRESCALER,
    _INVALID_PROJECTION,
    _INVALID_TEMPERAMENT,
    _INVALID_UNCHANGED,
    _INVALID_WEIGHT,
    _LOAD_FAILED,
    _MATLABEL_FONT,
    _MATLABEL_MIN_FONT,
    _MEMORY_STORE,
    _MODE_FILLS,
    _OPTION_HOVER_DELEGATION,
    _PAD,
    _PANEL_W,
    _PENDING_TEXT_COLOR,
    _PREVIEW_COLOR,
    _PREVIEW_REMOVE_COLOR,
    _PREVIEW_REMOVE_TEXT_COLOR,
    _PREVIEW_TEXT_COLOR,
    _PTEXT_DUAL_VECTOR_KIND,
    _SEAM,
    _STACKED_EXIT_JS,
    _STACKED_MAIN_FONT,
    _STATE_PARAM,
    _STORAGE_SECRET,
    _STORE_KEY,
    _SUBPICK_POPUP_W,
    _T,
    _TAB_H,
    _TAB_W,
    _TABNAV_JS,
    _TARGET_LIMIT_DEBOUNCE,
    _TILE_FONT,
    _TILE_HOST,
    _TILE_IN_CELL_LAYERS,
    _TINTS,
    _TOOLTIP_DELAY_MS,
    _TOOLTIP_DISMISS_JS,
    _TOUR_JS,
    _TOUR_STEPS,
    _TRANSPOSE_MARK,
    _UNITS_MAX_FONT,
    _WHEEL_STEPS,
    _ZOOM_JS,
    VALUE_KINDS,
    _audio_bank,
    _decode_state,
    _doc_store,
    _encode_state,
    _formchooser_options,
    _Gesture,
    _GridValueSpec,
    _GroupedSelect,
    _hover_index,
    _KindHandlers,
    _option_key,
    _projection_prompt,
    _set_offlist_prompt,
    _VecGridEdit,
    _vgroup_key,
)
from rtt.app.reconciler import _Reconciler
from rtt.app.render_html import (
    _FOLD_GLYPH,
    _TILE_CELL,
    _TILE_CELL_X,
    _TILE_CELL_Y,
    _TILE_FRAME_H,
    _TILE_FRAME_W,
    _TILE_MATH,
    _bar_chart,
    _block_panes,
    _bold_units,
    _cents_parts,
    _control_svg,
    _digit_fit_font,
    _example_html,
    _fit_font,
    _freeze_container,
    _general_part_html,
    _gentuning_parts,
    _limit_text,
    _line_style,
    _math_html,
    _mathexpr_html,
    _mode_svg,
    _option_box_svg,
    _parse_int,
    _power_parts,
    _ptext_font,
    _range_chart,
    _ratio_font,
    _ratio_parts,
    _select_props,
    _tile_fold_html,
    _tile_name_pieces,
    _underline_html,
    _units_font,
    _units_html,
    _wave_svg,
    _wheel_step,
)
from rtt.app.rendering import Renderer

_log = logging.getLogger(__name__)

# NiceGUI's User test simulation builds the real page but hands the test no reference to the _Page
# object (only its ui elements), so the virtualization tests — which must call the renderer's
# _on_viewport / inspect the materialized set on the live page — have no other way to reach it.
# Recorded only under the simulation; production never appends here. Re-imported fresh per render
# test, so it stays a singleton.
_SIMULATED_PAGES: list = []


class _Page:
    def __init__(self, state: str | None = None) -> None:
        self.gestures = GestureController(self)
        self.renderer = Renderer(self)
        self.edits = EditController(self)
        self.builder = PageBuilder(self)
        self.builder._setup_page_head()
        self._init_page_client(self._load_document(state))
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
        # Dark mode is a global VIEWING preference, kept out of the document's Show settings: it
        # persists under its own store key, so "select all / none" and Reset — which act only on
        # editor.settings — never touch it. apply_theme drives the CSS overlay (assets/rtt-dark.css)
        # by toggling the `rtt-dark` class on <body>, and paints the margin frame inline (its colour
        # beats Quasar's body background the same way the static "#fff" did before).
        self.dark_mode = bool(_doc_store().get(_DARK_KEY, False))

        self.apply_theme()

        self.chapter = self._clamp_chapter(
            _doc_store().get(_CHAPTER_KEY, show_settings.CHAPTER_DEFAULT)
        )

        # The Editor owns the whole document — temperament, view selections, the Show
        # settings (editor.settings) and the folded rows/columns/tiles (editor.collapsed) —
        # and the undo/redo history over all of it. We persist that document per browser
        # (app.storage.user) so a refresh restores exactly where the user left off; a
        # corrupt/old blob is ignored, falling back to the as-shipped defaults.
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
        self.rec = _Reconciler(self.editor, self.gestures)
        self.building = False
        self.last_lay = None
        self.refs: dict = {}
        return loaded_from_url

    def _init_page_client(self, loaded_from_url: bool) -> None:
        # capture this page's Client now, while the slot context is valid. render() can run from an
        # off-loop background task (_commit_render), where the slot stack is empty and ui.run_javascript
        # — which finds its client via the current slot — would raise. Calling client.run_javascript on
        # the captured client needs no slot, so the busy-scrim push works from the background task too.
        self.page_client = ui.context.client
        self.page_client.on_disconnect(self._on_disconnect)
        if helpers.is_user_simulation():
            _SIMULATED_PAGES.append(self)
        # the client reports its visible scroll rectangle here (freeze.js emits it on scroll/resize/
        # boot); the renderer re-materializes the virtualized body pane against the cached layout.
        ui.on("rtt_viewport", self.renderer._on_viewport, throttle=0.05)
        ui.run_javascript(_OPTION_HOVER_DELEGATION)
        ui.run_javascript(_TOOLTIP_DISMISS_JS)
        ui.run_javascript(_BUSY_JS)
        if loaded_from_url:
            ui.run_javascript("window.history.replaceState({}, '', window.location.pathname)")

    def _wire_reconciler(self) -> None:
        # DERIVE the reconciler's callback namespace from the @cb_method marks on the edit/gesture
        # controllers — there is no hand-maintained name list to drift from the actual methods.
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
        self._sync_show_availability()

    def _available_keys(self):
        return [
            k for k in show_settings.IMPLEMENTED if show_settings.reveal_chapter(k) <= self.chapter
        ]

    def _sync_show_availability(self):
        for key, box in self.boxes.items():
            disabled = (
                key not in show_settings.IMPLEMENTED
                or show_settings.reveal_chapter(key) > self.chapter
            )
            box.props("disable") if disabled else box.props(remove="disable")
            # the example sample greys WITH the checkbox — the single disabled styling for every
            # reason (the box's own label/glyph grey via Quasar's .disabled; this matches the sample)
            self.examples[key].classes(add="rtt-ex-disabled") if disabled else self.examples[
                key
            ].classes(remove="rtt-ex-disabled")
        states = [self.editor.settings[k] for k in self._available_keys()]
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

    def _token_index(self, cid, name):
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
    # Serve the DandDsRTT org icon as a LOCAL file (assets/favicon.png — the org's GitHub avatar,
    # vendored). A remote URL would let NiceGUI emit it into the page <link rel=icon> (the tab still
    # works) but registers /favicon.ico → get_favicon_response(), which raises ValueError on any
    # remote URL — every browser/bot/health-check hit on /favicon.ico then 500s. A local file routes
    # /favicon.ico to a working FileResponse (NiceGUI gates on helpers.is_file), so the icon serves
    # and the route stops erroring.
    favicon = str(Path(__file__).parent / "assets" / "favicon.png")
    run_kwargs = {
        "title": "D&D's RTT App",
        "favicon": favicon,
        "show": False,
        "port": port,
        "storage_secret": os.environ.get("STORAGE_SECRET", _STORAGE_SECRET),
        # The heavy retuning commits now render off the event loop (see _commit_render), so the
        # websocket heartbeat keeps flowing through them. A few paths still build synchronously — the
        # initial page (no socket yet), a structural hover PREVIEW the first time a high-limit state is
        # seen (it warms the cache, so it's a one-off), a drag preview. Give the heartbeat generous
        # headroom so one of those brief sync builds — slower still under parallel CPU load — can't trip
        # the "lost connection" reload NiceGUI's default 3 s timeout caused. (Derived pings: interval
        # max(0.8·t, 4) = 24 s, timeout max(0.4·t, 2) = 12 s.)
        "reconnect_timeout": 30.0,
    }
    if hosted_port:
        run_kwargs.update(host="0.0.0.0", reload=False)
    else:
        worktrees = Path(__file__).resolve().parents[2] / ".claude" / "worktrees"
        # watch the assets too, not just *.py (uvicorn's default), so an audio.js / rtt.css edit
        # hot-reloads on its own — otherwise a JS/CSS-only change leaves the running instance stale
        # until some unrelated .py file happens to change (a JS-only audio fix silently failed to land).
        run_kwargs.update(
            reload=True,
            uvicorn_reload_includes="*.py,*.css,*.js",
            uvicorn_reload_excludes=_reload_excludes(worktrees),
        )
    ui.run(**run_kwargs)


if __name__ in {"__main__", "__mp_main__"}:
    main()
