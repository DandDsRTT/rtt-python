"""Load NiceGUI's selenium-free ``User`` test plugin so the render tests
(``tests/test_web_render.py``) can drive the live page in-process — the layer the
smoke tests deliberately skip. ``pytest_plugins`` must live in the rootdir conftest."""

pytest_plugins = ["nicegui.testing.user_plugin"]
