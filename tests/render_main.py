"""NiceGUI "main file" for the in-process render tests (``tests/test_web_render.py``).

NiceGUI's ``User`` simulation runs this via ``runpy`` as ``__main__`` inside a freshly
reset page registry. Importing :mod:`rtt.app.app` is what registers its ``@ui.page("/")``,
so we first evict any cached copy (pytest has already imported it while collecting the
other web tests) to force the decorator to re-run into this registry. ``ui.run()`` starts
no server under the simulation's ``NICEGUI_USER_SIMULATION`` flag — it just wires the app
for the in-process ASGI client. We pass a ``storage_secret`` so ``app.storage.user`` (which
the app reads/writes to persist its document across refreshes) is enabled, matching how
:func:`rtt.app.app.main` runs the real server.
"""

import sys

for _name in [m for m in list(sys.modules) if m == "rtt" or m.startswith("rtt.")]:
    del sys.modules[_name]

import rtt.app.app
from nicegui import ui

ui.run(storage_secret="render-test")
