"""NiceGUI front end for the RTT monolith.

The layout is the spreadsheet coordinate model (:mod:`rtt.web.spreadsheet`): rows
are the temperament's quantities, columns the sets they're shown over, cells on
shared prime/generator axes. The renderer is persistent and reconciling — one
element per entity id, moved/updated on each state change rather than rebuilt —
so rows/columns animate via CSS transitions. Editing the mapping recomputes
in-process; domain expand/shrink and undo are available. No HTTP layer.
"""

from __future__ import annotations

from nicegui import ui

from rtt.web import settings as show_settings
from rtt.web import spreadsheet
from rtt.web.editor import Editor

_PAD = 12  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration

_CSS = f"""
.rtt-title {{ font-family:'Cambria',Georgia,serif; font-size:30px; font-weight:bold;
             color:#000; margin:6px 0 8px 2px; }}
.rtt-undo {{ width:100px !important; height:22px !important; min-height:22px !important;
            background:#fff !important; border:1px solid #888 !important; border-radius:0 !important;
            box-shadow:none !important; padding:0 !important; margin:0; }}
.rtt-undo .q-btn__content {{ color:#777 !important; font-size:14px;
            font-family:'Cambria',Georgia,serif; }}

.rtt-outer {{ background:#c0c0c0; padding:{_PAD}px; width:max-content;
              font-family:'Cambria',Georgia,serif; }}
.rtt-board {{ position:relative; transition:width {_T}, height {_T}; }}
@keyframes rtt-in {{ from {{ opacity:0; }} to {{ opacity:1; }} }}
.rtt-line, .rtt-block, .rtt-cell {{ animation:rtt-in {_T} ease; }}

.rtt-line {{ position:absolute; z-index:1; opacity:1; transition:left {_T}, top {_T},
            width {_T}, height {_T}, opacity {_T}; }}
.rtt-line-v {{ border-left:1px solid #e0e0e0; width:0; }}
.rtt-line-h {{ border-top:1px solid #e0e0e0; height:0; }}
.rtt-block {{ position:absolute; z-index:2; background:#e0e0e0; opacity:1;
             transition:left {_T}, top {_T}, width {_T}, height {_T}, opacity {_T}; }}
.rtt-cell {{ position:absolute; z-index:3; display:flex; align-items:center; justify-content:center;
            opacity:1; transition:left {_T}, top {_T}, opacity {_T}; }}

.rtt-white {{ width:26px; height:26px; display:flex; align-items:center; justify-content:center;
             background:#fff; outline:1px solid #c8c8c8; color:#000; font-size:14px; }}
.rtt-colheader {{ font-size:13px; font-weight:bold; color:#000; white-space:nowrap; }}
.rtt-rowlabel {{ font-size:13px; font-weight:bold; color:#000; width:100%; text-align:right;
                padding-right:8px; }}
.rtt-genratio {{ font-size:14px; color:#000; }}
.rtt-val {{ font-size:14px; color:#000; }}
.rtt-tval {{ font-size:12px; color:#000; white-space:nowrap; }}
.rtt-cellinput {{ width:26px !important; min-height:26px; }}
.rtt-cellinput .q-field__control {{ width:26px !important; height:26px !important; min-height:26px !important;
            padding:0 !important; background:#fff; outline:1px solid #c8c8c8; }}
.rtt-cellinput .q-field__control::before, .rtt-cellinput .q-field__control::after {{ display:none !important; }}
.rtt-cellinput .q-field__native {{ text-align:center; padding:0 !important; color:#000; font-size:14px;
            min-height:26px; font-family:'Cambria',Georgia,serif; }}
.rtt-cellinput .q-field__bottom, .rtt-cellinput .q-field__marginal {{ display:none !important; }}
.rtt-btn {{ width:20px !important; min-width:20px !important; height:20px !important;
           min-height:20px !important; background:#fff !important; border:1px solid #888 !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }}
.rtt-btn .q-btn__content {{ color:#000 !important; font-size:15px;
           font-family:'Cambria',Georgia,serif; }}

.rtt-gear {{ width:26px !important; min-width:26px !important; height:26px !important;
            min-height:26px !important; padding:0 !important; box-shadow:none !important; }}
.rtt-gear .q-icon {{ color:#777 !important; font-size:20px; }}
.rtt-show-card {{ font-family:'Cambria',Georgia,serif; background:#fff; color:#000;
                 min-width:440px; padding:14px 18px; border-radius:0; box-shadow:0 2px 12px #0003; }}
.rtt-show-title {{ font-size:22px; font-weight:bold; margin-bottom:6px; }}
.rtt-show-groups {{ gap:44px; align-items:flex-start; flex-wrap:nowrap; }}
.rtt-show-grouptitle {{ font-size:13px; font-weight:bold; color:#000;
                       margin-bottom:2px; white-space:nowrap; }}
.rtt-show-item .q-checkbox__label {{ font-family:'Cambria',Georgia,serif; font-size:13px; color:#000; }}
"""

_LABEL_KINDS = {"prime", "genratio", "colheader", "rowlabel", "target", "mapped", "tval"}


def _parse_int(text):
    """``text`` -> int, or None for blank/partial input (matching the old parseInt)."""
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return None


