from __future__ import annotations

from nicegui import ui

from rtt.app import (
    presets,
    service,
    spreadsheet,
    tooltips,
)
from rtt.app.page_assets import (
    _INT_WHEEL_JS,
    _SUBPICK_POPUP_W,
    _formchooser_options,
    _GroupedSelect,
    _projection_prompt,
    _set_offlist_prompt,
)
from rtt.app.render_html import (
    _FOLD_GLYPH,
    _control_svg,
    _limit_text,
    _select_props,
)


class _ReconChoosers:
    def __init__(self, r) -> None:
        self.r = r

    def _build_rangemode(self, cb: spreadsheet.CellBox, wrap) -> None:
        wrap.classes("rtt-rangemode")
        opts = {}
        for mode in ("monotone", "tradeoff"):
            opt = ui.element("div").classes("rtt-rangeopt")
            with opt:
                ui.element("span").classes("rtt-rangebox")
                ui.label(mode).classes("rtt-rangelabel")
            opt.on("click", lambda _=None, m=mode: self.r._cb.on_range_mode(m))
            opts[mode] = opt
        self.r.cells[cb.id].chooser.rangeopts = opts

    def _update_rangemode(self, cb: spreadsheet.CellBox) -> None:
        for mode, opt in self.r.cells[cb.id].chooser.rangeopts.items():
            (
                opt.classes(add="rtt-rangeopt-on")
                if mode == cb.text
                else opt.classes(remove="rtt-rangeopt-on")
            )

    def _build_scheme_button(self, cb: spreadsheet.CellBox, _wrap) -> None:
        self.r.cells[cb.id].chooser.scheme_button = (
            ui.button(
                cb.text, on_click=lambda: self.r._cb.act(self.r._editor.back_to_scheme), color=None
            )
            .props("unelevated dense no-caps")
            .classes("rtt-scheme-btn")
        )

    def _update_scheme_button(self, cb: spreadsheet.CellBox) -> None:
        btn = self.r.cells[cb.id].chooser.scheme_button
        (
            btn.classes(add="rtt-scheme-btn-idle")
            if not self.r._editor.manual_tuning
            else btn.classes(remove="rtt-scheme-btn-idle")
        )

    def _build_foldtoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        item = cb.id.split("toggle:", 1)[1]
        self.r.cells[cb.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
            "rtt-glyph rtt-toggle"
        )
        self.r.cells[cb.id].chooser.fold_state = cb.text
        wrap.on("click", lambda _=None, it=item: self.r._cb.on_toggle(it))

    def _build_alltoggle(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.r.cells[cb.id].display.html = ui.html(_control_svg(_FOLD_GLYPH[cb.text])).classes(
            "rtt-glyph rtt-toggle"
        )
        self.r.cells[cb.id].chooser.fold_state = cb.text
        wrap.on("click", lambda _=None: self.r._cb.on_toggle_all())

    def _update_foldtoggle(self, cb: spreadsheet.CellBox) -> None:
        if self.r.handles(cb.id).chooser.fold_state != cb.text:
            self.r.cells[cb.id].display.html.set_content(_control_svg(_FOLD_GLYPH[cb.text]))
            self.r.cells[cb.id].chooser.fold_state = cb.text

    def _arm_option_hover(self, sel, wrap, cid: str) -> None:
        sel.add_slot(
            "option",
            f"""
            <q-item v-bind="props.itemProps" :data-optidx="props.opt.value" data-optcid="{cid}">
                <q-item-section><q-item-label>{{{{ props.opt.label }}}}</q-item-label></q-item-section>
            </q-item>
        """,
        )
        wrap.on("opthover", lambda e: self.r._cb.on_chooser_hover(cid, e.args), args=["detail"])
        sel.on("popup-show", lambda _=None: self.r._cb.on_popup(cid, True))
        sel.on("popup-hide", lambda _=None: self.r._cb.on_popup(cid, False))

    def _build_preset(self, cb: spreadsheet.CellBox, wrap) -> None:
        name = cb.id.split(":")[1]
        if name == "target":
            self._build_preset_target(cb, wrap)
        elif name == "temperament":
            self._build_preset_temperament(cb, wrap)
        else:
            options, value, prompt = self._scheme_options(cb, name)
            self._build_scheme_select(cb, wrap, options, value, prompt)

    def _build_preset_target(self, cb: spreadsheet.CellBox, wrap) -> None:
        limit, family = self.r._target_preset_values()
        with ui.element("div").classes("rtt-preset-target"):
            num = (
                ui.input(
                    value=_limit_text(limit), on_change=lambda _e: self.r._cb.on_target_change()
                )
                .props(
                    'dense borderless hide-bottom-space placeholder="-" inputmode=numeric debounce=300'
                )
                .classes("rtt-preset-num")
            )
            # make the limit input CONTROLLED (ui.input defaults loopback off, leaving the box
            # uncontrolled during typing). Off, the server can't overwrite what was typed, so a
            # rejected non-number couldn't be reverted nor a value reddened-in-place. On, the
            # server's value always wins — debounce keeps the echo to once-per-settled-entry.
            self._wire_target_limit(num, cb)
            sel = (
                ui.select(
                    list(presets.TARGET_SETS),
                    value=family,
                    on_change=lambda _e: self.r._cb.on_target_change(),
                )
                .props(_select_props(cb.w - 30))
                .classes("rtt-preset")
            )
        _set_offlist_prompt(sel, family)
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = (num, sel)

    def _wire_target_limit(self, num, cb: spreadsheet.CellBox) -> None:
        num.LOOPBACK = True
        num._props["loopback"] = True
        num.on(
            "wheel",
            lambda e: self.r._cb.on_target_limit_wheel(e.args.get("deltaY")),
            args=["deltaY"],
            js_handler=_INT_WHEEL_JS,
        )
        num.on("focus", lambda _=None: self.r._cb.on_cell_focus(cb.id))
        num.on("blur", lambda _=None, cid=cb.id: self.r._cb.on_cell_blur(cid))
        # Enter commits the typed limit. The field is debounce=300 + loopback-controlled, so its
        # value only settles to the server (firing the on_change commit) after a typing pause or
        # on blur — pressing Enter alone did nothing (the reported "Enter doesn't submit the
        # TILT/OLD number, only blur"). Blur the input on Enter: Quasar flushes the debounced
        # value at once (committing via on_change) and the native blur runs on_cell_blur. Pure
        # client-side, so it also works when the debounce hasn't yet elapsed.
        num.on("keydown.enter", js_handler="(e) => e.target.blur()")
        # ...and previews each keystroke LIVE the way a wheel notch does, reddening the rows the
        # typed limit would drop before the debounced commit reflows them away. on_change is the
        # debounced model-value (the commit); this must fire at once on each keystroke instead.
        # NOT the DOM `input` event: a Quasar QInput doesn't forward native `input` to a NiceGUI
        # `.on()` listener (it never reaches the socket — verified), so an `.on("input")` preview
        # silently never ran. `keyup` DOES fire on the QInput; and since NiceGUI's `args=` only
        # filters TOP-LEVEL event keys (it can't pull the nested `target.value`), mirror the
        # wheel's js_handler trick and emit the live DOM text ourselves — `e.args` is then the
        # typed string (the loopback-debounced model value lags a keystroke, so read the event).
        num.on(
            "keyup",
            lambda e: self.r._cb.on_target_limit_preview(e.args),
            js_handler="(e) => emit(e.target.value)",
        )

    def _build_preset_temperament(self, cb: spreadsheet.CellBox, wrap) -> None:
        value = presets.identify(self.r._editor.state)
        sel = (
            _GroupedSelect(
                presets.temperament_options(),
                value=value,
                is_divider=presets.is_divider,
                on_change=lambda e: self.r._cb.on_preset(cb.id, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        _set_offlist_prompt(sel, value)
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = sel

    def _scheme_options(self, cb: spreadsheet.CellBox, name: str) -> tuple[list, object, str]:
        if name == "prescaler":
            options = list(presets.prescaler_options(self.r._editor.settings["alt_complexity"]))
            value = self.r._editor.displayed_prescaler_name
            return options, (value if value in options else None), "-"
        if name == "projection":
            options = presets.projection_options(self.r._editor.state)
            value = self.r._editor.displayed_projection_scheme_name
            return options, (value if value in options else None), _projection_prompt(cb.id)
        options = presets.tuning_scheme_options(
            service.is_all_interval(self.r._editor.tuning_scheme),
            self.r._editor.settings["alt_complexity"],
            self.r._editor.settings["weighting"],
        )
        scheme = self.r._editor.displayed_tuning_scheme_name
        return options, (scheme if scheme in options else None), "-"

    def _build_scheme_select(self, cb, wrap, options, value, prompt) -> None:
        sel = (
            ui.select(
                options, value=value, on_change=lambda e: self.r._cb.on_preset(cb.id, e.value)
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        _set_offlist_prompt(sel, value, prompt)
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = sel

    def _chooser_reflow_hold(self, cid: str) -> bool:
        # True while a generic chooser hover's REFLOW preview is re-rendering the grid for THIS
        # chooser: the hovered chooser's q-select value + open popup must stay steady across that
        # re-render (re-setting a q-select's value / options would disrupt or close its open popup),
        # so the cell's update is skipped while it holds. Held by chooser GROUP, not exact id: a
        # preset and its copy (preset:tuning ⟷ preset:tuning:gens, preset:projection ⟷
        # preset:projection:gens — one selection shown in two tiles) must move together, else the
        # non-hovered twin would flip to the hypothetical value while the hovered one stays put, so
        # the two faces would disagree mid-preview. The group is the cid's first two ":"-segments
        # (the copy adds a 3rd), so the base + every copy share it. The generic-chooser analogue of
        # the temperament guard below, which groups its own copies via the "preset:temperament" prefix.
        g = self.r._cur_gesture
        if g is None or g.kind != "chooser" or not g.reflowed or g.source is None:
            return False

        def group(c):
            return ":".join(c.split(":")[:2])

        return group(cid) == group(g.source)

    def _update_preset(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        if cb.id.startswith("preset:temperament"):
            g = self.r._cur_gesture
            if g is not None and g.kind == "temp" and g.reflowed:
                return
            value = presets.identify(self.r._editor.state)
            self.r.cells[cb.id].chooser.select.value = value
            _set_offlist_prompt(self.r.cells[cb.id].chooser.select, value)
        elif cb.id == "preset:target":
            num, sel = self.r.cells[cb.id].chooser.select
            limit, family = self.r._target_preset_values()
            num.value = _limit_text(limit)
            sel.value = family
            _set_offlist_prompt(sel, family)
            num.set_enabled(not cb.disabled)
            sel.set_enabled(not cb.disabled)
            self._sync_target_limit_error(num, family, limit)
        elif cb.id == "preset:prescaler":
            options = list(presets.prescaler_options(self.r._editor.settings["alt_complexity"]))
            value = self.r._editor.displayed_prescaler_name
            value = value if value in options else None
            self.r.cells[cb.id].chooser.select.set_options(options, value=value)
            _set_offlist_prompt(self.r.cells[cb.id].chooser.select, value)
            self.r.cells[cb.id].chooser.select.set_enabled(not cb.disabled)
        elif cb.id.startswith("preset:projection"):
            options = presets.projection_options(self.r._editor.state)
            value = self.r._editor.displayed_projection_scheme_name
            value = value if value in options else None
            self.r.cells[cb.id].chooser.select.set_options(options, value=value)
            _set_offlist_prompt(self.r.cells[cb.id].chooser.select, value, prompt=_projection_prompt(cb.id))
            self.r.cells[cb.id].chooser.select.set_enabled(not cb.disabled)
        else:
            name = self.r._editor.displayed_tuning_scheme_name
            options = presets.tuning_scheme_options(
                service.is_all_interval(self.r._editor.tuning_scheme),
                self.r._editor.settings["alt_complexity"],
                self.r._editor.settings["weighting"],
            )
            scheme = name if name in options else None
            self.r.cells[cb.id].chooser.select.set_options(options, value=scheme)
            _set_offlist_prompt(self.r.cells[cb.id].chooser.select, scheme)
            self.r.cells[cb.id].chooser.select.set_enabled(not cb.disabled)

    def _build_subpick(self, cb, wrap, options, value):
        sel = (
            ui.select(
                options,
                value=value if value in options else None,
                on_change=lambda e, cid=cb.id: self.r._cb.on_subpick(cid, e.value),
            )
            .props(_select_props(_SUBPICK_POPUP_W))
            .classes("rtt-preset rtt-subpick")
        )
        _set_offlist_prompt(sel, value if value in options else None)
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = sel

    def _build_etpick(self, cb, wrap):
        db = self.r._editor.state.domain_basis
        value = (
            None if cb.pending else presets.identify_et(self.r._editor.state.mapping[cb.gen], db)
        )
        self._build_subpick(cb, wrap, presets.et_options(db), value)

    def _build_commapick(self, cb, wrap):
        db = self.r._editor.state.domain_basis
        value = (
            None
            if cb.pending
            else presets.identify_comma(self.r._editor.state.comma_basis[cb.comma], db)
        )
        self._build_subpick(cb, wrap, presets.comma_options(db), value)

    def _update_subpick(self, cb):
        g = self.r._cur_gesture
        if g is not None and g.kind == "temp" and g.reflowed:
            return
        sel = self.r.handles(cb.id).chooser.select
        if not isinstance(sel, ui.select):
            return
        db = self.r._editor.state.domain_basis
        if cb.id.startswith("etpick:"):
            options = presets.et_options(db)
            if cb.pending or cb.gen >= len(self.r._editor.state.mapping):
                value = None
            else:
                value = presets.identify_et(self.r._editor.state.mapping[cb.gen], db)
        else:
            options = presets.comma_options(db)
            if cb.pending or cb.comma >= len(self.r._editor.state.comma_basis):
                value = None
            else:
                value = presets.identify_comma(self.r._editor.state.comma_basis[cb.comma], db)
        value = value if value in options else None
        sel.set_options(options, value=value)
        _set_offlist_prompt(sel, value)

    def _sync_target_limit_error(self, num, family, limit) -> None:
        problem = service.target_limit_problem(family, limit)
        num.classes(
            add="rtt-limit-error" if problem else "", remove="" if problem else "rtt-limit-error"
        )
        if self.r.target_limit_tip is not None:
            self.r.target_limit_tip.set_text(
                tooltips.target_limit_help(problem)
                if problem
                else tooltips.control_help("preset", "preset:target")
            )
            self.r.target_limit_tip.classes(
                add="rtt-tip-error" if problem else "", remove="" if problem else "rtt-tip-error"
            )

    def _build_control_select(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = (
            ui.select(
                list(cb.values),
                value=cb.text or None,
                on_change=lambda e, cid=cb.id: self.r._cb.on_control_select(cid, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = sel

    def _update_control_select(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.r.cells[cb.id].chooser.select.set_options(list(cb.values), value=cb.text or None)
        self.r.cells[cb.id].chooser.select.set_enabled(not cb.disabled)

    def _build_control_check(self, cb: spreadsheet.CellBox, wrap) -> None:
        self.r.cells[cb.id].chooser.check = (
            ui.checkbox(
                cb.text,
                value=cb.checked,
                on_change=lambda e, cid=cb.id: self.r._cb.on_control_select(cid, e.value),
            )
            .props("dense")
            .classes("rtt-control-check")
        )
        apply = self._control_check_preview(cb)
        if apply is not None:
            self._preview_control(wrap, apply)

    def _control_check_preview(self, cb: spreadsheet.CellBox):
        if cb.id == "control:diminuator":
            return lambda: self.r._editor.set_diminuator_replaced(
                not service.diminuator_replaced(self.r._editor.tuning_scheme)
            )
        if cb.id == "control:all_interval":
            return lambda: self.r._editor.set_all_interval(
                not service.is_all_interval(self.r._editor.tuning_scheme)
            )
        return None

    def _update_control_check(self, cb: spreadsheet.CellBox) -> None:
        self.r.cells[cb.id].chooser.check.value = cb.checked

    def _build_formchooser(self, cb: spreadsheet.CellBox, wrap) -> None:
        sel = (
            ui.select(
                _formchooser_options(cb.id),
                value=cb.text or "",
                on_change=lambda e, c=cb.id: self.r._cb.on_form_choose(c, e.value),
            )
            .props(_select_props(cb.w))
            .classes("rtt-preset")
        )
        self._arm_option_hover(sel, wrap, cb.id)
        self.r.cells[cb.id].chooser.select = sel

    def _update_formchooser(self, cb: spreadsheet.CellBox) -> None:
        if self._chooser_reflow_hold(cb.id):
            return
        self.r.cells[cb.id].chooser.select.set_options(_formchooser_options(cb.id), value=cb.text or "")

    def _preview_control(self, el, apply) -> None:
        el.on("mouseenter", lambda _=None: self.r._cb.control_hover(apply))
        el.on("mouseleave", lambda _=None: self.r._cb.control_unhover())

    def _preview_rank_remove(self, el, axis: str, idx: int) -> None:
        el.on("mouseenter", lambda _=None: self.r._cb.rank_remove_hover(axis, idx))
        el.on("mouseleave", lambda _=None: self.r._cb.rank_remove_unhover())
