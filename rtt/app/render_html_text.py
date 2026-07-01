from __future__ import annotations

import html
import math

from rtt.app import service, spreadsheet_constants
from rtt.library.formatting import strip_negative_zero

_EXPR_MAX_FONT = 9.0
_EXPR_MIN_FONT = 3.5
_EXPR_CHAR_W = 0.5


def _fit_font(
    line: str,
    width: float,
    max_font: float = _EXPR_MAX_FONT,
    min_font: float = _EXPR_MIN_FONT,
    char_width: float = _EXPR_CHAR_W,
) -> float:
    if not line:
        return max_font
    fit = (width - 2) / (len(line) * char_width)
    return max(min_font, min(max_font, fit))


_LOG2 = "log₂"


def _elide_expr_line(line: str, width: float) -> str:
    max_chars = (width - 2) / (_EXPR_MIN_FONT * _EXPR_CHAR_W)
    if len(line) <= max_chars:
        return line
    cut = line.rfind(_LOG2)
    if cut < 0:
        return line
    head, operand = line[: cut + len(_LOG2)], line[cut + len(_LOG2) :]
    return head + ("(…/…)" if "/" in operand else "…")


def _math_expression_html(text: str, width: float) -> str:
    lines = "".join(
        f'<div style="font-size:{_fit_font(line, width):.2f}px">{html.escape(line)}</div>'
        for line in (_elide_expr_line(raw, width) for raw in text.split("\n"))
    )
    return f'<div class="rtt-math-expression-stack">{lines}</div>'


def _units_font(text: str, width: float, max_font: float) -> float:
    return _fit_font(text, width, max_font=max_font)


def _parse_int(text: str) -> int | None:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


def _wheel_step(value, delta_y, step=1) -> str:
    text = str(value).strip()
    if step <= 0:
        return text
    if not text:
        cur = 0.0
    else:
        try:
            cur = float(text.replace("∞", "inf"))
        except ValueError:
            return text
    if not math.isfinite(cur):
        return text
    new = cur + (step if delta_y < 0 else -step)
    if isinstance(step, int):
        return str(int(new)) if new == int(new) else str(new)
    decimals = max(0, -math.floor(math.log10(step)))
    return strip_negative_zero(f"{round(new, decimals):.{decimals}f}")


def _limit_text(limit) -> str | None:
    return None if limit is None else str(limit)


def _ratio_parts(text) -> tuple[str, str] | None:
    num, sep, den = str(text).partition("/")
    return (num, den) if sep and num and den else None


def _cents_parts(text) -> tuple[str, str]:
    whole, _, frac = str(text).partition(".")
    return whole, frac


def _approach_visible(editor) -> bool:
    return service.domain_has_nonprimes(editor.state.domain_basis)


def _generator_tuning_parts(text: str) -> tuple[str, str, str]:
    if not text:
        return "", "", ""
    sign, body = ("−", text[1:]) if text.startswith("-") else ("+", text)
    whole, frac = _cents_parts(body)
    return sign, whole, frac


def _power_parts(text) -> tuple[str, str]:
    return (text, "(max)") if text == "∞" else (text, "")


# There is no browser to measure text width in-process, so these per-glyph em-widths for the
# .rtt-plain-text face estimate it; they are conservative upper bounds over the (narrower) STIX Two Text
# body face, so a value's estimate stays above its real render and never spills.
_PLAIN_TEXT_DEFAULT_EM = 0.59
_PLAIN_TEXT_GLYPH_EM = {
    **dict.fromkeys("0123456789", 0.59),
    ".": 0.25,
    "-": 0.35,
    "/": 0.52,
    " ": 0.24,
    "[": 0.37,
    "]": 0.37,
    "{": 0.41,
    "}": 0.41,
    "⟨": 0.38,
    "⟩": 0.38,
    "⟪": 0.58,
    "⟫": 0.58,
    "—": 1.0,
}


def _plain_text_units(text: str) -> float:
    return sum(_PLAIN_TEXT_GLYPH_EM.get(c, _PLAIN_TEXT_DEFAULT_EM) for c in text)


def _plain_text_font(text: str, width: float) -> float:
    units = _plain_text_units(text)
    fit = (width - 2) / units if units else spreadsheet_constants.PLAIN_TEXT_MAX_FONT
    return int(min(spreadsheet_constants.PLAIN_TEXT_MAX_FONT, fit) * 10) / 10


_RATIO_MAX_FONT = 13.0
_RATIO_DIGIT_EM = _PLAIN_TEXT_GLYPH_EM["0"]
_RATIO_PADDING = 6.0


def _digit_fit_font(longest, width: float, max_font: float) -> float:
    if not longest:
        return max_font
    fit = (width - _RATIO_PADDING) / (longest * _RATIO_DIGIT_EM)
    return int(min(max_font, fit) * 10) / 10


def _ratio_font(num, den, width: float) -> float:
    return _digit_fit_font(max(len(num), len(den)), width, _RATIO_MAX_FONT)
