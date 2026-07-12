from __future__ import annotations


def gesture_render(gesture_controller, prebuilt=None) -> None:
    gesture_controller.gesture_rendering = True
    try:
        gesture_controller._renderer.render(prebuilt)
    finally:
        gesture_controller.gesture_rendering = False
