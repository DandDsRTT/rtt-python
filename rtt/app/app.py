from __future__ import annotations

import asyncio
import base64
import json
import logging
import math
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
from rtt.app.editor import Editor
from rtt.app.marks import (
    BR_COLOR,
    PENDING_COLOR,
    ebk_svg,
)
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

_log = logging.getLogger(__name__)

from rtt.app.page_assets import (
    _KindHandlers,
    _ASSETS,
    _PAD,
    _T,
    _PANEL_W,
    _TAB_W,
    _TAB_H,
    _CHROME_H,
    _TOOLTIP_DELAY_MS,
    _STORE_KEY,
    _STATE_PARAM,
    _DARK_KEY,
    _CHAPTER_KEY,
    _STORAGE_SECRET,
    _MEMORY_STORE,
    _doc_store,
    _encode_state,
    _decode_state,
    _INVALID_TEMPERAMENT,
    _INVALID_FORM,
    _SUBPICK_POPUP_W,
    _INVALID_PROJECTION,
    _INVALID_EMBEDDING,
    _INVALID_PRESCALER,
    _INVALID_WEIGHT,
    _INVALID_UNCHANGED,
    _LOAD_FAILED,
    _SEAM,
    _PENDING_TEXT_COLOR,
    _PREVIEW_COLOR,
    _PREVIEW_TEXT_COLOR,
    _PREVIEW_REMOVE_COLOR,
    _PREVIEW_REMOVE_TEXT_COLOR,
    _CELL_BORDER_W,
    _CELL_BORDER,
    _CELL_FONT,
    _GENSIGN_W,
    _STACKED_MAIN_FONT,
    _TINTS,
    _DARK_FRAME,
    _DARK_CELL,
    _DARK_MARK,
    _DARK_TEXT,
    _DARK_MUTED,
    _WHEEL_STEPS,
    _INT_WHEEL_JS,
    _TARGET_LIMIT_DEBOUNCE,
    _BUSY_DELAY_MS,
    _BUSY_SAFETY_MS,
    _GridValueSpec,
    _VecGridEdit,
    _GRIDVALUE_SPECS,
    _vgroup_key,
    _MODE_FILLS,
    _AUDIO_GLYPHS,
    _AUDIO_JS,
    _FREEZE_JS,
    _FRACTION_JS,
    _DECIMAL_JS,
    _TABNAV_JS,
    _TOUR_JS,
    _TOUR_STEPS,
    _STACKED_EXIT_JS,
    _GROUP_EXIT_JS,
    _CSS_VARS,
    _FONT_FACE,
    _CSS_DARK_VARS,
    _CSS,
    _UNITS_MAX_FONT,
    _CELLUNIT_MAX_FONT,
    _MATLABEL_FONT,
    _MATLABEL_MIN_FONT,
    _EBK_SVG_KINDS,
    _EBK_SQUARE,
    _TRANSPOSE_MARK,
    _PTEXT_DUAL_VECTOR_KIND,
    _GENERAL_TILE_LINES,
    _TILE_IN_CELL_LAYERS,
    _TILE_HOST,
    _TILE_FONT,
    _AUDIO_BANK,
    _audio_bank,
    _OPTION_HOVER_DELEGATION,
    _TOOLTIP_DISMISS_JS,
    VALUE_KINDS,
    _ZOOM_JS,
    _GUIDE_JS,
    _BUSY_JS,
    _GroupedSelect,
    _set_offlist_prompt,
    _projection_prompt,
    _formchooser_options,
    _hover_index,
    _option_key,
    _Gesture,
)

from rtt.app.reconciler import _Reconciler


