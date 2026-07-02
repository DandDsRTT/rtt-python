"""In-process render coverage for the NiceGUI page — the layer the smoke tests skip.

The rest of the suite builds the layout model (spreadsheet.build) and the pure
helpers, but never executes index()/render()/build_cell, so a stale reference or a
bad widget call there passes the suite green yet 500s the live page. NiceGUI's
``User`` simulation runs the real page in-process (no browser): opening it drives
the default render, toggling a Show feature drives that feature's render branch, and
editing a cell drives the input -> handler -> render pipeline. The ``user`` fixture
also fails on any ERROR log, so a broken render is caught even when it doesn't raise.

Cells are located by the marker each carries (``.mark(cb.id)`` in build_cell, the
Python-side parallel of the data-eid the JS reconciler uses).
"""

import asyncio
import copy
import logging
import re
import sys
from fractions import Fraction
from types import SimpleNamespace

import nicegui.ui as ui
import pytest
from nicegui import core
from nicegui.element_filter import ElementFilter
from nicegui.elements.tooltip import Tooltip
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from rtt.app import app as web_app
from rtt.app import rendering as web_rendering
from rtt.app import _editing_tuning, page_assets, service, spreadsheet, spreadsheet_constants
from rtt.app import settings as show_settings
from rtt.app.editor import Editor


_GENERAL_KEY_BY_LABEL = {label: key for key, label, _d in dict(show_settings.SHOW_GROUPS)["general"]}


def _toggle(user: User, label: str) -> None:
    """Flip the Show layer carrying ``label`` — a general layer via its dummy-tile part, a
    specific-group layer via its checkbox."""
    key = _GENERAL_KEY_BY_LABEL.get(label)
    if key is not None:
        user.find(marker=f"showpart:{key}").click()
    else:
        user.find(kind=ui.checkbox, content=label).click()


_SPECIFIC_LABEL_BY_KEY = {key: label
                          for key, label, _d in dict(show_settings.SHOW_GROUPS)["app features"]}


_SPECIFIC_LABEL_BY_KEY = {key: label
                          for key, label, _d in dict(show_settings.SHOW_GROUPS)["app features"]}


async def _enable(user: User, label: str) -> None:
    """Open the page and turn on the Show toggle carrying ``label`` — first revealing its panel
    ancestors (a nested control's row is hidden until its whole parent chain is on, e.g. weighting
    and tuning ranges now nest under optimization)."""
    await user.open("/")
    if label not in _GENERAL_KEY_BY_LABEL:
        spec_key = next((k for k, group_label, _ in dict(show_settings.SHOW_GROUPS)["app features"]
                         if group_label == label), None)
        if spec_key is not None:
            defaults = show_settings.defaults()
            for anc in sorted(show_settings.ancestors_of(spec_key), key=show_settings.depth_of):
                if not defaults.get(anc, False) and anc in _SPECIFIC_LABEL_BY_KEY:
                    _toggle(user, _SPECIFIC_LABEL_BY_KEY[anc])
    _toggle(user, label)


_FEATURE_CELLS = [
    ("row/col header symbols", "matrix_label:row:mapping:primes:0"),
    ("plain text values", "plain_text:mapping:primes"),
    ("presets", "preset:temperament"),
    ("presets", "preset:tuning:generators"),
    ("charts", "chart:retune:targets"),
    ("tuning ranges", "rangemode:tuning:generators"),
    ("tile units", "units:mapping:primes"),
    ("optimization", "optimization:power"),
]


_FEATURE_CELLS = [
    ("row/col header symbols", "matrix_label:row:mapping:primes:0"),
    ("plain text values", "plain_text:mapping:primes"),
    ("presets", "preset:temperament"),
    ("presets", "preset:tuning:generators"),
    ("charts", "chart:retune:targets"),
    ("tuning ranges", "rangemode:tuning:generators"),
    ("tile units", "units:mapping:primes"),
    ("optimization", "optimization:power"),
]


def _pick_terminology(user: User, mode: str) -> None:
    user.find(marker=f"terminologyradio:{mode}").click()


