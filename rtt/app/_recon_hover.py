from __future__ import annotations

_HOVER_ARMED_JS = "(e) => { if (window.__rttHoverArmed) emit(); }"


def preview_control(reconciler, element, apply) -> None:
    element.on(
        "mouseenter",
        lambda _=None: reconciler._callbacks.control_hover(apply),
        js_handler=_HOVER_ARMED_JS,
    )
    element.on("mouseleave", lambda _=None: reconciler._callbacks.control_unhover())


def preview_rank_remove(reconciler, element, axis: str, index: int) -> None:
    element.on(
        "mouseenter",
        lambda _=None: reconciler._callbacks.rank_remove_hover(axis, index),
        js_handler=_HOVER_ARMED_JS,
    )
    element.on("mouseleave", lambda _=None: reconciler._callbacks.rank_remove_unhover())
