from __future__ import annotations

from nicegui import ui

from rtt.app import service, tooltips
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
    _STACKED_EXIT_JS,
    _WHEEL_STEPS,
)
from rtt.app.spreadsheet_constants import VALUE_KINDS


def cur_gesture(gestures):
    return gestures.gesture if gestures is not None else None


def target_preset_values(editor):
    if editor.target_override is not None or service.is_all_interval(editor.tuning_scheme):
        return None, None
    state = editor.state
    if not service.target_interval_set(editor.target_spec, state.domain_basis):
        return None, None
    family = editor.target_family
    limit = editor.target_limit
    if limit is None:
        limit = service.default_target_limit(family, state.domain_basis)
    return limit, family


def tag_audio(element, cell_box) -> None:
    tile, index, cents = cell_box.audio
    element.classes(add="rtt-speaker").props(
        f'data-audio="{tile}" data-idx="{index}" data-cents="{cents:.6f}"'
    )


def attach_guide_link(wrap, guide_help, tile, text) -> None:
    # Quasar: a ui.tooltip hides the moment the cursor leaves the cell toward it, so its link can't
    # be clicked; these data-attrs feed a custom body-level hover-card (guide.js) that stays open.
    wrap.classes("rtt-guide-link")
    wrap._props["data-guide-text"] = text
    wrap._props["data-guide-tile"] = tile
    if guide_help.url:
        wrap._props["data-guide-loc"] = guide_help.location
        wrap._props["data-guide-url"] = guide_help.url


def attach_hover_help(reconciler, wrap, cell_box) -> None:
    plain = tooltips.control_help(cell_box.kind, cell_box.id)
    relabeled = tooltips.control_help(cell_box.kind, cell_box.id, pretransform=True)
    help_text = relabeled if reconciler.pretransform else plain
    if cell_box.kind in VALUE_KINDS:
        wrap.classes("rtt-zoomable")
        if help_text:
            wrap._props["data-zoomhelp"] = help_text
    elif help_text:
        if cell_box.id in tooltips.MEAN_DAMAGE_IDS:
            with wrap:
                reconciler.cells[cell_box.id].mean_damage_tip = ui.tooltip(help_text)
        elif cell_box.id == "preset:target":
            with wrap:
                reconciler.target_limit_tip = ui.tooltip(help_text)
        elif plain != relabeled:
            with wrap:
                reconciler.cells[cell_box.id].help_tip = (ui.tooltip(help_text), plain, relabeled)
        else:
            wrap.tooltip(help_text)
    if cell_box.kind in ("symbol", "caption"):
        parts = cell_box.id.split(":")
        if len(parts) == 3:
            _attach_tile_guide(reconciler, wrap, cell_box, parts[1], parts[2])
    elif cell_box.kind in VALUE_KINDS and cell_box.guide_key is not None:
        _attach_tile_guide(reconciler, wrap, cell_box, *cell_box.guide_key)


def _attach_tile_guide(reconciler, wrap, cell_box, row_key, column_key) -> None:
    guide_help = tooltips.tile_guide_help(row_key, column_key)
    if guide_help is None:
        return
    guide_help_pretransform = tooltips.tile_guide_help_for_cell(
        f"caption:{row_key}:{column_key}", pretransform=True
    )
    text = guide_help_pretransform.text if reconciler.pretransform else guide_help.text
    attach_guide_link(wrap, guide_help, f"{row_key}:{column_key}", text)
    if guide_help.text != guide_help_pretransform.text:
        reconciler.cells[cell_box.id].guide_help_text = (
            guide_help.text,
            guide_help_pretransform.text,
        )


def draft_cancel_eid(cell_box):
    by_kind = {
        "mapping": "map_minus:pending",
        "comma_cell": "comma_minus:pending",
        "interest_cell": "interest_minus:pending",
        "held_cell": "held_minus:pending",
        "target_cell": "target_minus:pending",
    }
    if cell_box.kind in by_kind:
        return by_kind[cell_box.kind]
    by_head = {
        "comma": "comma_minus:pending",
        "interest": "interest_minus:pending",
        "held": "held_minus:pending",
        "target": "target_minus:pending",
        "generator": "map_minus:pending",
        "prime": "element_minus:pending",
        "basis": "element_minus:basis:pending",
    }
    return by_head.get(cell_box.id.split(":")[0])


def _draft_escape_js(cancel_element_id):
    return (
        f"(e) => {{const b=document.querySelector('[data-eid=\"{cancel_element_id}\"] .rtt-glyph');"
        "if(b){e.preventDefault();b.click();}}"
    )


def wire_cell_input(reconciler, wrap, cell_box) -> None:
    if cell_box.kind.endswith(("plus", "minus")):
        wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
    edit_input = (
        reconciler.cells[cell_box.id].value.input
        or reconciler.cells[cell_box.id].value.plain_text_input
    )
    if edit_input is not None:
        denominator = reconciler.cells[cell_box.id].value.denominator_input
        guard = _STACKED_EXIT_JS if denominator is not None else None
        cancel_element_id = draft_cancel_eid(cell_box) if cell_box.pending else None
        for fld in (edit_input, denominator) if denominator is not None else (edit_input,):
            fld.on(
                "focus",
                lambda _=None, cell_id=cell_box.id: reconciler._cell_box.on_cell_focus(cell_id),
                js_handler=guard,
            )
            fld.on(
                "blur",
                lambda _=None, cell_id=cell_box.id: reconciler._cell_box.on_cell_blur(cell_id),
                js_handler=guard,
            )
            fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
            if cancel_element_id is not None:
                fld.on("keydown.escape", js_handler=_draft_escape_js(cancel_element_id))
    if cell_box.kind in _WHEEL_STEPS:
        wrap.on(
            "wheel",
            lambda e, cell_id=cell_box.id: reconciler._cell_box.on_value_wheel(
                cell_id, e.args.get("deltaY")
            ),
            args=["deltaY"],
            js_handler=_INT_WHEEL_JS,
        )