def _terminology_opt_selected(user: User, mode: str) -> bool:
    return "rtt-range-option-on" in next(iter(user.find(marker=f"terminologyradio:{mode}").elements))._classes


def _pick_ebk(user: User, mode: str) -> None:
    user.find(marker=f"ebkradio:{mode}").click()


def _ebk_opt_selected(user: User, mode: str) -> bool:
    return "rtt-range-option-on" in next(iter(user.find(marker=f"ebkradio:{mode}").elements))._classes


def _radio_selected(user: User, cell_id: str, values):
    """The value whose option carries rtt-range-option-on in a control_radio (e.g. control:slope)."""
    for v in values:
        if "rtt-range-option-on" in next(iter(user.find(marker=f"{cell_id}:{v}").elements))._classes:
            return v
    return None


def _radio_enabled(user: User, cell_id: str) -> bool:
    return "rtt-range-mode-disabled" not in next(iter(user.find(marker=cell_id).elements))._classes


def _scheme_select(user: User):
    return next(e for e in user.find(kind=ui.select).elements if "minimax-S" in (e.options or {}))


def _op_classes(user: User, marker: str) -> list[str]:
    """The CSS classes on a ratio-op button (the reduce/reciprocate glyphs flanking an interval's bar)."""
    return next(iter(user.find(marker=marker).elements))._classes


def _cell_left(user: User, cell_id: str) -> float:
    """A grid cell's current x — the translate offset the reconciler placed it at, in px. Cells are
    positioned by transform:translate(Xpx,Ypx) (so a reflow rides the compositor, not left/top), so x
    is the first translate argument; the inline left is pinned to 0."""
    tf = next(iter(user.find(marker=cell_id).elements))._style["transform"]
    return float(tf.split("translate(", 1)[1].split("px", 1)[0])


def _wrap(user: User, cell_id: str):
    return next(iter(user.find(marker=cell_id).elements))


def _part_classes(user: User, key: str) -> list[str]:
    """The CSS classes render() has put on the general dummy tile's part for ``key``."""
    return next(iter(user.find(marker=f"showpart:{key}").elements))._classes


def _row_classes(user: User, key: str) -> list[str]:
    """The CSS classes on the specific-group toggle row for ``key`` (the chapter slider hides a
    row by adding ``rtt-chapter-hidden``)."""
    return next(iter(user.find(marker=f"showrow:{key}").elements))._classes


def _marked(user: User, marker: str, *, required: bool = True):
    """The single live element carrying ``marker`` — the stable test handle the view stamps on a
    cell's inner control via ``.mark()`` (see _recon_value: ``{cell_id}:numerator`` / ``:denominator`` / ``:whole``
    / ``:fraction`` / ``:sign`` / ``:main`` / ``:sub`` / ``:editbox``). The marker-keyed replacement for
    walking ``default_slot.children`` by index, so an added wrapper or reordered child can't shift it.
    Returns None (not raising) when ``required`` is False and no such element is rendered."""
    with user._client:
        els = list(ElementFilter(marker=marker, only_visible=True))
    if els:
        return els[0]
    if required:
        raise AssertionError(f"no rendered element carries marker {marker!r}")
    return None


