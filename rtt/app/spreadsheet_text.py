from __future__ import annotations

import re

from rtt.app import service
from rtt.app.grid_tables import NORM_SUB_CLOSE, NORM_SUB_OPEN, RINGABLE_KINDS, SUBSCRIPT_L
from rtt.app.layout import CellBox, Layout
from rtt.app.spreadsheet_constants import (
    CAPTION_CHAR_WIDTH,
    CAPTION_FONT,
    CAPTION_LINE,
    LINE_WIDTH,
    OPTION_BOX_PX,
    PRESCALING_BOX_DIM_WIDTH,
    PRESET_HEIGHT,
    STRIP,
)


def emit_option_check(cells, name: str, label: str, checked: bool, check_x, control_y) -> None:
    check_y = control_y + (PRESET_HEIGHT - OPTION_BOX_PX) / 2
    cells.append(
        CellBox(
            f"control:{name}",
            check_x,
            check_y,
            PRESCALING_BOX_DIM_WIDTH,
            OPTION_BOX_PX,
            "control_check",
            text="",
            checked=checked,
        )
    )
    cells.append(
        CellBox(
            f"caption:{name}",
            check_x,
            control_y + PRESET_HEIGHT,
            PRESCALING_BOX_DIM_WIDTH,
            CAPTION_LINE,
            "caption",
            text=label,
        )
    )


def _mathit(letter: str) -> str:
    return "ℎ" if letter == "h" else chr(0x1D44E + ord(letter) - ord("a"))


_SUBSCRIPTS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _sub(n: int) -> str:
    return str(n).translate(_SUBSCRIPTS)


def _subscript_coord(text: str, letter: str, replacement: str) -> str:
    return re.sub(rf"(?<![A-Za-z]){letter}(?![A-Za-z])", replacement, text)


def _count_sym(sym: str) -> str:
    head = _mathit(sym[0])
    if len(sym) == 1:
        return head
    if sym[1:] == "L":
        return head + SUBSCRIPT_L
    raise ValueError(f"unknown counts symbol: {sym!r}")


def _pretransform_label(text: str) -> str:
    for old, new in (
        ("prescaled", "pretransformed"),
        ("prescaling", "pretransforming"),
        ("prescaler", "pretransformer"),
    ):
        text = text.replace(old, new)
    return text


def _prescaler_col_labels(
    letter: str, show_equivalences: bool, all_interval: bool, show_superspace: bool = False
) -> dict:
    def norm(inner):
        return lambda i: f"‖{inner(i)}‖{NORM_SUB_OPEN}q{NORM_SUB_CLOSE}"

    def complexity_target(i):
        symbol = f"c{_sub(i + 1)}"
        if not show_equivalences:
            return symbol
        inner = f"{letter}[{i + 1}]" if all_interval else f"{letter}𝐭{_sub(i + 1)}"
        return f"{symbol} = ‖{inner}‖{NORM_SUB_OPEN}q{NORM_SUB_CLOSE}"

    labels = {
        ("prescaling", "commas"): letter + "𝐜",
        ("prescaling", "targets"): letter + "𝐭",
        ("prescaling", "held"): letter + "𝐡",
        ("prescaling", "detempering"): letter + "𝐝",
        ("complexity", "primes"): norm(lambda i: f"{letter}[{i + 1}]"),
        ("complexity", "commas"): norm(lambda i: f"{letter}𝐜{_sub(i + 1)}"),
        ("complexity", "held"): norm(lambda i: f"{letter}𝐡{_sub(i + 1)}"),
        ("complexity", "detempering"): norm(lambda i: f"{letter}𝐝{_sub(i + 1)}"),
        ("complexity", "targets"): complexity_target,
    }
    if show_superspace:
        labels[("prescaling", "primes")] = letter + "𝐛" + SUBSCRIPT_L + "ₛ"
        labels[("complexity", "superspace_primes")] = norm(lambda i: f"{letter}[{i + 1}]")
        labels[("complexity", "primes")] = norm(lambda i: f"{letter}𝐛{SUBSCRIPT_L}ₛ{_sub(i + 1)}")
    return labels


def _log_operand(ratio: str) -> str:
    numerator, _, denominator = ratio.partition("/")
    return numerator if denominator == "1" else f"({numerator}/{denominator})"


def _math_expr(operand: str, value: float, show_value: bool, decimals: bool = True) -> str:
    if operand == "1":
        return "0"
    expr = f"1200 · log₂{operand}"
    return f"{expr}\n= {service.cents(value, decimals)}" if show_value else expr


def _prescale_math_expr(
    coeff, prime_term: str, value: float, show_value: bool, decimals: bool = True
) -> str:
    if coeff == 1:
        expr = prime_term
    elif coeff == -1:
        expr = f"-{prime_term}"
    else:
        expr = f"{coeff} · {prime_term}"
    return f"{expr}\n= {service.prescale_text(value, decimals)}" if show_value else expr


