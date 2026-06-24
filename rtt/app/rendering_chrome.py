from __future__ import annotations

from rtt.app import service, tooltips
from rtt.app import settings as show_settings
from rtt.app.page_assets import _STORE_KEY, _TILE_HOST, _doc_store


class _ChromeSyncMixin:
    def _sync_mean_damage_tips(self) -> None:
        mean_damage_help_text = tooltips.mean_damage_help(
            service.is_all_interval(self.page.editor.tuning_scheme)
        )
        for cid in tooltips.MEAN_DAMAGE_IDS:
            if self.page.rec.handles(cid).mean_damage_tip is not None:
                self.page.rec.cells[cid].mean_damage_tip.set_text(mean_damage_help_text)
                continue
            wrap = self.page.rec.entity(cid).el
            if wrap is not None and wrap._props.get("data-zoomhelp") != mean_damage_help_text:
                wrap._props["data-zoomhelp"] = mean_damage_help_text
                wrap.update()

    def _sync_pretransform_help(self, pretransform: bool) -> None:
        # a size-sensitizing / matrix-prescaler scheme relabels "prescaler" → "pretransformer" in the
        # grid (effective_captions). The same relabel must reach the help wording: the prescaler-preset
        # tooltip and the 𝑋 tile's guide card. These cells persist across a scheme switch (same id →
        # update_cell, not make_cell), so the relabel is re-applied here every render, mirroring
        # _sync_mean_damage_tips' swap of the mean-damage wording.
        rec = self.page.rec
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
        self.page.refs["undo"].set_enabled(self.page.editor.can_undo)
        self.page.refs["redo"].set_enabled(self.page.editor.can_redo)
        self.page.refs["reset"].set_enabled(
            self.page.editor.can_reset or self.page.chapter != show_settings.CHAPTER_DEFAULT
        )
        if self.page.chapter_slider.value != self.page.chapter:
            self.page.chapter_slider.value = self.page.chapter
        if lay.approach_box is not None:
            ax, ay, aw, ah = lay.approach_box
            self.page.refs["approach"].style(
                f"position:absolute; left:{ax}px; top:{ay - fy}px; width:{aw}px; height:{ah}px"
            )
            self.page.refs["approach"].set_visibility(True)
        else:
            self.page.refs["approach"].set_visibility(False)
        for key, opt in self.page.refs["approach_opts"].items():
            (
                opt.classes(add="rtt-rangeopt-on")
                if key == self.page.editor.nonprime_basis_approach
                else opt.classes(remove="rtt-rangeopt-on")
            )
        for key, box in self.page.boxes.items():
            if box.value != self.page.editor.settings[key]:
                box.value = self.page.editor.settings[key]
        self._sync_tile_parts()
        self.page._sync_show_availability()
        gesture_idle = (
            self.page.gestures.gesture is None or self.page.gestures.gesture.token is None
        )
        if gesture_idle and not (self.page.load_failed and not self.page.editor.can_undo):
            _doc_store()[_STORE_KEY] = self.page.editor.serialize()

    def _sync_tile_parts(self) -> None:
        for key, parts in self.page.tile_parts.items():
            shown = (
                self.page.editor.settings["names"]
                if key == "mnemonics"
                else self.page.editor.settings[key]
            )
            host = _TILE_HOST.get(key)
            inert = host is not None and not self.page.editor.settings[host]
            for part in parts:
                part.classes(
                    add="rtt-part-on" if shown else "rtt-part-off",
                    remove="rtt-part-off" if shown else "rtt-part-on",
                )
                part.classes(add="rtt-part-inert") if inert else part.classes(
                    remove="rtt-part-inert"
                )
                if key == "mnemonics":
                    part.classes(add="rtt-mnem-underline") if self.page.editor.settings[
                        "mnemonics"
                    ] else part.classes(remove="rtt-mnem-underline")