def _approx_markers(user: User, cell_id: str) -> list:
    """The ``rtt-approximate`` "~" labels rendered inside a cell (the approximate-ratio marker). Walks the
    cell wrap's descendants — the ~ rides the ``.rtt-ratio`` face, not the wrap itself."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    found, stack = [], list(wrap.default_slot.children)
    while stack:
        element = stack.pop()
        if "rtt-approximate" in getattr(element, "_classes", []):
            found.append(element)
        slot = getattr(element, "default_slot", None)
        stack.extend(slot.children if slot is not None else [])
    return found


class _DecCellProxy:
    """Makes an in-place stacked-DECIMAL (cents) cell read/write like the old single-input cell, so
    the suite's ``_cell_child(...).value`` / ``.set_value(...)`` calls keep working across the split
    into a whole-part field + a fraction field. ``.value`` rejoins them (and prepends "-" when the
    generator-tuning cell's sign glyph shows "−", so it reads like the old signed cents string);
    ``.set_value`` writes a full value through the whole field (decimal_value's "." passthrough splits
    a decimal, and a bare integer clears the fraction first so no stale fraction rejoins) and then
    BLURS the cell — the cents cells commit on blur, not per keystroke, so setting the value alone
    wouldn't retune. Every other attribute (._props, .trigger, …) delegates to the whole-part input."""

    def __init__(self, user, whole, frac, sign=None):
        self._user, self._whole, self._frac, self._sign = user, whole, frac, sign

    @property
    def value(self):
        whole = str(self._whole.value)
        if "." in whole:
            mag = whole
        else:
            f = str(self._frac.value).lstrip(".")
            mag = whole if not f else f"{whole}.{f}"
        if self._sign is not None and self._sign.text not in ("+", ""):
            return f"-{mag}"
        return mag

    def set_value(self, v):
        v = str(v)
        if "." not in v:
            self._frac.set_value("")
        self._whole.set_value(v)
        UserInteraction(self._user, {self._whole}, None).trigger("blur")

    def __getattr__(self, name):
        return getattr(self._whole, name)


def _cell_child(user: User, cell_id: str):
    """The inner control of a grid cell (the marker rides its wrap). An editable stacked-fraction
    cell wraps its numerator + denominator inputs in a .rtt-fraction-edit box; the NUMERATOR is the
    "primary" control the marker-based interactions drive (and, headless, a whole ``"3/2"`` typed
    into it still commits — cell_value rejoins it with the empty denominator). An editable stacked-
    decimal (cents) cell wraps a whole-part + fraction input in a .rtt-decimal-edit box; a sign-aware
    proxy makes it read/write like the old single input (see _DecCellProxy)."""
    wrap = next(iter(user.find(marker=cell_id).elements))
    cls = getattr(wrap, "_classes", [])
    if "rtt-fraction-cell" in cls:
        return _marked(user, f"{cell_id}:numerator")
    if "rtt-decimal-cell" in cls:
        whole, frac = _dec_inputs(user, cell_id)
        sign = _marked(user, f"{cell_id}:sign", required=False)
        return _DecCellProxy(user, whole, frac, sign)
    return wrap.default_slot.children[0]


def _dec_mode(user: User, cell_id: str) -> str:
    """An editable decimal cell's data-decmode ("int" — a bare whole, no fraction line — or "dec" —
    the whole over a small .fraction), read off its .rtt-decimal-edit box. The decimal twin of the
    fraction cell's data-fracmode; the resting view the server sets from the committed value."""
    box = _marked(user, f"{cell_id}:editbox")
    return box._props.get("data-decmode", "")


def _frac_inputs(user: User, cell_id: str):
    """The (numerator, denominator) input fields of an editable stacked-fraction cell — the two
    separate fields that replaced the old overlaid num-over-den face, located by their stable
    ``{cell_id}:numerator`` / ``:denominator`` markers (the bar div between them no longer matters)."""
    return _marked(user, f"{cell_id}:numerator"), _marked(user, f"{cell_id}:denominator")


def _ratio_value(user: User, cell_id: str) -> str:
    """The committed ratio a stacked-fraction cell shows, rejoined from its numerator + denominator
    inputs the way cell_value does (a blank/1 denominator is the big-integer view, so it returns the
    bare numerator)."""
    numerator, denominator = _frac_inputs(user, cell_id)
    return numerator.value if denominator.value in ("", "1") else f"{numerator.value}/{denominator.value}"


def _wrap_classes(user: User, cell_id: str) -> list[str]:
    """The CSS classes on a grid cell's wrap (e.g. rtt-preview-change when an edit moves its value)."""
    return next(iter(user.find(marker=cell_id).elements))._classes


def _ro_ratio_face(user: User, cell_id: str):
    """A READ-ONLY ratio face (generator_ratio / comma_ratio: detempering, generators, unchanged auto-list)
    as ``(numerator_text, denominator_text, collapsed)``. ``collapsed`` is True when the value is a
    whole ratio ``"n/1"`` shown as a bare integer — flagged by ``rtt-fraction-whole`` on the .rtt-fraction
    div (the ~ omitted, the bar and denominator hidden). The wrap's first child is the .rtt-ratio
    container (a label-only "–" placeholder has no .rtt-fraction, so callers pass it only when the value
    is a real ratio)."""
    face = _cell_child(user, cell_id)
    frac = next(c for c in face.default_slot.children if "rtt-fraction" in getattr(c, "_classes", []))
    collapsed = "rtt-fraction-whole" in getattr(frac, "_classes", [])
    numerator, denominator = _marked(user, f"{cell_id}:numerator"), _marked(user, f"{cell_id}:denominator")
    return numerator.text, denominator.text, collapsed


def _click_glyph(user: User, cell_id: str) -> None:
    """Click a grid glyph control (held_plus, …) whose click handler rides the inner element
    rather than the marked wrap, so the marker-based click the fixture exposes can't reach it."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).click()


def _commit(user: User, cell_id: str) -> None:
    """Fire a ratio_cell input's blur handler. The editable quantities-row ratios commit the whole
    typed fraction on blur / Enter (not per keystroke — parsing "2" of "25/24" would momentarily
    retune to 2/1), so a test sets the value then commits it here."""
    UserInteraction(user, {_cell_child(user, cell_id)}, None).trigger("blur")


def _cell_text(user: User, cell_id: str) -> str:
    child = _cell_child(user, cell_id)
    if "rtt-ratio" in getattr(child, "_classes", []):
        numerator = _marked(user, f"{cell_id}:numerator", required=False)
        if numerator is not None:
            denominator = _marked(user, f"{cell_id}:denominator", required=False)
            return f"{numerator.text}/{denominator.text}" if denominator is not None else numerator.text
        inner = child.default_slot.children
        return getattr(inner[0], "text", "") if inner else ""
    return getattr(child, "text", "")


def _stacked_face(user: User, cell_id: str):
    """The (main label, sub label) of an editable cell's stacked OVERLAY face — the overlay that makes
    a value read like a read-only tuning value cell (the main glyph big, a small line below). Now used
    only by the editable POWER cell (∞ over "(max)"): the .rtt-stacked-main / .rtt-stacked-sub labels,
    located by their stable ``{cell_id}:main`` / ``:sub`` markers. The cents cells (prescaler / weight /
    generator tuning) edit IN PLACE now — read them via _dec_inputs."""
    return _marked(user, f"{cell_id}:main"), _marked(user, f"{cell_id}:sub")


def _ro_stacked_face(user: User, cell_id: str):
    """The (main, sub) labels of a READ-ONLY stacked value face (a tuning value cell): the
    .rtt-stacked-main / .rtt-stacked-sub labels, located by their stable ``{cell_id}:main`` / ``:sub``
    markers so a per-cell unit riding the wrap can't shift the index."""
    return _marked(user, f"{cell_id}:main"), _marked(user, f"{cell_id}:sub")


def _ro_value(user: User, cell_id: str) -> str:
    """The displayed value of a READ-ONLY stacked value cell (a tuning_value / read-only weight or
    cents face): its big .rtt-stacked-main glyph joined with the small .rtt-stacked-sub line below
    (e.g. "697" + ".564" -> "697.564"). The read-only twin of the editable cells' _dec_value /
    .value — used to assert that a hover PREVIEW reflows a cell's value (shows the NEW number), not
    just rings it."""
    main, sub = _ro_stacked_face(user, cell_id)
    return f"{main.text}{sub.text}"


def _dec_inputs(user: User, cell_id: str):
    """The (whole, fraction) input fields of an editable stacked-DECIMAL (cents) cell — the two
    separate fields that replaced the old overlaid whole-over-.fraction face, the decimal twin of
    _frac_inputs, located by their stable ``{cell_id}:whole`` / ``:fraction`` markers (no dependence on the
    optional sign glyph or the dot div sitting beside them)."""
    return _marked(user, f"{cell_id}:whole"), _marked(user, f"{cell_id}:fraction")


def _dec_value(user: User, cell_id: str) -> str:
    """The committed magnitude an editable decimal cell shows, rejoined from its whole + fraction
    fields the way decimal_value does (a blank fraction is the big-integer view → the bare whole).
    Unsigned — the generator cell's sign rides on its glyph (read it via _generator_tuning_face)."""
    whole, frac = _dec_inputs(user, cell_id)
    f = str(frac.value).lstrip(".")
    return whole.value if not f else f"{whole.value}.{f}"


def _generator_tuning_face(user: User, cell_id: str):
    """The (sign, whole, fraction) of a generator-tuning cell's in-place signed cents editor. The
    generator_map shows an explicit, clickable sign glyph (+ ordinarily assumed, − when negative) left of the
    big whole part, the small dot-led fraction stacked below. The sign is a label (its .text); the
    whole + fraction are the two real input fields (their .value), now edited in place. Returns
    (sign_label, whole_input, fraction_input), each located by its stable ``{cell_id}:sign`` /
    ``:whole`` / ``:fraction`` marker."""
    sign = _marked(user, f"{cell_id}:sign")
    whole, frac = _dec_inputs(user, cell_id)
    return sign, whole, frac


def _ratio_face(user: User, cell_id: str):
    """The (numerator, denominator) INPUT fields of an editable stacked-fraction cell. The cell is
    now edited in place (no overlay face): the numerator and denominator are two real inputs, so the
    face's "text" is each input's ``.value``."""
    return _frac_inputs(user, cell_id)


def _target_preset(user: User):
    """The (numeric-limit, TILT/OLD family-select) pair of the target chooser — the one
    preset that nests two controls in a flex div inside its cell wrap."""
    container = _cell_child(user, "preset:target")
    number, selection = container.default_slot.children
    return number, selection


def _preset_tooltip_text(user: User, cell_id: str):
    wrap = next(iter(user.find(marker=cell_id).elements))
    tips = [c for c in wrap.default_slot.children if isinstance(c, Tooltip)]
    return tips[0].text if tips else None


def _renders_inside(user: User, cell_marker: str, region_marker: str) -> bool:
    """True if the cell's wrap is a descendant of the region (corner / column strip / body board)."""
    cell = next(iter(user.find(marker=cell_marker).elements))
    region = next(iter(user.find(marker=region_marker).elements))
    slot = cell.parent_slot
    while slot is not None:
        if slot.parent is region:
            return True
        slot = slot.parent.parent_slot
    return False


def _px(element, prop: str) -> float:
    return float(element._style.get(prop).rstrip("px"))


_ENABLE_HTML_CELLS = [
    ("tile units", "units:mapping:primes"),
    ("charts", "chart:retune:targets"),
]


_DEFAULT_HTML_CELLS = ["caption:mapping:primes", "bracket:map:0:l", "symbol:mapping:primes"]


def _escape_target(user: User, cell_id: str) -> str:
    """The data-eid the cell's keydown.escape js_handler clicks (the draft's − cancel button).
    The handler is js-only — the in-process User plugin can't run it, so lock the wiring
    structurally the way the typed-limit keyup guard does; clicking the − itself is covered
    by the *_minus:pending cancel tests."""
    listeners = list(_cell_child(user, cell_id)._event_listeners.values())
    esc = next(listener for listener in listeners if listener.type == "keydown.escape")
    m = re.search(r'data-eid="([^"]+)"', esc.js_handler)
    return m.group(1)


def _live():
    """The module object the live page actually runs from (render_main re-imports rtt.app.app per
    fixture, so the test's top-level `web_app` is a stale earlier copy)."""
    return sys.modules["rtt.app.app"]


def _live_assets():
    return sys.modules["rtt.app.page_assets"]


def _live_render():
    return sys.modules["rtt.app.render_html"]


def _live_page():
    live = sys.modules["rtt.app.app"]
    return live, live._SIMULATED_PAGES[-1]


def _body_cells(live, page):
    layout = page.runtime.last_lay
    fx, fy = layout.freeze_x, layout.freeze_y
    body = [c for c in layout.cells if _live_render()._freeze_container(c, fx, fy) == "body" and not c.pending]
    return layout, fx, fy, body
