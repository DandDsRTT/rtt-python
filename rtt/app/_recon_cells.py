from __future__ import annotations

from nicegui import ui

from rtt.app import service, tooltips
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
    _STACKED_EXIT_JS,
    _WHEEL_STEPS,
    VALUE_KINDS,
)


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


def tag_audio(el, cell_box) -> None:
    tile, idx, cents = cell_box.audio
    el.classes(add="rtt-spk").props(
        f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"'
    )


def attach_guide_link(wrap, gh, tile, text) -> None:
    # Quasar: a ui.tooltip hides the moment the cursor leaves the cell toward it, so its link can't
    # be clicked; these data-attrs feed a custom body-level hover-card (_GUIDE_JS) that stays open.
    wrap.classes("rtt-guide-link")
    wrap._props["data-guide-text"] = text
    wrap._props["data-guide-tile"] = tile
    if gh.url:
        wrap._props["data-guide-loc"] = gh.location
        wrap._props["data-guide-url"] = gh.url


def attach_hover_help(rec, wrap, cell_box) -> None:
    plain = tooltips.control_help(cell_box.kind, cell_box.id)
    relabeled = tooltips.control_help(cell_box.kind, cell_box.id, pretransform=True)
    help_text = relabeled if rec.pretransform else plain
    if cell_box.kind in VALUE_KINDS:
        wrap.classes("rtt-zoomable")
        if help_text:
            wrap._props["data-zoomhelp"] = help_text
    elif help_text:
        if cell_box.id in tooltips.MEAN_DAMAGE_IDS:
            with wrap:
                rec.cells[cell_box.id].mean_damage_tip = ui.tooltip(help_text)
        elif cell_box.id == "preset:target":
            with wrap:
                rec.target_limit_tip = ui.tooltip(help_text)
        elif plain != relabeled:
            with wrap:
                rec.cells[cell_box.id].help_tip = (ui.tooltip(help_text), plain, relabeled)
        else:
            wrap.tooltip(help_text)
    if cell_box.kind in ("symbol", "caption"):
        gh = tooltips.tile_guide_help_for_cell(cell_box.id)
        if gh is not None:
            gh_pt = tooltips.tile_guide_help_for_cell(cell_box.id, pretransform=True)
            text = gh_pt.text if rec.pretransform else gh.text
            attach_guide_link(wrap, gh, cell_box.id.split(":", 1)[1], text)
            if gh.text != gh_pt.text:
                rec.cells[cell_box.id].guide_help_text = (gh.text, gh_pt.text)


def draft_cancel_eid(cell_box):
    by_kind = {
        "mapping": "map_minus:pending",
        "commacell": "comma_minus:pending",
        "interestcell": "interest_minus:pending",
        "heldcell": "held_minus:pending",
        "targetcell": "target_minus:pending",
    }
    if cell_box.kind in by_kind:
        return by_kind[cell_box.kind]
    by_head = {
        "comma": "comma_minus:pending",
        "interest": "interest_minus:pending",
        "held": "held_minus:pending",
        "target": "target_minus:pending",
        "gen": "map_minus:pending",
        "prime": "element_minus:pending",
        "basis": "element_minus:basis:pending",
    }
    return by_head.get(cell_box.id.split(":")[0])


def _draft_escape_js(cancel_eid):
    return (
        f"(e) => {{const b=document.querySelector('[data-eid=\"{cancel_eid}\"] .rtt-glyph');"
        "if(b){e.preventDefault();b.click();}}"
    )


def wire_cell_input(rec, wrap, cell_box) -> None:
    if cell_box.kind.endswith(("plus", "minus")):
        wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
    edit_input = rec.cells[cell_box.id].value.input or rec.cells[cell_box.id].value.plain_text_input
    if edit_input is not None:
        den = rec.cells[cell_box.id].value.den_input
        guard = _STACKED_EXIT_JS if den is not None else None
        cancel_eid = draft_cancel_eid(cell_box) if cell_box.pending else None
        for fld in (edit_input, den) if den is not None else (edit_input,):
            fld.on(
                "focus",
                lambda _=None, cid=cell_box.id: rec._cb.on_cell_focus(cid),
                js_handler=guard,
            )
            fld.on(
                "blur", lambda _=None, cid=cell_box.id: rec._cb.on_cell_blur(cid), js_handler=guard
            )
            fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
            if cancel_eid is not None:
                fld.on("keydown.escape", js_handler=_draft_escape_js(cancel_eid))
    if cell_box.kind in _WHEEL_STEPS:
        wrap.on(
            "wheel",
            lambda e, cid=cell_box.id: rec._cb.on_value_wheel(cid, e.args.get("deltaY")),
            args=["deltaY"],
            js_handler=_INT_WHEEL_JS,
        )