class _Page:
    def __init__(self, state: str | None = None) -> None:
        self._setup_page_head()
        self._init_page_client(self._load_document(state))
        self._build_edit_specs()
        self._build_vector_list_specs()
        self._wire_reconciler()
        self._init_render_state()
        self._build_layout()
        self.render()
        self.apply_chapter()
        if self.load_failed[0]:
            ui.notify(
                _LOAD_FAILED, type="warning", position="top", multi_line=True, close_button=True
            )

    def _setup_page_head(self) -> None:
        ui.add_css(_CSS)
        ui.tooltip.default_props(f"delay={_TOOLTIP_DELAY_MS}")
        ui.add_body_html(
            f"<script>{_AUDIO_JS}\nwindow.rttAudio.glyphs = {json.dumps(_AUDIO_GLYPHS)};</script>"
        )
        ui.add_body_html(f"<script>{_FREEZE_JS}</script>")
        ui.add_body_html(f"<script>{_FRACTION_JS}</script>")
        ui.add_body_html(f"<script>{_DECIMAL_JS}</script>")
        ui.add_body_html(f"<script>{_TABNAV_JS}</script>")
        ui.add_body_html(f"<script>{_ZOOM_JS}</script>")
        ui.add_body_html(f"<script>{_GUIDE_JS}</script>")
        ui.add_body_html(
            f"<script>window.rttTour={{steps:{json.dumps(_TOUR_STEPS)},autostart:true}};\n"
            f"{_TOUR_JS}</script>"
        )
        # trim NiceGUI's default 16px content padding to a slim margin around the whole app
        ui.query(".nicegui-content").style("padding:6px")

        # the busy scrim (fixed, viewport-covering, hidden until revealed): shown while a heavy
        # state change re-solves the tuning off the event loop, so the user sees "Computing…"
        # rather than a frozen grid, and the clicks they'd otherwise pile up are swallowed. Built
        # once, here, so it outlives every grid rebuild (see _request_render / _commit_render).
        with ui.element("div").classes("rtt-busy"):
            with ui.element("div").classes("rtt-busy-card"):
                ui.element("div").classes("rtt-busy-spin")
                ui.label("Computing…")

    def _load_document(self, state: str | None) -> bool:
        # Dark mode is a global VIEWING preference, kept out of the document's Show settings: it
        # persists under its own store key, so "select all / none" and Reset — which act only on
        # editor.settings — never touch it. apply_theme drives the CSS overlay (assets/rtt-dark.css)
        # by toggling the `rtt-dark` class on <body>, and paints the margin frame inline (its colour
        # beats Quasar's body background the same way the static "#fff" did before).
        self.dark_mode = [bool(_doc_store().get(_DARK_KEY, False))]

        self.apply_theme()

        self.chapter = [
            self._clamp_chapter(_doc_store().get(_CHAPTER_KEY, show_settings.CHAPTER_DEFAULT))
        ]

        # The Editor owns the whole document — temperament, view selections, the Show
        # settings (editor.settings) and the folded rows/columns/tiles (editor.collapsed) —
        # and the undo/redo history over all of it. We persist that document per browser
        # (app.storage.user) so a refresh restores exactly where the user left off; a
        # corrupt/old blob is ignored, falling back to the as-shipped defaults.
        self.editor = Editor()
        self.load_failed = [False]
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
                    self.load_failed[0] = True
        self.rec = _Reconciler(self.editor)
        self.building = [False]
        self.last_lay = [None]
        self.refs: dict = {}
        self.target_limit_commit = [None]
        return loaded_from_url

    def _init_page_client(self, loaded_from_url: bool) -> None:
        # capture this page's Client now, while the slot context is valid. render() can run from an
        # off-loop background task (_commit_render), where the slot stack is empty and ui.run_javascript
        # — which finds its client via the current slot — would raise. Calling client.run_javascript on
        # the captured client needs no slot, so the busy-scrim push works from the background task too.
        self.page_client = ui.context.client
        self.page_client.on_disconnect(self._on_disconnect)
        ui.run_javascript(_OPTION_HOVER_DELEGATION)
        ui.run_javascript(_TOOLTIP_DISMISS_JS)
        ui.run_javascript(_BUSY_JS)
        if loaded_from_url:
            ui.run_javascript("window.history.replaceState({}, '', window.location.pathname)")

        self.gesture_rendering = [False]
        # a comma−/mapping− hover's transient rank-removal preview — None | ("comma", idx) | ("row", idx).
        # Pure view state (not a gesture, not document state): render() threads it into the build so the
        # builder reflows the dual axis (the born generator/comma ghosts green, the leaver reds, the
        # survivors amber). Set on mouseenter, cleared on mouseleave and on any committing act().
        self.rank_remove = [None]
        self.rank_rendering = [False]

    def _build_edit_specs(self) -> None:
        self._MAPPING_EDIT = _VecGridEdit(
            group="gens",
            count=lambda: len(self.editor.state.mapping),
            cell_id=ids.mapping_cell,
            pending=lambda: self.editor.pending_mapping_row,
            set_pending=self.editor.set_pending_mapping_row,
            commit=self.editor.edit_mapping,
            validate=service.is_proper_temperament,
            guard=lambda: self.editor.settings["temperament_tiles"],
        )
        self._COMMA_EDIT = _VecGridEdit(
            group="commas",
            count=lambda: len(self.editor.state.comma_basis),
            cell_id=ids.comma_cell,
            pending=lambda: self.editor.pending_comma,
            set_pending=self.editor.set_pending_comma,
            commit=self.editor.edit_comma_basis,
            validate=lambda basis: service.is_proper_temperament(
                service.from_comma_basis(basis).mapping
            ),
        )

    def _build_vector_list_specs(self) -> None:
        self._INTEREST_EDIT = _VecGridEdit(
            group="interest",
            count=lambda: len(self.editor.interest_vectors),
            cell_id=ids.interest_cell,
            pending=lambda: self.editor.pending_interest,
            set_pending=self.editor.set_pending_interest,
            commit=self.editor.set_interest_vectors,
            draft_arms=True,
        )
        self._HELD_EDIT = _VecGridEdit(
            group="held",
            count=lambda: len(self.editor.held_vectors),
            cell_id=ids.held_cell,
            pending=lambda: self.editor.pending_held,
            set_pending=self.editor.set_pending_held,
            commit=self.editor.set_held_vectors,
            draft_arms=True,
        )
        self._TARGET_EDIT = _VecGridEdit(
            group="targets",
            count=lambda: len(
                self.editor.target_override
                or service.target_interval_set(
                    self.editor.target_spec, self.editor.state.domain_basis
                )
            ),
            cell_id=ids.target_cell,
            pending=lambda: self.editor.pending_target,
            set_pending=self.editor.set_pending_target,
            commit=self.editor.set_target_override_vectors,
            draft_arms=True,
        )

        self.draft_focus = {
            "comma": ("comma:pending", "commacell"),
            "target": ("target:pending", "targetcell"),
            "held": ("held:pending", "heldcell"),
            "interest": ("interest:pending", "interestcell"),
            "element": ("prime:pending", None),
            "mapping": (None, "mapping"),
        }

        self.drag_src = [None]
        self.reorder_dst = [None]

    _CB_METHODS: ClassVar[tuple[str, ...]] = (
        "act",
        "add_interval",
        "combine_begin",
        "combine_preview",
        "combine_commit",
        "combine_end",
        "control_hover",
        "control_unhover",
        "rank_remove_hover",
        "rank_remove_unhover",
        "gentuning_hover",
        "gentuning_unhover",
        "on_cell_blur",
        "on_cell_focus",
        "on_popup",
        "on_comma_change",
        "on_unchanged_change",
        "on_drag_start",
        "on_drag_enter",
        "on_drag_end",
        "on_drop",
        "on_control_select",
        "on_form_choose",
        "on_gentuning_change",
        "on_gentuning_wheel",
        "on_value_wheel",
        "on_target_limit_wheel",
        "on_target_limit_preview",
        "on_chooser_hover",
        "on_held_change",
        "on_interest_change",
        "on_mapping_change",
        "on_form_change",
        "on_power_change",
        "on_prescaler_change",
        "on_weight_change",
        "on_preset",
        "on_subpick",
        "on_ptext_edit",
        "on_ratio_change",
        "transform_interval",
        "on_element_change",
        "on_element_preview",
        "on_range_mode",
        "on_target_cells_change",
        "on_target_change",
        "on_toggle",
        "on_toggle_all",
    )

    def _wire_reconciler(self) -> None:
        self.rec._cb = SimpleNamespace(**{n: getattr(self, n) for n in self._CB_METHODS})

    def _init_render_state(self) -> None:
        # ---- off-loop commit render + busy scrim ----------------------------------------------------
        # A state change that retunes (raising the prime limit, adding/editing a comma or held interval,
        # picking a scheme, undo/redo across such an edit…) re-solves the tuning. At a high prime limit
        # that solve takes a few SECONDS, and run inline on the event loop it would block NiceGUI's
        # websocket heartbeat — the client misses its ping, drops the socket ("lost connection"), and the
        # page looks crashed until a hard reload. So the retuning paths render through _request_render
        # instead of calling render() directly: the heavy solve runs in a worker thread (numpy/scipy
        # release the GIL, so the loop keeps answering pings), warming the tuning memo; render() then
        # rebuilds on the loop from that warm cache (fast).
        #
        # The "Computing…" busy scrim is driven CLIENT-side (see _BUSY_JS), not from here: the moment a
        # committing control is used the browser arms the scrim and reveals it if the work outlasts a
        # short delay — so it appears even while the server's loop is busy (a *synchronous* re-render,
        # e.g. a Show toggle, can't send a "show scrim" message until it has already finished) and while
        # the browser is busy patching a big grid. render() ends by calling rttBusy.done() to clear it.
        self.render_inflight = [False]
        self.render_again = [False]
        self.render_after = [None]

        self.drawer_open = [False]

    def _build_layout(self) -> None:
        with ui.element("div").classes("rtt-shell"):
            self.panelgroup = ui.element("div").classes("rtt-panelgroup")
            with self.panelgroup:
                with ui.element("div").classes("rtt-chrome"):
                    self._pane_chrome()
                self._build_drawer()
            self._build_grid_pane()

    def _dark_icon(self):
        return "light_mode" if self.dark_mode[0] else "dark_mode"

    def apply_theme(self):
        body = ui.query("body")
        body.classes(add="rtt-dark") if self.dark_mode[0] else body.classes(remove="rtt-dark")
        body.style(f"background:{_DARK_FRAME if self.dark_mode[0] else '#fff'}")

    def on_dark_toggle(self):
        self.dark_mode[0] = not self.dark_mode[0]
        _doc_store()[_DARK_KEY] = self.dark_mode[0]
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
        ch = self.chapter[0]
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
            k
            for k in show_settings.IMPLEMENTED
            if show_settings.reveal_chapter(k) <= self.chapter[0]
        ]

    def _sync_show_availability(self):
        for key, box in self.boxes.items():
            disabled = (
                key not in show_settings.IMPLEMENTED
                or show_settings.reveal_chapter(key) > self.chapter[0]
            )
            box.props("disable") if disabled else box.props(remove="disable")
            # the example sample greys WITH the checkbox — the single disabled styling for every
            # reason (the box's own label/glyph grey via Quasar's .disabled; this matches the sample)
            self.examples[key].classes(add="rtt-ex-disabled") if disabled else self.examples[
                key
            ].classes(remove="rtt-ex-disabled")
        states = [self.editor.settings[k] for k in self._available_keys()]
        was_building = self.building[0]
        self.building[0] = True
        try:
            self.select_all_box.value = bool(states) and all(states)
        finally:
            self.building[0] = was_building
        self.select_all_box.classes(add="rtt-show-mixed") if (
            any(states) and not all(states)
        ) else self.select_all_box.classes(remove="rtt-show-mixed")

    def on_chapter_change(self, v):
        if self.building[0]:
            return
        self.chapter[0] = self._clamp_chapter(v)
        _doc_store()[_CHAPTER_KEY] = self.chapter[0]
        self.editor.disable_hidden_settings(self.chapter[0])
        self.apply_chapter()
        self.render()

    def reset_everything(self):
        self.chapter[0] = show_settings.CHAPTER_DEFAULT
        _doc_store()[_CHAPTER_KEY] = self.chapter[0]
        self.act(self.editor.reset)
        self.apply_chapter()

    def _on_disconnect(self):
        if self.target_limit_commit[0] is not None:
            self.target_limit_commit[0].cancel()
        self.end_gesture()

    def col_tokens(self, name):
        ids = self.last_lay[0].identities if self.last_lay[0] is not None else None
        return [tok for tok, _ in (ids or {}).get(name, [])]

    def _token_index(self, cid, name):
        token = cid.split(":", 1)[1]
        for i, tok in enumerate(self.col_tokens(name)):
            if str(tok) == token:
                return i
        return None

    def gesture_render(self):
        self.gesture_rendering[0] = True
        try:
            self.render()
        finally:
            self.gesture_rendering[0] = False

    def end_gesture(self):
        g, self.rec.gesture = self.rec.gesture, None
        if g is not None and g.token is not None:
            self.editor.restore_for_preview(g.token)
        return g

    def end_chooser_gesture(self):
        if self.rec.gesture is not None and self.rec.gesture.kind == "chooser":
            self.end_gesture()

    def compute_rings(self, lay):
        if not self.editor.settings["preview_highlighting"]:
            return frozenset(), frozenset()
        static_red = frozenset(cb.id for cb in lay.cells if cb.preview_remove)
        static_amber = frozenset(cb.id for cb in lay.cells if cb.preview_change)
        amber, red = self._gesture_rings(lay)
        pending = frozenset(cb.id for cb in lay.cells if cb.pending)
        return (amber | static_amber) - pending, (red | static_red) - pending

    def _gesture_rings(self, lay):
        g = self.rec.gesture
        if g is None:
            return frozenset(), frozenset()
        if g.apply is not None:
            base = g.baseline if g.baseline is not None else lay
            token = self.editor.capture_for_preview()
            try:
                g.apply()
                hyp = self.editor.layout(prev_ids=base.identities)
                amber = spreadsheet_text.changed_cell_ids(base, hyp)
                red = spreadsheet_text.removed_cell_ids(lay, hyp)
            finally:
                self.editor.restore_for_preview(token)
            return amber - {g.source}, red
        if g.baseline is not None:
            amber = spreadsheet_text.changed_cell_ids(g.baseline, lay) - {g.source}
            if g.target_pred is not None:
                amber |= frozenset(cb.id for cb in lay.cells if g.target_pred(cb))
            return amber, frozenset()
        return frozenset(), frozenset()

    def paint_cell(self, eid, amber, red):
        # idempotently set one cell's ring classes from the computed sets. Self-guarded on the cached
        # ring state so an unchanged cell is skipped entirely (the common case — rings move only around
        # the gesture); both render()'s sweep and paint_rings()'s hover sweep go through here, so the
        # cache stays consistent whichever path painted last. (NiceGUI's classes() is itself change-
        # detected, so even an un-guarded no-op sends nothing over the socket — this skips the Python.)
        el = self.rec.els.get(eid)
        if el is None:
            return  # a ring id with no DOM element (nothing on screen to mark) — skip
        rsig = (eid in amber, eid in red)
        if self.rec.ring_sig.get(eid) == rsig:
            return
        el.classes(
            add="rtt-preview-change" if eid in amber else "",
            remove="" if eid in amber else "rtt-preview-change",
        )
        el.classes(
            add="rtt-preview-remove" if eid in red else "",
            remove="" if eid in red else "rtt-preview-remove",
        )
        self.rec.ring_sig[eid] = rsig

    def paint_rings(self):
        lay = self.last_lay[0]
        if lay is None:
            return
        amber, red = self.compute_rings(lay)
        for cb in lay.cells:
            self.paint_cell(cb.id, amber, red)

    def take_over_gesture(self):
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self.gesture_render()

    def _edit_candidate(self, apply):
        g = self.rec.gesture
        if g is None or g.kind != "edit":
            return
        g.apply = apply
        self.paint_rings()

    def _rebase_edit_gesture(self):
        g = self.rec.gesture
        if g is not None and g.kind == "edit":
            g.baseline = self.last_lay[0]
            self.paint_rings()

    def _finish_edit(self, preview, outcome) -> None:
        # outcome is ("incomplete",) | ("invalid", message) | ("ok", commit). A preview arms the
        # candidate (the commit itself when ok, else nothing); a real edit commits / notifies / no-ops.
        if preview:
            self._edit_candidate(outcome[1] if outcome[0] == "ok" else None)
            return
        if outcome[0] == "invalid":
            ui.notify(outcome[1], type="negative", position="top")
            self.render()
        elif outcome[0] == "ok":
            outcome[1]()
            self._request_render()

    def _edit_pending_vector(self, spec, preview, toks, d) -> None:
        cell_id = spec.cell_id
        pt = spreadsheet_text.pending_token(toks)
        if any(cell_id(pt, p) not in self.rec.inputs for p in range(d)):
            if preview:
                self._edit_candidate(None)
            return
        values = [_parse_int(self.rec.inputs[cell_id(pt, p)].value) for p in range(d)]
        if preview:
            self._edit_candidate(
                (lambda v=values: spec.set_pending(v)) if spec.draft_arms else None
            )
            return
        spec.set_pending(values)
        if spec.pending() is None:
            # the change is applied (it retunes) — render OFF the loop, then rebase the gesture
            # on the fresh layout so its rings go away NOW (no blur fires)
            self._request_render(after=self._rebase_edit_gesture)

    def _edit_vector_grid(self, spec, preview=False):
        if self.building[0] or (spec.guard is not None and not spec.guard()):
            return
        d = self.editor.state.d
        toks = self.col_tokens(spec.group)
        if spec.pending() is not None:
            self._edit_pending_vector(spec, preview, toks, d)
            return
        cell_id = spec.cell_id
        count = spec.count()
        if len(toks) != count or any(
            cell_id(toks[i], p) not in self.rec.inputs for i in range(count) for p in range(d)
        ):
            self._finish_edit(preview, ("incomplete",))
            return
        vectors = [
            [_parse_int(self.rec.inputs[cell_id(toks[i], p)].value) for p in range(d)]
            for i in range(count)
        ]
        if any(v is None for vec in vectors for v in vec):
            self._finish_edit(preview, ("incomplete",))
            return
        if spec.validate is not None and not spec.validate(vectors):
            self._finish_edit(preview, ("invalid", _INVALID_TEMPERAMENT))
            return
        self._finish_edit(preview, ("ok", lambda: spec.commit(vectors)))

    def on_mapping_change(self, preview=False):
        self._edit_vector_grid(self._MAPPING_EDIT, preview)

    def on_form_change(self, preview=False):
        if self.building[0] or not self.editor.settings.get("form_tiles"):
            return
        r = len(self.editor.state.mapping)
        rc = len(service.canonical_mapping(self.editor.state.mapping))
        if any(ids.form_cell(i, j) not in self.rec.inputs for i in range(r) for j in range(rc)):
            if preview:
                self._edit_candidate(None)
            return
        rows = [
            [_parse_int(self.rec.inputs[ids.form_cell(i, j)].value) for j in range(rc)]
            for i in range(r)
        ]
        if any(v is None for row in rows for v in row):
            if preview:
                self._edit_candidate(None)
            return
        if service.mapping_from_form_matrix(self.editor.state.mapping, rows) is None:
            if preview:
                self._edit_candidate(None)
                return
            ui.notify(_INVALID_FORM, type="negative", position="top")
            self.render()
            return
        if preview:
            self._edit_candidate(lambda: self.editor.edit_form_matrix(rows))
            return
        self.editor.edit_form_matrix(rows)
        self._request_render()  # a form change re-stores the mapping (a new generating set) — render off the loop

    def on_comma_change(self, preview=False):
        self._edit_vector_grid(self._COMMA_EDIT, preview)

    def on_unchanged_change(self, preview=False):
        if self.building[0]:
            return
        d, r = self.editor.state.d, self.editor.state.r
        if any(ids.unchanged_cell(j, p) not in self.rec.inputs for j in range(r) for p in range(d)):
            self._finish_edit(preview, ("incomplete",))
            return
        vectors = [
            [_parse_int(self.rec.inputs[ids.unchanged_cell(j, p)].value) for p in range(d)]
            for j in range(r)
        ]
        if any(v is None for vec in vectors for v in vec):
            self._finish_edit(preview, ("invalid", _INVALID_UNCHANGED))
            return
        try:
            ratios = service.comma_ratios(
                tuple(tuple(v) for v in vectors), self.editor.state.domain_basis
            )
        except (ValueError, ZeroDivisionError, ArithmeticError):
            self._finish_edit(preview, ("invalid", _INVALID_UNCHANGED))
            return
        self._finish_edit(preview, ("ok", lambda: self.editor.set_unchanged_basis(ratios)))

    def on_interest_change(self, preview=False):
        self._edit_vector_grid(self._INTEREST_EDIT, preview)

    def on_held_change(self, preview=False):
        self._edit_vector_grid(self._HELD_EDIT, preview)

    def on_target_cells_change(self, preview=False):
        self._edit_vector_grid(self._TARGET_EDIT, preview)

    def on_ratio_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        group, tok = cid.split(":")
        raw = self.rec.cell_value(cid)
        if raw in ("", "?/?"):
            self.render()
            return
        try:
            vector = service.interval_vector(
                raw, self.editor.state.d, self.editor.state.domain_basis
            )
        except ValueError as exc:
            ui.notify(str(exc), type="negative", position="top")
            self.render()
            return

        self._apply_ratio_edit(group, tok, vector)
        # a quantities-row ratio edit routes into a retuning setter (comma/held/target/unchanged) —
        # render off the loop. (An interest edit doesn't retune, but the warm build is cheap.)
        self._request_render()

    def _replace_interval_vector(self, group, tok, vector, current, setter) -> None:
        list_name = {
            "target": "targets",
            "held": "held",
            "interest": "interest",
            "comma": "commas",
        }.get(group)
        toks = self.col_tokens(list_name) if list_name else []
        pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
        vectors = [list(v) for v in current]
        if vectors[pos] != list(vector):
            vectors[pos] = vector
            setter(vectors)

    def _apply_ratio_edit(self, group, tok, vector) -> None:
        if tok == "pending":
            {
                "comma": self.editor.set_pending_comma,
                "interest": self.editor.set_pending_interest,
                "held": self.editor.set_pending_held,
                "target": self.editor.set_pending_target,
            }[group](vector)
        elif group == "comma":
            self._replace_interval_vector(
                group, tok, vector, self.editor.state.comma_basis, self.editor.edit_comma_basis
            )
        elif group == "interest":
            self._replace_interval_vector(
                group, tok, vector, self.editor.interest_vectors, self.editor.set_interest_vectors
            )
        elif group == "held":
            self._replace_interval_vector(
                group, tok, vector, self.editor.held_vectors, self.editor.set_held_vectors
            )
        elif group == "unchanged":
            ratios = [
                self.rec.cell_value(f"unchanged:{j}")
                for j in range(self.editor.state.r)
                if f"unchanged:{j}" in self.rec.inputs
            ]
            if len(ratios) == self.editor.state.r and all(ratios):
                self.editor.set_unchanged_basis(tuple(ratios))
        else:
            targets = self.editor.target_override or service.target_interval_set(
                self.editor.target_spec, self.editor.state.domain_basis
            )
            self._replace_interval_vector(
                group,
                tok,
                vector,
                service.target_interval_vectors(
                    targets, self.editor.state.d, self.editor.state.domain_basis
                ),
                self.editor.set_target_override_vectors,
            )

    def _transform_domain_element(self, cid, op, index) -> None:
        new_raw = service.transform_ratio(
            self.rec.cell_value(cid), op, self.editor.state.domain_basis
        )
        if new_raw is None:
            return  # no-op / unparseable
        parsed = service.parse_domain_element(new_raw)
        if parsed is None:
            ui.notify(
                f"“{new_raw}” is not a valid basis element (≠ 1)",
                type="negative",
                position="top",
            )
            self.render()
            return
        if not service.can_set_domain_element(self.editor.state, index, parsed):
            ui.notify(f"{new_raw} would make the basis dependent", type="negative", position="top")
            self.render()
            return
        self.editor.set_domain_element(index, new_raw)
        self._request_render()

    def _interval_group_state(self, group):
        if group == "comma":
            return self.editor.state.comma_basis, self.editor.edit_comma_basis, "commas"
        if group == "target":
            targets = self.editor.target_override or service.target_interval_set(
                self.editor.target_spec, self.editor.state.domain_basis
            )
            current = service.target_interval_vectors(
                targets, self.editor.state.d, self.editor.state.domain_basis
            )
            return current, self.editor.set_target_override_vectors, "targets"
        if group == "held":
            return self.editor.held_vectors, self.editor.set_held_vectors, "held"
        return self.editor.interest_vectors, self.editor.set_interest_vectors, "interest"

    def transform_interval(self, cid, op):
        # the equave-reduce / reciprocate buttons flanking an editable interval ratio (commas / targets
        # / held / interest) or an editable domain basis element (prime). Resolve the cell's value,
        # apply the op, and route it through the SAME setter a manual edit uses — one undo step, every
        # dependent row recomputed. A no-op (already reduced, or a unison reciprocated) commits nothing,
        # so a disabled button is safe.
        if self.building[0] or cid not in self.rec.inputs:
            return
        group, tok = cid.split(":")
        if group not in ("comma", "target", "held", "interest", "prime") or tok == "pending":
            return
        self._end_commit_gestures()
        if group == "prime":  # relabel a domain basis element to its reduced / reciprocated ratio
            self._transform_domain_element(cid, op, int(tok))
            return
        current, setter, list_name = self._interval_group_state(group)
        toks = self.col_tokens(list_name)
        pos = toks.index(int(tok)) if int(tok) in toks else int(tok)
        if not 0 <= pos < len(current):
            return
        v = tuple(int(x) for x in current[pos])
        if op == "reciprocate":
            new_v = tuple(-x for x in v)
        else:
            new_v = tuple(
                int(x) for x in service.equave_reduce_vector(v, self.editor.state.domain_basis)
            )
        if list(new_v) == list(v):
            return
        vectors = [list(x) for x in current]
        vectors[pos] = list(new_v)
        setter(vectors)
        self._request_render()

    def _commit_pending_element(self, raw, parsed) -> None:
        if not service.can_add_domain_element(self.editor.state, parsed):
            ui.notify(
                f"{raw} isn’t independent of the existing basis",
                type="negative",
                position="top",
            )
            self.render()
            return
        self.editor.set_pending_element(raw)
        self._request_render()  # a new domain element retunes — render off the loop

    def on_element_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        raw = self.rec.cell_value(cid)
        tok = cid.split(":")[1]
        if raw in ("", "?/?"):
            self.render()
            return
        parsed = service.parse_domain_element(raw)
        if parsed is None:
            ui.notify(
                f"“{raw}” is not a positive rational basis element (≠ 1)",
                type="negative",
                position="top",
            )
            self.render()
            return
        if tok == "pending":
            self._commit_pending_element(raw, parsed)
            return
        index = int(tok)
        if parsed == self.editor.state.domain_basis[index]:
            return
        if not service.can_set_domain_element(self.editor.state, index, parsed):
            ui.notify(f"{raw} would make the basis dependent", type="negative", position="top")
            self.render()
            return
        self.editor.set_domain_element(index, raw)
        self._request_render()  # relabelling a domain element retunes — render off the loop

    def on_element_preview(self, cid):
        g = self.rec.gesture
        if (
            self.building[0]
            or g is None
            or g.kind != "edit"
            or g.source != cid
            or cid not in self.rec.inputs
        ):
            return
        raw = self.rec.cell_value(cid)
        tok = cid.split(":")[1]
        parsed = service.parse_domain_element(raw) if raw not in ("", "?/?") else None
        if tok == "pending":
            valid = parsed is not None and service.can_add_domain_element(self.editor.state, parsed)
        else:
            valid = (
                parsed is not None
                and parsed != self.editor.state.domain_basis[int(tok)]
                and service.can_set_domain_element(self.editor.state, int(tok), parsed)
            )
        if not valid:
            self._edit_candidate(None)
        elif tok == "pending":
            self._edit_candidate(lambda: self.editor.set_pending_element(raw))
        else:
            self._edit_candidate(lambda: self.editor.set_domain_element(int(tok), raw))

    def on_power_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        if cid not in ("optimization:power", "control:q"):
            return
        raw = str(self.rec.inputs[cid].value).strip().lower()
        if raw in ("∞", "inf", "max", "minimax"):
            power = float("inf")
        else:
            try:
                power = float(raw)
            except ValueError:
                return
            if not math.isfinite(power) or power <= 0:
                return
        if cid == "control:q":
            if power < 1:
                return
            self.editor.set_complexity_norm_power(power)
        else:
            self.editor.set_optimization_power(power)
        self._request_render()  # a new optimization / complexity power retunes — render off the loop

    def _gen_position(self, tok):
        toks = self.col_tokens("gens")
        return toks.index(tok) if tok in toks else tok

    def on_gentuning_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        mag = self.rec.decimal_value(cid)
        if not mag:
            return
        try:
            cents = abs(float(mag))
        except ValueError:
            return
        glyph = self.rec.gensign_faces.get(cid)
        if glyph is not None and glyph.text not in ("+", ""):
            cents = -cents
        i = int(cid.rsplit(":", 1)[1])
        if ":ssgen:" in cid:
            self.editor.set_superspace_generator_tuning_component(i, cents)
        else:
            self.editor.set_generator_tuning_component(self._gen_position(i), cents)
        self._request_render()  # a manual generator override re-derives the maps — render off the loop

    def on_gentuning_wheel(self, cid, delta_y):
        if self.building[0] or not delta_y:
            return
        i, steps = int(cid.rsplit(":", 1)[1]), (1 if delta_y < 0 else -1)
        if ":ssgen:" in cid:
            self.editor.nudge_superspace_generator_tuning_component(i, steps)
        else:
            self.editor.nudge_generator_tuning_component(self._gen_position(i), steps)
        # off the loop — rapid notches coalesce into one trailing rebuild at the value you land on
        self._request_render()

    def on_value_wheel(self, cid, delta_y):
        if self.building[0] or not delta_y or cid not in self.rec.inputs:
            return
        step = _WHEEL_STEPS.get(self.rec.kinds.get(cid))
        if step is None:
            return
        if cid in self.rec.den_inputs:
            self.building[0] = True
            self.rec.set_decimal_value(cid, _wheel_step(self.rec.decimal_value(cid), delta_y, step))
            self.building[0] = False
            self.on_prescaler_change(cid)
            return
        self.rec.inputs[cid].value = _wheel_step(self.rec.inputs[cid].value, delta_y, step)
        commit = {
            "mapping": self.on_mapping_change,
            "commacell": self.on_comma_change,
            "interestcell": self.on_interest_change,
            "heldcell": self.on_held_change,
            "targetcell": self.on_target_cells_change,
            "formcell": self.on_form_change,
        }.get(self.rec.kinds.get(cid))
        if commit is not None:
            commit()

    def on_target_limit_wheel(self, delta_y):
        # step the TILT/OLD limit by ±1 per wheel notch. Unlike a matrix/vector cell, COMMITTING a
        # new limit rebuilds the whole target interval set, re-solves the tuning and re-renders the
        # grid — far too heavy to run on every notch. A fast scroll would queue one such solve per
        # notch, each costlier than the last as the set grows, and grind the app to a halt. So step
        # the shown number now (under the build guard, so the field's own on_target_change echo is a
        # no-op — handle_event runs it inline) and DEBOUNCE the commit: the value is server-side, so
        # the loopback-controlled field actually advances, while a re-armed task collapses the whole
        # gesture into ONE solve at the limit you land on. Focus-gated client-side (see _INT_WHEEL_JS).
        if self.building[0] or not delta_y:
            return
        num = self.rec.selects["preset:target"][0]
        self.building[0] = True
        num.value = _wheel_step(num.value, delta_y)
        self.building[0] = False
        self.on_target_limit_preview()
        if self.target_limit_commit[0] is not None:
            self.target_limit_commit[0].cancel()
        self.target_limit_commit[0] = background_tasks.create(
            self._debounced_target_commit(), name="target-limit-commit"
        )

    async def _debounced_target_commit(self):
        # the tail of a target-limit wheel gesture: once the notches stop for _TARGET_LIMIT_DEBOUNCE,
        # commit the number now in the field with the one real solve + render. A new notch cancels
        # this and arms a fresh one. The debounce collapses the whole gesture into one commit, so an
        # even odd-limit (OLD) you land on toasts once here (not once per notch) and the render reddens it.
        # We run off the loop (a background task), where the slot stack is empty — so enter the captured
        # page client's context, or on_target_change's ui.notify can't resolve the client and the toast
        # silently vanishes (render reaches its client the same captured-client way, see page_client above).
        try:
            await asyncio.sleep(_TARGET_LIMIT_DEBOUNCE)
        except asyncio.CancelledError:
            return
        self.target_limit_commit[0] = None
        with self.page_client:
            self.on_target_change()

    def on_target_limit_preview(self, typed=None):
        # live edit preview for the TILT/OLD limit field, mirroring on_element_preview: as the shown
        # limit changes (a wheel notch steps it, a keystroke types it) but BEFORE the debounced commit
        # reflows the grid, the candidate rings the target interval cells the new limit would MOVE
        # (amber) / REMOVE (red) in place. LOWERING the limit drops intervals; reddening them while
        # they're still on screen is what shows "what's going away" — a post-commit render can't, the
        # reflow has already deleted them. RAISING it just rings the survivors that move (the added
        # rows are off-screen until committed, so they can't ring), like every other no-reflow add
        # preview. `typed` is the live field text for a keystroke (the loopback field's debounced
        # model value lags a keystroke behind); the wheel passes None and reads the stepped number.
        g = self.rec.gesture
        if self.building[0] or g is None or g.kind != "edit" or g.source != "preset:target":
            return
        num, sel = self.rec.selects["preset:target"]
        family = sel.value or "TILT"
        raw = num.value if typed is None else typed
        if service.target_limit_problem(family, raw) == "whole":
            self._edit_candidate(None)
            return
        text = (str(raw) if raw is not None else "").strip()
        spec = f"{int(float(text))}-{family}" if text else family
        try:
            valid = bool(service.target_interval_set(spec, self.editor.state.domain_basis))
        except Exception as exc:
            _log.debug("target spec %r rejected: %r", spec, exc)
            valid = False
        if not valid:
            self._edit_candidate(None)
            return
        self._edit_candidate(lambda: self.editor.set_target_spec(spec))

    def on_prescaler_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        raw = self.rec.decimal_value(cid)
        if not raw:
            return
        try:
            value = float(raw)
        except ValueError:
            return
        parts = cid.split(":")
        i, j = int(parts[3]), int(parts[4])
        if not math.isfinite(value) or (i == j and value <= 0):
            ui.notify(_INVALID_PRESCALER, type="negative", position="top")
            self.render()
            return
        self.editor.set_custom_prescaler_entry(i, j, value)
        self._request_render()  # the prescaler drives the weighted tuning solve — render off the loop

    def on_weight_change(self, cid):
        if self.building[0] or cid not in self.rec.inputs:
            return
        weights = []
        for other in self.rec.inputs:
            if not other.startswith("weight:"):
                continue
            raw = self.rec.decimal_value(other)
            if not raw:
                return
            try:
                w = float(raw)
            except ValueError:
                return
            if not math.isfinite(w) or w <= 0:
                ui.notify(_INVALID_WEIGHT, type="negative", position="top")
                self.render()
                return
            weights.append(w)
        self.editor.set_custom_weights(weights)
        self._request_render()  # the weights drive the tuning solve — render off the loop

    _PTEXT_EDITORS: ClassVar[dict[str, str]] = {
        "ptext:mapping:primes": "try_edit_mapping_text",
        "ptext:mapping:canongens": "try_edit_form_matrix_text",
        "ptext:vectors:commas": "try_edit_comma_basis_text",
        "ptext:tuning:gens": "set_generator_tuning_text",
        "ptext:tuning:ssgens": "set_superspace_generator_tuning_text",
        "ptext:vectors:targets": "set_target_override_text",
        "ptext:prescaling:primes": "set_custom_prescaler_text",
        "ptext:projection:primes": "try_edit_projection_text",
        "ptext:projection:gens": "try_edit_embedding_text",
    }

    def on_ptext_edit(self, cid, value):
        if self.building[0]:
            return
        editor_method = self._PTEXT_EDITORS.get(cid)
        if editor_method is None:
            return
        if not self.editor.settings.get("ebk", True):
            value = service.simple_matrix_to_ebk(value, _PTEXT_DUAL_VECTOR_KIND.get(cid, False))
        if getattr(self.editor, editor_method)(value):
            self.rec.ptext_inputs[cid].classes(remove="rtt-ptext-error")
            self._request_render()  # a typed dual (mapping/commas/tuning/targets/P/G…) retunes — off the loop
            return
        self.rec.ptext_inputs[cid].classes(add="rtt-ptext-error")
        toast = self._ptext_error_toast(cid, value)
        if toast:
            ui.notify(toast, type="negative", position="top")

    def _ptext_error_toast(self, cid, value):
        if cid == "ptext:mapping:primes":
            st = service.parse_mapping_state(value)
            if st is not None and not service.is_proper_temperament(st.mapping):
                return _INVALID_TEMPERAMENT
        elif cid == "ptext:vectors:commas":
            b = service.parse_comma_basis(value)
            if b is not None and not service.is_proper_temperament(
                service.from_comma_basis(b).mapping
            ):
                return _INVALID_TEMPERAMENT
        elif cid == "ptext:projection:primes" and service.parse_projection(value) is not None:
            return _INVALID_PROJECTION
        elif (
            cid == "ptext:projection:gens"
            and service.parse_embedding(value, self.editor.state.d, len(self.editor.state.mapping))
            is not None
        ):
            return _INVALID_EMBEDDING
        return None

    def _end_commit_gestures(self):
        # a commit ends any hover-family gesture FIRST — its rings are previews of a click that
        # has now landed (or been superseded), and a token gesture must restore the real document
        # before the action mutates it (e.g. Ctrl+Z while a temperament hover holds a hypothetical
        # doc). The edit/wheel gestures survive their own commits and end on blur/mouseleave.
        if self.rec.gesture is not None and self.rec.gesture.kind in (
            "hover",
            "chooser",
            "temp",
            "drag",
        ):
            self.end_gesture()
        self.rank_remove[0] = None

    def act(self, action):
        # the universal click/keyboard commit: end gestures, mutate, then render OFF the loop
        # (_request_render) — most of these actions retune (expand/shrink, undo/redo across an
        # edit, a structural remove, back-to-scheme), so the heavy solve must not block the socket.
        self._end_commit_gestures()
        action()
        self._request_render()

    def add_interval(self, action, group):
        # add the draft column, then focus into it: the quantities ratio cell if its row is shown
        # (the layout emitted it), else the first gridded vector cell (prime 0) of the draft column.
        # A draft add doesn't retune (the pending green vector isn't committed), so its build is
        # light — render SYNCHRONOUSLY (not the off-loop _request_render) so last_lay is current for
        # the focus hand-off below, which reads the just-built layout.
        self._end_commit_gestures()
        action()
        self.render()
        quant_id, vec_kind = self.draft_focus[group]
        lay = self.last_lay[0]
        if any(cb.id == quant_id for cb in lay.cells):
            target = quant_id
        elif vec_kind is not None:
            target = next(
                (cb.id for cb in lay.cells if cb.pending and cb.prime == 0 and cb.kind == vec_kind),
                None,
            )
        else:
            target = None
        if target is None and group == "element":
            target = next((cb.id for cb in lay.cells if cb.id == "basis:pending"), None)
        inp = self.rec.inputs.get(target) if target is not None else None
        if inp is not None:
            self._focus_draft_cell(inp)

    def _focus_draft_cell(self, inp) -> None:
        # Focus into the freshly-created draft cell AND select its contents, so the "?" placeholder
        # the draft starts with is highlighted — the first keystroke replaces it instead of typing
        # after it (no backspace needed). select() resolves through getElement().$refs.qRef to
        # QInput.select() (a native input.select()); it is a harmless no-op on the empty
        # integer-vector fallback cell. A direct runMethod can lose a race in a real (visible)
        # browser: the cell-create 'update' and this focus message can be delivered in one frame,
        # so the focus runs before Vue has mounted the new cell and populated its $ref — and
        # silently no-ops. So defer to the next macrotask and poll briefly for the mount (getElement
        # returns the ref once it exists). setTimeout works whether the page is visible or hidden —
        # requestAnimationFrame would be paused while hidden (e.g. the render tests / a backgrounded
        # tab), so it is the wrong tool here.
        # The draft cell can be off-screen — a + at a far edge, or an add fired by keyboard while
        # scrolled away. So after focusing, scroll the grid body the minimum that brings the cell
        # fully into view (past the frozen left rowband, clear of the top edge). Setting scrollLeft/
        # Top fires the body's own scroll listener, which re-pins the frozen header (see freeze.js).
        ui.run_javascript(
            f"(function(){{var id={inp.id},n=0;function go(){{var c=getElement(id);"
            f"if(c){{runMethod(id,'focus',[]);runMethod(id,'select',[]);"
            f"var el=document.activeElement,cell=el&&el.closest&&el.closest('.rtt-cell'),"
            f"body=cell&&cell.closest('.rtt-gridbody');"
            f"if(body){{var cr=cell.getBoundingClientRect(),br=body.getBoundingClientRect(),"
            f"band=body.querySelector('.rtt-rowband'),bw=band?band.getBoundingClientRect().width:0,pl=24,pt=8;"
            f"if(cr.left<br.left+bw+pl)body.scrollLeft-=br.left+bw+pl-cr.left;"
            f"else if(cr.right>br.right-pl)body.scrollLeft+=cr.right-br.right+pl;"
            f"if(cr.top<br.top+pt)body.scrollTop-=br.top+pt-cr.top;"
            f"else if(cr.bottom>br.bottom-pt)body.scrollTop+=cr.bottom-br.bottom+pt;}}return;}}"
            f"if(n++<60)setTimeout(go,16);}}setTimeout(go,0);}})()"
        )

    def on_show_toggle(self, key, value):
        if self.building[0]:
            return
        if key == "nonstandard_domain" and not value and self.editor.basis_is_nonstandard:
            self.editor.exit_nonstandard_domain()
            self.render()
            return
        self.editor.set_show(key, value)
        self.render()

    def on_select_all(self, value):
        if self.building[0]:
            return
        self.editor.set_all_show(value, self._available_keys())
        self.render()

    def on_part_click(self, key):
        if self.building[0]:
            return
        host = _TILE_HOST.get(key)
        if host is not None and not self.editor.settings[host]:
            return
        self.editor.set_show(key, not self.editor.settings[key])
        self.render()

    def on_preset(self, cid, value):
        if self.building[0]:
            return
        if cid.startswith("preset:temperament"):
            if value in presets.TEMPERAMENT_COMMAS:
                self.end_gesture()
                self.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[value])
                self._request_render()  # a loaded temperament retunes — render off the loop
            else:
                self.render()
            return
        apply = self._candidate_apply(cid, value)
        if apply is not None:
            self.end_chooser_gesture()
            apply()
            self._request_render()  # a tuning / prescaler preset re-solves — render off the loop

    def on_subpick(self, cid, value):
        if self.building[0] or value is None:
            return
        self.end_gesture()
        db = self.editor.state.domain_basis
        if cid == "etpick:draft":
            self.editor.set_pending_mapping_row(list(presets.et_value_to_val(value, db)))
            ok = self.editor.pending_mapping_row is None
        elif cid == "commapick:draft":
            self.editor.set_pending_comma(list(presets.comma_value_to_vector(value, db)))
            ok = self.editor.pending_comma is None
        elif cid.startswith("etpick:"):
            i = self._token_index(cid, "gens")
            ok = i is not None and self.editor.set_mapping_row(
                i, presets.et_value_to_val(value, db)
            )
        else:
            c = self._token_index(cid, "commas")
            ok = c is not None and self.editor.set_comma(
                c, presets.comma_value_to_vector(value, db)
            )
        if not ok:
            ui.notify(_INVALID_TEMPERAMENT, type="negative", position="top")
        self.render()

    def on_form_choose(self, cid, value):
        if self.building[0]:
            return
        apply = self._candidate_apply(cid, value)
        if apply is not None:
            self.end_chooser_gesture()
            apply()
            self._request_render()  # canonicalizing re-keys the tuning solve — render off the loop

    def on_target_change(self):
        if self.building[0]:
            return
        self.end_chooser_gesture()
        num, sel = self.rec.selects["preset:target"]
        family = sel.value or "TILT"
        problem = service.target_limit_problem(family, num.value)
        if problem == "whole":
            # a non-number is never accepted: toast and re-render, which restores the committed
            # value (the input is loopback-controlled, so the server's value overwrites the garbage)
            ui.notify(tooltips.target_limit_help("whole"), type="negative", position="top")
            self.render()
            return
        text = (num.value or "").strip()
        spec = f"{int(float(text))}-{family}" if text else family
        try:
            valid = bool(service.target_interval_set(spec, self.editor.state.domain_basis))
        except Exception as exc:
            _log.debug("target spec %r rejected: %r", spec, exc)
            valid = False
        if not valid:
            return
        if problem == "odd":
            ui.notify(tooltips.target_limit_help("odd"), type="negative", position="top")
        self.editor.set_target_spec(spec)
        self._request_render()  # a new target set re-weights the optimization (retunes) — render off the loop

    def on_control_select(self, cid, value):
        if self.building[0] or value is None:
            return
        apply = self._candidate_apply(cid, value)
        if apply is not None:
            self.end_chooser_gesture()
            apply()
        elif cid == "control:diminuator":
            self.editor.set_diminuator_replaced(bool(value))
        elif cid == "control:all_interval":
            self.editor.set_all_interval(bool(value))
        else:
            return
        self._request_render()  # a weighting / complexity / all-interval trait change retunes — off the loop

    def on_range_mode(self, value):
        if self.building[0] or value is None:
            return
        self.editor.set_range_mode(value)
        self.render()

    def on_toggle(self, item):
        self.editor.toggle_collapsed(item)
        self.render()

    def on_toggle_all(self):
        self.editor.set_collapsed(
            spreadsheet_text.toggle_all_collapsed(self.last_lay[0], self.editor.collapsed)
        )
        self.render()

    def on_cell_focus(self, cid):
        self.take_over_gesture()
        self.rec.gesture = _Gesture(kind="edit", source=cid, baseline=self.last_lay[0])

    def on_cell_blur(self, cid=None):
        g = self.rec.gesture
        if g is not None and g.kind in ("edit", "wheel") and (cid is None or g.source == cid):
            self.end_gesture()
            self.paint_rings()

    def combine_begin(self):
        self.end_gesture()
        self.rec.gesture = _Gesture(
            kind="drag", token=self.editor.capture_for_preview(), baseline=self.last_lay[0]
        )

    def combine_preview(self, apply, target_pred=None):
        g = self.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.editor.restore_for_preview(g.token)
        g.target_pred = target_pred if apply is not None else None
        if apply is not None:
            apply()
        self.gesture_render()

    def combine_commit(self, apply):
        g = self.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self.act(apply)

    def combine_end(self):
        g = self.rec.gesture
        if g is None or g.kind != "drag":
            return
        self.end_gesture()
        self.render()

    def control_hover(self, apply):
        if not self.editor.settings["preview_highlighting"]:
            return
        g = self.rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        prev = None
        if g is not None and g.kind == "wheel":
            prev = g
        elif g is not None:
            self.take_over_gesture()
        self.rec.gesture = _Gesture(kind="hover", apply=apply, prev=prev)
        self.paint_rings()

    def control_unhover(self):
        g = self.rec.gesture
        if g is None or g.kind != "hover":
            return
        self.rec.gesture = g.prev
        self.paint_rings()

    def rank_remove_hover(self, axis, idx):
        if not self.editor.settings["preview_highlighting"]:
            return
        if self.rec.gesture is not None and self.rec.gesture.kind in ("edit", "drag"):
            return
        self.rank_remove[0] = (axis, idx)
        self.rank_rendering[0] = True
        try:
            self.render()
        finally:
            self.rank_rendering[0] = False

    def rank_remove_unhover(self):
        if self.rank_remove[0] is not None:
            self.rank_remove[0] = None
            self.render()

    def _cell_xy(self, lay, eid):
        for c in lay.cells:
            if c.id == eid:
                return (round(c.x), round(c.y))
        return None

    def chooser_hover(self, cid, apply):
        if not self.editor.settings["preview_highlighting"]:
            return
        g = self.rec.gesture
        if g is not None and g.kind in ("edit", "drag"):
            return
        if g is not None and (g.kind != "chooser" or g.source != cid):
            self.take_over_gesture()
        if self.rec.gesture is None:
            self.rec.gesture = _Gesture(
                kind="chooser",
                source=cid,
                token=self.editor.capture_for_preview(),
                baseline=self.last_lay[0],
            )
        g = self.rec.gesture
        self.editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        if apply is None:
            g.apply = None
            self.paint_rings()
            return
        base = g.baseline
        apply()
        hyp = self.editor.layout(prev_ids=base.identities if base is not None else None)
        disturbs = base is not None and (
            spreadsheet_text.removed_cell_ids(base, hyp)
            or self._cell_xy(base, cid) != self._cell_xy(hyp, cid)
        )
        if disturbs:
            self.editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def chooser_unhover(self):
        g = self.rec.gesture
        if g is None or g.kind != "chooser":
            return
        was = self.end_gesture()
        if was is not None and was.reflowed:
            self.render()
        else:
            self.paint_rings()

    def _end_temperament_preview(self):
        g = self.rec.gesture
        if g is None or g.kind != "temp":
            return
        was = self.end_gesture()
        if was.reflowed:
            self.render()
        else:
            self.paint_rings()

    def _temperament_hover_preview(self, key):
        if key not in presets.TEMPERAMENT_COMMAS:
            self._end_temperament_preview()
            return
        g = self.rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return
            self.end_gesture()
            g = self.rec.gesture = _Gesture(
                kind="temp", token=self.editor.capture_for_preview(), baseline=self.last_lay[0]
            )
        self.editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        base = self.editor.state
        self.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
        hyp = self.editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self.editor.restore_for_preview(g.token)
            g.apply = lambda: self.editor.edit_comma_basis(presets.TEMPERAMENT_COMMAS[key])
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    def _ensure_temp_gesture(self):
        g = self.rec.gesture
        if g is None or g.kind != "temp":
            if g is not None and g.kind in ("edit", "drag"):
                return None
            self.end_gesture()
            g = self.rec.gesture = _Gesture(
                kind="temp", token=self.editor.capture_for_preview(), baseline=self.last_lay[0]
            )
        self.editor.restore_for_preview(g.token)
        if g.reflowed:
            g.reflowed = False
            g.apply = None
            self.gesture_render()
        return g

    def _subpick_hover_preview(self, cid, value):
        if value is None:
            self._end_temperament_preview()
            return
        db = self.editor.state.domain_basis
        draft = cid in ("etpick:draft", "commapick:draft")
        idx = None
        if not draft:
            idx = self._token_index(cid, "gens" if cid.startswith("etpick:") else "commas")
            if idx is None:
                self._end_temperament_preview()
                return
        g = self._ensure_temp_gesture()
        if g is None:
            return
        if draft:
            self._preview_subpick_draft(cid, value, db, g)
        else:
            self._preview_subpick_pick(cid, value, db, idx, g)

    def _preview_subpick_draft(self, cid, value, db, g) -> None:
        if cid == "etpick:draft":
            self.editor.pending_mapping_row = list(presets.et_value_to_val(value, db))
        else:
            self.editor.pending_comma = list(presets.comma_value_to_vector(value, db))
        g.apply = None
        g.reflowed = True
        self.gesture_render()

    def _preview_subpick_pick(self, cid, value, db, idx, g) -> None:
        if cid.startswith("etpick:"):

            def apply(i=idx, v=value):
                return self.editor.set_mapping_row(i, presets.et_value_to_val(v, db))
        else:

            def apply(c=idx, v=value):
                return self.editor.set_comma(c, presets.comma_value_to_vector(v, db))

        base = self.editor.state
        apply()
        hyp = self.editor.state
        if hyp.d < base.d or hyp.r < base.r or hyp.n < base.n:
            self.editor.restore_for_preview(g.token)
            g.apply = apply
            self.paint_rings()
        else:
            g.apply = None
            g.reflowed = True
            self.gesture_render()

    _APPLY_SETTERS: ClassVar[tuple[tuple[str, str], ...]] = (
        ("preset:tuning", "set_tuning_scheme"),
        ("preset:prescaler", "set_complexity_prescaler"),
        ("preset:projection", "set_established_projection"),
        ("control:slope", "set_weight_slope"),
    )

    def _candidate_apply(self, cid, value):
        if value is None:
            return None
        for prefix, setter in self._APPLY_SETTERS:
            if cid.startswith(prefix):
                return lambda v=value, s=setter: getattr(self.editor, s)(v)
        if cid == "control:complexity":
            return self._complexity_apply(value)
        if cid.startswith("formchooser:"):
            return self._formchooser_apply(cid, value)
        return None

    def _complexity_apply(self, value):
        if value == "custom":
            return None
        internal = next((k for k, v in service.COMPLEXITY_DISPLAYS.items() if v == value), value)
        return lambda: self.editor.set_complexity_name(internal)

    def _formchooser_apply(self, cid, value):
        name = cid.split(":", 1)[1]
        if name == "mapping":
            if value not in service.MAPPING_FORM_KEYS:
                return None
            return lambda: self.editor.set_mapping_form(value)
        if value not in service.COMMA_BASIS_FORM_KEYS:
            return None
        return lambda: self.editor.set_comma_basis_form(value)

    def on_chooser_hover(self, cid, detail):
        # the shared option-hover preview entry for every q-select armed via _arm_option_hover: the
        # delegation fires `opthover` at the chooser's cell wrap carrying the hovered option's positional
        # index in `detail` (-1 / None on leave). Map it back to the option's key through the live
        # select, then preview applying it. Temperament + the sub-pickers route to their own sticky
        # reflow path; the rest (including the TILT/OLD family) go through chooser_hover below, which
        # reflows a value-only pick and reddens one that would remove cells.
        entry = self.rec.selects.get(cid)
        sel = entry[1] if isinstance(entry, tuple) else entry
        if not isinstance(sel, ui.select):
            return
        index = _hover_index(detail)
        if index is not None and self.rec.popup_state.get(cid) == "closed":
            return
        if cid.startswith(("etpick:", "commapick:")):
            self._subpick_hover_preview(cid, _option_key(sel, index) if index is not None else None)
            return
        if cid.startswith("preset:temperament"):
            self._temperament_hover_preview(_option_key(sel, index))
            return
        if index is None or not sel.enabled:
            self.chooser_unhover()
            return
        self._hover_value_chooser(cid, sel, index, entry)

    def _hover_value_chooser(self, cid, sel, index, entry) -> None:
        if cid == "preset:target":
            family = _option_key(sel, index)
            if family not in presets.TARGET_SETS:
                self.chooser_unhover()
                return
            text = (entry[0].value or "").strip()
            try:
                spec = f"{int(float(text))}-{family}" if text else family
            except ValueError:
                spec = family
            self.chooser_hover(cid, lambda: self.editor.set_target_spec(spec))
            return
        apply = self._candidate_apply(cid, _option_key(sel, index))
        if apply is None:
            self.chooser_unhover()
            return
        self.chooser_hover(cid, apply)

    def on_popup(self, cid, is_open):
        # a chooser's Quasar popup opened/closed: feed the server-side gate (see on_chooser_hover)
        # and treat the close as the gesture's leave — the option the pointer was on is gone, so a
        # live chooser/temperament preview ends (ungated; only positive arms are gated).
        self.rec.popup_state[cid] = "open" if is_open else "closed"
        if not is_open:
            self.on_chooser_hover(cid, None)

    def gentuning_hover(self, cid):
        g = self.rec.gesture
        if g is not None and g.kind in ("edit", "drag", "hover"):
            return
        self.take_over_gesture()
        self.rec.gesture = _Gesture(kind="wheel", source=cid, baseline=self.last_lay[0])

    def gentuning_unhover(self, cid):
        g = self.rec.gesture
        if g is None or g.kind != "wheel" or g.source != cid:
            return
        self.end_gesture()
        self.paint_rings()

    def on_drag_start(self, lst, idx):
        self.drag_src[0] = (lst, idx)
        self.reorder_dst[0] = (lst, idx)
        self.end_gesture()
        self.rec.gesture = _Gesture(
            kind="drag", token=self.editor.capture_for_preview(), baseline=self.last_lay[0]
        )

    def on_drag_enter(self, dst_list, dst_idx):
        g = self.rec.gesture
        if (
            g is None
            or g.kind != "drag"
            or self.drag_src[0] is None
            or (dst_list, dst_idx) == self.reorder_dst[0]
        ):
            return
        self.reorder_dst[0] = (dst_list, dst_idx)
        self.editor.restore_for_preview(g.token)
        idx = dst_idx if dst_idx is not None else (1 << 30)
        self.editor.move_interval(self.drag_src[0][0], self.drag_src[0][1], dst_list, idx)
        self.gesture_render()

    def on_drag_end(self):
        if self.rec.gesture is not None and self.rec.gesture.kind == "drag":
            self.end_gesture()
            self.render()
        self.drag_src[0] = None
        self.reorder_dst[0] = None

    def on_drop(self, dst_list, dst_idx):
        src = self.drag_src[0]
        self.drag_src[0] = None
        self.reorder_dst[0] = None
        had_preview = self.rec.gesture is not None and self.rec.gesture.kind == "drag"
        if had_preview:
            self.end_gesture()
        if not src:
            if had_preview:
                self.render()
            return
        idx = dst_idx if dst_idx is not None else (1 << 30)
        if self.editor.move_interval(src[0], src[1], dst_list, idx) or had_preview:
            self.render()

    def _request_render(self, after=None):
        # schedule an off-loop commit render; a request arriving while one is in flight collapses
        # into a single trailing rebuild (the state it lands on is the only one that matters).
        # ``after`` runs on the loop once render() has rebuilt — for the few commits with a
        # synchronous tail that reads the fresh layout (a draft column materializing then rebasing
        # its edit gesture off last_lay).
        if helpers.is_user_simulation():
            # the in-process User test harness drives clicks/edits and inspects the DOM right after,
            # with no chance for a background task to run — and there is no real socket to protect.
            # Render synchronously there: tests see the same immediate rebuild they always did, and
            # the off-loop machinery (a production websocket concern) is exercised by the live probe.
            self.render()
            if after is not None:
                after()
            return
        if self.render_inflight[0]:
            self.render_again[0] = True
            self.render_after[0] = after
            return
        background_tasks.create(self._commit_render(after))

    async def _commit_render(self, after=None):
        self.render_inflight[0] = True
        try:
            again = True
            cont = after
            while again:
                prev = self.last_lay[0].identities if self.last_lay[0] is not None else None
                try:
                    # warm the tuning memo off the loop; the result is discarded — render() below
                    # recomputes the layout, now a cache hit. (editor.layout is read-only, and the
                    # mutation that triggered this already ran synchronously in the handler.)
                    await asyncio.to_thread(self.editor.layout, prev_ids=prev)
                except Exception:
                    _log.exception("off-loop layout warm-up failed; rendering on the loop")
                self.render()
                if cont is not None:
                    cont()
                again = self.render_again[0]
                self.render_again[0] = False
                cont = self.render_after[0]
                self.render_after[0] = None
        finally:
            self.render_inflight[0] = False

    def apply_view_classes(self):
        # Two of the `interface` Show behaviours gate the whole app through a single <body> class each,
        # so one CSS rule (assets/rtt.css) handles every element: `animations` off adds rtt-no-anim
        # (which zeroes the --t transition var, so every change snaps instead of sliding/fading) and
        # `tooltips` off adds rtt-no-tooltips (which hides every .q-tooltip). Unlike dark mode these
        # live in editor.settings — toggled in the Show panel, so select-all / Reset reach them — so
        # render() re-applies them after any toggle (and on the initial build, before cells animate in).
        # The third behaviour, preview_highlighting, has no body class: it's gated in Python at the
        # preview source (compute_rings + the hover handlers) so no ring or reflow is even produced.
        # render() can run OFF the loop (the _commit_render background task — every act()-driven commit:
        # reset, undo/redo, a structural edit), where the slot stack is empty and ui.query would raise
        # "slot stack ... is empty", aborting the whole render (grid never updates, busy scrim never
        # clears). Enter the captured page client so the <body> query resolves; in the synchronous /
        # test path this just nests harmlessly inside the already-live slot.
        with self.page_client:
            body = ui.query("body")
            body.classes(add="rtt-no-anim") if not self.editor.settings[
                "animations"
            ] else body.classes(remove="rtt-no-anim")
            body.classes(add="rtt-no-tooltips") if not self.editor.settings[
                "tooltips"
            ] else body.classes(remove="rtt-no-tooltips")

    def _build_grid_pane(self) -> None:
        self.grid_pane = ui.element("div").classes("rtt-app").mark("gridpane")
        with self.grid_pane:
            self.colhead = ui.element("div").classes("rtt-colhead").mark("colhead")
            with self.colhead:
                self.colhead_inner = (
                    ui.element("div").classes("rtt-colhead-inner").mark("colheadinner")
                )
            self._build_corner()
            self._build_gridbody()

    def _build_drawer(self) -> None:
        drawer = ui.element("div").classes("rtt-drawer")
        with drawer, ui.element("div").classes("rtt-drawer-inner"):
            self._build_show_frozen()
            self.boxes: dict = {}
            self.examples: dict = {}
            self.tile_parts: dict = {}
            self.show_rows: dict = {}
            self.show_scroll = ui.element("div").classes("rtt-show-scroll").mark("showscroll")
            with self.show_scroll:
                self._build_chapter_group()
                for group_name, items in show_settings.SHOW_GROUPS:
                    with ui.element("div").classes("rtt-show-group"):
                        if group_name == "general":
                            self._build_general_tile()
                        else:
                            self._build_show_group(items)

    def _build_corner(self) -> None:
        self.corner = ui.element("div").classes("rtt-corner").mark("corner")
        with self.corner:
            self._build_title_buttons()
            self._build_approach_radio()

    def _build_gridbody(self) -> None:
        self.gridbody = ui.element("div").classes("rtt-gridbody").mark("gridbody")
        with self.gridbody:
            self.board = ui.element("div").classes("rtt-gridcontent").mark("board")
            with self.board, ui.element("div").classes("rtt-band"):
                self.rowband = ui.element("div").classes("rtt-rowband").mark("rowband")
        self.refs["approach"].move(self.board)
        self.cell_parents = {
            "corner": self.corner,
            "col": self.colhead_inner,
            "row": self.rowband,
            "body": self.board,
        }

    def _icon_button(self, ref, icon, on_click, classes, help_key):
        self.refs[ref] = (
            ui.button(icon=icon, on_click=on_click, color=None)
            .props("flat dense")
            .classes(classes)
            .mark(ref)
            .tooltip(tooltips.CHROME_HELP[help_key])
        )

    def _share_link(self) -> None:
        self._end_commit_gestures()
        token = _encode_state(self.editor.serialize())
        ui.run_javascript(
            "(async function(){"
            f"var u=location.origin+location.pathname+'?{_STATE_PARAM}='+{json.dumps(token)};"
            "try{await navigator.clipboard.writeText(u);}"
            "catch(e){var t=document.createElement('textarea');t.value=u;"
            "document.body.appendChild(t);t.select();"
            "document.execCommand('copy');t.remove();}})()"
        )
        ui.notify("Shareable link copied to clipboard")

    def _arm_history_previews(self) -> None:
        def arm(btn, can, op):
            btn.on("mouseenter", lambda _=None: self.control_hover(op) if can() else None)
            btn.on("mouseleave", lambda _=None: self.control_unhover())

        arm(self.refs["undo"], lambda: self.editor.can_undo, self.editor.undo)
        arm(self.refs["redo"], lambda: self.editor.can_redo, self.editor.redo)
        arm(self.refs["reset"], lambda: self.editor.can_reset, self.editor.reset)

    def _build_title_buttons(self) -> None:
        with ui.element("div").classes("rtt-titletile").mark("titletile"):
            with ui.element("div").classes("rtt-tile-btns"):
                self._icon_button(
                    "undo",
                    "undo",
                    lambda: self.act(self.editor.undo),
                    "rtt-iconbtn rtt-hk-undo",
                    "undo",
                )
                self._icon_button(
                    "redo",
                    "redo",
                    lambda: self.act(self.editor.redo),
                    "rtt-iconbtn rtt-hk-redo",
                    "redo",
                )
                self._icon_button(
                    "reset", "restart_alt", self.reset_everything, "rtt-iconbtn", "reset"
                )
                self._icon_button(
                    "share", "share", self._share_link, "rtt-iconbtn rtt-noarm", "share"
                )
                self._icon_button(
                    "tour",
                    "help_outline",
                    lambda: ui.run_javascript("window.rttTour && window.rttTour.start()"),
                    "rtt-iconbtn rtt-noarm",
                    "tour",
                )
                self._arm_history_previews()

    def _build_approach_radio(self) -> None:
        # the chapter-9 nonstandard-domain-approach radio: prime-based, nonprime-based, or
        # the library's neutral default (which reads a nonprime element as a formal prime).
        # Built as the standard square radio (the tuning-ranges range-mode style — a vertical
        # list of square options), NOT a Quasar inline radio. Hidden when the domain has no
        # nonprime element — the trait is meaningless there — and revealed when a basis like
        # 2.3.13/5 carries one. render() fills the live option and sets visibility each pass.
        approach_options = {
            "prime-based": "prime-based",
            "nonprime-based": "nonprime-based",
            "": "neutral",
        }

        def on_approach_change(value):
            if self.building[0] or value is None:
                return
            self.editor.set_nonprime_basis_approach(value)
            self._request_render()  # the nonprime approach changes how the tuning solves — off the loop

        def on_approach_hover(value):
            # preview the hovered approach option: ring the cells reading the temperament that
            # way would move, without committing (control_hover reverts it). None = leaving the
            # radio, so clear the preview. Each option is its own hover target (mouseenter).
            if value is None:
                self.control_unhover()
                return
            self.control_hover(lambda a=value: self.editor.set_nonprime_basis_approach(a))

        self.refs["approach"] = (
            ui.element("div").classes("rtt-approach rtt-rangemode").mark("approach")
        )
        self.refs["approach_opts"] = {}
        with self.refs["approach"]:
            for key, label in approach_options.items():
                opt = ui.element("div").classes("rtt-rangeopt")
                with opt:
                    ui.element("span").classes("rtt-rangebox")
                    ui.label(label).classes("rtt-rangelabel")
                opt.on("click", lambda _=None, k=key: on_approach_change(k))
                opt.on("mouseenter", lambda _=None, k=key: on_approach_hover(k))
                opt.mark(f"approach-{label}")
                self.refs["approach_opts"][key] = opt
        self.refs["approach"].on("mouseleave", lambda _=None: on_approach_hover(None))

    def _build_show_frozen(self) -> None:
        self.show_frozen = ui.element("div").classes("rtt-show-frozen").mark("showfrozen")
        with self.show_frozen:
            with ui.element("div").classes("rtt-show-all"):
                self.select_all_box = (
                    ui.checkbox(
                        "select all / none",
                        value=all(self.editor.settings[k] for k in show_settings.IMPLEMENTED),
                        on_change=lambda e: self.on_select_all(e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark("showall")
                    .tooltip(tooltips.CHROME_HELP["select_all"])
                )
                self.dark_btn = (
                    ui.button(on_click=self.on_dark_toggle, color=None)
                    .props(f"flat dense round icon={self._dark_icon()}")
                    .classes("rtt-darktoggle")
                    .mark("darkmode")
                    .tooltip(tooltips.CHROME_HELP["dark_mode"])
                )

    def _build_chapter_group(self) -> None:
        with ui.element("div").classes("rtt-show-group rtt-chapter-group"):
            with ui.element("div").classes("rtt-chapter-head"):
                ui.label("guide chapter").classes("rtt-chapter-title")
                self.chapter_reading = (
                    ui.label(self._chapter_reading(self.chapter[0]))
                    .classes("rtt-chapter-reading")
                    .mark("chapterreading")
                )
            self.chapter_slider = (
                ui.slider(
                    min=show_settings.CHAPTER_MIN,
                    max=show_settings.CHAPTER_STAR,
                    step=1,
                    value=self.chapter[0],
                    on_change=lambda e: self.on_chapter_change(e.value),
                )
                .props("markers snap dense color=grey-8")
                .classes("rtt-chapter-slider")
                .mark("chapterslider")
                .tooltip(tooltips.CHROME_HELP["chapter"])
            )

    def _tile_part(self, key, html, *, marked=False, size=None, style=""):
        fs = size if size is not None else _TILE_FONT.get(key)
        css = (f"font-size:{fs}px;" if fs else "") + style
        el = ui.html(html).classes("rtt-tile-part").tooltip(tooltips.SHOW_HELP[key])
        if key == "mnemonics":
            el.classes(add="rtt-tile-mnem")
        if marked:
            el.mark(f"showpart:{key}")
        if css:
            el.style(css)
        el.on("click", lambda k=key: self.on_part_click(k))
        self.tile_parts.setdefault(key, []).append(el)
        return el

    def _tile_named_part(self, key, *, size=None, style=""):
        return self._tile_part(key, _general_part_html(key), marked=True, size=size, style=style)

    def _build_general_tile(self) -> None:
        ui.label("tile features").classes("rtt-show-tiletitle").mark("tiletitle")
        with ui.element("div").classes("rtt-show-tile"):
            with ui.element("div").classes("rtt-tile-head"):
                ui.html(_tile_fold_html()).classes("rtt-tile-fold")
                self.refs["audio_bank"] = _audio_bank()
            for line in _GENERAL_TILE_LINES:
                if "gridded_values" in line:
                    self._build_tile_grid_line()
                elif "names" in line:
                    before, _letter, after = _tile_name_pieces()
                    with ui.element("div").classes("rtt-tile-line"):
                        self._tile_part("names", _escape(before), marked=True)
                        self._tile_named_part("mnemonics")
                        self._tile_part("names", _escape(after))
                elif "presets" in line:
                    with (
                        ui.element("div").classes("rtt-tile-line rtt-tile-line-wide"),
                        ui.element("div").classes("rtt-tile-cbox"),
                    ):
                        self._tile_named_part("presets")
                else:
                    with ui.element("div").classes("rtt-tile-line"):
                        for key in line:
                            self._tile_named_part(key)

    def _build_tile_grid_line(self) -> None:
        gut = 20
        hgut = 18
        cell_x = hgut + gut + _TILE_CELL_X
        cell_y = _TILE_CELL_Y
        row_y = cell_y + (_TILE_CELL - 13) // 2
        with (
            ui.element("div").classes("rtt-tile-line"),
            ui.element("div").style(
                f"position:relative;"
                f"width:{hgut + gut + _TILE_FRAME_W + gut + hgut}px;height:{_TILE_FRAME_H}px"
            ),
        ):
            self._tile_named_part(
                "drag_to_combine",
                size=15,
                style=f"position:absolute;left:0;top:{cell_y}px;width:{hgut}px;"
                f"height:{_TILE_CELL}px;justify-content:center",
            )
            self._tile_part(
                "header_symbols",
                _general_part_html("header_symbols"),
                marked=True,
                size=_TILE_FONT["rowlabel"],
                style=f"position:absolute;left:{hgut}px;top:{row_y}px;width:{gut - 3}px;"
                "height:13px;justify-content:flex-end",
            )
            self._tile_named_part(
                "gridded_values",
                style=f"position:absolute;left:{hgut + gut}px;top:0",
            )
            self._tile_value_stack(cell_x, cell_y)

    def _tile_value_stack(self, cell_x, cell_y) -> None:
        self._tile_named_part(
            "math_expressions",
            size=_fit_font(_TILE_MATH, _TILE_CELL),
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 1}px;"
            f"width:{_TILE_CELL}px;height:9px;justify-content:center",
        )
        self._tile_named_part(
            "quantities",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 10}px;"
            f"width:{_TILE_CELL}px;height:11px;justify-content:center",
        )
        self._tile_named_part(
            "decimals",
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 20}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center",
        )
        self._tile_part(
            "cell_units",
            _general_part_html("cell_units"),
            marked=True,
            size=_TILE_FONT["cellunit"],
            style=f"position:absolute;left:{cell_x}px;top:{cell_y + 28}px;"
            f"width:{_TILE_CELL}px;height:8px;justify-content:center;color:#555",
        )

    def _build_show_group(self, items) -> None:
        with ui.element("div").classes("rtt-show-head"):
            ui.label("show").classes("rtt-show-title")
            ui.label("example").classes("rtt-show-examplehdr")
        for key, label, _ in items:
            row = ui.element("div").classes("rtt-show-row").mark(f"showrow:{key}")
            with row:
                box = (
                    ui.checkbox(
                        label,
                        value=self.editor.settings[key],
                        on_change=lambda e, k=key: self.on_show_toggle(k, e.value),
                    )
                    .props("dense size=xs color=grey-8")
                    .classes("rtt-show-item")
                    .mark(f"showbox:{key}")
                    .tooltip(tooltips.SHOW_HELP[key])
                )
                example = (
                    ui.html(_example_html(key)).classes("rtt-ex-cell").mark(f"showexample:{key}")
                )
            self.boxes[key] = box
            self.examples[key] = example
            self.show_rows[key] = row
            parent = show_settings.SUBCONTROLS.get(key)
            if parent:
                box.style(f"margin-left:{show_settings.depth_of(key) * 18}px")
                row.bind_visibility_from(self.boxes[parent], "value")

    def _size_panes(self, lay, fx, fy) -> None:
        base_w = lay.width + lay.right_overhang + 2 * _PAD
        base_h = lay.height + 2 * _PAD
        self.grid_pane.style(f"width:{base_w}px; height:{base_h}px")
        fit_w = lay.width + 2 * _PAD
        self.grid_pane.props(f'data-base-w="{base_w}" data-base-h="{base_h}" data-fit-w="{fit_w}"')
        self.board.style(f"width:{lay.width}px; height:{lay.height - fy}px")
        self.colhead.style(f"height:{fy}px")
        self.colhead_inner.style(f"width:{lay.width}px; height:{fy}px")
        self.corner.style(f"width:{fx}px; height:{fy}px")
        self.gridbody.style(f"top:{_PAD + fy}px")
        self.rowband.style(f"width:{fx}px; height:{lay.height - fy}px")
        self.show_frozen.style(f"height:{max(0, fy - _CHROME_H)}px")
        self.show_scroll.style(f"max-height:calc(100vh - {_PAD + fy}px)")

    def _render_lines(self, lay, fx, fy, seen) -> None:
        def place_line(ln, suffix, parent, shift):
            eid = ln.id + suffix
            seen.add(eid)
            if eid not in self.rec.els:
                with parent:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    self.rec.els[eid] = ui.element("div").classes(cls).props(f'data-eid="{eid}"')
            sty = _line_style(ln, shift)
            if self.rec.styled.get(eid) != sty:  # only restyle a line that actually moved
                self.rec.els[eid].style(sty)
                self.rec.styled[eid] = sty

        for ln in lay.lines:
            x0, x1 = (ln.pos, ln.pos) if ln.orientation == "v" else (ln.start, ln.start + ln.length)
            y0, y1 = (ln.start, ln.start + ln.length) if ln.orientation == "v" else (ln.pos, ln.pos)
            if x1 >= fx and y1 >= fy:
                place_line(ln, "", self.board, fy)
            if x1 >= fx and y0 < fy:
                place_line(ln, "#col", self.colhead_inner, 0)
            if x0 < fx and y1 >= fy:
                place_line(ln, "#row", self.rowband, fy)

    def _render_blocks(self, lay, fx, fy, seen) -> None:
        def place_block(bl, pane):
            suffix = "" if pane == "body" else "#" + pane
            shift = 0 if pane in ("col", "corner") else fy
            eid = bl.id + suffix
            seen.add(eid)
            if eid not in self.rec.els:
                with self.cell_parents[pane]:
                    cls = (
                        "rtt-block-boxed"
                        if bl.boxed
                        else "rtt-washbase"
                        if bl.tint == "base"
                        else "rtt-wash"
                        if bl.tint
                        else "rtt-block"
                    )
                    self.rec.els[eid] = (
                        ui.element("div").classes(cls).props(f'data-eid="{eid}"').mark(eid)
                    )
            # position via transform:translate (anchored at left:0;top:0), so a wash/box that SHIFTS
            # on a reflow rides the compositor like the cells; its size (a wash growing to cover a new
            # column) stays on width/height — unavoidably a layout op, but the shift is the common case.
            style = f"left:0; top:0; transform:translate({bl.x}px,{bl.y - shift}px); width:{bl.w}px; height:{bl.h}px"
            if bl.tint in _TINTS:
                style += f"; background:var(--wash-{bl.tint})"
            if (
                self.rec.styled.get(eid) != style
            ):  # only restyle a block that actually moved/recoloured
                self.rec.els[eid].style(style)
                self.rec.styled[eid] = style

        for bl in lay.blocks:
            for pane in _block_panes(bl, fx, fy):
                place_block(bl, pane)

    def _sync_mean_damage_tips(self) -> None:
        mean_damage_help_text = tooltips.mean_damage_help(
            service.is_all_interval(self.editor.tuning_scheme)
        )
        for cid in tooltips.MEAN_DAMAGE_IDS:
            if cid in self.rec.mean_damage_tips:
                self.rec.mean_damage_tips[cid].set_text(mean_damage_help_text)
                continue
            wrap = self.rec.els.get(cid)
            if wrap is not None and wrap._props.get("data-zoomhelp") != mean_damage_help_text:
                wrap._props["data-zoomhelp"] = mean_damage_help_text
                wrap.update()

    def _sync_chrome(self, lay, fy) -> None:
        self.refs["undo"].set_enabled(self.editor.can_undo)
        self.refs["redo"].set_enabled(self.editor.can_redo)
        self.refs["reset"].set_enabled(
            self.editor.can_reset or self.chapter[0] != show_settings.CHAPTER_DEFAULT
        )
        if self.chapter_slider.value != self.chapter[0]:
            self.chapter_slider.value = self.chapter[0]
        if lay.approach_box is not None:
            ax, ay, aw, ah = lay.approach_box
            self.refs["approach"].style(
                f"position:absolute; left:{ax}px; top:{ay - fy}px; width:{aw}px; height:{ah}px"
            )
            self.refs["approach"].set_visibility(True)
        else:
            self.refs["approach"].set_visibility(False)
        for key, opt in self.refs["approach_opts"].items():
            (
                opt.classes(add="rtt-rangeopt-on")
                if key == self.editor.nonprime_basis_approach
                else opt.classes(remove="rtt-rangeopt-on")
            )
        for key, box in self.boxes.items():
            if box.value != self.editor.settings[key]:
                box.value = self.editor.settings[key]
        for key, parts in self.tile_parts.items():
            shown = (
                self.editor.settings["names"] if key == "mnemonics" else self.editor.settings[key]
            )
            host = _TILE_HOST.get(key)
            inert = host is not None and not self.editor.settings[host]
            for part in parts:
                part.classes(
                    add="rtt-part-on" if shown else "rtt-part-off",
                    remove="rtt-part-off" if shown else "rtt-part-on",
                )
                part.classes(add="rtt-part-inert") if inert else part.classes(
                    remove="rtt-part-inert"
                )
                if key == "mnemonics":
                    part.classes(add="rtt-mnem-underline") if self.editor.settings[
                        "mnemonics"
                    ] else part.classes(remove="rtt-mnem-underline")
        self._sync_show_availability()
        gesture_idle = self.rec.gesture is None or self.rec.gesture.token is None
        if gesture_idle and not (self.load_failed[0] and not self.editor.can_undo):
            _doc_store()[_STORE_KEY] = self.editor.serialize()

    def _make_cell_if_new(self, cb, fx, fy, cold) -> str:
        if cb.id in self.rec.els and self.rec.kinds[cb.id] != cb.kind:
            self.rec.drop(cb.id)
        container = _freeze_container(cb, fx, fy)
        if cb.id not in self.rec.els:
            with self.cell_parents[container]:
                self.rec.make_cell(cb)
            # two-step entrance: a cell BORN on an incremental render (not the cold first paint)
            # is WITHHELD (.rtt-withhold → opacity 0) while the existing cells slide to open the
            # room, and only fades in once the reflow has SETTLED. A retuning commit can render in
            # stages (the handler's render, then the off-loop retune render), so a fixed delay
            # would reveal it mid-expansion — instead rttScheduleReveal (pushed at the end of every
            # render) debounces the reveal, firing one beat after renders STOP. The cold paint has
            # no room to make, and a PENDING draft must be typeable at once, so neither is withheld.
            if not cold and not cb.pending:
                self.rec.els[cb.id].classes(add="rtt-withhold")
        return container

    def _update_cell_content(self, cb) -> None:
        # content depends on the cell's value fields AND its w/h (width-fitted faces re-fit on
        # resize), so the signature carries both; audio rides along (a retune rebakes the pitch).
        # BUT an interactive cell — one carrying an input, select, checkbox or fraction-mode box —
        # can have its DOM changed by the USER (typing) or hover JS between renders, so its cached
        # signature no longer reflects the live DOM. Such a cell is always re-asserted, so an
        # improper-commit REVERT restores the box even though its value is unchanged from the last
        # render (the bug that surfaced here). Read-only display cells — the vast majority — are
        # only the server's to change, so the cache safely skips them.
        csig = (spreadsheet_text._cell_content(cb), cb.w, cb.h, cb.audio)
        volatile = any(
            cb.id in d
            for d in (
                self.rec.inputs,
                self.rec.den_inputs,
                self.rec.ptext_inputs,
                self.rec.selects,
                self.rec.checks,
                self.rec.frac_edits,
                self.rec.ratio_ops,
            )
        )
        if volatile or self.rec.content_sig.get(cb.id) != csig:
            self.rec.update_cell(cb)
            self.rec.content_sig[cb.id] = csig

    def _render_cells(self, lay, fx, fy, seen, amber, red, cold) -> None:
        for cb in lay.cells:
            seen.add(cb.id)
            container = self._make_cell_if_new(cb, fx, fy, cold)
            # body + row cells live in the scroll space (shifted up by fy); column + corner cells
            # keep native coords in their frozen strip / corner. Each reconcile step (reposition,
            # refresh content, repaint rings) runs only when its own signature changed, so an
            # interaction that moves a handful of cells doesn't re-run the whole page's per-cell work.
            top = cb.y - (fy if container in ("body", "row") else 0)
            # position via transform:translate (anchored at the container origin) rather than left/top,
            # so a reflow animates on the COMPOSITOR (the .rtt-cell transition rides `transform`) instead
            # of left/top — which would re-run layout every frame for every moving cell, the jank when a
            # basis/column change shifts most of the grid at once. Size still rides width/height.
            geo = f"left:0; top:0; transform:translate({cb.x}px,{top}px); width:{cb.w}px; height:{cb.h}px"
            if self.rec.styled.get(cb.id) != geo:
                self.rec.els[cb.id].style(geo)
                self.rec.styled[cb.id] = geo
            self._update_cell_content(cb)
            self.paint_cell(cb.id, amber, red)  # self-guards on ring_sig (no-op when unchanged)

        for eid in [e for e in self.rec.els if e not in seen]:
            self.rec.drop(eid)

    def _end_stale_gestures(self) -> None:
        # Renders end gestures that don't render: a render arriving while a hover / chooser /
        # temp / drag gesture is live — and NOT initiated by that gesture's own handler
        # (gesture_render) — is by definition an external commit or unrelated rebuild, so the
        # gesture ends here, structurally, whatever path the commit took (act, a chooser's
        # on_change, a Show toggle, the debounced target commit...). end_gesture restores a held
        # token FIRST, so the layout below builds from the real document. The edit/wheel gestures
        # legitimately render mid-gesture (their commits) and end on blur/mouseleave instead —
        # but any doc-moving render consumes a pending edit candidate (it is stale once the doc
        # moves; the baseline diff takes over, and no hypothetical solve runs inside a commit).
        g = self.rec.gesture
        if g is not None and not self.gesture_rendering[0]:
            if g.kind in ("hover", "chooser", "temp", "drag"):
                self.end_gesture()
            else:
                g.apply = None
        if not self.rank_rendering[0]:
            self.rank_remove[0] = None

    def _validate_gesture_source(self, lay) -> None:
        g = self.rec.gesture
        if g is not None and g.source is not None:
            src_kind = next((cb.kind for cb in lay.cells if cb.id == g.source), None)
            if src_kind is None or (
                g.source in self.rec.kinds and self.rec.kinds[g.source] != src_kind
            ):
                self.end_gesture()

    def render(self):
        self._end_stale_gestures()
        self.building[0] = True
        try:
            self.apply_view_classes()
            prev = self.last_lay[0].identities if self.last_lay[0] is not None else None
            cold = self.last_lay[0] is None  # the first render: every cell is new, so it must NOT
            #                                     stagger (no room to make yet) — the whole grid paints at once
            lay = self.editor.layout(prev_ids=prev, preview_remove=self.rank_remove[0])
            self.last_lay[0] = lay
            fx, fy = lay.freeze_x, lay.freeze_y
            self._size_panes(lay, fx, fy)
            seen = set()

            self._render_lines(lay, fx, fy, seen)
            self._render_blocks(lay, fx, fy, seen)
            self._validate_gesture_source(lay)
            amber, red = self.compute_rings(lay)
            self._render_cells(lay, fx, fy, seen, amber, red, cold)
            self._sync_mean_damage_tips()
            self._sync_chrome(lay, fy)
        finally:
            self.building[0] = False
        # clear the busy scrim: this render is the result the user was waiting on, so whatever the
        # client armed (see _BUSY_JS) comes down now. The message rides out with this render's DOM
        # patch, so the scrim stays up across the patch and lifts once the new grid is on screen.
        # Skipped under the User test harness, where there's no live client (and run_javascript from
        # inside a handler-driven render hits a torn-down slot context); the scrim is browser-only.
        if not helpers.is_user_simulation():
            self.page_client.run_javascript(
                "window.rttBusy && window.rttBusy.done();"
                " window.rttScheduleReveal && window.rttScheduleReveal()"
            )

    def toggle_drawer(self):
        self.drawer_open[0] = not self.drawer_open[0]
        self.panelgroup.classes(add="rtt-open") if self.drawer_open[0] else self.panelgroup.classes(
            remove="rtt-open"
        )

    def _pane_chrome(self):
        ui.button(icon="menu", on_click=self.toggle_drawer, color=None).props("flat dense").classes(
            "rtt-hamburger"
        ).tooltip(tooltips.CHROME_HELP["settings"])
        ui.label("D&D's RTT app").classes("rtt-sidetitle")


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
