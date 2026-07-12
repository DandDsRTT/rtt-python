from __future__ import annotations


def gesture_render(gesture_controller) -> None:
    gesture_controller.gesture_rendering = True
    try:
        gesture_controller._renderer.render()
    finally:
        gesture_controller.gesture_rendering = False
