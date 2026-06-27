from __future__ import annotations

from dataclasses import replace

from rtt.app import presets, service, terminology
from rtt.app import spreadsheet_geometry_query as query
from rtt.app.grid_tables import (
    BLANKED_NUMBER_KINDS,
    FORM_CHOOSERS,
    GRIDDED_KINDS,
    PRESET_COPIES,
    PRESETS,
    RINGABLE_KINDS,
)
from rtt.app.layout import Block, CellBox
from rtt.app.spreadsheet_constants import (
    BAND_GAP,
    BOX_INNER,
    BOX_OUTER,
    CAPTION_LINE,
    COL_W,
    OPT_COL_GAP,
    PAD,
    PRESET_H,
    PRESET_W,
    SCHEME_BTN_SQ,
    SCHEME_LABEL_W,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _fold_glyph, _pretransform_label, emit_option_check


def transform_cells(cells, resolved, geometry, ctx) -> tuple:
    cells = _filter_gridded_quantities(cells, resolved)
    cells = _mark_doomed_unchanged_column(cells, resolved, geometry)
    cells = _mark_born_column(cells, resolved, geometry)
    cells = _mark_dual_axis_previews(cells, resolved, geometry, ctx)
    return tuple(cells)


def _filter_gridded_quantities(cells, resolved):
    _r = resolved
    if not _r.flags.gridded_values:
        return [cb for cb in cells if cb.kind not in GRIDDED_KINDS]
    if not _r.flags.quantities:
        return [replace(cb, blank=True, text="") if cb.kind in BLANKED_NUMBER_KINDS else cb
                for cb in cells]
    return cells


def _mark_doomed_unchanged_column(cells, resolved, geometry):
    _r = resolved
    if not ((_r.commas.pending is not None or _r.ghosts.comma) and _r.unchanged.shown and _r.dims.nu):
        return cells
    doomed_x = query.comma_left(geometry, _r, _r.dims.nc_shown + _r.dims.nu - 1)
    return [replace(cb, preview_remove=True)
            if (cb.w == COL_W and cb.x == doomed_x
                and cb.kind not in ("count", "caption", "colgrip"))
            else cb
            for cb in cells]


def _mark_born_column(cells, resolved, geometry):
    _r = resolved
    if not _r.unchanged.born:
        return cells
    born_x = query.comma_left(geometry, _r, _r.dims.nc_shown + _r.dims.nu - 1)
    return [replace(cb, pending=True)
            if (cb.w == COL_W and cb.x == born_x
                and cb.kind not in ("count", "caption", "colgrip"))
            else cb
            for cb in cells]


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


def _mark_dual_axis_previews(cells, resolved, geometry, ctx):
    _r = resolved
    remove_rows = change_rows = remove_commas = change_commas = frozenset()
    if _r.commas.pending is not None and _r.dims.r:
        remove_rows, change_rows = frozenset({_r.dims.r - 1}), frozenset(range(_r.dims.r - 1))
    if ctx.pending_mapping_row is not None and _r.dims.nc:
        remove_commas, change_commas = frozenset({_r.dims.nc - 1}), frozenset(range(_r.dims.nc - 1))
    if ctx.preview_remove is not None:
        axis, idx = ctx.preview_remove
        if axis == "comma":
            remove_commas, change_rows = frozenset({idx}), frozenset(range(_r.dims.r))
        else:
            remove_rows, change_commas = frozenset({idx}), frozenset(range(_r.dims.nc))
    if not (remove_rows or change_rows or remove_commas or change_commas):
        return cells
    red_xs = frozenset(query.comma_left(geometry, _r, c) for c in remove_commas)
    amber_xs = frozenset(query.comma_left(geometry, _r, c) for c in change_commas)
    axes = (remove_rows, red_xs, change_rows, amber_xs)
    return [_dual_preview(cb, axes) for cb in cells]


def emit_controls(resolved, geometry, ctx) -> EmitResult:
    cells: list = []
    blocks: list = []
    _emit_presets(cells, blocks, resolved, geometry, ctx)
    _emit_all_interval_check_fallback(cells, resolved, geometry, ctx)
    _emit_form_choosers(cells, blocks, resolved, geometry, ctx)
    _emit_scheme_buttons(cells, blocks, resolved, geometry, ctx)
    _emit_ptext_band(cells, resolved, geometry, ctx)
    return EmitResult(cells=tuple(cells), blocks=tuple(blocks))


def emit_tile_toggles(geometry, ctx) -> EmitResult:
    cells: list = []
    for _bid, rkey, ckey in geometry.tiles:
        if ((rkey, ckey) in geometry.declared_tiles
                and rkey in geometry.rows and ckey in geometry.col_x
                and query.row_open(geometry, ctx.collapsed, rkey) and query.col_open(geometry, ctx.collapsed, ckey)):
            glyph = _fold_glyph(f"tile:{rkey}:{ckey}" in ctx.collapsed)
            tog_x, _tw = query.tile_span_box(geometry, rkey, ckey)
            cells.append(CellBox(f"toggle:tile:{rkey}:{ckey}",
                                 tog_x - PAD + TOGGLE_INSET, geometry.rows[rkey].tile_top - PAD + TOGGLE_INSET,
                                 TOGGLE, TOGGLE, "tiletoggle", text=glyph))
    return EmitResult(cells=tuple(cells))


def _is_sole_option(options, value) -> bool:
    opts = options if isinstance(options, dict) else {o: o for o in options}
    return len(opts) == 1 and value in opts


def _preset_locked(resolved, ctx, name: str) -> bool:
    _r = resolved
    if name == "tuning":
        options = presets.tuning_scheme_options(
            service.is_all_interval(ctx.tuning_scheme),
            ctx.settings["alt_complexity"], ctx.settings["weighting"],
            ctx.settings["terminology"])
        return _is_sole_option(options, _r.scalars.displayed_tuning_name)
    if name == "prescaler":
        return _is_sole_option(presets.prescaler_options(ctx.settings["alt_complexity"]),
                               _r.labels.realized_prescaler)
    if name == "projection":
        return not presets.projection_options(ctx.state)
    return False


def _control_box(cells, blocks, resolved, geometry, box_id: str, ckey: str, top, cap_w, label,
                 disabled: bool = False, scheme_btn: bool = False, form_chooser=None):
    _r = resolved
    form_label = form_chooser[1] if form_chooser else None
    dropdown_w, label_h, box_h = query.control_dims(geometry, ckey, cap_w, label, scheme_btn, form_label)
    box_x, box_y = geometry.col_x[ckey], top + BOX_OUTER
    blocks.append(Block(box_id, box_x, box_y, geometry.col_w[ckey], box_h, boxed=True))
    ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER
    if scheme_btn:
        _emit_scheme_button(cells, ctrl_x, ctrl_y, ckey)
        ctrl_y += SCHEME_BTN_SQ + BAND_GAP
    if label:
        cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                             "caption", text=label, align="left", disabled=disabled))
    if form_chooser:
        fid, fcap = form_chooser
        form_y = ctrl_y + PRESET_H + label_h + BAND_GAP
        cells.append(CellBox(fid, ctrl_x, form_y, dropdown_w, PRESET_H, "formchooser",
                             text=_r.canon.mapping_form_key if fid.endswith(":mapping") else _r.canon.comma_basis_form_key))
        cells.append(CellBox(f"{fid}:label", ctrl_x, form_y + PRESET_H, dropdown_w, CAPTION_LINE,
                             "caption", text=fcap, align="left"))
    return ctrl_x, dropdown_w, ctrl_y


