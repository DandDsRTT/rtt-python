"""Entry point for the RTT monolith web UI: ``python app.py``."""

import os

# The "leaked semaphore objects" notice at shutdown is emitted by the
# multiprocessing resource_tracker *subprocess*, which re-reads its warning
# config from the environment — so warnings.filterwarnings() in this process
# can't reach it; only PYTHONWARNINGS, inherited at spawn, can.
os.environ.setdefault(
    "PYTHONWARNINGS",
    "ignore::UserWarning:multiprocessing.resource_tracker",
)

from rtt.app.app import main

if __name__ in {"__main__", "__mp_main__"}:
    main()
