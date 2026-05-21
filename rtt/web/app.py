"""NiceGUI front end for the RTT monolith.

Thin glue over :class:`rtt.web.editor.Editor`. The layout comes from
:mod:`rtt.web.grid`, which reproduces the original app's coordinate grid (shared
prime axis, #e0e0e0 padded blocks, #c0c0c0 margins, #e0e0e0 grid lines). Editing
the mapping or comma basis recomputes the dual in-process; domain expand/shrink
and undo are also available. No HTTP layer.
"""

from __future__ import annotations

from nicegui import ui

from rtt.web import grid, service
from rtt.web.editor import Editor

# The original app's styles (styles.scss), plus the title/undo and the input/button chrome.
_CSS = """
.rtt-title { font-family:'Cambria',Georgia,serif; font-size:30px; font-weight:bold;
             color:#000; margin:6px 0 8px 2px; }
.rtt-undo { width:100px !important; height:22px !important; min-height:22px !important;
            background:#fff !important; border:1px solid #888 !important; border-radius:0 !important;
            box-shadow:none !important; padding:0 !important; margin:0 0 10px 2px; }
.rtt-undo .q-btn__content { color:#777 !important; font-size:14px;
            font-family:'Cambria',Georgia,serif; }

.rtt-container { display:grid; grid-auto-columns:min-content; grid-auto-rows:min-content;
                 background:#c0c0c0; padding:10px; width:max-content;
                 font-family:'Cambria',Georgia,serif; }
.square-box { width:30px; height:30px; display:flex; align-items:center; justify-content:center;
              background:#e0e0e0; }
.square-input { width:30px; height:30px; display:flex; align-items:center; justify-content:center;
                background:#e0e0e0; }
.corner-padding { background:#e0e0e0; width:100%; height:100%; min-width:10px; }
.vertical-padding { min-height:10px; background:#e0e0e0; width:100%; height:100%; }
.horizontal-padding { min-width:10px; background:#e0e0e0; height:100%; width:100%; }
.corner-margin { background:#c0c0c0; width:100%; height:100%; min-width:10px; }
.vertical-margin { min-height:10px; background:#c0c0c0; width:100%; height:100%;
                   display:flex; justify-content:center; }
.horizontal-margin { min-width:10px; background:#c0c0c0; height:100%; width:100%;
                     display:flex; align-items:center; }
.blank { background:#e0e0e0; width:100%; height:100%; }
.empty-box-element { height:100%; width:100%; display:flex; justify-content:center; align-items:center; }
.box-name { z-index:10; background:#e0e0e0; text-align:center; width:100%; height:100%;
            color:#444; font-size:12px; display:flex; align-items:center; justify-content:center; }
.grid-line-horizontal { border-top:1px solid #e0e0e0; width:100%; height:0; }
.grid-line-vertical { border-left:1px solid #e0e0e0; height:100%; width:0; }

.rtt-whitebox { width:26px; height:26px; display:flex; align-items:center; justify-content:center;
                background:#fff; outline:1px solid #c8c8c8; color:#000; font-size:14px; }
.rtt-cell { width:26px !important; min-height:26px; }
.rtt-cell .q-field__control { width:26px !important; height:26px !important; min-height:26px !important;
            padding:0 !important; background:#fff; outline:1px solid #c8c8c8; }
.rtt-cell .q-field__control::before, .rtt-cell .q-field__control::after { display:none !important; }
.rtt-cell .q-field__native { text-align:center; padding:0 !important; color:#000; font-size:14px;
            min-height:26px; font-family:'Cambria',Georgia,serif; }
.rtt-cell .q-field__bottom, .rtt-cell .q-field__marginal { display:none !important; }
.rtt-btn { width:20px !important; min-width:20px !important; height:20px !important;
           min-height:20px !important; background:#fff !important; border:1px solid #888 !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }
.rtt-btn .q-btn__content { color:#000 !important; font-size:15px;
           font-family:'Cambria',Georgia,serif; }
"""


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
    mapping_inputs: dict = {}  # (gen, prime) -> input
    comma_inputs: dict = {}  # (comma, prime) -> input
    building = [False]
    refs: dict = {}

    def _matrix(inputs, rows, cols):
        matrix = [[_parse_int(inputs[(r, c)].value) for c in range(cols)] for r in range(rows)]
        if any(v is None for row in matrix for v in row):
            return None
        return matrix

    def _shape(state):
        return (state.d, len(state.mapping), len(state.comma_basis))

    def _sync_undo():
        refs["undo"].set_enabled(editor.can_undo)

    def on_mapping_change():
        if building[0]:
            return
        matrix = _matrix(mapping_inputs, len(editor.state.mapping), editor.state.d)
        if matrix is None:
            return
        before = _shape(editor.state)
        editor.edit_mapping(matrix)
        _sync_undo()
        if _shape(editor.state) == before:
            building[0] = True
            for (comma, prime), inp in comma_inputs.items():
                inp.value = str(editor.state.comma_basis[comma][prime])
            building[0] = False
        else:
            board.refresh()

    def on_comma_change():
        if building[0]:
            return
        matrix = _matrix(comma_inputs, len(editor.state.comma_basis), editor.state.d)
        if matrix is None:
            return
        before = _shape(editor.state)
        editor.edit_comma_basis(matrix)
        _sync_undo()
        if _shape(editor.state) == before:
            building[0] = True
            for (gen, prime), inp in mapping_inputs.items():
                inp.value = str(editor.state.mapping[gen][prime])
            building[0] = False
        else:
            board.refresh()

    def act(action):
        action()
        board.refresh()
        _sync_undo()

    def _render_cell(cell, state):
        style = f"grid-row:{cell.row}; grid-column:{cell.col} / span {cell.colspan}"
        with ui.element("div").classes(cell.css).style(style):
            if cell.hline:
                ui.element("div").classes("grid-line-horizontal")
            if cell.vline:
                ui.element("div").classes("grid-line-vertical")
            if cell.kind == "prime":
                with ui.element("div").classes("rtt-whitebox"):
                    ui.label(cell.text)
            elif cell.kind == "mapping":
                mapping_inputs[(cell.gen, cell.prime)] = ui.input(
                    value=str(state.mapping[cell.gen][cell.prime]),
                    on_change=lambda e: on_mapping_change(),
                ).props("dense borderless").classes("rtt-cell")
            elif cell.kind == "comma":
                comma_inputs[(cell.comma, cell.prime)] = ui.input(
                    value=str(state.comma_basis[cell.comma][cell.prime]),
                    on_change=lambda e: on_comma_change(),
                ).props("dense borderless").classes("rtt-cell")
            elif cell.kind == "minus":
                btn = ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
                btn.set_enabled(editor.can_shrink)
            elif cell.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cell.kind == "name":
                ui.label(cell.text)

    @ui.refreshable
    def board():
        building[0] = True
        mapping_inputs.clear()
        comma_inputs.clear()
        state = editor.state
        primes = service.standard_primes(state.d)
        cells = grid.build(state.d, len(state.mapping), len(state.comma_basis), primes)
        with ui.element("div").classes("rtt-container"):
            for cell in cells:
                _render_cell(cell, state)
        building[0] = False

    ui.label("RTT App").classes("rtt-title")
    refs["undo"] = ui.button("undo", on_click=lambda: act(editor.undo), color=None) \
        .props("no-caps unelevated square").classes("rtt-undo")
    refs["undo"].set_enabled(editor.can_undo)
    board()


def main() -> None:
    ui.run(title="RTT", reload=False, show=False, port=8137)


if __name__ in {"__main__", "__mp_main__"}:
    main()
