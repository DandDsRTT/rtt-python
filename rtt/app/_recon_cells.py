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


def tag_audio(el, cb) -> None:
    tile, idx, cents = cb.audio
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


def attach_hover_help(rec, wrap, cb) -> None:
    plain = tooltips.control_help(cb.kind, cb.id)
    relabeled = tooltips.control_help(cb.kind, cb.id, pretransform=True)
    help_text = relabeled if rec.pretransform else plain
    if cb.kind in VALUE_KINDS:
        wrap.classes("rtt-zoomable")
        if help_text:
            wrap._props["data-zoomhelp"] = help_text
    elif help_text:
        if cb.id in tooltips.MEAN_DAMAGE_IDS:
            with wrap:
                rec.cells[cb.id].mean_damage_tip = ui.tooltip(help_text)
        elif cb.id == "preset:target":
            with wrap:
                rec.target_limit_tip = ui.tooltip(help_text)
        elif plain != relabeled:
            with wrap:
                rec.cells[cb.id].help_tip = (ui.tooltip(help_text), plain, relabeled)
        else:
            wrap.tooltip(help_text)
    if cb.kind in ("symbol", "caption"):
        gh = tooltips.tile_guide_help_for_cell(cb.id)
        if gh is not None:
            gh_pt = tooltips.tile_guide_help_for_cell(cb.id, pretransform=True)
            text = gh_pt.text if rec.pretransform else gh.text
            attach_guide_link(wrap, gh, cb.id.split(":", 1)[1], text)
            if gh.text != gh_pt.text:
                rec.cells[cb.id].guide_help_text = (gh.text, gh_pt.text)


def wire_cell_input(rec, wrap, cb) -> None:
    if cb.kind.endswith(("plus", "minus")):
        wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
    edit_input = rec.cells[cb.id].value.input or rec.cells[cb.id].value.ptext_input
    if edit_input is not None:
        den = rec.cells[cb.id].value.den_input
        guard = _STACKED_EXIT_JS if den is not None else None
        for fld in (edit_input, den) if den is not None else (edit_input,):
            fld.on("focus", lambda _=None, cid=cb.id: rec._cb.on_cell_focus(cid), js_handler=guard)
            fld.on("blur", lambda _=None, cid=cb.id: rec._cb.on_cell_blur(cid), js_handler=guard)
            fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
    if cb.kind in _WHEEL_STEPS:
        wrap.on(
            "wheel",
            lambda e, cid=cb.id: rec._cb.on_value_wheel(cid, e.args.get("deltaY")),
            args=["deltaY"],
            js_handler=_INT_WHEEL_JS,
        )
