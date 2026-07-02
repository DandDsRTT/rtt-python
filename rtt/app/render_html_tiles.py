from __future__ import annotations

from html import escape as _escape

from rtt.app import grid_tables, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.marks import angle_bracket, brace, square_bracket, top_bracket
from rtt.app.render_html_glyphs import _FOLD_GLYPH, _control_svg, _example_chart
from rtt.app.render_html_markup import _math_html, _units_html
from rtt.app.render_html_text import _cents_parts

_EXAMPLE_TEXT: dict[str, str] = {
    "counts": "𝑑",
    "interval_vectors": "[−4 4 −1⟩",
    "ebk": "⟨1 0 -4]",
    "app_units": "p₁/",
    "temperament_tiles": "𝑀",
    "form": "𝑀" + grid_tables.SUBSCRIPT_C,
    "form_controls": "canonical form",
    "form_tiles": "𝐹",
    "tuning_tiles": "T",
    "optimization": "𝑝",
    "weighting": "𝒘",
    "all_interval": "minimax-S",
    "alt_complexity": "E-lp",
    "custom_weights": "1.5",
    "projection": "𝑃",
    "interest": "𝐢",
    "generator_detempering": "D",
    "nonstandard_domain": "Bₗ",
    "identity_objects": "𝑀ⱼ",
}


_CELL_FRAME = "border:var(--cell-border);background:var(--cell-bg)"


def _ratio_face_html(numerator: str, denominator: str) -> str:
    return (
        '<span class="rtt-fraction">'
        f'<span class="rtt-fraction-numerator">{numerator}</span>'
        f'<span class="rtt-fraction-denominator">{denominator}</span>'
        "</span>"
    )


_EXAMPLE_HTML = {
    "interval_ratios": _ratio_face_html("81", "80"),
    "animations": (
        '<span style="position:relative;display:inline-block;width:34px;height:16px">'
        '<span style="position:absolute;left:0;top:1px;width:13px;height:13px;'
        'border:1px solid var(--tile-border);background:var(--cell-bg);opacity:0.35"></span>'
        '<span style="position:absolute;left:11px;top:1px;width:13px;height:13px;'
        f'{_CELL_FRAME}"></span>'
        '<span class="material-icons" style="position:absolute;right:-3px;top:1px;'
        'font-size:13px;color:var(--fg-icon)">east</span></span>'
    ),
    "preview_highlighting": (
        '<span style="display:inline-flex;align-items:center;justify-content:center;'
        "width:22px;height:16px;background:var(--cell-bg);"
        "box-shadow:inset 0 0 0 2px var(--preview-color);"
        'color:var(--preview-text-color);font-size:10px">3</span>'
    ),
    "tooltips": (
        '<span style="position:relative;display:inline-block;background:var(--demo-tip-bg);'
        "color:var(--demo-tip-fg);"
        'font-size:9px;line-height:1;padding:3px 5px;border-radius:3px">help'
        '<span style="position:absolute;left:6px;bottom:-3px;width:0;height:0;'
        "border-left:3px solid transparent;border-right:3px solid transparent;"
        'border-top:3px solid var(--demo-tip-bg)"></span></span>'
    ),
    "tuning_ranges": (
        '<svg width="14" height="20" viewBox="0 0 14 20" style="display:block">'
        '<rect x="6" y="2" width="2" height="16" style="fill:var(--fg)"/>'
        '<rect x="2" y="2" width="10" height="2" style="fill:var(--fg)"/>'
        '<rect x="2" y="16" width="10" height="2" style="fill:var(--fg)"/></svg>'
    ),
    "mapping_demos": (
        '<svg width="30" height="20" viewBox="0 0 30 20" style="display:block">'
        '<g fill="none" stroke-width="1" style="stroke:var(--c-gridline)">'
        '<rect x="2" y="2" width="8" height="7"/><rect x="10" y="2" width="8" height="7"/>'
        '<rect x="2" y="9" width="8" height="7"/><rect x="10" y="9" width="8" height="7"/></g>'
        '<path d="M6 2 L6 16 L26 16" fill="none" stroke-width="2.5" style="stroke:var(--demo-accent)"/>'
        '<path d="M14 2 L14 16" fill="none" stroke-width="2.5" style="stroke:var(--demo-accent)"/>'
        '<rect x="22" y="12.5" width="7" height="7" stroke-width="1.5" '
        'style="fill:var(--demo-accent-soft);stroke:var(--demo-accent)"/>'
        '<text x="5.4" y="13.5" font-size="7" style="fill:var(--demo-accent-ink)">×</text>'
        '<text x="19" y="18" font-size="7" style="fill:var(--demo-accent-ink)">+</text></svg>'
    ),
}

_COLORIZATION_LETTER = {"temperament": "𝑀", "tuning": "𝐺", "form": "𝐹"}


def _colorization_example_html(key: str) -> str:
    group = key.split("_", maxsplit=1)[0]
    letter = _COLORIZATION_LETTER[group]
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:36px;height:14px;background:var(--wash-{group})">{_math_html(letter)}</span>'
    )


def _example_html(key: str) -> str:
    if key in show_settings.GROUPING_PARENTS:
        return ""
    if key in _EXAMPLE_HTML:
        return _EXAMPLE_HTML[key]
    if key.split("_", maxsplit=1)[0] in _COLORIZATION_LETTER and key.endswith("_colorization"):
        return _colorization_example_html(key)
    return f'<span class="rtt-ex">{_math_html(_EXAMPLE_TEXT[key])}</span>'