def _emit_scheme_button(cells, x, y, ckey: str) -> None:
    cells.append(CellBox(f"scheme:{ckey}", x, y, SCHEME_BTN_SQ, SCHEME_BTN_SQ, "scheme_button", text="✕"))
    label_y = y + (SCHEME_BTN_SQ - CAPTION_LINE) / 2
    cells.append(CellBox(f"scheme:{ckey}:label", x + SCHEME_BTN_SQ + 2, label_y, SCHEME_LABEL_W,
                         CAPTION_LINE, "caption", text="return to scheme", align="left"))


def _emit_preset(cells, blocks, resolved, geometry, ctx, preset_text, cid, name, rkey, ckey, label):
    _r = resolved
    if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
        return
    if geometry.size_factor or _r.scalars.prescaler_is_matrix:
        label = _pretransform_label(label)
    top = query.ptext_band_y(geometry, rkey) + geometry.rows[rkey].ptext
    disabled = (name == "target" and service.is_all_interval(ctx.tuning_scheme)) \
        or _preset_locked(resolved, ctx, name)
    fc = next((fn for fn, rk, ck, _l in FORM_CHOOSERS if rk == rkey and ck == ckey), None)
    form_chooser = (f"formchooser:{fc}", "form") if (fc and query.preset_form_label(resolved, name, rkey, ckey)) else None
    cx, cw, cy = _control_box(cells, blocks, resolved, geometry, f"block:{cid}", ckey, top, query.preset_cap(name), label,
                              disabled=disabled, scheme_btn=(name == "projection"),
                              form_chooser=form_chooser)
    cells.append(CellBox(cid, cx, cy, cw, PRESET_H, "preset", text=preset_text[name],
                         disabled=disabled))
    if name == "target" and ctx.settings["all_interval"]:
        emit_option_check(cells, "all_interval", "all-interval",
                           service.is_all_interval(ctx.tuning_scheme), cx + cw + OPT_COL_GAP, cy)
    if name == "prescaler" and ctx.settings["alt_complexity"]:
        emit_option_check(cells, "diminuator", "replace diminuator",
                           service.diminuator_replaced(ctx.tuning_scheme), cx + cw + OPT_COL_GAP, cy)


