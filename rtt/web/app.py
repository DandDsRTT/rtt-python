"""NiceGUI front end for the RTT monolith.

Thin glue over :class:`rtt.web.editor.Editor`: it renders the mapping and comma
basis as editable grids, recomputes the dual via the editor on every valid edit,
and offers domain expand/shrink and undo. No HTTP layer — handlers call the
library (through the service) in-process.
"""

from __future__ import annotations

from nicegui import ui

from rtt.web import service
from rtt.web.editor import Editor

_CSS = """
.rtt-page { font-family: 'Cambria', Georgia, serif; }
.rtt-container { background:#c0c0c0; padding:12px; gap:16px; align-items:flex-start;
                 width:max-content; border-radius:4px; }
.rtt-box { background:#e0e0e0; padding:8px; gap:6px; align-items:center; border-radius:2px; }
.rtt-name { color:#333; padding-top:4px; }
.rtt-prime { color:#666; font-style:italic; width:34px; text-align:center; }
.rtt-cell { width:34px; }
.rtt-cell input { text-align:center !important; padding:2px 0 !important; }
.rtt-controls .q-btn { min-width:24px; min-height:24px; padding:0; }
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
    ui.query("body").classes("rtt-page")

    editor = Editor()
    mapping_inputs: list[list] = []
    comma_inputs: list[list] = []
    building = [False]

    def gathered(inputs):
        """Read the live cell elements into an int matrix, or None if incomplete."""
        matrix = [[_parse_int(cell.value) for cell in row] for row in inputs]
        if any(value is None for row in matrix for value in row):
            return None
        return matrix

    def on_mapping_change() -> None:
        if building[0]:
            return
        matrix = gathered(mapping_inputs)
        if matrix is None:
            return
        editor.edit_mapping(matrix)
        render_comma.refresh()  # rebuild only the dependent grid; keep edit focus
        render_undo.refresh()

    def on_comma_change() -> None:
        if building[0]:
            return
        # comma_inputs is comma-major (rows = commas); the grid shows it transposed
        matrix = gathered(comma_inputs)
        if matrix is None:
            return
        editor.edit_comma_basis(matrix)
        render_mapping.refresh()
        render_undo.refresh()

    def act(action) -> None:
        action()
        render_all()

    @ui.refreshable
    def render_undo() -> None:
        ui.button("undo", on_click=lambda: act(editor.undo)) \
            .props("flat dense").set_enabled(editor.can_undo)

    @ui.refreshable
    def render_header() -> None:
        d = editor.state.d
        with ui.column().classes("rtt-box"):
            with ui.row().classes("rtt-controls").style("gap:4px"):
                ui.button("−", on_click=lambda: act(editor.shrink)) \
                    .props("dense").set_enabled(editor.can_shrink)
                ui.button("+", on_click=lambda: act(editor.expand)).props("dense")
            with ui.grid(columns=d).style("gap:4px"):
                for prime in service.standard_primes(d):
                    ui.label(str(prime)).classes("rtt-prime")

    @ui.refreshable
    def render_mapping() -> None:
        building[0] = True
        mapping_inputs.clear()
        mapping = editor.state.mapping
        with ui.column().classes("rtt-box"):
            with ui.grid(columns=len(mapping[0])).style("gap:4px"):
                for row in mapping:
                    cells = []
                    for value in row:
                        cell = ui.input(value=str(value), on_change=lambda e: on_mapping_change()) \
                            .props("dense outlined").classes("rtt-cell")
                        cells.append(cell)
                    mapping_inputs.append(cells)
            ui.label("mapping").classes("rtt-name")
        building[0] = False

    @ui.refreshable
    def render_comma() -> None:
        building[0] = True
        comma_inputs.clear()
        comma_basis = editor.state.comma_basis
        n, d = len(comma_basis), len(comma_basis[0])
        cells = [[None] * d for _ in range(n)]
        with ui.column().classes("rtt-box"):
            with ui.grid(columns=n).style("gap:4px"):
                for prime_index in range(d):  # commas shown as columns
                    for comma_index in range(n):
                        cell = ui.input(
                            value=str(comma_basis[comma_index][prime_index]),
                            on_change=lambda e: on_comma_change(),
                        ).props("dense outlined").classes("rtt-cell")
                        cells[comma_index][prime_index] = cell
            ui.label("comma basis").classes("rtt-name")
        comma_inputs.extend(cells)
        building[0] = False

    def render_all() -> None:
        render_undo.refresh()
        render_header.refresh()
        render_mapping.refresh()
        render_comma.refresh()

    with ui.column().classes("rtt-page"):
        render_undo()
        with ui.row().classes("rtt-container"):
            with ui.column().style("gap:6px"):
                render_header()
                render_mapping()
            render_comma()


def main() -> None:
    ui.run(title="RTT", reload=False, show=False, port=8137)


if __name__ in {"__main__", "__mp_main__"}:
    main()
