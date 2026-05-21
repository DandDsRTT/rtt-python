"""Entry point for the RTT monolith web UI: ``python app.py``."""

from rtt.web.app import main

if __name__ in {"__main__", "__mp_main__"}:
    main()
