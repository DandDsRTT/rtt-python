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
    SCHEME_BUTTON_SQ,
    SCHEME_LABEL_W,
    TOGGLE,
    TOGGLE_INSET,
)
from rtt.app.spreadsheet_emit_model import EmitResult
from rtt.app.spreadsheet_text import _fold_glyph, _pretransform_label, emit_option_check


def transform_cells(cells, resolved, geometry, context) -> tuple:
    cells = _filter_gridded_quantities(cells, resolved)
    cells = _mark_doomed_unchanged_column(cells, resolved, geometry)
    cells = _mark_born_column(cells, resolved, geometry)
    cells = _mark_dual_axis_previews(cells, resolved, geometry, context)
    return tuple(cells)


def _filter_gridded_quantities(cells, resolved):
    if not resolved.flags.gridded_values:
        return [cell_box for cell_box in cells if cell_box.kind not in GRIDDED_KINDS]
    if not resolved.flags.quantities:
        return [replace(cell_box, blank=True, text="") if cell_box.kind in BLANKED_NUMBER_KINDS else cell_box
                for cell_box in cells]
    return cells


def _mark_doomed_unchanged_column(cells, resolved, geometry):
    if not ((resolved.commas.pending is not None or resolved.ghosts.comma) and resolved.unchanged.shown and resolved.dims.unchanged_count):
        return cells
    doomed_x = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + resolved.dims.unchanged_count - 1)
    return [replace(cell_box, preview_remove=True)
            if (cell_box.w == COL_W and cell_box.x == doomed_x
                and cell_box.kind not in ("count", "caption", "colgrip"))
            else cell_box
            for cell_box in cells]


def _mark_born_column(cells, resolved, geometry):
    if not resolved.unchanged.born:
        return cells
    born_x = query.comma_left(geometry, resolved, resolved.dims.comma_count_shown + resolved.dims.unchanged_count - 1)
    return [replace(cell_box, pending=True)
            if (cell_box.w == COL_W and cell_box.x == born_x
                and cell_box.kind not in ("count", "caption", "colgrip"))
            else cell_box
            for cell_box in cells]


def _dual_preview(cell_box, axes):
    remove_rows, red_xs, change_rows, amber_xs = axes
    if cell_box.kind not in RINGABLE_KINDS or cell_box.preview_remove:
        return cell_box
    if cell_box.gen in remove_rows or cell_box.x in red_xs:
        return replace(cell_box, preview_remove=True, pending=False)
    if cell_box.pending:
        return cell_box
    if cell_box.gen in change_rows or cell_box.x in amber_xs:
        return replace(cell_box, preview_change=True)
    return cell_box


def _mark_dual_axis_previews(cells, resolved, geometry, context):
    remove_rows = change_rows = remove_commas = change_commas = frozenset()
    if resolved.commas.pending is not None and resolved.dims.rank:
        remove_rows, change_rows = frozenset({resolved.dims.rank - 1}), frozenset(range(resolved.dims.rank - 1))
    if context.pending_mapping_row is not None and resolved.dims.comma_count:
        remove_commas, change_commas = frozenset({resolved.dims.comma_count - 1}), frozenset(range(resolved.dims.comma_count - 1))
    if context.preview_remove is not None:
        axis, idx = context.preview_remove
        if axis == "comma":
            remove_commas, change_rows = frozenset({idx}), frozenset(range(resolved.dims.rank))
        else:
            remove_rows, change_commas = frozenset({idx}), frozenset(range(resolved.dims.comma_count))
    if not (remove_rows or change_rows or remove_commas or change_commas):
        return cells
    red_xs = frozenset(query.comma_left(geometry, resolved, c) for c in remove_commas)
    amber_xs = frozenset(query.comma_left(geometry, resolved, c) for c in change_commas)
    axes = (remove_rows, red_xs, change_rows, amber_xs)
    return [_dual_preview(cell_box, axes) for cell_box in cells]


def emit_controls(resolved, geometry, context) -> EmitResult:
    cells: list = []
    blocks: list = []
    _emit_presets(cells, blocks, resolved, geometry, context)
    _emit_all_interval_check_fallback(cells, resolved, geometry, context)
    _emit_form_choosers(cells, blocks, resolved, geometry, context)
    _emit_scheme_buttons(cells, blocks, resolved, geometry, context)
    _emit_plain_text_band(cells, resolved, geometry, context)
    return EmitResult(cells=tuple(cells), blocks=tuple(blocks))


