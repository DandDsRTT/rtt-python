from __future__ import annotations

import logging

from nicegui import ui

from rtt.app import (
    service,
    spreadsheet,
    tooltips,
)
from rtt.app._recon_buttons import _ReconButtons
from rtt.app._recon_choosers import _ReconChoosers
from rtt.app._recon_display import _ReconDisplayCells
from rtt.app._recon_drag import _ReconDrag
from rtt.app._recon_handles import EMPTY as _EMPTY_HANDLES
from rtt.app._recon_handles import EMPTY_ENTITY as _EMPTY_ENTITY
from rtt.app._recon_handles import CellHandles, EntityHandles
from rtt.app._recon_value import _ReconValueCells
from rtt.app.editor import Editor
from rtt.app.page_assets import (
    _CELLUNIT_MAX_FONT,
    _EBK_SVG_KINDS,
    _INT_WHEEL_JS,
    _STACKED_EXIT_JS,
    _WHEEL_STEPS,
    VALUE_KINDS,
    _KindHandlers,
)
from rtt.app.render_html import (
    _bold_units,
    _cents_parts,
    _units_font,
)

_log = logging.getLogger(__name__)


class _Reconciler:
    def __init__(self, editor: Editor, gestures=None) -> None:
        self._editor = editor
        # the gesture state machine is OWNED by the GestureController; the reconciler only
        # READS the live gesture (to honour a chooser/temperament preview hold while updating a
        # cell). It borrows it through this narrow back-reference rather than owning the state.
        self._gestures = gestures
        self._cb = None
        self._row_drag: int | None = None
        self._col_drag: tuple[str, int] | None = None
        self.pretransform = False
        self._init_handles()
        self.cell_kinds: dict[str, _KindHandlers] = {}
        self._value = _ReconValueCells(self)
        self._display = _ReconDisplayCells(self)
        self._choose = _ReconChoosers(self)
        self._buttons = _ReconButtons(self)
        self._drag = _ReconDrag(self)
        # Explicit sibling collaborators: the few cross-component calls (a button wiring a chooser's
        # hover-preview, a value cell arming a drag) name their peer directly instead of reaching
        # through self.r into a sibling — so each component declares whom it talks to.
        self._buttons._choose = self._choose
        self._value._choose = self._choose
        self._value._drag = self._drag
        self._register_display_kinds()
        self._register_value_kinds()
        self._register_label_kinds()
        self._register_control_kinds()
        self._register_button_kinds()

    @property
    def _cur_gesture(self):
        return self._gestures.gesture if self._gestures is not None else None

    def _init_handles(self) -> None:
        # Two stores, both keyed by id. cells: a CellHandles record per CELL — every element handle +
        # per-cell last-rendered value travels in one record, so a new handle is a new field, never a
        # parallel dict you must remember to sweep. entities: an EntityHandles record per ENTITY (a
        # superset of cells — lines and washes also get an element + the style/ring change-guard
        # caches), grouping the el + styled + ring_sig that always co-vary for an entity. make_cell
        # creates both for a cell; render() creates an entities record for each line/wash; drop()
        # removes an id from both.
        self.cells: dict[str, CellHandles] = {}
        self.entities: dict[str, EntityHandles] = {}
        self.target_limit_tip = (
            None  # the target chooser's ui.tooltip (text swaps to an invalid-limit message)
        )

    def _register_display_kinds(self) -> None:
        for _ebk_kind in _EBK_SVG_KINDS:
            self.cell_kinds[_ebk_kind] = _KindHandlers(
                self._display._build_svgfill, self._display._update_ebk
            )
        self.cell_kinds["chart"] = _KindHandlers(
            self._display._build_svgfill, self._display._update_chart
        )
        self.cell_kinds["rangechart"] = _KindHandlers(
            self._display._build_svgfill, self._display._update_rangechart
        )

        self.cell_kinds["count"] = _KindHandlers(
            self._display._build_count, self._display._update_mathcell
        )
        self.cell_kinds["symbol"] = _KindHandlers(
            self._display._build_symbol, self._display._update_mathcell
        )
        self.cell_kinds["matlabel"] = _KindHandlers(
            self._display._build_matlabel, self._display._update_mathcell
        )
        self.cell_kinds["units"] = _KindHandlers(
            self._display._build_units, self._display._update_mathcell
        )
        self.cell_kinds["caption"] = _KindHandlers(
            self._display._build_caption, self._display._update_caption
        )

        self.cell_kinds["ptextpending"] = _KindHandlers(
            self._display._build_ptextpending, self._display._update_ptextpending
        )
        self.cell_kinds["mathexpr"] = _KindHandlers(
            self._display._build_mathexpr, self._display._update_mathexpr
        )

    def _register_value_kinds(self) -> None:
        _gridvalue = _KindHandlers(self._value._build_gridvalue, self._value._update_gridvalue)
        for _gv_kind in (
            "mapping",
            "commacell",
            "unchangedcell",
            "interestcell",
            "heldcell",
            "targetcell",
            "formcell",
        ):
            self.cell_kinds[_gv_kind] = _gridvalue
        self.cell_kinds["prescalercell"] = _KindHandlers(
            self._value._build_prescalercell, self._value._update_prescalercell
        )
        self.cell_kinds["weightcell"] = _KindHandlers(
            self._value._build_weightcell, self._value._update_weightcell
        )
        self.cell_kinds["powerinput"] = _KindHandlers(
            self._value._build_powerinput, self._value._update_powerinput
        )
        self.cell_kinds["powerdisplay"] = _KindHandlers(
            self._value._build_powerdisplay, self._value._update_powerdisplay
        )
        self.cell_kinds["gentuningcell"] = _KindHandlers(
            self._value._build_gentuningcell, self._value._update_gentuningcell
        )

        self.cell_kinds["ptextedit"] = _KindHandlers(
            self._value._build_ptextedit, self._value._update_ptextedit
        )

        self.cell_kinds["genratio"] = _KindHandlers(
            self._value._build_genratio, self._value._update_ratio
        )
        self.cell_kinds["ratiocell"] = _gridvalue
        self.cell_kinds["elementcell"] = _gridvalue
        self.cell_kinds["elementratio"] = _gridvalue
        self.cell_kinds["commaratio"] = _KindHandlers(
            self._value._build_commaratio, self._value._update_ratio
        )
        self.cell_kinds["tuningvalue"] = _KindHandlers(
            self._value._build_tuning_value, self._value._update_tuning_value
        )

    def _register_label_kinds(self) -> None:
        _value_builder = self._value._label_builder("rtt-value")
        self.cell_kinds["prime"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["mapped"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["vec"] = _KindHandlers(_value_builder, self._value._update_label)
        self.cell_kinds["colheader"] = _KindHandlers(
            self._value._label_builder("rtt-colheader"), self._value._update_label
        )
        self.cell_kinds["rowlabel"] = _KindHandlers(
            self._value._label_builder("rtt-rowlabel"), self._value._update_label
        )
        self.cell_kinds["ptext"] = _KindHandlers(
            self._value._label_builder("rtt-ptext"), self._value._update_ptext
        )
        self.cell_kinds["transpose"] = _KindHandlers(
            self._value._label_builder("rtt-transpose"), self._value._update_label
        )
        self.cell_kinds["boxtitle"] = _KindHandlers(
            self._value._label_builder("rtt-boxtitle"), None
        )

    def _register_control_kinds(self) -> None:
        self.cell_kinds["rangemode"] = _KindHandlers(
            self._choose._build_rangemode, self._choose._update_rangemode
        )
        self.cell_kinds["scheme_button"] = _KindHandlers(
            self._choose._build_scheme_button, self._choose._update_scheme_button
        )
        self.cell_kinds["rowtoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["coltoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["tiletoggle"] = _KindHandlers(
            self._choose._build_foldtoggle, self._choose._update_foldtoggle
        )
        self.cell_kinds["alltoggle"] = _KindHandlers(
            self._choose._build_alltoggle, self._choose._update_foldtoggle
        )

        self.cell_kinds["preset"] = _KindHandlers(
            self._choose._build_preset, self._choose._update_preset
        )
        self.cell_kinds["etpick"] = _KindHandlers(
            self._choose._build_etpick, self._choose._update_subpick
        )
        self.cell_kinds["commapick"] = _KindHandlers(
            self._choose._build_commapick, self._choose._update_subpick
        )
        self.cell_kinds["control_select"] = _KindHandlers(
            self._choose._build_control_select, self._choose._update_control_select
        )
        self.cell_kinds["control_check"] = _KindHandlers(
            self._choose._build_control_check, self._choose._update_control_check
        )
        self.cell_kinds["formchooser"] = _KindHandlers(
            self._choose._build_formchooser, self._choose._update_formchooser
        )

    def _register_button_kinds(self) -> None:
        self.cell_kinds["minus"] = _KindHandlers(self._buttons._build_minus)
        self.cell_kinds["plus"] = _KindHandlers(self._buttons._build_plus)
        self.cell_kinds["gen_minus"] = _KindHandlers(self._buttons._build_gen_minus)
        self.cell_kinds["gen_plus"] = _KindHandlers(self._buttons._build_gen_plus)
        self.cell_kinds["map_minus"] = _KindHandlers(self._buttons._build_map_minus)
        self.cell_kinds["map_plus"] = _KindHandlers(self._buttons._build_map_plus)
        self.cell_kinds["map_drag"] = _KindHandlers(self._drag._build_map_drag)
        self.cell_kinds["int_drag"] = _KindHandlers(self._drag._build_int_drag)
        self.cell_kinds["basis_minus"] = _KindHandlers(self._buttons._build_basis_minus)
        self.cell_kinds["comma_minus"] = _KindHandlers(self._buttons._build_comma_minus)
        self.cell_kinds["comma_plus"] = _KindHandlers(self._buttons._build_comma_plus)
        self.cell_kinds["element_plus"] = _KindHandlers(self._buttons._build_element_plus)
        self.cell_kinds["element_minus"] = _KindHandlers(self._buttons._build_element_minus)
        self.cell_kinds["interest_minus"] = _KindHandlers(self._buttons._build_interest_minus)
        self.cell_kinds["interest_plus"] = _KindHandlers(self._buttons._build_interest_plus)
        self.cell_kinds["held_minus"] = _KindHandlers(self._buttons._build_held_minus)
        self.cell_kinds["held_plus"] = _KindHandlers(self._buttons._build_held_plus)
        self.cell_kinds["target_minus"] = _KindHandlers(self._buttons._build_target_minus)
        self.cell_kinds["target_plus"] = _KindHandlers(self._buttons._build_target_plus)
        self.cell_kinds["colgrip"] = _KindHandlers(self._buttons._build_colgrip)

    def drop(self, eid: str) -> None:
        self.entities[eid].el.delete()
        self.cells.pop(eid, None)
        self.entities.pop(eid, None)

    def _attach_guide_link(self, wrap, gh: tooltips.GuideHelp, tile: str, text: str) -> None:
        # the hover-card (a body-level div built by _GUIDE_JS) reads these and renders a card that
        # stays open while hovered, so its "Read in the Guide" link is actually clickable — a Quasar
        # tooltip can't be (it hides the moment the cursor leaves the cell toward it). data-guide-tile
        # ties a tile's name + symbol cells into ONE hover zone so the card doesn't jump (the link
        # doesn't run away) when the cursor crosses from one to the other.
        wrap.classes("rtt-guide-link")
        wrap._props["data-guide-text"] = text
        wrap._props["data-guide-tile"] = tile
        if gh.url:
            wrap._props["data-guide-loc"] = gh.location
            wrap._props["data-guide-url"] = gh.url

    def make_cell(self, cb: spreadsheet.CellBox) -> None:
        # build a cell's element in the active parent (the caller opens the freeze container),
        # register it + its kind (and audio key) so render() can place and reconcile it after.
        # data-eid drives the JS reconciler; .mark(cb.id) is its Python-side parallel,
        # letting the User-fixture render tests locate a cell by its stable id
        self.cells[cb.id] = CellHandles()
        self.entities[cb.id] = EntityHandles()
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"').mark(cb.id)
        with wrap:
            self.cell_kinds[cb.kind].build(cb, wrap)
            if cb.audio is not None:
                self._tag_audio(wrap, cb)
        # Hover affordances. A gridded VALUE cell (VALUE_KINDS) becomes .rtt-zoomable — hovering it
        # pops the zoom magnifier (a client-side clone, _ZOOM_JS), and its own hover help (if any —
        # the editable cells' "type to edit…", the mean damage / dual(𝑞) explanations) folds INTO that
        # magnifier as data-zoomhelp rather than a separate tooltip, so value cells carry exactly one
        # hover popup. Every other control keeps its plain help tooltip. All wording still lives in
        # rtt.app.tooltips; a NEW kind must be classified there (READONLY_KINDS or a help entry) or
        # test_web_tooltips' completeness sweep fails. The mark/data-eid ride the wrap, so the magnifier
        # (which clones the wrap) and any tooltip hang off it too.
        self._attach_hover_help(wrap, cb)
        self.entities[cb.id].el = wrap
        self.cells[cb.id].kind = cb.kind
        self._wire_cell_input(wrap, cb)

    def _attach_hover_help(self, wrap, cb: spreadsheet.CellBox) -> None:
        plain = tooltips.control_help(cb.kind, cb.id)
        relabeled = tooltips.control_help(cb.kind, cb.id, pretransform=True)
        help_text = relabeled if self.pretransform else plain
        if cb.kind in VALUE_KINDS:
            wrap.classes("rtt-zoomable")
            if help_text:
                wrap._props["data-zoomhelp"] = help_text
        elif help_text:
            if cb.id in tooltips.MEAN_DAMAGE_IDS:
                with wrap:
                    self.cells[cb.id].mean_damage_tip = ui.tooltip(help_text)
            elif cb.id == "preset:target":
                with wrap:
                    self.target_limit_tip = ui.tooltip(help_text)
            elif plain != relabeled:
                with wrap:
                    self.cells[cb.id].help_tip = (ui.tooltip(help_text), plain, relabeled)
            else:
                wrap.tooltip(help_text)
        if cb.kind in ("symbol", "caption"):
            gh = tooltips.tile_guide_help_for_cell(cb.id)
            if gh is not None:
                gh_pt = tooltips.tile_guide_help_for_cell(cb.id, pretransform=True)
                text = gh_pt.text if self.pretransform else gh.text
                self._attach_guide_link(wrap, gh, cb.id.split(":", 1)[1], text)
                if gh.text != gh_pt.text:
                    self.cells[cb.id].guide_help_text = (gh.text, gh_pt.text)

    def _wire_cell_input(self, wrap, cb: spreadsheet.CellBox) -> None:
        if cb.kind.endswith(("plus", "minus")):
            wrap.on("mousedown", js_handler="(e) => e.preventDefault()")
        edit_input = self.cells[cb.id].input or self.cells[cb.id].ptext_input
        if edit_input is not None:
            den = self.cells[cb.id].den_input
            guard = _STACKED_EXIT_JS if den is not None else None
            for fld in (edit_input, den) if den is not None else (edit_input,):
                fld.on(
                    "focus", lambda _=None, cid=cb.id: self._cb.on_cell_focus(cid), js_handler=guard
                )
                fld.on(
                    "blur", lambda _=None, cid=cb.id: self._cb.on_cell_blur(cid), js_handler=guard
                )
                fld.on("keydown.enter", js_handler="(e) => e.target.blur()")
        if cb.kind in _WHEEL_STEPS:
            wrap.on(
                "wheel",
                lambda e, cid=cb.id: self._cb.on_value_wheel(cid, e.args.get("deltaY")),
                args=["deltaY"],
                js_handler=_INT_WHEEL_JS,
            )

    def update_cell(self, cb: spreadsheet.CellBox) -> None:
        handlers = self.cell_kinds[cb.kind]
        if handlers.update is not None:
            handlers.update(cb)
        if cb.unit:
            if self.cells[cb.id].cell_unit is None:
                with self.entities[cb.id].el:
                    self.cells[cb.id].cell_unit = ui.html("").classes("rtt-cellunit")
                self.entities[cb.id].el.classes(add="rtt-cell-united")
            if self.cells[cb.id].cell_unit_text != (cb.unit, cb.w):
                self.cells[cb.id].cell_unit.set_content(_bold_units(cb.unit))
                self.cells[cb.id].cell_unit.style(
                    f"font-size:{_units_font(cb.unit, cb.w, _CELLUNIT_MAX_FONT):.2f}px"
                )
                self.cells[cb.id].cell_unit_text = (cb.unit, cb.w)
        elif self.cells[cb.id].cell_unit is not None:
            self.cells[cb.id].cell_unit.delete()
            self.cells[cb.id].cell_unit = None
            self.cells[cb.id].cell_unit_text = None
            self.entities[cb.id].el.classes(remove="rtt-cell-united")
        if cb.audio is not None:
            self._tag_audio(self.entities[cb.id].el, cb)

    def _tag_audio(self, el, cb: spreadsheet.CellBox) -> None:
        tile, idx, cents = cb.audio
        el.classes(add="rtt-spk").props(
            f'data-audio="{tile}" data-idx="{idx}" data-cents="{cents:.6f}"'
        )

    def handles(self, cid: str) -> CellHandles:
        return self.cells.get(cid, _EMPTY_HANDLES)

    def entity(self, eid: str) -> EntityHandles:
        return self.entities.get(eid, _EMPTY_ENTITY)

    def cell_value(self, cid: str) -> str:
        num = str(self.cells[cid].input.value).strip()
        if not num:
            return ""
        if num == "?":
            return "?/?"
        if "/" in num:
            return num
        den = str(self.cells[cid].den_input.value).strip() if self.cells[cid].den_input else ""
        return num if den in ("", "1", "?") else f"{num}/{den}"

    def decimal_value(self, cid: str) -> str:
        whole = str(self.cells[cid].input.value).strip()
        if not whole:
            return ""
        if "." in whole:
            return whole
        frac = (
            str(self.cells[cid].den_input.value).strip().lstrip(".")
            if self.cells[cid].den_input
            else ""
        )
        return whole if not frac else f"{whole}.{frac}"

    def set_decimal_value(self, cid: str, text: str) -> None:
        whole, frac = _cents_parts(text)
        self.cells[cid].input.value = whole
        if self.cells[cid].den_input:
            self.cells[cid].den_input.value = frac

    def _target_preset_values(self):
        if self._editor.target_override is not None or service.is_all_interval(
            self._editor.tuning_scheme
        ):
            return None, None
        family = self._editor.target_family
        limit = self._editor.target_limit
        if limit is None:
            limit = service.default_target_limit(family, self._editor.state.domain_basis)
        return limit, family
