"""NiceGUI front end for the RTT monolith.

Thin glue over :class:`rtt.web.editor.Editor`. The mapping and comma basis are
laid out on a single shared prime-axis grid (matching the original app): the
prime header sits above the mapping columns, an empty d x d square holds the
shared axis, and the comma basis hangs to its right with its prime-rows aligned
to that square. Editing either matrix recomputes the dual in-process; domain
expand/shrink and undo are also available. No HTTP layer.
"""

from __future__ import annotations

from nicegui import ui

from rtt.web import service
from rtt.web.editor import Editor

_TILE = 30  # px, one grid cell
_MARGIN = 10  # px, gap between the controls row and the matrices

_CSS = f"""
.rtt-title {{ font-family:'Cambria',Georgia,serif; font-size:30px; font-weight:bold;
             color:#000; margin:6px 0 8px 2px; }}
.rtt-undo {{ width:100px !important; height:22px !important; min-height:22px !important;
            background:#fff !important; border:1px solid #888 !important; border-radius:0 !important;
            box-shadow:none !important; padding:0 !important; margin:0 0 10px 2px; }}
.rtt-undo .q-btn__content {{ color:#777 !important; font-size:14px;
            font-family:'Cambria',Georgia,serif; }}
.rtt-grid {{ display:grid; background:#c0c0c0; padding:{_MARGIN}px; width:max-content;
            font-family:'Cambria',Georgia,serif; }}
.rtt-tile {{ background:#e0e0e0; width:{_TILE}px; height:{_TILE}px; display:flex;
            align-items:center; justify-content:center; }}
.rtt-white {{ width:26px; height:26px; display:flex; align-items:center; justify-content:center;
             background:#fff; outline:1px solid #c8c8c8; }}
.rtt-prime {{ color:#000; font-size:15px; }}
.rtt-cell {{ width:26px; min-height:26px; }}
.rtt-cell .q-field__control {{ height:26px !important; min-height:26px !important; padding:0 !important;
             background:#fff; outline:1px solid #c8c8c8; }}
.rtt-cell .q-field__control::before, .rtt-cell .q-field__control::after {{ display:none !important; }}
.rtt-cell .q-field__native {{ text-align:center; padding:0 !important; color:#000; font-size:15px;
             font-family:'Cambria',Georgia,serif; min-height:26px; }}
.rtt-cell .q-field__bottom, .rtt-cell .q-field__marginal {{ display:none !important; }}
.rtt-ctl {{ width:20px !important; min-width:20px !important; height:20px !important;
           min-height:20px !important; background:#fff !important; border:1px solid #888 !important;
           border-radius:0 !important; padding:0 !important; box-shadow:none !important; }}
.rtt-ctl .q-btn__content {{ color:#000 !important; font-size:16px; min-width:0;
           font-family:'Cambria',Georgia,serif; }}
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
    mapping_inputs: list[list] = []  # [generator][prime]
    comma_inputs: list[list] = []  # [comma][prime]
    building = [False]
    refs: dict = {}

    def gather(grid):
        matrix = [[_parse_int(cell.value) for cell in row] for row in grid]
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
        matrix = gather(mapping_inputs)
        if matrix is None:
            return
        before = _shape(editor.state)
        editor.edit_mapping(matrix)
        _sync_undo()
        if _shape(editor.state) == before:  # comma basis shape unchanged -> update in place
            building[0] = True  # writing .value would otherwise re-fire on_comma_change
            cb = editor.state.comma_basis
            for k, comma in enumerate(cb):
                for i, value in enumerate(comma):
                    comma_inputs[k][i].value = str(value)
            building[0] = False
        else:
            board.refresh()

    def on_comma_change():
        if building[0]:
            return
        matrix = gather(comma_inputs)
        if matrix is None:
            return
        before = _shape(editor.state)
        editor.edit_comma_basis(matrix)
        _sync_undo()
        if _shape(editor.state) == before:  # mapping shape unchanged -> update in place
            building[0] = True  # writing .value would otherwise re-fire on_mapping_change
            for r, row in enumerate(editor.state.mapping):
                for c, value in enumerate(row):
                    mapping_inputs[r][c].value = str(value)
            building[0] = False
        else:
            board.refresh()

    def act(action):
        action()
        board.refresh()
        _sync_undo()

    @ui.refreshable
    def board():
        building[0] = True
        mapping_inputs.clear()
        comma_inputs.clear()
        state = editor.state
        d, rank, n = state.d, len(state.mapping), len(state.comma_basis)
        primes = service.standard_primes(d)

        # Row tracks: controls, margin, then a contiguous block of header + square + mapping.
        rows = ["auto", f"{_MARGIN}px"] + [f"{_TILE}px"] * (1 + d + rank)
        cols = [f"{_TILE}px"] * d + [f"{_TILE}px"] + [f"{_TILE}px"] * n
        grid = ui.element("div").classes("rtt-grid").style(
            f"grid-template-columns:{' '.join(cols)}; grid-template-rows:{' '.join(rows)};"
        )
        # 1-indexed grid lines. header row = 3; square rows = 4..3+d; mapping rows = 4+d..3+d+rank.
        header_row = 3
        square_top = 4
        mapping_top = 4 + d

        def at(el, r, c, *, col_span=1):
            el.style(f"grid-row:{r}; grid-column:{c} / span {col_span}")

        with grid:
            # domain controls: - above the last prime, + just to its right
            minus = ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                .props("unelevated dense no-caps square").classes("rtt-ctl")
            minus.set_enabled(editor.can_shrink)
            at(minus, 1, d)
            plus = ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                .props("unelevated dense no-caps square").classes("rtt-ctl")
            at(plus, 1, d + 1)

            # prime header (white cells, like the original's domain inputs)
            for i, prime in enumerate(primes):
                with ui.element("div").classes("rtt-tile").style(
                    f"grid-row:{header_row}; grid-column:{i + 1}"
                ):
                    with ui.element("div").classes("rtt-white"):
                        ui.label(str(prime)).classes("rtt-prime")

            # empty d x d shared-axis square
            for r in range(d):
                for c in range(d):
                    ui.element("div").classes("rtt-tile").style(
                        f"grid-row:{square_top + r}; grid-column:{c + 1}"
                    )

            # comma basis (commas as columns), prime-rows aligned with the square
            for k in range(n):
                col = []
                for i in range(d):
                    with ui.element("div").classes("rtt-tile").style(
                        f"grid-row:{square_top + i}; grid-column:{d + 2 + k}"
                    ):
                        cell = ui.input(
                            value=str(state.comma_basis[k][i]),
                            on_change=lambda e: on_comma_change(),
                        ).props("dense borderless").classes("rtt-cell")
                    col.append(cell)
                comma_inputs.append(col)

            # mapping (generators as rows), columns aligned with the header
            for r in range(rank):
                row_cells = []
                for c in range(d):
                    with ui.element("div").classes("rtt-tile").style(
                        f"grid-row:{mapping_top + r}; grid-column:{c + 1}"
                    ):
                        cell = ui.input(
                            value=str(state.mapping[r][c]),
                            on_change=lambda e: on_mapping_change(),
                        ).props("dense borderless").classes("rtt-cell")
                    row_cells.append(cell)
                mapping_inputs.append(row_cells)

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