def emit_tile_toggles(geometry, context) -> EmitResult:
    cells: list = []
    for _bid, row_key, column_key in geometry.tiles:
        if ((row_key, column_key) in geometry.declared_tiles
                and row_key in geometry.rows and column_key in geometry.col_x
                and query.row_open(geometry, context.collapsed, row_key) and query.col_open(geometry, context.collapsed, column_key)):
            glyph = _fold_glyph(f"tile:{row_key}:{column_key}" in context.collapsed)
            tog_x, _tw = query.tile_span_box(geometry, row_key, column_key)
            cells.append(CellBox(f"toggle:tile:{row_key}:{column_key}",
                                 tog_x - PAD + TOGGLE_INSET, geometry.rows[row_key].tile_top - PAD + TOGGLE_INSET,
                                 TOGGLE, TOGGLE, "tiletoggle", text=glyph))
    return EmitResult(cells=tuple(cells))


def _is_sole_option(options, value) -> bool:
    opts = options if isinstance(options, dict) else {o: o for o in options}
    return len(opts) == 1 and value in opts


def _preset_locked(resolved, context, name: str) -> bool:
    if name == "tuning":
        options = presets.tuning_scheme_options(
            service.is_all_interval(context.tuning_scheme),
            context.settings["alt_complexity"], context.settings["weighting"],
            context.settings["terminology"])
        return _is_sole_option(options, resolved.scalars.displayed_tuning_name)
    if name == "prescaler":
        return _is_sole_option(presets.prescaler_options(context.settings["alt_complexity"]),
                               resolved.labels.realized_prescaler)
    if name == "projection":
        return not presets.projection_options(context.state)
    return False


def _control_box(cells, blocks, resolved, geometry, box_id: str, column_key: str, top, cap_w, label,
                 disabled: bool = False, scheme_button: bool = False, form_chooser=None):
    form_label = form_chooser[1] if form_chooser else None
    dropdown_w, label_h, box_h = query.control_dims(geometry, column_key, cap_w, label, scheme_button, form_label)
    box_x, box_y = geometry.col_x[column_key], top + BOX_OUTER
    blocks.append(Block(box_id, box_x, box_y, geometry.col_w[column_key], box_h, boxed=True))
    ctrl_x, ctrl_y = box_x + BOX_INNER, box_y + BOX_INNER
    if scheme_button:
        _emit_scheme_button(cells, ctrl_x, ctrl_y, column_key)
        ctrl_y += SCHEME_BUTTON_SQ + BOX_INNER
    if label:
        cells.append(CellBox(f"{box_id}:label", ctrl_x, ctrl_y + PRESET_H, dropdown_w, label_h,
                             "caption", text=label, align="left", disabled=disabled))
    if form_chooser:
        fid, fcap = form_chooser
        form_y = ctrl_y + PRESET_H + label_h + BAND_GAP
        cells.append(CellBox(fid, ctrl_x, form_y, dropdown_w, PRESET_H, "formchooser",
                             text=resolved.canon.mapping_form_key if fid.endswith(":mapping") else resolved.canon.comma_basis_form_key))
        cells.append(CellBox(f"{fid}:label", ctrl_x, form_y + PRESET_H, dropdown_w, CAPTION_LINE,
                             "caption", text=fcap, align="left"))
    return ctrl_x, dropdown_w, ctrl_y


def _emit_scheme_button(cells, x, y, column_key: str) -> None:
    cells.append(CellBox(f"scheme:{column_key}", x, y, SCHEME_BUTTON_SQ, SCHEME_BUTTON_SQ, "scheme_button", text="✕"))
    label_y = y + (SCHEME_BUTTON_SQ - CAPTION_LINE) / 2
    cells.append(CellBox(f"scheme:{column_key}:label", x + SCHEME_BUTTON_SQ + 2, label_y, SCHEME_LABEL_W,
                         CAPTION_LINE, "caption", text="return to scheme", align="left"))


def _emit_preset(cells, blocks, resolved, geometry, context, preset_text, cid, name, row_key, column_key, label):
    if not query.tile_open(geometry, context.collapsed, row_key, column_key):
        return
    if geometry.size_factor or resolved.scalars.prescaler_is_matrix:
        label = _pretransform_label(label)
    top = query.plain_text_band_y(geometry, row_key) + geometry.rows[row_key].plain_text
    disabled = (name == "target" and service.is_all_interval(context.tuning_scheme)) \
        or _preset_locked(resolved, context, name)
    fc = next((fn for fn, rk, ck, _l in FORM_CHOOSERS if rk == row_key and ck == column_key), None)
    form_chooser = (f"formchooser:{fc}", "form") if (fc and query.preset_form_label(resolved, name, row_key, column_key)) else None
    cx, cw, cy = _control_box(cells, blocks, resolved, geometry, f"block:{cid}", column_key, top, query.preset_cap(name), label,
                              disabled=disabled, scheme_button=(name == "projection"),
                              form_chooser=form_chooser)
    cells.append(CellBox(cid, cx, cy, cw, PRESET_H, "preset", text=preset_text[name],
                         disabled=disabled))
    if name == "target" and context.settings["all_interval"]:
        emit_option_check(cells, "all_interval", "all-interval",
                           service.is_all_interval(context.tuning_scheme), cx + cw + OPT_COL_GAP, cy)
    if name == "prescaler" and context.settings["alt_complexity"]:
        emit_option_check(cells, "diminuator", "replace diminuator",
                           service.diminuator_replaced(context.tuning_scheme), cx + cw + OPT_COL_GAP, cy)


