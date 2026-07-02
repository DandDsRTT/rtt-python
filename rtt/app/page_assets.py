from __future__ import annotations

import base64
import hashlib
import json
import logging
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from nicegui import app, helpers, ui

from rtt.app import (
    service,
    spreadsheet,
    spreadsheet_constants,
    tooltips,
)
from rtt.app.marks import (
    BR_COLOR,
    PENDING_COLOR,
)
from rtt.app.render_html import (
    _RATIO_MAX_FONT,
    _mode_svg,
    _option_box_svg,
    _wave_svg,
)

_log = logging.getLogger(__name__)


def callback_method(function):
    function._rtt_cb = True
    return function


class _KindHandlers(NamedTuple):
    build: Callable
    update: Callable | None = None


_ASSETS = Path(__file__).parent / "assets"

_CACHE_FOREVER = 31536000

# Self-host the body font same-origin so every machine renders the same face (a non-self-hosted face
# falls back per-OS to differing proportional digits). The Math face supplies the ⟨⟩⟪⟫ EBK brackets
# the Text face omits. Registering at import is idempotent across the reload worker and the test
# re-imports (FastAPI's duplicate route is harmless — first match wins).
app.add_static_files("/rtt-fonts", _ASSETS / "fonts", max_cache_age=_CACHE_FOREVER)
app.add_static_files("/rtt-assets", _ASSETS, max_cache_age=_CACHE_FOREVER)


