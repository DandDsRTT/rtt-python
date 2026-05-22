"""NiceGUI front end for the RTT monolith.

The layout is a coordinate space (:mod:`rtt.web.layout`) of first-class line,
block and cell entities with stable ids. The renderer is *persistent and
reconciling*: it keeps one element per entity id and, on every state change,
moves/updates the survivors and adds/removes the rest — never a full rebuild.
With CSS transitions, expanding or shrinking the domain animates (axes slide,
new ones fade in) instead of popping. Editing recomputes the dual in-process;
no HTTP layer.
"""

from __future__ import annotations

from nicegui import ui

from rtt.web import layout, service
from rtt.web.editor import Editor

_PAD = 10  # px margin of #c0c0c0 around the coordinate space
_T = "0.25s"  # transition duration

_CSS = f"""
.rtt-title {{ font-family:'Cambria',Georgia,serif; font-size:30px; font-weight:bold;
             color:#000; margin:6px 0 8px 2px; }}
.rtt-undo {{ width:100px !important; height:22px !important; min-height:22px !important;
            background:#fff !important; border:1px solid #888 !important; border-radius:0 !important;
            box-shadow:none !important; padding:0 !important; margin:0 0 10px 2px; }}
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
.rtt-name {{ color:#444; font-size:11px; white-space:nowrap; }}
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
    els: dict = {}  # entity id -> outer element (persists across renders)
    inputs: dict = {}  # cell id -> the q-input element
    building = [False]
    refs: dict = {}

    def _gather(kind):
        d, count = editor.state.d, len(editor.state.mapping if kind == "mapping" else editor.state.comma_basis)
        key = (lambda i, p: f"cell:{kind}:{i}:{p}")
        matrix = [[_parse_int(inputs[key(i, p)].value) for p in range(d)] for i in range(count)]
        return None if any(v is None for row in matrix for v in row) else matrix

    def on_mapping_change():
        if building[0]:
            return
        matrix = _gather("mapping")
        if matrix is not None:
            editor.edit_mapping(matrix)
            render()

    def on_comma_change():
        if building[0]:
            return
        matrix = _gather("comma")
        if matrix is not None:
            editor.edit_comma_basis(matrix)
            render()

    def act(action):
        action()
        render()

    def _make_cell(cb):
        wrap = ui.element("div").classes("rtt-cell").props(f'data-eid="{cb.id}"')
        with wrap:
            if cb.kind in ("mapping", "comma"):
                handler = on_mapping_change if cb.kind == "mapping" else on_comma_change
                inputs[cb.id] = ui.input(on_change=lambda e, fn=handler: fn()) \
                    .props("dense borderless").classes("rtt-cellinput")
            elif cb.kind == "prime":
                with ui.element("div").classes("rtt-white"):
                    ui.label(cb.text)
            elif cb.kind == "minus":
                refs["minus"] = ui.button("-", on_click=lambda: act(editor.shrink), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "plus":
                ui.button("+", on_click=lambda: act(editor.expand), color=None) \
                    .props("unelevated dense no-caps square").classes("rtt-btn")
            elif cb.kind == "name":
                ui.label(cb.text).classes("rtt-name")
        return wrap

    def render():
        building[0] = True
        st = editor.state
        lay = layout.build_layout(st.d, len(st.mapping), len(st.comma_basis),
                                  service.standard_primes(st.d))
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
            elif cb.kind == "comma":
                inputs[cb.id].value = str(st.comma_basis[cb.comma][cb.prime])

        for eid in [e for e in els if e not in seen]:
            els[eid].delete()
            del els[eid]
            inputs.pop(eid, None)

        if "minus" in refs:
            refs["minus"].set_enabled(editor.can_shrink)
        refs["undo"].set_enabled(editor.can_undo)
        building[0] = False

    ui.label("RTT App").classes("rtt-title")
    refs["undo"] = ui.button("undo", on_click=lambda: act(editor.undo), color=None) \
        .props("no-caps unelevated square").classes("rtt-undo")
    with ui.element("div").classes("rtt-outer"):
        board = ui.element("div").classes("rtt-board")
    render()


def main() -> None:
    ui.run(title="RTT", reload=False, show=False, port=8137)


if __name__ in {"__main__", "__mp_main__"}:
    main()
