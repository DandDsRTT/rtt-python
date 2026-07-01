from __future__ import annotations

from rtt.app.spreadsheet_constants import DASH
from rtt.library.formatting import strip_negative_zero


def cents(value, decimals: bool = True) -> str:
    if value is None:
        return DASH
    return strip_negative_zero(f"{value:.{3 if decimals else 0}f}")


def prescale_text(value: float, decimals: bool = True) -> str:
    return str(int(value)) if value == int(value) else cents(value, decimals)