@ui.page("/")
def index() -> None:
    ui.add_css(_CSS)
    ui.query("body").style("background:#fff")

    editor = Editor()
    settings = show_settings.defaults()  # which parts of the grid are visible
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # mapping cell id -> q-input
    labels: dict = {}  # cell id -> the label whose text tracks state
    building = [False]
    refs: dict = {}

    def on_mapping_change():
        if building[0] or not settings["temperament_boxes"]:  # no editable matrix when hidden
            return
        d, r = editor.state.d, len(editor.state.mapping)
        matrix = [[_parse_int(inputs[f"cell:mapping:{i}:{p}"].value) for p in range(d)] for i in range(r)]
        if any(v is None for row in matrix for v in row):
            return
        editor.edit_mapping(matrix)
        render()

    def act(action):
        action()
        render()

    def on_show_toggle(key, value):
        settings[key] = value
        render()  # the reconciling renderer animates the affected rows/columns in or out

    def _make_cell(cb):
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"')
        with wrap:
            if cb.kind == "mapping":
                inputs[cb.id] = ui.input(on_change=lambda e: on_mapping_change()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prime":
                with ui.element("div").classes("rtt-white"):
                    labels[cb.id] = ui.label(cb.text)
            elif cb.kind == "genratio":
                labels[cb.id] = ui.label(cb.text).classes("rtt-genratio")
            elif cb.kind in ("target", "mapped"):
                labels[cb.id] = ui.label(cb.text).classes("rtt-val")
            elif cb.kind == "tval":
                labels[cb.id] = ui.label(cb.text).classes("rtt-tval")
            elif cb.kind == "colheader":
                labels[cb.id] = ui.label(cb.text).classes("rtt-colheader")
            elif cb.kind == "rowlabel":
                labels[cb.id] = ui.label(cb.text).classes("rtt-rowlabel")
            elif cb.kind == "minus":
                refs["minus"] = ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
        return wrap

    def render():
        building[0] = True
        st = editor.state
        lay = spreadsheet.build(st, settings)
        board.style(f"width:{lay.width}px; height:{lay.height}px")
        seen = set()

        for ln in lay.lines:
            seen.add(ln.id)
            if ln.id not in els:
                with board:
                    cls = "rtt-line " + ("rtt-line-v" if ln.orientation == "v" else "rtt-line-h")
                    els[ln.id] = ui.element("div").classes(cls).props(f'data-eid="{ln.id}"')
            if ln.orientation == "v":
                els[ln.id].style(f"left:{ln.pos}px; top:{ln.start}px; height:{ln.length}px")
            else:
                els[ln.id].style(f"top:{ln.pos}px; left:{ln.start}px; width:{ln.length}px")

        for bl in lay.blocks:
            seen.add(bl.id)
            if bl.id not in els:
                with board:
                    els[bl.id] = ui.element("div").classes("rtt-block").props(f'data-eid="{bl.id}"')
            els[bl.id].style(f"left:{bl.x}px; top:{bl.y}px; width:{bl.w}px; height:{bl.h}px")

        for cb in lay.cells:
            seen.add(cb.id)
            if cb.id not in els:
                with board:
                    els[cb.id] = _make_cell(cb)
            els[cb.id].style(f"left:{cb.x}px; top:{cb.y}px; width:{cb.w}px; height:{cb.h}px")
            if cb.kind == "mapping":
                inputs[cb.id].value = str(st.mapping[cb.gen][cb.prime])
            elif cb.kind in _LABEL_KINDS:
                labels[cb.id].set_text(cb.text)

        for eid in [e for e in els if e not in seen]:
            els[eid].delete()
            del els[eid]
            inputs.pop(eid, None)
            labels.pop(eid, None)

        if "minus" in refs:
            refs["minus"].set_enabled(editor.can_shrink)
        refs["undo"].set_enabled(editor.can_undo)
        refs["redo"].set_enabled(editor.can_redo)
        building[0] = False

    with ui.dialog() as show_dialog, ui.card().classes("rtt-show-card"):
        ui.label("Show").classes("rtt-show-title")
        with ui.row().classes("rtt-show-groups"):
            for group_name, items in show_settings.SHOW_GROUPS:
                with ui.column().classes("rtt-show-group"):
                    ui.label(group_name).classes("rtt-show-grouptitle")
                    for key, label, _ in items:
                        ui.checkbox(label, value=settings[key],
                                    on_change=lambda e, k=key: on_show_toggle(k, e.value)) \
                            .props("dense size=xs color=grey-8").classes("rtt-show-item")

    ui.label("RTT App").classes("rtt-title")
    with ui.row().style("gap:6px; margin-bottom:10px; align-items:center"):
        refs["undo"] = ui.button("undo", on_click=lambda: act(editor.undo), color=None) \
            .props("no-caps unelevated square").classes("rtt-undo")
        refs["redo"] = ui.button("redo", on_click=lambda: act(editor.redo), color=None) \
            .props("no-caps unelevated square").classes("rtt-undo")
        ui.button(icon="settings", on_click=show_dialog.open, color=None) \
            .props("flat dense round").classes("rtt-gear")
    with ui.element("div").classes("rtt-outer"):
        board = ui.element("div").classes("rtt-board")

    def on_key(e):
        if not (e.action.keydown and e.modifiers.ctrl):
            return
        is_z = e.key == "z" or e.key == "Z"
        if e.key == "y" or (is_z and e.modifiers.shift):
            act(editor.redo)
        elif is_z:
            act(editor.undo)

    ui.keyboard(on_key=on_key)
    render()


def main() -> None:
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8137
    ui.run(title="RTT", reload=False, show=False, port=port)


if __name__ in {"__main__", "__mp_main__"}:
    main()
