"""NiceGUI "main file" for the in-process render tests (``tests/test_web_render.py``).

NiceGUI's ``User`` simulation runs this via ``runpy`` as ``__main__`` inside a freshly
reset page registry. Importing :mod:`rtt.web.app` is what registers its ``@ui.page("/")``,
so we first evict any cached copy (pytest has already imported it while collecting the
other web tests) to force the decorator to re-run into this registry. ``ui.run()`` is a
no-op under the simulation's ``NICEGUI_USER_SIMULATION`` flag — it wires the app for the
in-process ASGI client without starting a server.
"""

import sys

for _name in [m for m in list(sys.modules) if m == "rtt" or m.startswith("rtt.")]:
    del sys.modules[_name]

import rtt.web.app  # noqa: E402, F401  — the import registers @ui.page("/")
from nicegui import ui  # noqa: E402

ui.run()