def _format_power(power: float) -> str:
    if power == float("inf"):
        return "∞"
    return str(int(power)) if power == int(power) else str(power)


def _power_mean(damages, power: float) -> float:
    ds = [abs(d) for d in damages]
    if not ds:
        return 0.0
    if power == float("inf"):
        return max(ds)
    return (sum(d**power for d in ds) / len(ds)) ** (1 / power)


def _title_w(title: str) -> int:
    widest = max(len(line) for line in title.splitlines())
    return max(STRIP, widest * 8 + 10)


def _fold_glyph(is_collapsed: bool) -> str:
    return "unfold_more" if is_collapsed else "unfold_less"


def _foldable_ids(cells) -> set:
    return {c.id.split("toggle:", 1)[1] for c in cells if c.kind in ("rowtoggle", "columntoggle")}


def toggle_all_collapsed(layout, collapsed) -> set:
    foldable = _foldable_ids(layout.cells)
    if foldable and foldable <= collapsed:
        return set()
    return set(collapsed) | foldable


_CONTENT_FIELDS = (
    "kind",
    "text",
    "values",
    "ranges",
    "indicator",
    "indicator_label",
    "pending",
    "checked",
    "blank",
    "unit",
    "underlines",
)


def _cell_content(cell: CellBox) -> tuple:
    return tuple(getattr(cell, field) for field in _CONTENT_FIELDS)


def changed_cell_ids(old: Layout, new: Layout) -> frozenset:
    before = {c.id: _cell_content(c) for c in old.cells}
    return frozenset(
        c.id
        for c in new.cells
        if c.kind in RINGABLE_KINDS and (c.id not in before or before[c.id] != _cell_content(c))
    )


def removed_cell_ids(old: Layout, new: Layout) -> frozenset:
    after = {c.id for c in new.cells}
    return frozenset(
        c.id for c in old.cells if c.kind in RINGABLE_KINDS and not c.pending and c.id not in after
    )


def _match_tokens_by_key(tokens, previous, keys) -> list[bool]:
    claimed = [False] * len(previous)
    for j, key in enumerate(keys):
        for pi, (token, pkey) in enumerate(previous):
            if not claimed[pi] and pkey == key:
                tokens[j], claimed[pi] = token, True
                break
    return claimed


def _claim_unmatched_tokens(tokens, previous, claimed, keys) -> None:
    unclaimed = iter([pi for pi in range(len(previous)) if not claimed[pi]])
    for j in range(len(keys)):
        if tokens[j] is None:
            pi = next(unclaimed, None)
            if pi is None:
                break
            tokens[j] = previous[pi][0]


def assign_column_tokens(previous, keys, claim_unmatched=False):
    keys = list(keys)
    previous = list(previous or [])
    tokens = [None] * len(keys)
    if len(keys) == len(previous) and sorted(keys) != sorted(k for _, k in previous):
        for j in range(len(keys)):
            tokens[j] = previous[j][0]
    else:
        claimed = _match_tokens_by_key(tokens, previous, keys)
        if claim_unmatched:
            _claim_unmatched_tokens(tokens, previous, claimed, keys)
    nxt = max([t for t in tokens if t is not None] + [token for token, _ in previous] + [-1]) + 1
    for j in range(len(keys)):
        if tokens[j] is None:
            tokens[j], nxt = nxt, nxt + 1
    return list(zip(tokens, keys, strict=False))


def pending_token(tokens) -> int:
    return max(tokens, default=-1) + 1


def _wrap_chars(words: list[str], max_chars: int) -> int:
    lines, cur = 1, 0
    for word in words:
        wlen = len(word)
        if cur and cur + 1 + wlen > max_chars:
            lines, cur = lines + 1, 0
        if cur == 0 and wlen > max_chars:
            lines += (wlen - 1) // max_chars
            cur = (wlen - 1) % max_chars + 1
        else:
            cur += (1 if cur else 0) + wlen
    return lines


def _chars_per_line(width: float, font: float = CAPTION_FONT) -> int:
    return max(1, int((width - 4) / (font * CAPTION_CHAR_WIDTH)))


def _wrap_lines(text: str, width: float, font: float = CAPTION_FONT) -> int:
    return _wrap_chars(text.split(), _chars_per_line(width, font))


def _min_width_for_lines(text: str, max_lines: int, font: float = CAPTION_FONT) -> int:
    words = text.split()
    for chars in range(1, len(text) + 1):
        if _wrap_chars(words, chars) <= max_lines:
            return int(chars * font * CAPTION_CHAR_WIDTH + 4) + 1
    return int(len(text) * font * CAPTION_CHAR_WIDTH + 4) + 1


def _bus_span(positions) -> tuple[float, float]:
    ext = LINE_WIDTH if positions[-1] != positions[0] else 0
    return positions[0] - ext / 2, (positions[-1] - positions[0]) + ext
