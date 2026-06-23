from __future__ import annotations

from html import escape as _escape

from rtt.app import grid_tables

_DESCENDERS = "gjpqy"


def _underline_html(text: str, spans) -> str:
    out, i = [], 0
    for start, length in sorted(spans):
        seg = text[start : start + length]
        tag = '<u class="rtt-desc">' if any(c in _DESCENDERS for c in seg) else "<u>"
        out.append(_escape(text[i:start]) + tag + _escape(seg) + "</u>")
        i = start + length
    out.append(_escape(text[i:]))
    return "".join(out)


_MATH_ALPHABET_RANGES = (
    (0x1D7CE, 0x1D7D7, "0", True, False),
    (0x1D400, 0x1D419, "A", True, False),
    (0x1D41A, 0x1D433, "a", True, False),
    (0x1D434, 0x1D44D, "A", False, True),
    (0x1D44E, 0x1D467, "a", False, True),
    (0x1D468, 0x1D481, "A", True, True),
    (0x1D482, 0x1D49B, "a", True, True),
)


def _demath(ch: str) -> tuple[str, bool, bool] | None:
    cp = ord(ch)
    for lo, hi, base, bold, italic in _MATH_ALPHABET_RANGES:
        if lo <= cp <= hi:
            return chr(ord(base) + cp - lo), bold, italic
    return None


def _math_html(text: str) -> str:
    out = []
    for ch in text:
        if ch == grid_tables.NORM_SUB_OPEN:
            out.append('<sub style="font-style:italic">')
            continue
        if ch == grid_tables.NORM_SUB_CLOSE:
            out.append("</sub>")
            continue
        if ch == grid_tables.SUB_OPEN:
            out.append("<sub>")
            continue
        if ch == grid_tables.SUB_CLOSE:
            out.append("</sub>")
            continue
        styled = _demath(ch)
        if styled is None:
            out.append(_escape(ch))
            continue
        base, bold, italic = styled
        css = (["font-weight:700"] if bold else []) + (["font-style:italic"] if italic else [])
        out.append(f'<span style="{";".join(css)}">{_escape(base)}</span>')
    return "".join(out)


_UNIT_PLAIN = ("oct", "¢", "/", " ")


_SUB_TAGS = {
    grid_tables.SUB_OPEN: "<sub>",
    grid_tables.SUB_CLOSE: "</sub>",
    grid_tables.NORM_SUB_OPEN: '<sub style="font-style:italic">',
    grid_tables.NORM_SUB_CLOSE: "</sub>",
}


def _run_html(s: str) -> str:
    return "".join(_SUB_TAGS.get(ch) or _escape(ch) for ch in s)


def _bold_units(value) -> str:
    out, run = [], []

    def flush():
        if run:
            out.append(f"<b>{_run_html(''.join(run))}</b>")
            run.clear()

    i = 0
    while i < len(value):
        plain = next((t for t in _UNIT_PLAIN if value.startswith(t, i)), None)
        if plain is not None:
            flush()
            out.append(_escape(plain))
            i += len(plain)
        else:
            run.append(value[i])
            i += 1
    flush()
    return "".join(out)


def _units_html(text: str) -> str:
    prefix = "units: "
    if text.startswith(prefix):
        return f'<span class="rtt-units-pre">{prefix}</span>{_bold_units(text[len(prefix) :])}'
    return _bold_units(text)
