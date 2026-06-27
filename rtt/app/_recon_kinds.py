from __future__ import annotations

from rtt.app import _recon_buttons as buttons
from rtt.app import _recon_choosers as choosers
from rtt.app import _recon_display as display
from rtt.app import _recon_drag as drag
from rtt.app import _recon_value as value
from rtt.app.page_assets import _EBK_SVG_KINDS, GRIDVALUE_KINDS, _KindHandlers


def register_display_kinds(cell_kinds) -> None:
    for _ebk_kind in _EBK_SVG_KINDS:
        cell_kinds[_ebk_kind] = _KindHandlers(display.build_svgfill, display.update_ebk)
    cell_kinds["chart"] = _KindHandlers(display.build_svgfill, display.update_chart)
    cell_kinds["rangechart"] = _KindHandlers(display.build_svgfill, display.update_rangechart)

    cell_kinds["count"] = _KindHandlers(display.build_count, display.update_mathcell)
    cell_kinds["symbol"] = _KindHandlers(display.build_symbol, display.update_mathcell)
    cell_kinds["matlabel"] = _KindHandlers(display.build_matlabel, display.update_mathcell)
    cell_kinds["units"] = _KindHandlers(display.build_units, display.update_mathcell)
    cell_kinds["caption"] = _KindHandlers(display.build_caption, display.update_caption)

    cell_kinds["ptextpending"] = _KindHandlers(
        display.build_ptextpending, display.update_ptextpending
    )
    cell_kinds["mathexpr"] = _KindHandlers(display.build_mathexpr, display.update_mathexpr)


def register_value_kinds(cell_kinds) -> None:
    _gridvalue = _KindHandlers(value.build_gridvalue, value.update_gridvalue)
    for _gv_kind in GRIDVALUE_KINDS:
        cell_kinds[_gv_kind] = _gridvalue
    cell_kinds["prescalercell"] = _KindHandlers(
        value.build_prescalercell, value.update_prescalercell
    )
    cell_kinds["weightcell"] = _KindHandlers(value.build_weightcell, value.update_weightcell)
    cell_kinds["powerinput"] = _KindHandlers(value.build_powerinput, value.update_powerinput)
    cell_kinds["powerdisplay"] = _KindHandlers(value.build_powerdisplay, value.update_powerdisplay)
    cell_kinds["gentuningcell"] = _KindHandlers(
        value.build_gentuningcell, value.update_gentuningcell
    )

    cell_kinds["ptextedit"] = _KindHandlers(value.build_ptextedit, value.update_ptextedit)

    cell_kinds["genratio"] = _KindHandlers(value.build_genratio, value.update_ratio)
    cell_kinds["commaratio"] = _KindHandlers(value.build_commaratio, value.update_ratio)
    cell_kinds["tuningvalue"] = _KindHandlers(value.build_tuning_value, value.update_tuning_value)


def register_label_kinds(cell_kinds) -> None:
    _value_builder = value.label_builder("rtt-value")
    cell_kinds["prime"] = _KindHandlers(_value_builder, value.update_label)
    cell_kinds["mapped"] = _KindHandlers(value.build_mapped, value.update_ratio)
    cell_kinds["vec"] = _KindHandlers(_value_builder, value.update_label)
    cell_kinds["colheader"] = _KindHandlers(
        value.label_builder("rtt-colheader"), value.update_label
    )
    cell_kinds["rowlabel"] = _KindHandlers(value.label_builder("rtt-rowlabel"), value.update_label)
    cell_kinds["ptext"] = _KindHandlers(value.label_builder("rtt-ptext"), value.update_ptext)
    cell_kinds["transpose"] = _KindHandlers(
        value.label_builder("rtt-transpose"), value.update_label
    )
    cell_kinds["boxtitle"] = _KindHandlers(value.label_builder("rtt-boxtitle"), None)


def register_control_kinds(cell_kinds) -> None:
    cell_kinds["rangemode"] = _KindHandlers(choosers.build_rangemode, choosers.update_rangemode)
    cell_kinds["scheme_button"] = _KindHandlers(
        choosers.build_scheme_button, choosers.update_scheme_button
    )
    cell_kinds["rowtoggle"] = _KindHandlers(choosers.build_foldtoggle, choosers.update_foldtoggle)
    cell_kinds["coltoggle"] = _KindHandlers(choosers.build_foldtoggle, choosers.update_foldtoggle)
    cell_kinds["tiletoggle"] = _KindHandlers(choosers.build_foldtoggle, choosers.update_foldtoggle)
    cell_kinds["alltoggle"] = _KindHandlers(choosers.build_alltoggle, choosers.update_foldtoggle)

    cell_kinds["preset"] = _KindHandlers(choosers.build_preset, choosers.update_preset)
    cell_kinds["etpick"] = _KindHandlers(choosers.build_etpick, choosers.update_subpick)
    cell_kinds["commapick"] = _KindHandlers(choosers.build_commapick, choosers.update_subpick)
    cell_kinds["control_select"] = _KindHandlers(
        choosers.build_control_select, choosers.update_control_select
    )
    cell_kinds["control_check"] = _KindHandlers(
        choosers.build_control_check, choosers.update_control_check
    )
    cell_kinds["formchooser"] = _KindHandlers(
        choosers.build_formchooser, choosers.update_formchooser
    )


def register_button_kinds(cell_kinds) -> None:
    cell_kinds["minus"] = _KindHandlers(buttons.build_minus)
    cell_kinds["plus"] = _KindHandlers(buttons.build_plus)
    cell_kinds["gen_minus"] = _KindHandlers(buttons.build_gen_minus)
    cell_kinds["gen_plus"] = _KindHandlers(buttons.build_gen_plus)
    cell_kinds["map_minus"] = _KindHandlers(buttons.build_map_minus)
    cell_kinds["map_plus"] = _KindHandlers(buttons.build_map_plus)
    cell_kinds["map_drag"] = _KindHandlers(drag.build_map_drag)
    cell_kinds["int_drag"] = _KindHandlers(drag.build_int_drag)
    cell_kinds["basis_minus"] = _KindHandlers(buttons.build_basis_minus)
    cell_kinds["comma_minus"] = _KindHandlers(buttons.build_comma_minus)
    cell_kinds["comma_plus"] = _KindHandlers(buttons.build_comma_plus)
    cell_kinds["element_plus"] = _KindHandlers(buttons.build_element_plus)
    cell_kinds["element_minus"] = _KindHandlers(buttons.build_element_minus)
    cell_kinds["interest_minus"] = _KindHandlers(buttons.build_interest_minus)
    cell_kinds["interest_plus"] = _KindHandlers(buttons.build_interest_plus)
    cell_kinds["held_minus"] = _KindHandlers(buttons.build_held_minus)
    cell_kinds["held_plus"] = _KindHandlers(buttons.build_held_plus)
    cell_kinds["target_minus"] = _KindHandlers(buttons.build_target_minus)
    cell_kinds["target_plus"] = _KindHandlers(buttons.build_target_plus)
    cell_kinds["colgrip"] = _KindHandlers(buttons.build_colgrip)
