from __future__ import annotations

from dataclasses import replace

from rtt.app import presets, service
from rtt.app.grid_tables import (
    _FACTOR_GROUP,
    BLANKED_NUMBER_KINDS,
    CELL_FACTORS,
    FORM_CHOOSERS,
    GRIDDED_KINDS,
    PRESET_COPIES,
    PRESETS,
    RINGABLE_KINDS,
    SPINE_COLUMN_GROUP,
    SPINE_COLUMNS,
    SPINE_ROW_GROUP,
    SPINE_ROWS,
    SUPERSPACE_REGION_COLUMNS,
    SUPERSPACE_REGION_ROWS,
)
from rtt.app.layout import Block, CellBox
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BOX_INNER,
    BOX_OUTER,
    CAPTION_LINE,
    COL_W,
    CTRL_LABEL_GAP,
    LBOX_DIM_W,
    OPT_COL_GAP,
    OPTION_BOX_PX,
    PAD,
    PRESET_H,
    PRESET_W,
    SCHEME_BTN_SQ,
    SCHEME_LABEL_W,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_text import _fold_glyph, _pretransform_label


class _ControlsMixin:
    def tile_groups(self, rkey: str, ckey: str):
        region = set()
        if rkey == "canon" or ckey == "canongens":
            region |= {"temperament", "form"}
        if rkey in ("projection", "tuning"):
            region |= {"tuning"}
        if self.show_unchanged and ckey == "commas":
            return {"temperament", "tuning"} | region
        if rkey in SPINE_ROWS and ckey in SPINE_COLUMN_GROUP:
            return self._as_groups(SPINE_COLUMN_GROUP[ckey]) | region
        if ckey in SPINE_COLUMNS and rkey in SPINE_ROW_GROUP:
            return self._as_groups(SPINE_ROW_GROUP[rkey]) | region
        if ckey in SUPERSPACE_REGION_COLUMNS or rkey in SUPERSPACE_REGION_ROWS:
            groups = {"tuning"}
            if SPINE_COLUMN_GROUP.get(ckey) == "temperament":
                groups.add("temperament")
            return groups | region
        return {_FACTOR_GROUP[f] for f in CELL_FACTORS.get((rkey, ckey), ())} | region

    @staticmethod
    def _as_groups(g):
        return {g} if isinstance(g, str) else set(g)

    @staticmethod
    def _is_sole_option(options, value) -> bool:
        opts = options if isinstance(options, dict) else {o: o for o in options}
        return len(opts) == 1 and value in opts

    def _preset_locked(self, name: str) -> bool:
        if name == "tuning":
            options = presets.tuning_scheme_options(
                service.is_all_interval(self.tuning_scheme),
                self.settings["alt_complexity"], self.settings["weighting"])
            return self._is_sole_option(options, self.displayed_tuning_name)
        if name == "prescaler":
            return self._is_sole_option(presets.prescaler_options(self.settings["alt_complexity"]),
                                        self._realized_prescaler)
        if name == "projection":
            return not presets.projection_options(self.state)
        return False

    def control_box(self, box_id: str, ckey: str, top, cap_w, label, disabled: bool = False,
                    scheme_btn: bool = False, form_chooser=None):
        form_label = form_chooser[1] if form_chooser else None
        dropdown_w, label_h, box_h = self.control_dims(ckey, cap_w, label, scheme_btn, form_label)
        box_x, box_y = self.col_x[ckey], top + BOX_OUTER
        self.blocks.append(Block(box_id, box_x, box_y, self.col_w[ckey], box_h, boxed=True))
        ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER
        if scheme_btn:
            self.emit_scheme_button(ctrl_x, ctrl_y, ckey)
            ctrl_y += SCHEME_BTN_SQ + CTRL_LABEL_GAP
        if label:
            self.cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                                 "caption", text=label, align="left", disabled=disabled))
        if form_chooser:
            fid, fcap = form_chooser
            form_y = ctrl_y + PRESET_H + label_h + BAND_GAP
            self.cells.append(CellBox(fid, ctrl_x, form_y, dropdown_w, PRESET_H, "formchooser",
                                 text=self.mapping_form_key if fid.endswith(":mapping") else self.comma_basis_form_key))
            self.cells.append(CellBox(f"{fid}:label", ctrl_x, form_y + PRESET_H, dropdown_w, CAPTION_LINE,
                                 "caption", text=fcap, align="left"))
        return ctrl_x, dropdown_w, ctrl_y

    def _preset_form_label(self, name: str, rkey: str, ckey: str):
        embeds = (name == "temperament" and self.show_form_controls
                  and any(rk == rkey and ck == ckey for _n, rk, ck, _l in FORM_CHOOSERS))
        return "form" if embeds else None

    def control_region(self, box_id: str, ckey: str, top, content_h):
        box_y = top + BOX_OUTER
        self._control_region_boxes.append(Block(box_id, self.col_x[ckey], box_y, self.col_w[ckey],
                                                 2 * BOX_INNER + content_h, boxed=True))
        return self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER

    def control_region_band_h(self, content_h):
        return 2 * BOX_OUTER + 2 * BOX_INNER + content_h

    def emit_all_interval_check(self, check_x, ctrl_y) -> None:
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2
        self.cells.append(CellBox("control:all_interval", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.is_all_interval(self.tuning_scheme)))
        self.cells.append(CellBox("caption:all_interval", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="all-interval"))

    def emit_scheme_button(self, x, y, ckey: str) -> None:
        self.cells.append(CellBox(f"scheme:{ckey}", x, y, SCHEME_BTN_SQ, SCHEME_BTN_SQ, "scheme_button", text="✕"))
        label_y = y + (SCHEME_BTN_SQ - CAPTION_LINE) / 2
        self.cells.append(CellBox(f"scheme:{ckey}:label", x + SCHEME_BTN_SQ + 2, label_y, SCHEME_LABEL_W,
                             CAPTION_LINE, "caption", text="return to scheme", align="left"))

    def emit_diminuator_check(self, check_x, ctrl_y) -> None:
        check_y = ctrl_y + (PRESET_H - OPTION_BOX_PX) / 2
        self.cells.append(CellBox("control:diminuator", check_x, check_y, LBOX_DIM_W, OPTION_BOX_PX,
                             "control_check", text="", checked=service.diminuator_replaced(self.tuning_scheme)))
        self.cells.append(CellBox("caption:diminuator", check_x, check_y + OPTION_BOX_PX, LBOX_DIM_W,
                             CAPTION_LINE, "caption", text="replace diminuator"))

    def _emit_preset(self, preset_text, cid, name, rkey, ckey, label):
        if not self.tile_open(rkey, ckey):
            return
        if self.size_factor or self.prescaler_is_matrix:
            label = _pretransform_label(label)
        top = self.ptext_band_y(rkey) + self.rows[rkey].ptext
        disabled = (name == "target" and service.is_all_interval(self.tuning_scheme)) \
            or self._preset_locked(name)
        fc = next((fn for fn, rk, ck, _l in FORM_CHOOSERS if rk == rkey and ck == ckey), None)
        form_chooser = (f"formchooser:{fc}", "form") if (fc and self._preset_form_label(name, rkey, ckey)) else None
        cx, cw, cy = self.control_box(f"block:{cid}", ckey, top, self.preset_cap(name), label,
                                      disabled=disabled, scheme_btn=(name == "projection"),
                                      form_chooser=form_chooser)
        self.cells.append(CellBox(cid, cx, cy, cw, PRESET_H, "preset", text=preset_text[name],
                             disabled=disabled))
        if name == "target" and self.settings["all_interval"]:
            self.emit_all_interval_check(cx + cw + OPT_COL_GAP, cy)
        if name == "prescaler" and self.settings["alt_complexity"]:
            self.emit_diminuator_check(cx + cw + OPT_COL_GAP, cy)

    def _emit_presets(self) -> None:
        if not self.show_presets:
            return
        preset_text = {"temperament": "", "target": self.target_spec,
                          "tuning": service.base_scheme_name(self.tuning_scheme) or "",
                          "prescaler": self._realized_prescaler or "",
                          "projection": self.displayed_projection_name or ""}
        for name, rkey, ckey, label in PRESETS:
            col = "ssprimes" if name == "prescaler" and self.show_superspace else ckey
            self._emit_preset(preset_text, f"preset:{name}", name, rkey, col, label)
        for name, rkey, ckey, label in PRESET_COPIES:
            col = "ssgens" if (name == "tuning" and ckey == "gens"
                               and self.show_superspace_generators) else ckey
            self._emit_preset(preset_text, f"preset:{name}:{col}", name, rkey, col, label)

    def _emit_all_interval_check_fallback(self) -> None:
        if self.settings["all_interval"] and not self.show_presets and self.tile_open("vectors", "targets"):
            top = self.ptext_band_y("vectors") + self.rows["vectors"].ptext
            self.emit_all_interval_check(self.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)

    def _emit_form_choosers(self) -> None:
        if self.show_form_controls and not self.show_presets:
            for name, rkey, ckey, label in FORM_CHOOSERS:
                if not self.tile_open(rkey, ckey):
                    continue
                top = self.ptext_band_y(rkey) + self.rows[rkey].ptext + self.rows[rkey].pre
                cx, cw, cy = self.control_box(f"block:formchooser:{name}", ckey, top, PRESET_W, label)
                self.cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser",
                                     text=self.mapping_form_key if name == "mapping" else self.comma_basis_form_key))

    def _emit_scheme_buttons(self) -> None:
        if self.settings["projection"] and not self.show_presets:
            for ckey in ("primes", "gens"):
                if not self.tile_open("projection", ckey):
                    continue
                top = self.ptext_band_y("projection") + self.rows["projection"].ptext
                box_y = top + BOX_OUTER
                self.blocks.append(Block(f"block:scheme:{ckey}", self.col_x[ckey], box_y, self.col_w[ckey],
                                         BOX_INNER + SCHEME_BTN_SQ + CTRL_LABEL_GAP, boxed=True))
                self.emit_scheme_button(self.col_x[ckey] + BOX_INNER, box_y + BOX_INNER, ckey)

    def _emit_ptext_band(self) -> None:
        if self.show_ptext:
            for (rkey, ckey), text in self.ptext_strings.items():
                if not self.tile_open(rkey, ckey):
                    continue
                if ((rkey, ckey) == ("vectors", "commas") and self.pending is not None) \
                        or ((rkey, ckey) == ("vectors", "targets") and self.pending_target is not None) \
                        or ((rkey, ckey) == ("mapping", "primes") and self.pending_mapping_row is not None):
                    kind = "ptextpending"
                elif self.ptext_editable(rkey, ckey) and (ckey != "targets" or self.targets_editable):
                    kind = "ptextedit"
                else:
                    kind = "ptext"
                self.cells.append(CellBox(f"ptext:{rkey}:{ckey}", self.col_x[ckey], self.ptext_band_y(rkey),
                                     self.col_w[ckey], self.ptext_height(rkey, ckey), kind, text=text))

    def _emit_tile_toggles(self) -> None:
        for _bid, rkey, ckey in self.tiles:
            if ((rkey, ckey) in self.declared_tiles
                    and rkey in self.rows and ckey in self.col_x and self.row_open(rkey) and self.col_open(ckey)):
                glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in self.collapsed)
                tog_x, _tw = self.tile_span_box(rkey, ckey)
                self.cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                     tog_x - PAD + TOGGLE_INSET, self.rows[rkey].tile_top - PAD + TOGGLE_INSET,
                                     TOGGLE, TOGGLE, "tiletoggle", text=glyph))

    def _filter_gridded_quantities(self) -> None:
        if not self.gridded:
            self.cells = [cb for cb in self.cells if cb.kind not in GRIDDED_KINDS]
        elif not self.show_quantities:
            self.cells = [replace(cb, blank=True, text="") if cb.kind in BLANKED_NUMBER_KINDS else cb
                     for cb in self.cells]

    def _mark_doomed_unchanged_column(self) -> None:
        if (self.pending is not None or self.ghost_comma) and self.show_unchanged and self.nu:
            doomed_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, preview_remove=True)
                          if (cb.w == COL_W and cb.x == doomed_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

    def _mark_born_column(self) -> None:
        if self.born_u:
            born_x = self.comma_left(self.nc_shown + self.nu - 1)
            self.cells = [replace(cb, pending=True)
                          if (cb.w == COL_W and cb.x == born_x
                              and cb.kind not in ("count", "caption", "colgrip"))
                          else cb
                          for cb in self.cells]

    @staticmethod
    def _dual_preview(cb, axes):
        remove_rows, red_xs, change_rows, amber_xs = axes
        if cb.kind not in RINGABLE_KINDS or cb.preview_remove:
            return cb
        if cb.gen in remove_rows or cb.x in red_xs:
            return replace(cb, preview_remove=True, pending=False)
        if cb.pending:
            return cb
        if cb.gen in change_rows or cb.x in amber_xs:
            return replace(cb, preview_change=True)
        return cb

    def _mark_dual_axis_previews(self) -> None:
        remove_rows = change_rows = remove_commas = change_commas = frozenset()
        if self.pending is not None and self.r:
            remove_rows, change_rows = frozenset({self.r - 1}), frozenset(range(self.r - 1))
        if self.pending_mapping_row is not None and self.nc:
            remove_commas, change_commas = frozenset({self.nc - 1}), frozenset(range(self.nc - 1))
        if self.preview_remove is not None:
            axis, idx = self.preview_remove
            if axis == "comma":
                remove_commas, change_rows = frozenset({idx}), frozenset(range(self.r))
            else:
                remove_rows, change_commas = frozenset({idx}), frozenset(range(self.nc))
        if remove_rows or change_rows or remove_commas or change_commas:
            red_xs = frozenset(self.comma_left(c) for c in remove_commas)
            amber_xs = frozenset(self.comma_left(c) for c in change_commas)
            axes = (remove_rows, red_xs, change_rows, amber_xs)
            self.cells = [self._dual_preview(cb, axes) for cb in self.cells]

    def _apply_value_display_filters(self) -> None:
        self._filter_gridded_quantities()
        self._mark_doomed_unchanged_column()
        self._mark_born_column()
        self._mark_dual_axis_previews()
