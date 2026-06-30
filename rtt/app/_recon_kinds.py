from __future__ import annotations

from rtt.app import _recon_buttons as buttons
from rtt.app import _recon_choosers as choosers
from rtt.app import _recon_display as display
from rtt.app import _recon_drag as drag
from rtt.app import _recon_value as value
from rtt.app import _recon_value_kinds as value_kinds
from rtt.app.page_assets import _EBK_SVG_KINDS, GRIDVALUE_KINDS, _KindHandlers


def register_display_kinds(cell_kinds) -> None:
    for _ebk_kind in _EBK_SVG_KINDS:
        cell_kinds[_ebk_kind] = _KindHandlers(display.build_svgfill, display.update_ebk)
    cell_kinds["chart"] = _KindHandlers(display.build_svgfill, display.update_chart)
    cell_kinds["rangechart"] = _KindHandlers(display.build_svgfill, display.update_rangechart)

    cell_kinds["count"] = _KindHandlers(display.build_count, display.update_mathcell)
    cell_kinds["symbol"] = _KindHandlers(display.build_symbol, display.update_mathcell)
    cell_kinds["matrix_label"] = _KindHandlers(display.build_matrix_label, display.update_mathcell)
    cell_kinds["units"] = _KindHandlers(display.build_units, display.update_mathcell)
    cell_kinds["caption"] = _KindHandlers(display.build_caption, display.update_caption)

    cell_kinds["plain_text_pending"] = _KindHandlers(
        display.build_plain_text_pending, display.update_plain_text_pending
    )
    cell_kinds["mathexpr"] = _KindHandlers(display.build_mathexpr, display.update_mathexpr)


def register_value_kinds(cell_kinds) -> None:
    _gridvalue = _KindHandlers(value.build_gridvalue, value.update_gridvalue)
    for _gv_kind in GRIDVALUE_KINDS:
        cell_kinds[_gv_kind] = _gridvalue
    cell_kinds["prescalercell"] = _KindHandlers(
        value_kinds.build_prescalercell, value_kinds.update_prescalercell
    )
    cell_kinds["weightcell"] = _KindHandlers(
        value_kinds.build_weightcell, value_kinds.update_weightcell
    )
    cell_kinds["powerinput"] = _KindHandlers(
        value_kinds.build_powerinput, value_kinds.update_powerinput
    )
    cell_kinds["powerdisplay"] = _KindHandlers(
        value_kinds.build_powerdisplay, value_kinds.update_powerdisplay
    )
    cell_kinds["gentuningcell"] = _KindHandlers(
        value_kinds.build_gentuningcell, value_kinds.update_gentuningcell
    )

    cell_kinds["plain_text_edit"] = _KindHandlers(
        value_kinds.build_plain_text_edit, value_kinds.update_plain_text_edit
    )

    cell_kinds["genratio"] = _KindHandlers(value_kinds.build_genratio, value_kinds.update_ratio)
    cell_kinds["commaratio"] = _KindHandlers(value_kinds.build_commaratio, value_kinds.update_ratio)
    cell_kinds["tuningvalue"] = _KindHandlers(
        value_kinds.build_tuning_value, value_kinds.update_tuning_value
    )


def register_label_kinds(cell_kinds) -> None:
    _value_builder = value_kinds.label_builder("rtt-value")
    cell_kinds["prime"] = _KindHandlers(_value_builder, value_kinds.update_label)
    cell_kinds["mapped"] = _KindHandlers(value_kinds.build_mapped, value_kinds.update_ratio)
    cell_kinds["vector"] = _KindHandlers(_value_builder, value_kinds.update_label)
    cell_kinds["colheader"] = _KindHandlers(
        value_kinds.label_builder("rtt-column-header"), value_kinds.update_label
    )
    cell_kinds["rowlabel"] = _KindHandlers(
        value_kinds.label_builder("rtt-row-label"), value_kinds.update_label
    )
    cell_kinds["plain_text"] = _KindHandlers(
        value_kinds.label_builder("rtt-plain-text"), value_kinds.update_plain_text
    )
    cell_kinds["transpose"] = _KindHandlers(
        value_kinds.label_builder("rtt-transpose"), value_kinds.update_label
    )
    cell_kinds["boxtitle"] = _KindHandlers(value_kinds.label_builder("rtt-box-title"), None)


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
