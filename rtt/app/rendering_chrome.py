from __future__ import annotations

from rtt.app import service, tooltips
from rtt.app import settings as show_settings
from rtt.app.page_assets import _STORE_KEY, _TILE_HOST, _doc_store


def sync_mean_damage_tips(rec, editor) -> None:
    mean_damage_help_text = tooltips.mean_damage_help(service.is_all_interval(editor.tuning_scheme))
    for cid in tooltips.MEAN_DAMAGE_IDS:
        if rec.handles(cid).mean_damage_tip is not None:
            rec.cells[cid].mean_damage_tip.set_text(mean_damage_help_text)
            continue
        wrap = rec.entity(cid).el
        if wrap is not None and wrap._props.get("data-zoomhelp") != mean_damage_help_text:
            wrap._props["data-zoomhelp"] = mean_damage_help_text
            wrap.update()


def sync_pretransform_help(rec, pretransform: bool) -> None:
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


def sync_chrome(r, lay, fy) -> None:
    r._chrome.refs["undo"].set_enabled(r._editor.can_undo)
    r._chrome.refs["redo"].set_enabled(r._editor.can_redo)
    r._chrome.refs["reset"].set_enabled(
        r._editor.can_reset or r._runtime.chapter != show_settings.CHAPTER_DEFAULT
    )
    if r._chrome.chapter_slider.value != r._runtime.chapter:
        r._chrome.chapter_slider.value = r._runtime.chapter
    terminology_radio = r._chrome.refs.get("terminology")
    if (
        terminology_radio is not None
        and terminology_radio.value != r._editor.settings["terminology"]
    ):
        terminology_radio.value = r._editor.settings["terminology"]
    if lay.approach_box is not None:
        ax, ay, aw, ah = lay.approach_box
        r._chrome.refs["approach"].style(
            f"position:absolute; left:{ax}px; top:{ay - fy}px; width:{aw}px; height:{ah}px"
        )
        r._chrome.refs["approach"].set_visibility(True)
    else:
        r._chrome.refs["approach"].set_visibility(False)
    for key, opt in r._chrome.refs["approach_opts"].items():
        (
            opt.classes(add="rtt-rangeopt-on")
            if key == r._editor.nonprime_basis_approach
            else opt.classes(remove="rtt-rangeopt-on")
        )
    for key, box in r._chrome.boxes.items():
        if box.value != r._editor.settings[key]:
            box.value = r._editor.settings[key]
    sync_tile_parts(r._editor, r._chrome)
    r._sync_availability()
    gesture_idle = r._gestures.gesture is None or r._gestures.gesture.token is None
    if gesture_idle and not (r._runtime.load_failed and not r._editor.can_undo):
        _doc_store()[_STORE_KEY] = r._editor.serialize()


def sync_tile_parts(editor, chrome) -> None:
    for key, parts in chrome.tile_parts.items():
        shown = editor.settings["names"] if key == "mnemonics" else editor.settings[key]
        host = _TILE_HOST.get(key)
        inert = host is not None and not editor.settings[host]
        for part in parts:
            part.classes(
                add="rtt-part-on" if shown else "rtt-part-off",
                remove="rtt-part-off" if shown else "rtt-part-on",
            )
            part.classes(add="rtt-part-inert") if inert else part.classes(remove="rtt-part-inert")
            if key == "mnemonics":
                part.classes(add="rtt-mnem-underline") if editor.settings[
                    "mnemonics"
                ] else part.classes(remove="rtt-mnem-underline")
