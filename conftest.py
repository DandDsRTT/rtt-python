"""Load NiceGUI's selenium-free ``User`` test plugin so the render tests
(``tests/app/integration/test_web_render.py``) can drive the live page in-process — the layer the
smoke tests deliberately skip. ``pytest_plugins`` must live in the rootdir conftest."""

import os

# The render harness has no live browser, so it never reports a scroll viewport: left at the bounded
# production default, the virtualized body pane would materialize only the top-left cells and the
# element-tree assertions (which expect every cell present after ``user.open("/")``) would fail. Force
# a viewport large enough to admit the whole grid, so the virtualization filter still runs but never
# elides a cell. ``setdefault`` lets a probe override it. See ``rtt.app.app._initial_viewport``.
os.environ.setdefault("RTT_VIRT_VIEWPORT", "200000x200000")

pytest_plugins = ["nicegui.testing.user_plugin"]
