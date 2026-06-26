from __future__ import annotations

from rtt.app import _recon_buttons as buttons
from rtt.app import _recon_choosers as choosers
from rtt.app import _recon_display as display
from rtt.app import _recon_drag as drag
from rtt.app import _recon_value as value
from rtt.app.page_assets import _EBK_SVG_KINDS, _KindHandlers


def register_display_kinds(rec) -> None:
    for _ebk_kind in _EBK_SVG_KINDS:
        rec.cell_kinds[_ebk_kind] = _KindHandlers(display.build_svgfill, display.update_ebk)
    rec.cell_kinds["chart"] = _KindHandlers(display.build_svgfill, display.update_chart)
    rec.cell_kinds["rangechart"] = _KindHandlers(display.build_svgfill, display.update_rangechart)

    rec.cell_kinds["count"] = _KindHandlers(display.build_count, display.update_mathcell)
    rec.cell_kinds["symbol"] = _KindHandlers(display.build_symbol, display.update_mathcell)
    rec.cell_kinds["matlabel"] = _KindHandlers(display.build_matlabel, display.update_mathcell)
    rec.cell_kinds["units"] = _KindHandlers(display.build_units, display.update_mathcell)
    rec.cell_kinds["caption"] = _KindHandlers(display.build_caption, display.update_caption)

    rec.cell_kinds["ptextpending"] = _KindHandlers(
        display.build_ptextpending, display.update_ptextpending
    )
    rec.cell_kinds["mathexpr"] = _KindHandlers(display.build_mathexpr, display.update_mathexpr)


def register_value_kinds(rec) -> None:
    _gridvalue = _KindHandlers(value.build_gridvalue, value.update_gridvalue)
    for _gv_kind in (
        "mapping",
        "commacell",
        "unchangedcell",
        "interestcell",
        "heldcell",
        "targetcell",
        "formcell",
    ):
        rec.cell_kinds[_gv_kind] = _gridvalue
    rec.cell_kinds["prescalercell"] = _KindHandlers(
        value.build_prescalercell, value.update_prescalercell
    )
    rec.cell_kinds["weightcell"] = _KindHandlers(value.build_weightcell, value.update_weightcell)
    rec.cell_kinds["powerinput"] = _KindHandlers(value.build_powerinput, value.update_powerinput)
    rec.cell_kinds["powerdisplay"] = _KindHandlers(
        value.build_powerdisplay, value.update_powerdisplay
    )
    rec.cell_kinds["gentuningcell"] = _KindHandlers(
        value.build_gentuningcell, value.update_gentuningcell
    )

    rec.cell_kinds["ptextedit"] = _KindHandlers(value.build_ptextedit, value.update_ptextedit)

    rec.cell_kinds["genratio"] = _KindHandlers(value.build_genratio, value.update_ratio)
    rec.cell_kinds["ratiocell"] = _gridvalue
    rec.cell_kinds["elementcell"] = _gridvalue
    rec.cell_kinds["elementratio"] = _gridvalue
    rec.cell_kinds["commaratio"] = _KindHandlers(value.build_commaratio, value.update_ratio)
    rec.cell_kinds["tuningvalue"] = _KindHandlers(
        value.build_tuning_value, value.update_tuning_value
    )


def register_label_kinds(rec) -> None:
    _value_builder = value.label_builder("rtt-value")
    rec.cell_kinds["prime"] = _KindHandlers(_value_builder, value.update_label)
    rec.cell_kinds["mapped"] = _KindHandlers(_value_builder, value.update_label)
    rec.cell_kinds["vec"] = _KindHandlers(_value_builder, value.update_label)
    rec.cell_kinds["colheader"] = _KindHandlers(
        value.label_builder("rtt-colheader"), value.update_label
    )
    rec.cell_kinds["rowlabel"] = _KindHandlers(
        value.label_builder("rtt-rowlabel"), value.update_label
    )
    rec.cell_kinds["ptext"] = _KindHandlers(value.label_builder("rtt-ptext"), value.update_ptext)
    rec.cell_kinds["transpose"] = _KindHandlers(
        value.label_builder("rtt-transpose"), value.update_label
    )
    rec.cell_kinds["boxtitle"] = _KindHandlers(value.label_builder("rtt-boxtitle"), None)