def _content_hash(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()[:10]


def _asset_url(name: str) -> str:
    return f"/rtt-assets/{name}?v={_content_hash(_ASSETS / name)}"


def _font_url(file: str) -> str:
    return f"/rtt-fonts/{file}?v={_content_hash(_ASSETS / 'fonts' / file)}"


_PAD = 12
_T = "0.25s"
_PANEL_W = 330
_TAB_W = 40
_TAB_H = 218
_CHROME_H = 40
_TOOLTIP_DELAY_MS = 700
# Quasar defaults the tooltip show-delay to 0; this waits for a deliberate cursor rest instead.
_STORE_KEY = "rtt_doc"
_STATE_PARAM = "state"
_DARK_KEY = "rtt_dark"
_CHAPTER_KEY = "rtt_chapter"
_STORAGE_SECRET = "dnd-rtt-app"
# NiceGUI: under the in-process User test simulation app.storage.user is file-backed, so writing it
# per render litters the tree and races the harness teardown; a module-level dict gives the same
# survives-a-refresh persistence per test with no file I/O (production uses app.storage.user).
_MEMORY_STORE: dict = {}


def _doc_store() -> dict:
    return _MEMORY_STORE if helpers.is_user_simulation() else app.storage.user


_MAX_STATE_TOKEN = 16384
_MAX_STATE_BYTES = 256 * 1024


def _encode_state(data: dict) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode_state(token: str) -> dict:
    if len(token) > _MAX_STATE_TOKEN:
        raise ValueError("share-link token too long")
    decompressor = zlib.decompressobj()
    raw = decompressor.decompress(base64.urlsafe_b64decode(token.encode("ascii")), _MAX_STATE_BYTES)
    if not decompressor.eof:
        raise ValueError("share-link state exceeds the decompression cap")
    return json.loads(raw.decode("utf-8"))


_INVALID_TEMPERAMENT = (
    "Not a valid temperament: the generators must be independent and every prime reached."
)
_INVALID_FORM = (
    "Not a valid generator form: 𝐹 must be a square matrix with determinant ±1 (unimodular)."
)

_SUBPICK_POPUP_W = 220

_INVALID_PROJECTION = (
    "That isn't a valid projection — 𝑃 must be idempotent (𝑃² = 𝑃) with the commas in its kernel."
)
_INVALID_EMBEDDING = "That isn't a valid embedding — 𝑀𝐺 must equal the identity."

_INVALID_PRESCALER = "A prescaler diagonal entry must be a positive, finite number."
_INVALID_WEIGHT = "A damage weight must be a positive, finite number."

_INVALID_UNCHANGED = (
    "That isn't a valid unchanged-interval basis — each entry must be a whole number."
)

_LOAD_FAILED = (
    "Couldn’t restore your saved document — showing the defaults. Your saved data is kept; "
    "editing anything here will replace it."
)

_SEAM = "#999"
_PENDING_TEXT_COLOR = "color-mix(in srgb, var(--pending-color) 60%, black)"
_PREVIEW_COLOR = "#e8c00a"
_PREVIEW_TEXT_COLOR = "color-mix(in srgb, var(--preview-color) 60%, black)"
_PREVIEW_REMOVE_COLOR = "#e53935"
_PREVIEW_REMOVE_TEXT_COLOR = "color-mix(in srgb, var(--preview-remove-color) 60%, black)"
_CELL_BORDER_W = 1
_CELL_BORDER = f"{_CELL_BORDER_W}px solid {BR_COLOR}"
_CELL_FONT = spreadsheet_constants.CELL_FONT
_GENSIGN_W = 9
_STACKED_MAIN_FONT = spreadsheet_constants.STACKED_MAIN_FONT
_TINTS = {"tuning": "#9acdcd", "temperament": "#cdcd9a", "form": "#cd9acd"}

_DARK_FRAME = "#15171a"
_DARK_PANE = "#1f2329"
_DARK_PANEL = "#272c33"
_DARK_GROUP = "#2c323a"
_DARK_BOX = "#31373f"
_DARK_CELL = "#1b1f24"
_DARK_TEXT = "#e3e6ea"
_DARK_CAPTION = "#aeb4bc"
_DARK_MUTED = "#71777f"
_DARK_ICON = "#9aa1a9"
_DARK_HOVER_TEXT = "#cfd4da"
_DARK_MARK = "#8d949d"
_DARK_TILE_BORDER = "#454c54"
_DARK_SOFT_LINE = "#3c424a"
_DARK_INPUT_LINE = "#4e555d"

_DARK_PALETTE_VARS = (
    ("--dark-pane", _DARK_PANE),
    ("--dark-panel", _DARK_PANEL),
    ("--dark-group", _DARK_GROUP),
    ("--dark-box", _DARK_BOX),
    ("--dark-cell", _DARK_CELL),
    ("--dark-text", _DARK_TEXT),
    ("--dark-caption", _DARK_CAPTION),
    ("--dark-muted", _DARK_MUTED),
    ("--dark-icon", _DARK_ICON),
    ("--dark-hover-text", _DARK_HOVER_TEXT),
    ("--dark-mark", _DARK_MARK),
    ("--dark-tile-border", _DARK_TILE_BORDER),
    ("--dark-soft-line", _DARK_SOFT_LINE),
    ("--dark-input-line", _DARK_INPUT_LINE),
)

_WHEEL_STEPS = {
    "mapping": 1,
    "comma_cell": 1,
    "interest_cell": 1,
    "held_cell": 1,
    "target_cell": 1,
    "power_input": 1,
    "prescaler_cell": 0.001,
}
_INT_WHEEL_JS = (
    "(e) => { if (e.currentTarget.contains(document.activeElement)) "
    "{ e.preventDefault(); emit(e); } }"
)
_TARGET_LIMIT_DEBOUNCE = 0.3
_BUSY_DELAY_MS = 180
_BUSY_SAFETY_MS = 6000


class _GridValueSpec(NamedTuple):
    ratio_allowed: bool
    pending: bool
    commit: str
    preview: str | None
    cid_arg: bool
    arm: tuple | None = None


class _VecGridEdit(NamedTuple):
    group: str
    count: Callable[[], int]
    cell_id: Callable[[object, int], str]
    pending: Callable[[], object]
    set_pending: Callable[[list], None]
    commit: Callable[[list], None]
    validate: Callable[[list], bool] | None = None
    guard: Callable[[], bool] | None = None
    draft_arms: bool = False


_GRIDVALUE_SPECS = {
    "ratio_cell": _GridValueSpec(True, True, "on_ratio_change", None, True),
    "element_cell": _GridValueSpec(True, True, "on_element_change", "on_element_preview", True),
    "element_ratio": _GridValueSpec(True, True, "on_element_change", "on_element_preview", True),
    "mapping": _GridValueSpec(
        False, True, "on_mapping_change", "on_mapping_change", False, ("row",)
    ),
    "form_cell": _GridValueSpec(False, False, "on_form_change", "on_form_change", False),
    "comma_cell": _GridValueSpec(
        False, True, "on_comma_change", "on_comma_change", False, ("col", "comma")
    ),
    "unchanged_cell": _GridValueSpec(
        False, False, "on_unchanged_change", "on_unchanged_change", False
    ),
    "interest_cell": _GridValueSpec(
        False, True, "on_interest_change", "on_interest_change", False, ("col", "interest")
    ),
    "held_cell": _GridValueSpec(
        False, True, "on_held_change", "on_held_change", False, ("col", "held")
    ),
    "target_cell": _GridValueSpec(
        False, True, "on_target_cells_change", "on_target_cells_change", False, ("col", "target")
    ),
}


def _vgroup_key(cell_box: spreadsheet.CellBox) -> str:
    if cell_box.kind in ("mapping", "target_cell"):
        return cell_box.id.rsplit(":", 1)[0]
    if cell_box.kind == "form_cell":
        return "cell:form"
    parts = cell_box.id.split(":")
    return ":".join(parts[:2] + parts[3:])


_MODE_FILLS = (
    (frozenset({(1, 1)}), "note"),
    (frozenset({(2, 0), (1, 1), (0, 2)}), "arpeggio"),
    (frozenset({(0, 1), (1, 1), (2, 1)}), "chord"),
    (frozenset({(2, 0), (1, 1), (0, 2), (1, 2), (2, 1), (2, 2)}), "rolled chord"),
)
_AUDIO_GLYPHS = {
    "mute": [
        '<span class="material-icons rtt-audio-glyph">volume_up</span>',
        '<span class="material-icons rtt-audio-glyph">volume_off</span>',
    ],
    "wave": [_wave_svg(w) for w in ("sine", "square", "triangle", "sawtooth")],
    "mode": [_mode_svg(fill, name) for fill, name in _MODE_FILLS],
    "lock": [
        '<span class="material-icons rtt-audio-glyph">lock_open</span>',
        '<span class="material-icons rtt-audio-glyph">lock</span>',
    ],
    "root": '<span class="rtt-audio-root-glyph">1/1</span>',
}

_BOOT_JS = (_ASSETS / "boot.js").read_text(encoding="utf-8")

_STACKED_EDIT_JS = (_ASSETS / "stacked_edit.js").read_text(encoding="utf-8")

_AUDIO_JS = (_ASSETS / "audio.js").read_text(encoding="utf-8")

# Browser: the column-title strip sits outside the body scroller (so the scrollbar can stop below it),
# so CSS can't make it ride the scroll — this listener translateX-syncs it instead. scroll doesn't
# bubble, so it's caught in the capture phase.
_FREEZE_JS = (_ASSETS / "freeze.js").read_text(encoding="utf-8")

_FRACTION_JS = (_ASSETS / "fraction.js").read_text(encoding="utf-8")

_DECIMAL_JS = (_ASSETS / "decimal.js").read_text(encoding="utf-8")

_ACTIVECELL_JS = (_ASSETS / "activecell.js").read_text(encoding="utf-8")

_MAPPING_DEMO_JS = (_ASSETS / "mapping_demo.js").read_text(encoding="utf-8")

_TOUR_JS = (_ASSETS / "tour.js").read_text(encoding="utf-8")

# NiceGUI: a tour step's `selector` must be a real DOM region class, NOT a .mark() (which exists only under
# the test simulation), or the spotlight finds nothing in production.
_TOUR_STEPS = [
    {
        "selector": "",
        "title": "Welcome to D&D's RTT app",
        "body": "A grid for exploring regular temperaments. We'll start at the simplest view and build "
        "up from there. Use <b>Next</b> / <b>Back</b> (or the arrow keys), and <b>Skip</b> to leave "
        "anytime.",
    },
    {
        "selector": '.rtt-cell[data-eid^="cell:mapping:"]',
        "region": True,
        "place": "bottom",
        "title": "The mapping",
        "body": "This is the <b>mapping</b> — the heart of a temperament. It says how many of each "
        "generator it takes to approximate each prime: one row per generator, one column per prime. "
        "Everything else on the grid is computed from it.",
    },
    {
        "selector": '.rtt-cell[data-eid^="cell:comma:"]',
        "region": True,
        "place": "top",
        "interact": True,
        "gate": "demo",
        "title": "Tempering out",
        "body": "This little interval is the comma <b>81/80</b>. Hover it and watch the mapping send "
        "it to <b>[0 0]</b> — zero of every generator. It <b>vanishes</b>. That's what it means to "
        "<b>temper it out</b>: the temperament treats this comma as a unison, no change in pitch. "
        "<i>(Hover the comma to continue.)</i>",
    },
    {
        "selector": '.rtt-cell[data-eid^="cell:mapping:"]',
        "region": True,
        "place": "bottom",
        "interact": True,
        "gate": "edited",
        "title": "Try an edit",
        "body": "Your turn — the boxed numbers in the mapping are editable. Click one, type a "
        "different whole number, and press Enter. The whole grid recomputes around your new "
        "temperament. <b>Undo</b> up top always steps back. <i>(Make an edit to continue.)</i>",
    },
    {
        "selector": ".rtt-fan-button",
        "place": "bottom",
        "title": "Reshaping the grid",
        "body": "The grid grows and shrinks with you. A <b>+</b> adds a column or row — a new interval "
        "or mapping row; hovering a column or row reveals a <b>−</b> to remove it. The little "
        "chevrons expand or collapse a tile.",
    },
    {
        "selector": ".rtt-titletile",
        "place": "bottom",
        "title": "Undo, reset & share",
        "body": "Up here: <b>undo</b> / <b>redo</b> your edits, <b>reset</b> everything back to this "
        "simple starting point, and <b>share</b> a link that reopens the app in exactly this state.",
    },
    {
        "selector": ".rtt-chapter-group",
        "place": "right",
        "open": True,
        "interact": True,
        "gate": "chapter4",
        "title": "Reveal more, chapter by chapter",
        "body": "This is the settings panel — it controls everything the grid shows. Start with the "
        "<b>chapter</b> slider: it follows D&D's guide, revealing more one chapter at a time. Drag it "
        "from <b>2</b> up to <b>4</b> and watch the tuning and the other intervals of interest fill "
        "in. <i>(Drag to chapter 4 to continue.)</i>",
    },
    {
        "selector": ".rtt-show-general",
        "place": "right",
        "open": True,
        "title": "Tile features",
        "body": "This sample tile is a live menu: click any part of it — the name, the symbol, the "
        "value — to show or hide that feature across the whole grid.",
    },
    {
        "selector": ".rtt-show-scroll .rtt-show-group:last-child",
        "place": "right",
        "open": True,
        "title": "App features",
        "body": "These checkboxes reveal each kind of feature — including <b>mapping demos</b>, the one "
        "that drew those animations. The grid starts full; untick anything you don't need to "
        "declutter, and tick more back on as you explore.",
    },
    {
        "selector": "",
        "title": "Explore from here",
        "body": "That's the tour. Nothing here is permanent — <b>reset</b> brings back this simple "
        "starting point, and the <b>?</b> button replays this tour anytime. Happy tempering!",
    },
]

_STACKED_EXIT_JS = (
    "(e) => { const b = e.target.closest('.rtt-fraction-edit, .rtt-decimal-edit'); "
    "if (!b || !b.contains(e.relatedTarget)) emit(); }"
)

_GROUP_EXIT_JS = (
    "(e) => { const g = e.target.closest('[data-vgroup]'), "
    "t = e.relatedTarget && e.relatedTarget.closest && e.relatedTarget.closest('[data-vgroup]'); "
    "if (!g || !t || g.getAttribute('data-vgroup') !== t.getAttribute('data-vgroup')) emit(); }"
)


_WASH_TINT_CSS = "".join(f"--wash-{group}:{tint}; " for group, tint in _TINTS.items())

_CSS_VARS = f""":root {{
  --pad:{_PAD}px; --t:{_T}; --tab-w:{_TAB_W}px; --tab-h:{_TAB_H}px; --chrome-h:{_CHROME_H}px; --panel-w:{_PANEL_W}px;
  --seam:{_SEAM}; --ebk-mark:{BR_COLOR}; --pending-color:{PENDING_COLOR}; --pending-text-color:{_PENDING_TEXT_COLOR}; --preview-color:{_PREVIEW_COLOR}; --preview-text-color:{_PREVIEW_TEXT_COLOR}; --preview-remove-color:{_PREVIEW_REMOVE_COLOR}; --preview-remove-text-color:{_PREVIEW_REMOVE_TEXT_COLOR};
  --c-gridline:#e0e0e0;
  --wash-base:#fff; {_WASH_TINT_CSS}
  --cell-border-w:{_CELL_BORDER_W}px; --cell-border:{_CELL_BORDER}; --cell-font:{_CELL_FONT}px;
  --symbol-font:{spreadsheet_constants.SYMBOL_FONT}px; --caption-font:{spreadsheet_constants.CAPTION_FONT}px; --stacked-main-font:{spreadsheet_constants.STACKED_MAIN_FONT}px; --stacked-sub-font:{spreadsheet_constants.STACKED_SUB_FONT}px; --sub-font-pct:{spreadsheet_constants.SUB_FONT_PCT}%;
  --zoom-factor:{_CELL_FONT / _STACKED_MAIN_FONT};
  --label-w:{spreadsheet_constants.LABEL_WIDTH}px; --header-h:{spreadsheet_constants.HEADER_HEIGHT}px; --line-w:{spreadsheet_constants.LINE_WIDTH}px;
  --plain-text-edit-h:{spreadsheet_constants.PLAIN_TEXT_EDIT_HEIGHT}px; --option-box:{spreadsheet_constants.OPTION_BOX_PX}px; --button:{spreadsheet_constants.BUTTON}px; --preset-h:{spreadsheet_constants.PRESET_HEIGHT}px;
  --option-box-unchecked:url("{_option_box_svg(None)}");
  --option-box-checked:url("{_option_box_svg("#000")}");
  --option-box-disabled:url("{_option_box_svg("#888")}");
  --rtt-serif:'STIX Two Text','STIX Two Math','STIX Fallback',Georgia,serif;
  --rtt-units-sans:'Jost','Corbel','Candara','Trebuchet MS',sans-serif;
}}
"""

_FONT_FILES = (
    ("STIX Two Text", "normal", 400, "STIXTwoText-Regular-subset.woff2"),
    ("STIX Two Text", "italic", 400, "STIXTwoText-Italic-subset.woff2"),
    ("STIX Two Text", "normal", 700, "STIXTwoText-Bold-subset.woff2"),
    ("STIX Two Text", "italic", 700, "STIXTwoText-BoldItalic-subset.woff2"),
    ("STIX Two Math", "normal", 400, "STIXTwoMath-subset.woff2"),
    ("Jost", "normal", 400, "Jost-Regular.woff2"),
    ("Jost", "normal", 700, "Jost-Bold.woff2"),
)

_FONT_FACE = "".join(
    f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
    f"font-display:swap;src:url('{_font_url(file)}') format('woff2');}}"
    for fam, style, weight, file in _FONT_FILES
)

_FONT_FALLBACK = (
    "@font-face{font-family:'STIX Fallback';src:local('Georgia');"
    "ascent-override:76.2%;descent-override:23.8%;line-gap-override:25%;}"
)

_DARK_PALETTE_CSS = "".join(f"{name}:{value}; " for name, value in _DARK_PALETTE_VARS)

_CSS_DARK_VARS = f"""body.rtt-dark {{
  {_DARK_PALETTE_CSS}
  --option-box-unchecked:url("{_option_box_svg(None, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-checked:url("{_option_box_svg(_DARK_TEXT, box=_DARK_CELL, border=_DARK_MARK)}");
  --option-box-disabled:url("{_option_box_svg(_DARK_MUTED, box=_DARK_CELL, border=_DARK_MARK)}");
}}
"""
_CSS = (
    _FONT_FACE
    + _CSS_VARS
    + (_ASSETS / "rtt.css").read_text(encoding="utf-8")
    + _CSS_DARK_VARS
    + (_ASSETS / "rtt-dark.css").read_text(encoding="utf-8")
    + (_ASSETS / "tour.css").read_text(encoding="utf-8")
)

_CSS_FILES = ("rtt.css", "rtt-dark.css", "tour.css")

_JS_MODULES = (
    "boot.js",
    "stacked_edit.js",
    "audio.js",
    "freeze.js",
    "fraction.js",
    "decimal.js",
    "activecell.js",
    "zoom.js",
    "guide.js",
    "mapping_demo.js",
    "tour.js",
)

_PRELOAD_FONTS = (
    "STIXTwoText-Regular-subset.woff2",
    "STIXTwoText-Italic-subset.woff2",
    "STIXTwoText-Bold-subset.woff2",
    "STIXTwoMath-subset.woff2",
    "Jost-Regular.woff2",
)


def _head_html() -> str:
    preloads = "".join(
        f'<link rel="preload" as="font" type="font/woff2" href="{_font_url(file)}" crossorigin>'
        for file in _PRELOAD_FONTS
    )
    inline_style = f"<style>{_FONT_FACE}{_FONT_FALLBACK}{_CSS_VARS}{_CSS_DARK_VARS}</style>"
    stylesheets = "".join(
        f'<link rel="stylesheet" href="{_asset_url(name)}">' for name in _CSS_FILES
    )
    inline_data = (
        f"<script>window.__rttAudioGlyphs={json.dumps(_AUDIO_GLYPHS)};"
        f"window.rttFraction={{ratioFont:{_RATIO_MAX_FONT:g}}};"
        f"window.rttTour={{steps:{json.dumps(_TOUR_STEPS)},autostart:true}};</script>"
    )
    scripts = "".join(f'<script defer src="{_asset_url(name)}"></script>' for name in _JS_MODULES)
    return preloads + inline_style + stylesheets + inline_data + scripts


HEAD_HTML = _head_html()


_UNITS_MAX_FONT = 10.0
_CELLUNIT_MAX_FONT = 7.0
_MATRIX_LABEL_FONT = 11.0
_MATRIX_LABEL_MIN_FONT = 6.0


_EBK_SVG_KINDS = {"bracket", "ebktop", "ebkbrace", "ebkangle", "vbar", "hbar"}

GRIDVALUE_KINDS = frozenset(_GRIDVALUE_SPECS)

_EBK_SQUARE = str.maketrans("⟨{⟩}", "[[]]")
_TRANSPOSE_MARK = "ᵀ"

_PLAIN_TEXT_DUAL_VECTOR_KIND = {
    "plain_text:vectors:commas": True,
    "plain_text:vectors:targets": True,
    "plain_text:projection:generators": True,
    "plain_text:mapping:primes": False,
    "plain_text:projection:primes": False,
    "plain_text:prescaling:primes": False,
}


_GENERAL_TILE_LINES: tuple[tuple[str, ...], ...] = (
    ("drag_to_combine", "gridded_values", "math_expressions", "quantities", "decimals"),
    ("symbols", "equivalences"),
    ("mnemonics", "names"),
    ("units",),
    ("plain_text_values",),
    ("presets",),
    ("charts",),
    ("tile_controls",),
)

_TILE_IN_CELL_LAYERS: tuple[str, ...] = ("header_symbols", "cell_units")

_TILE_HOST: dict[str, str] = {
    "quantities": "gridded_values",
    "decimals": "gridded_values",
    "math_expressions": "gridded_values",
}

_TILE_FONT = {
    "symbols": 15,
    "equivalences": 15,
    "row_label": spreadsheet_constants.MATRIX_LABEL_HEIGHT - 2,
    "names": spreadsheet_constants.CAPTION_FONT,
    "mnemonics": spreadsheet_constants.CAPTION_FONT,
    "units": 10,
    "cellunit": 7,
    "plain_text_values": 11,
    "drag_to_combine": 18,
}


_AUDIO_BANK = (
    ("mute", _AUDIO_GLYPHS["mute"][0], "toggleMute"),
    ("wave", _AUDIO_GLYPHS["wave"][0], "cycleWave"),
    ("mode", _AUDIO_GLYPHS["mode"][0], "cycleMode"),
    ("hold", _AUDIO_GLYPHS["lock"][0], "toggleHold"),
    ("root", _AUDIO_GLYPHS["root"], "toggleRoot"),
)


def _audio_bank() -> ui.element:
    bank = ui.element("div").classes("rtt-tile-bank").mark("audiobank")
    with bank:
        for control, glyph, function in _AUDIO_BANK:
            ui.html(glyph).classes("rtt-audio-control").mark(f"audio_control:{control}").props(
                f'data-audio-control="{control}"'
            ).on("click", js_handler=f"() => window.rttAudio.{function}()").tooltip(
                tooltips.AUDIO_HELP[control]
            )
    return bank


# Quasar/Vue: the dropdown popup is teleported to <body>, so a per-option slot can't reach the server
# (its $parent is the menu, and Vue templates block non-whitelisted globals like `document`). So each
# option stamps data-optidx/data-optcid and this one document-level delegation reads them and fires an
# `opthover` CustomEvent at the chooser's cell. It debounces (~90 ms settle) and dedupes because each
# preview is a server re-solve and raw mouseover would flood the socket past its heartbeat (-> reload).
_OPTION_HOVER_DELEGATION = """
(() => {
  if (window.__rttOptHover) return;
  window.__rttOptHover = true;
  let lastCid = null, lastIdx = null, timer = null;
  const fire = (cid, d) => { if (cid === lastCid && d === lastIdx) return; lastCid = cid; lastIdx = d;
    const w = cid && document.querySelector('[data-eid="' + cid + '"]');
    if (w) w.dispatchEvent(new CustomEvent('opthover', {detail: d})); };
  const optOf = (n) => n && n.closest && n.closest('.q-item[data-optidx], .rtt-range-option[data-optidx]');
  document.addEventListener('mouseover', (e) => {
    const it = optOf(e.target);
    if (it) { clearTimeout(timer);
      const cid = it.getAttribute('data-optcid'), idx = parseInt(it.getAttribute('data-optidx'), 10);
      timer = setTimeout(() => fire(cid, idx), 90); }
  });
  document.addEventListener('mouseout', (e) => {
    const it = optOf(e.target);
    if (it && !optOf(e.relatedTarget)) { clearTimeout(timer); fire(it.getAttribute('data-optcid'), -1); }
  });
  // Browser: a removed element under the cursor does not fire mouseout reliably, so the pending
  // settle-timer is cancelled here on pointerdown rather than relying on the popup-removal mouseout.
  document.addEventListener('pointerdown', () => { clearTimeout(timer); lastCid = null; lastIdx = null; }, true);
})()
"""


# Quasar: a tooltip hides only on its anchor's `mouseleave`, so it strands on screen when the anchor is
# removed or reflowed out from under a stationary cursor before any leave fires. These capture-phase
# listeners synthesize that `mouseleave` (only — never blur, so the cells' blur-commit handlers stay
# untouched) before a reflow: from the pressed node on pointerdown, from the :hover node on keydown/wheel.
_TOOLTIP_DISMISS_JS = """
(() => {
  if (window.__rttTipDismiss) return;
  window.__rttTipDismiss = true;
  const dropFrom = (node) => {
    for (let el = node; el instanceof Element; el = el.parentElement) {
      el.dispatchEvent(new MouseEvent('mouseleave', {bubbles: false}));
    }
  };
  document.addEventListener('pointerdown', (e) => dropFrom(e.target), true);
  const dropHovered = () => {
    if (document.querySelector('.q-tooltip') === null) return;
    const hov = document.querySelectorAll(':hover');
    if (hov.length) dropFrom(hov[hov.length - 1]);
  };
  document.addEventListener('keydown', dropHovered, true);
  document.addEventListener('wheel', dropHovered, {capture: true, passive: true});
})()
"""


_SEED_DARK_JS = """
(() => {
  const dark = () => !!(window.matchMedia
    && window.matchMedia('(prefers-color-scheme: dark)').matches);
  try {
    if (typeof emitEvent === 'function') emitEvent('rtt_seed_dark', dark());
  } catch (e) {}
})()
"""


def boot_theme_head(dark_pref: bool | None) -> str:
    pref = "null" if dark_pref is None else ("true" if dark_pref else "false")
    return (
        "<style>body:not(.rtt-themed){visibility:hidden;}</style>"
        "<script>(function(){try{"
        f"var p={pref};"
        "var d=p===null?!!(window.matchMedia&&"
        "window.matchMedia('(prefers-color-scheme: dark)').matches):p;"
        f"document.documentElement.style.background=d?'{_DARK_FRAME}':'#fff';"
        "window.__rttBootDark=d;"
        "setTimeout(function(){var b=document.body;"
        "if(!b||b.classList.contains('rtt-themed'))return;"
        "if(window.__rttBootDark)b.classList.add('rtt-dark');"
        "b.classList.add('rtt-themed');},2000);"
        "}catch(e){}})();</script>"
    )
# The busy scrim is armed client-side because a synchronous re-render holds the event loop until it
# finishes, so the server can't send a "show scrim" message mid-work — only the browser can in that
# window. Every server render() ends by calling rttBusy.done(), so the scrim lifts when the grid lands.
_BUSY_JS = f"""
(() => {{
  if (window.rttBusy) return;
  let armTimer = null, safety = null;
  const scrim = () => document.querySelector('.rtt-busy');
  const reveal = () => {{ const o = scrim(); if (o) o.classList.add('rtt-busy-on'); }};
  const clear = () => {{
    if (armTimer) {{ clearTimeout(armTimer); armTimer = null; }}
    if (safety) {{ clearTimeout(safety); safety = null; }}
    const o = scrim(); if (o) o.classList.remove('rtt-busy-on');
  }};
  const arm = () => {{
    if (armTimer) clearTimeout(armTimer);
    if (safety) clearTimeout(safety);
    armTimer = setTimeout(reveal, {_BUSY_DELAY_MS});
    safety = setTimeout(clear, {_BUSY_SAFETY_MS});
  }};
  window.rttBusy = {{ arm, done: clear }};

  // reads --t off BODY, where the `animations`-off CSS class overrides it to 0s, so the reveal is
  // instant when animations are off.
  window.rttScheduleReveal = () => {{
    const t = getComputedStyle(document.body).getPropertyValue('--t').trim();
    const ms = (t.endsWith('ms') ? parseFloat(t) : parseFloat(t) * 1000) * 1.3;
    clearTimeout(window.__rttReveal);
    window.__rttReveal = setTimeout(() => {{
      document.querySelectorAll('.rtt-withhold').forEach(el => {{
        el.classList.remove('rtt-withhold');
        el.classList.add('rtt-reveal');
      }});
    }}, ms);
  }};

  // Browser: render() re-syncs control values programmatically (box.value = …), which fires SYNTHETIC
  // events; the e.isTrusted gate keeps those from re-arming the scrim after a render.
  const BUTTON = '.rtt-fan-button,.rtt-minus-button,.rtt-minus-button-v,.rtt-toggle,.rtt-icon-button';
  const at = (e, selector) => e.isTrusted && e.target && e.target.closest && e.target.closest(selector);
  document.addEventListener('pointerdown',
    (e) => {{ if (at(e, BUTTON) && !e.target.closest('.rtt-noarm')) window.rttBusy.arm(); }}, true);
  // Quasar's QCheckbox/QRadio commit on a CLICK of their role= div and never emit a DOM `change`,
  // so the committing settings controls are reached here on click, not on a `change` event.
  document.addEventListener('click', (e) => {{
    if (at(e, '[role=option],.q-item,.q-checkbox,.q-radio,.rtt-range-option')) window.rttBusy.arm();
  }}, true);
  // Browser: keys match on e.code (the physical key) so a Mac's Option+letter dead-keys and special
  // glyphs still match; preventDefault stops the browser's own Ctrl+Z / Alt-mnemonic / Cmd+, firing.
  document.addEventListener('keydown', (e) => {{
    if (!e.isTrusted) return;
    const mod = e.ctrlKey || e.metaKey;
    let selector = null, arm = true;
    if (mod && !e.altKey && e.code === 'KeyZ') selector = e.shiftKey ? '.rtt-hk-redo' : '.rtt-hk-undo';
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'KeyY') selector = '.rtt-hk-redo';
    else if (e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {{
      const k = {{KeyC: 'comma', KeyM: 'mapping', KeyT: 'target', KeyH: 'held', KeyI: 'interest', KeyE: 'element'}}[e.code];
      if (k) selector = '.rtt-hk-' + k;
    }}
    else if (mod && !e.altKey && !e.shiftKey && e.code === 'Comma') {{ selector = '.rtt-hamburger'; arm = false; }}  // pane toggle is pure CSS — don't flash the scrim
    if (selector) {{
      const el = document.querySelector(selector);
      if (el) {{ e.preventDefault(); if (arm) window.rttBusy.arm(); el.click(); return; }}
    }}
    if (e.key === 'Enter' && e.target.closest && e.target.closest('.rtt-cell')) window.rttBusy.arm();
  }}, true);

  // Browser: the shown scrim's pointer-events:auto veil eats the wheel along with clicks, so while it
  // is up the wheel deltas are forwarded to the grid's own scroller by hand.
  document.addEventListener('wheel', (e) => {{
    const o = scrim(); if (!o || !o.classList.contains('rtt-busy-on')) return;
    const body = document.querySelector('.rtt-gridbody'); if (!body) return;
    const f = e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? body.clientHeight : 1;
    body.scrollTop += e.deltaY * f;
    body.scrollLeft += e.deltaX * f;
  }}, {{capture: true, passive: true}});
}})()
"""


class _GroupedSelect(ui.select):
    def __init__(self, options, *, is_divider, **kwargs) -> None:
        self._is_divider = is_divider
        super().__init__(options, **kwargs)

    def _update_options(self) -> None:
        # NiceGUI rebuilds the Quasar option dicts in super()._update_options(), so the divider rows
        # must be re-flagged disabled here after it, or a later set_options()/update() drops the flag.
        super()._update_options()
        for option, value in zip(self._props["options"], self._values, strict=False):
            if self._is_divider(value):
                option["disable"] = True


def _set_offlist_prompt(select: ui.select, value, prompt: str = "-") -> None:
    if value is None:
        select.props(f'display-value="{prompt}"')
    else:
        select.props(remove="display-value")


def build_radio_option(label: str) -> ui.element:
    opt = ui.element("div").classes("rtt-range-option")
    with opt:
        ui.element("span").classes("rtt-rangebox")
        ui.label(label).classes("rtt-rangelabel")
    return opt


def build_radio_caption(text: str) -> None:
    ui.label(text).classes("rtt-radio-caption")


def _formchooser_options(cell_id: str) -> dict:
    if cell_id.endswith(":mapping"):
        return {
            "": "choose form",
            **{k: service.MAPPING_FORM_LABELS[k] for k in service.MAPPING_FORM_KEYS},
        }
    return {
        "": "choose form",
        **{k: service.COMMA_BASIS_FORM_LABELS[k] for k in service.COMMA_BASIS_FORM_KEYS},
    }


def _hover_index(detail) -> int | None:
    if isinstance(detail, dict):
        detail = next(iter(detail.values()), None)
    if isinstance(detail, (list, tuple)):
        detail = detail[0] if detail else None
    if isinstance(detail, bool) or not isinstance(detail, (int, float)):
        return None
    index = int(detail)
    return index if index >= 0 else None


def _option_key(select: ui.select, index: int | None):
    if index is None:
        return None
    keys = list(select.options)
    return keys[index] if 0 <= index < len(keys) else None


@dataclass
class _Gesture:
    kind: str
    source: str | None = None
    apply: Callable | None = None
    baseline: object | None = None
    target_pred: Callable | None = None
    token: tuple | None = None
    reflowed: bool = False
    previous: _Gesture | None = None