def _emit_presets(cells, blocks, resolved, geometry, ctx) -> None:
    _r = resolved
    if not _r.flags.presets:
        return
    preset_text = {"temperament": "", "target": ctx.target_spec,
                      "tuning": terminology.scheme(
                          service.base_scheme_name(ctx.tuning_scheme),
                          ctx.settings["terminology"]) or "",
                      "prescaler": _r.labels.realized_prescaler or "",
                      "projection": _r.scalars.displayed_projection_name or ""}
    for name, rkey, ckey, label in PRESETS:
        col = "ssprimes" if name == "prescaler" and _r.flags.superspace else ckey
        _emit_preset(cells, blocks, resolved, geometry, ctx, preset_text, f"preset:{name}", name, rkey, col, label)
    for name, rkey, ckey, label in PRESET_COPIES:
        col = "ssgens" if (name == "tuning" and ckey == "gens"
                           and _r.flags.superspace_generators) else ckey
        _emit_preset(cells, blocks, resolved, geometry, ctx, preset_text, f"preset:{name}:{col}", name, rkey, col, label)


def _emit_all_interval_check_fallback(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if ctx.settings["all_interval"] and not _r.flags.presets and query.tile_open(geometry, ctx.collapsed, "vectors", "targets"):
        top = query.ptext_band_y(geometry, "vectors") + geometry.rows["vectors"].ptext
        emit_option_check(cells, "all_interval", "all-interval",
                           service.is_all_interval(ctx.tuning_scheme),
                           geometry.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)


def _emit_form_choosers(cells, blocks, resolved, geometry, ctx) -> None:
    _r = resolved
    if _r.flags.form_controls and not _r.flags.presets:
        for name, rkey, ckey, label in FORM_CHOOSERS:
            if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
                continue
            top = query.ptext_band_y(geometry, rkey) + geometry.rows[rkey].ptext + geometry.rows[rkey].pre
            cx, cw, cy = _control_box(cells, blocks, resolved, geometry, f"block:formchooser:{name}", ckey, top, PRESET_W, label)
            cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser",
                                 text=_r.canon.mapping_form_key if name == "mapping" else _r.canon.comma_basis_form_key))


def _emit_scheme_buttons(cells, blocks, resolved, geometry, ctx) -> None:
    _r = resolved
    if ctx.settings["projection"] and not _r.flags.presets:
        for ckey in ("primes", "gens"):
            if not query.tile_open(geometry, ctx.collapsed, "projection", ckey):
                continue
            top = query.ptext_band_y(geometry, "projection") + geometry.rows["projection"].ptext
            box_y = top + BOX_OUTER
            blocks.append(Block(f"block:scheme:{ckey}", geometry.col_x[ckey], box_y, geometry.col_w[ckey],
                                2 * BOX_INNER + SCHEME_BTN_SQ, boxed=True))
            _emit_scheme_button(cells, geometry.col_x[ckey] + BOX_INNER, box_y + BOX_INNER, ckey)


def _emit_ptext_band(cells, resolved, geometry, ctx) -> None:
    _r = resolved
    if _r.flags.plain_text_values:
        for (rkey, ckey), text in geometry.ptext_strings.items():
            if not query.tile_open(geometry, ctx.collapsed, rkey, ckey):
                continue
            if ((rkey, ckey) == ("vectors", "commas") and _r.commas.pending is not None) \
                    or ((rkey, ckey) == ("vectors", "targets") and _r.targets.pending is not None) \
                    or ((rkey, ckey) == ("mapping", "primes") and ctx.pending_mapping_row is not None):
                kind = "ptextpending"
            elif query.ptext_editable(_r, rkey, ckey) and (ckey != "targets" or _r.scalars.targets_editable):
                kind = "ptextedit"
            else:
                kind = "ptext"
            cells.append(CellBox(f"ptext:{rkey}:{ckey}", geometry.col_x[ckey], query.ptext_band_y(geometry, rkey),
                                 geometry.col_w[ckey], query.ptext_height(_r, rkey, ckey), kind, text=text))