def register_control_kinds(rec) -> None:
    rec.cell_kinds["rangemode"] = _KindHandlers(choosers.build_rangemode, choosers.update_rangemode)
    rec.cell_kinds["scheme_button"] = _KindHandlers(
        choosers.build_scheme_button, choosers.update_scheme_button
    )
    rec.cell_kinds["rowtoggle"] = _KindHandlers(
        choosers.build_foldtoggle, choosers.update_foldtoggle
    )
    rec.cell_kinds["coltoggle"] = _KindHandlers(
        choosers.build_foldtoggle, choosers.update_foldtoggle
    )
    rec.cell_kinds["tiletoggle"] = _KindHandlers(
        choosers.build_foldtoggle, choosers.update_foldtoggle
    )
    rec.cell_kinds["alltoggle"] = _KindHandlers(
        choosers.build_alltoggle, choosers.update_foldtoggle
    )

    rec.cell_kinds["preset"] = _KindHandlers(choosers.build_preset, choosers.update_preset)
    rec.cell_kinds["etpick"] = _KindHandlers(choosers.build_etpick, choosers.update_subpick)
    rec.cell_kinds["commapick"] = _KindHandlers(choosers.build_commapick, choosers.update_subpick)
    rec.cell_kinds["control_select"] = _KindHandlers(
        choosers.build_control_select, choosers.update_control_select
    )
    rec.cell_kinds["control_check"] = _KindHandlers(
        choosers.build_control_check, choosers.update_control_check
    )
    rec.cell_kinds["formchooser"] = _KindHandlers(
        choosers.build_formchooser, choosers.update_formchooser
    )


def register_button_kinds(rec) -> None:
    rec.cell_kinds["minus"] = _KindHandlers(buttons.build_minus)
    rec.cell_kinds["plus"] = _KindHandlers(buttons.build_plus)
    rec.cell_kinds["gen_minus"] = _KindHandlers(buttons.build_gen_minus)
    rec.cell_kinds["gen_plus"] = _KindHandlers(buttons.build_gen_plus)
    rec.cell_kinds["map_minus"] = _KindHandlers(buttons.build_map_minus)
    rec.cell_kinds["map_plus"] = _KindHandlers(buttons.build_map_plus)
    rec.cell_kinds["map_drag"] = _KindHandlers(drag.build_map_drag)
    rec.cell_kinds["int_drag"] = _KindHandlers(drag.build_int_drag)
    rec.cell_kinds["basis_minus"] = _KindHandlers(buttons.build_basis_minus)
    rec.cell_kinds["comma_minus"] = _KindHandlers(buttons.build_comma_minus)
    rec.cell_kinds["comma_plus"] = _KindHandlers(buttons.build_comma_plus)
    rec.cell_kinds["element_plus"] = _KindHandlers(buttons.build_element_plus)
    rec.cell_kinds["element_minus"] = _KindHandlers(buttons.build_element_minus)
    rec.cell_kinds["interest_minus"] = _KindHandlers(buttons.build_interest_minus)
    rec.cell_kinds["interest_plus"] = _KindHandlers(buttons.build_interest_plus)
    rec.cell_kinds["held_minus"] = _KindHandlers(buttons.build_held_minus)
    rec.cell_kinds["held_plus"] = _KindHandlers(buttons.build_held_plus)
    rec.cell_kinds["target_minus"] = _KindHandlers(buttons.build_target_minus)
    rec.cell_kinds["target_plus"] = _KindHandlers(buttons.build_target_plus)
    rec.cell_kinds["colgrip"] = _KindHandlers(buttons.build_colgrip)
