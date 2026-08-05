from __future__ import annotations

_HOVER_ARMED_JS = (
    "(e) => { if (window.__rttHoverArmed) {"
    " window.rttHoverAnchor && window.rttHoverAnchor.set(e.currentTarget); emit(); } }"
)
_HOVER_LEAVE_JS = (
    "(e) => { window.rttHoverAnchor && window.rttHoverAnchor.clear(e.currentTarget); emit(); }"
)


def preview_control(reconciler, element, op, source_id=None, allow_reflow=False) -> None:
    element.on(
        "mouseenter",
        lambda _=None: reconciler._callbacks.control_hover(op, source_id, allow_reflow),
        js_handler=_HOVER_ARMED_JS,
    )
    element.on(
        "mouseleave",
        lambda _=None: reconciler._callbacks.control_unhover(),
        js_handler=_HOVER_LEAVE_JS,
    )


def wire_action(reconciler, wrap, clickable, op, source_id=None, allow_reflow=False) -> None:
    clickable.on("click", lambda _=None: reconciler._callbacks.act(op))
    preview_control(reconciler, wrap, op, source_id, allow_reflow)