_TILE_NAME = "tile name"
_TILE_SYMBOL = "𝒏"
_TILE_ROWLABEL = "𝒏₁"
_TILE_EQUIV = " = 𝑒G"
_TILE_MATH = "1200·log₂(3/2) ="
_TILE_VALUE = "701.955"
_TILE_UNITS = "¢/p"
_TILE_PLAIN_TEXT = "⟨1200 1902 2786]"

_TILE_MNEMONIC_AT = _TILE_NAME.index("n")


def _tile_name_pieces() -> tuple[str, str, str]:
    i = _TILE_MNEMONIC_AT
    return _TILE_NAME[:i], _TILE_NAME[i], _TILE_NAME[i + 1 :]


def _tile_fold_html() -> str:
    return _control_svg(_FOLD_GLYPH["unfold_less"])


_TILE_CELL = spreadsheet_constants.COLUMN_WIDTH
_TILE_BR_W = 9
_TILE_ENCLOSE = 5
_TILE_CAPTION = 5
_TILE_FRAME_W = _TILE_BR_W + _TILE_CELL + _TILE_BR_W
_TILE_FRAME_H = _TILE_CAPTION + _TILE_ENCLOSE + _TILE_CELL + _TILE_ENCLOSE + _TILE_CAPTION
_TILE_CELL_X = _TILE_BR_W
_TILE_CELL_Y = _TILE_CAPTION + _TILE_ENCLOSE


def _tile_cell_html() -> str:
    return f'<div style="width:100%;height:100%;box-sizing:border-box;{_CELL_FRAME}"></div>'


def _tile_brackets_html() -> str:
    def mark(x, y, width, height, inner):
        return (
            f'<div style="position:absolute;left:{x}px;top:{y}px;'
            f'width:{width}px;height:{height}px">{inner}</div>'
        )

    cell, cap, bracket_width, cell_x, cell_y = (
        _TILE_CELL,
        _TILE_CAPTION,
        _TILE_BR_W,
        _TILE_CELL_X,
        _TILE_CELL_Y,
    )
    span = _TILE_FRAME_W
    return (
        f'<div style="position:relative;width:{_TILE_FRAME_W}px;height:{_TILE_FRAME_H}px">'
        + mark(0, 0, span, cap, top_bracket(span, cap))
        + mark(0, _TILE_FRAME_H - cap, span, cap, brace(span, cap))
        + mark(0, cell_y, bracket_width, cell, angle_bracket(bracket_width, cell))
        + mark(
            cell_x + cell, cell_y, bracket_width, cell, square_bracket(bracket_width, cell, "right")
        )
        + "</div>"
    )


_TILE_POWER = "2"


def _tile_controls_html() -> str:
    def opt(label, on):
        cls = "rtt-range-option rtt-range-option-on" if on else "rtt-range-option"
        return (
            f'<span class="{cls}"><span class="rtt-rangebox"></span>'
            f'<span class="rtt-rangelabel">{label}</span></span>'
        )

    radio = (
        '<span class="rtt-range-mode" style="width:auto;padding:0;gap:2px">'
        + opt("additional", True)
        + opt("tile", False)
        + "</span>"
    )
    power = (
        '<span style="display:inline-flex;flex-direction:column;align-items:center;gap:1px">'
        '<span style="display:inline-flex;align-items:center;justify-content:center;'
        "width:22px;height:22px;background:var(--cell-bg);border:1px solid var(--tile-border);border-radius:2px;"
        f'font-size:13px;color:var(--fg)">{_TILE_POWER}</span>'
        '<span style="font-size:9px;color:var(--fg);line-height:1">controls</span></span>'
    )
    return f'<span style="display:flex;align-items:center;gap:10px">{radio}{power}</span>'


def _tile_preset_html() -> str:
    return (
        '<span style="display:flex;align-items:center;justify-content:space-between;'
        "gap:4px;width:100%;height:22px;box-sizing:border-box;background:var(--cell-bg);"
        "border:1px solid var(--tile-border);"
        'border-radius:2px;padding:0 2px 0 6px;font-size:13px;color:var(--fg)">(presets)'
        '<span class="material-icons" '
        'style="font-size:16px;color:var(--fg-icon)">arrow_drop_down</span></span>'
    )


_GENERAL_PART_BUILDERS = {
    "gridded_values": _tile_cell_html,
    "brackets": _tile_brackets_html,
    "math_expressions": lambda: _math_html(_TILE_MATH),
    "quantities": lambda: f'<span class="rtt-stacked-main">{_cents_parts(_TILE_VALUE)[0]}</span>',
    "decimals": lambda: f'<span class="rtt-stacked-sub">.{_cents_parts(_TILE_VALUE)[1]}</span>',
    "symbols": lambda: _math_html(_TILE_SYMBOL),
    "header_symbols": lambda: _math_html(_TILE_ROWLABEL),
    "equivalences": lambda: _math_html(_TILE_EQUIV),
    "names": lambda: _escape(_TILE_NAME),
    "mnemonics": lambda: _escape(_tile_name_pieces()[1]),
    "tile_units": lambda: f'<span class="rtt-units-pre">units: </span>{_units_html(_TILE_UNITS)}',
    "cell_units": lambda: _units_html(_TILE_UNITS),
    "plain_text_values": lambda: _math_html(_TILE_PLAIN_TEXT),
    "presets": _tile_preset_html,
    "charts": _example_chart,
    "tile_controls": _tile_controls_html,
    "drag_to_combine": lambda: (
        '<span class="material-icons" style="color:var(--fg-icon)">drag_indicator</span>'
    ),
}


def _general_part_html(key: str) -> str:
    if key not in _GENERAL_PART_BUILDERS:
        raise KeyError(key)
    return _GENERAL_PART_BUILDERS[key]()