def _emit_presets(cells, blocks, resolved, geometry, context) -> None:
    if not resolved.flags.presets:
        return
    preset_text = {"temperament": "", "target": context.target_spec,
                      "tuning": terminology.scheme(
                          service.base_scheme_name(context.tuning_scheme),
                          context.settings["terminology"]) or "",
                      "prescaler": resolved.labels.realized_prescaler or "",
                      "projection": resolved.scalars.displayed_projection_name or ""}
    for name, row_key, column_key, label in PRESETS:
        col = "superspace_primes" if name == "prescaler" and resolved.flags.superspace else column_key
        _emit_preset(cells, blocks, resolved, geometry, context, preset_text, f"preset:{name}", name, row_key, col, label)
    for name, row_key, column_key, label in PRESET_COPIES:
        col = "superspace_generators" if (name == "tuning" and column_key == "gens"
                           and resolved.flags.superspace_generators) else column_key
        _emit_preset(cells, blocks, resolved, geometry, context, preset_text, f"preset:{name}:{col}", name, row_key, col, label)


def _emit_all_interval_check_fallback(cells, resolved, geometry, context) -> None:
    if context.settings["all_interval"] and not resolved.flags.presets and query.tile_open(geometry, context.collapsed, "vectors", "targets"):
        top = query.plain_text_band_y(geometry, "vectors") + geometry.rows["vectors"].plain_text
        emit_option_check(cells, "all_interval", "all-interval",
                           service.is_all_interval(context.tuning_scheme),
                           geometry.col_x["targets"] + BOX_OUTER, top + BOX_OUTER + BOX_INNER)


def _emit_form_choosers(cells, blocks, resolved, geometry, context) -> None:
    if resolved.flags.form_controls and not resolved.flags.presets:
        for name, row_key, column_key, label in FORM_CHOOSERS:
            if not query.tile_open(geometry, context.collapsed, row_key, column_key):
                continue
            top = query.plain_text_band_y(geometry, row_key) + geometry.rows[row_key].plain_text + geometry.rows[row_key].preset
            cx, cw, cy = _control_box(cells, blocks, resolved, geometry, f"block:formchooser:{name}", column_key, top, PRESET_W, label)
            cells.append(CellBox(f"formchooser:{name}", cx, cy, cw, PRESET_H, "formchooser",
                                 text=resolved.canon.mapping_form_key if name == "mapping" else resolved.canon.comma_basis_form_key))


def _emit_scheme_buttons(cells, blocks, resolved, geometry, context) -> None:
    if context.settings["projection"] and not resolved.flags.presets:
        for column_key in ("primes", "gens"):
            if not query.tile_open(geometry, context.collapsed, "projection", column_key):
                continue
            top = query.plain_text_band_y(geometry, "projection") + geometry.rows["projection"].plain_text
            box_y = top + BOX_OUTER
            blocks.append(Block(f"block:scheme:{column_key}", geometry.col_x[column_key], box_y, geometry.col_w[column_key],
                                2 * BOX_INNER + SCHEME_BUTTON_SQ, boxed=True))
            _emit_scheme_button(cells, geometry.col_x[column_key] + BOX_INNER, box_y + BOX_INNER, column_key)


def _emit_plain_text_band(cells, resolved, geometry, context) -> None:
    if resolved.flags.plain_text_values:
        for (row_key, column_key), text in geometry.plain_text_strings.items():
            if not query.tile_open(geometry, context.collapsed, row_key, column_key):
                continue
            if ((row_key, column_key) == ("vectors", "commas") and resolved.commas.pending is not None) \
                    or ((row_key, column_key) == ("vectors", "targets") and resolved.targets.pending is not None) \
                    or ((row_key, column_key) == ("mapping", "primes") and context.pending_mapping_row is not None):
                kind = "plain_text_pending"
            elif query.plain_text_editable(resolved, row_key, column_key) and (column_key != "targets" or resolved.scalars.targets_editable):
                kind = "plain_text_edit"
            else:
                kind = "plain_text"
            cells.append(CellBox(f"plain_text:{row_key}:{column_key}", geometry.col_x[column_key], query.plain_text_band_y(geometry, row_key),
                                 geometry.col_w[column_key], query.plain_text_height(resolved, row_key, column_key), kind, text=text))
