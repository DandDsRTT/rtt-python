from __future__ import annotations

from rtt.app import service, tooltips
from rtt.app import settings as show_settings
from rtt.app.page_assets import _STORE_KEY, _TILE_HOST, _doc_store


class _ChromeSyncMixin:
    def _sync_mean_damage_tips(self) -> None:
        mean_damage_help_text = tooltips.mean_damage_help(
            service.is_all_interval(self._editor.tuning_scheme)
        )
        for cid in tooltips.MEAN_DAMAGE_IDS:
            if self._rec.handles(cid).mean_damage_tip is not None:
                self._rec.cells[cid].mean_damage_tip.set_text(mean_damage_help_text)
                continue
            wrap = self._rec.entity(cid).el
            if wrap is not None and wrap._props.get("data-zoomhelp") != mean_damage_help_text:
                wrap._props["data-zoomhelp"] = mean_damage_help_text
                wrap.update()

    def _sync_pretransform_help(self, pretransform: bool) -> None:
        rec = self._rec
        for h in rec.cells.values():
            if h.help_tip is not None:
                tip, plain, relabeled = h.help_tip
                tip.set_text(relabeled if pretransform else plain)
        for cid, h in rec.cells.items():
            if h.guide_help_text is None:
                continue
            plain, relabeled = h.guide_help_text
            wrap = rec.entity(cid).el
            text = relabeled if pretransform else plain
            if wrap is not None and wrap._props.get("data-guide-text") != text:
                wrap._props["data-guide-text"] = text
                wrap.update()

    def _sync_chrome(self, lay, fy) -> None:
        self._chrome.refs["undo"].set_enabled(self._editor.can_undo)
        self._chrome.refs["redo"].set_enabled(self._editor.can_redo)
        self._chrome.refs["reset"].set_enabled(
            self._editor.can_reset or self._runtime.chapter != show_settings.CHAPTER_DEFAULT
        )
        if self._chrome.chapter_slider.value != self._runtime.chapter:
            self._chrome.chapter_slider.value = self._runtime.chapter
        if lay.approach_box is not None:
            ax, ay, aw, ah = lay.approach_box
            self._chrome.refs["approach"].style(
                f"position:absolute; left:{ax}px; top:{ay - fy}px; width:{aw}px; height:{ah}px"
            )
            self._chrome.refs["approach"].set_visibility(True)
        else:
            self._chrome.refs["approach"].set_visibility(False)
        for key, opt in self._chrome.refs["approach_opts"].items():
            (
                opt.classes(add="rtt-rangeopt-on")
                if key == self._editor.nonprime_basis_approach
                else opt.classes(remove="rtt-rangeopt-on")
            )
        for key, box in self._chrome.boxes.items():
            if box.value != self._editor.settings[key]:
                box.value = self._editor.settings[key]
        self._sync_tile_parts()
        self._sync_availability()
        gesture_idle = self._gestures.gesture is None or self._gestures.gesture.token is None
        if gesture_idle and not (self._runtime.load_failed and not self._editor.can_undo):
            _doc_store()[_STORE_KEY] = self._editor.serialize()

    def _sync_tile_parts(self) -> None:
        for key, parts in self._chrome.tile_parts.items():
            shown = (
                self._editor.settings["names"] if key == "mnemonics" else self._editor.settings[key]
            )
            host = _TILE_HOST.get(key)
            inert = host is not None and not self._editor.settings[host]
            for part in parts:
                part.classes(
                    add="rtt-part-on" if shown else "rtt-part-off",
                    remove="rtt-part-off" if shown else "rtt-part-on",
                )
                part.classes(add="rtt-part-inert") if inert else part.classes(
                    remove="rtt-part-inert"
                )
                if key == "mnemonics":
                    part.classes(add="rtt-mnem-underline") if self._editor.settings[
                        "mnemonics"
                    ] else part.classes(remove="rtt-mnem-underline")
