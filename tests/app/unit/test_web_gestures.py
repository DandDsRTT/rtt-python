from types import SimpleNamespace

from rtt.app import _gesture_ops, _gesture_reorder
from rtt.app.gestures import GestureController
from rtt.app.page_assets import _Gesture


def _cell(cell_id, *, remove=False, change=False, pending=False):
    return SimpleNamespace(id=cell_id, preview_remove=remove, preview_change=change, pending=pending)


def _editor(*, highlight=True):
    return SimpleNamespace(
        settings={"preview_highlighting": highlight},
        restore_for_preview=lambda token: None,
    )


class _RecordingEditor:
    def __init__(self):
        self.restores = []

    settings = {"preview_highlighting": True}

    def restore_for_preview(self, token):
        self.restores.append(token)


class _FakeEl:
    def __init__(self):
        self.added = []
        self.removed = []

    def classes(self, add="", remove=""):
        if add:
            self.added.append(add)
        if remove:
            self.removed.append(remove)
        return self


class _FakeEntity:
    def __init__(self, element):
        self.element = element
        self.ring_sig = None


class _FakeRec:
    def __init__(self, entities):
        self.entities = entities

    def entity(self, element_id):
        return self.entities[element_id]


class TestWebGestures:
    def test_gesture_controller_constructs_without_a_page(self):
        g = GestureController(_editor(), SimpleNamespace())
        assert g.gesture is None
        assert g.drag_src is None

    def test_bind_wires_the_sibling_controllers_after_construction(self):
        g = GestureController(_editor(), SimpleNamespace())
        reconciler, renderer, edits = object(), object(), object()
        g.bind(reconciler, renderer, edits)
        assert g._rec is reconciler
        assert g._renderer is renderer
        assert g._edits is edits

    def test_compute_rings_static_only_when_no_gesture(self):
        g = GestureController(_editor(), SimpleNamespace())
        layout = SimpleNamespace(
            cells=[
                _cell("a", remove=True),
                _cell("b", change=True),
                _cell("c", pending=True),
                _cell("d", change=True, pending=True),
            ]
        )
        amber, red = g.compute_rings(layout)
        assert amber == frozenset({"b"})
        assert red == frozenset({"a"})

    def test_compute_rings_empty_when_preview_highlighting_off(self):
        g = GestureController(_editor(highlight=False), SimpleNamespace())
        layout = SimpleNamespace(cells=[_cell("a", remove=True)])
        assert g.compute_rings(layout) == (frozenset(), frozenset())

    def test_paint_cell_adds_amber_ring_and_records_signature(self):
        element = _FakeEl()
        reconciler = _FakeRec({"x": _FakeEntity(element)})
        g = GestureController(_editor(), SimpleNamespace())
        g.bind(reconciler, None, None)
        g.paint_cell("x", frozenset({"x"}), frozenset())
        assert "rtt-preview-change" in element.added
        assert reconciler.entities["x"].ring_sig == (True, False)

    def test_paint_cell_is_a_noop_when_signature_unchanged(self):
        element = _FakeEl()
        ent = _FakeEntity(element)
        ent.ring_sig = (True, False)
        g = GestureController(_editor(), SimpleNamespace())
        g.bind(_FakeRec({"x": ent}), None, None)
        g.paint_cell("x", frozenset({"x"}), frozenset())
        assert element.added == []

    def test_paint_cell_skips_missing_element(self):
        ent = _FakeEntity(None)
        g = GestureController(_editor(), SimpleNamespace())
        g.bind(_FakeRec({"x": ent}), None, None)
        g.paint_cell("x", frozenset({"x"}), frozenset())
        assert ent.ring_sig is None

    def test_end_gesture_restores_preview_token(self):
        ed = _RecordingEditor()
        g = GestureController(ed, SimpleNamespace())
        g.gesture = _Gesture(kind="drag", token=("snapshot",))
        was = g.end_gesture()
        assert g.gesture is None
        assert was.kind == "drag"
        assert ed.restores == [("snapshot",)]

    def test_gesture_render_toggles_flag_and_calls_render(self):
        rendered = []
        renderer = SimpleNamespace(render=lambda: rendered.append(True))
        g = GestureController(_editor(), SimpleNamespace())
        g.bind(None, renderer, None)
        _gesture_ops.gesture_render(g)
        assert rendered == [True]
        assert g.gesture_rendering is False

    def test_end_commit_gestures_ends_transient_gesture_and_clears_rank(self):
        ed = _RecordingEditor()
        g = GestureController(ed, SimpleNamespace())
        g.gesture = _Gesture(kind="hover")
        g.rank_remove = ("row", 2)
        g.end_commit_gestures()
        assert g.gesture is None
        assert g.rank_remove is None


class _DragEditor:
    settings = {"preview_highlighting": True}

    def __init__(self):
        self.moves = []

    def capture_for_preview(self):
        return ("token",)

    def restore_for_preview(self, token):
        pass

    def move_column(self, src, dst):
        self.moves.append(("column", src, dst))
        return src != dst

    def move_row(self, src, dst):
        self.moves.append(("row", src, dst))
        return src != dst

    def move_interval(self, src_list, src_idx, dst_list, dst_idx):
        self.moves.append(("interval", src_list, src_idx, dst_list, dst_idx))
        return (src_list, src_idx) != (dst_list, dst_idx)


def _drag_controller():
    ed = _DragEditor()
    renders = []
    runtime = SimpleNamespace(last_lay=None)
    g = GestureController(ed, runtime)
    g.bind(None, SimpleNamespace(render=lambda: renders.append(True)), None)
    return g, ed, renders


class TestBandDragRelease:
    def test_dropping_a_band_in_a_gap_commits_insert_before_that_gaps_key(self):
        g, ed, renders = _drag_controller()
        _gesture_reorder.on_band_drag_start(g, "column", "commas")
        _gesture_reorder.on_band_drop(g, "column", "primes")
        assert ("column", "commas", "primes") in ed.moves
        assert renders and g.drag_src is None

    def test_dropping_in_the_end_gap_appends(self):
        g, ed, _ = _drag_controller()
        _gesture_reorder.on_band_drag_start(g, "row", "mapping")
        _gesture_reorder.on_band_drop(g, "row", "")
        assert ("row", "mapping", None) in ed.moves

    def test_a_band_drag_does_not_reflow_the_grid_until_release(self):
        g, ed, renders = _drag_controller()
        _gesture_reorder.on_band_drag_start(g, "column", "commas")
        assert ed.moves == [] and renders == []

    def test_releasing_a_band_without_a_drop_reverts_and_commits_nothing(self):
        g, ed, _ = _drag_controller()
        _gesture_reorder.on_band_drag_start(g, "column", "commas")
        _gesture_reorder.on_band_drag_end(g)
        assert ed.moves == []
        assert g.drag_src is None and g.gesture is None

    def test_a_drop_commits_and_the_trailing_dragend_does_not_double(self):
        g, ed, _ = _drag_controller()
        _gesture_reorder.on_band_drag_start(g, "row", "mapping")
        _gesture_reorder.on_band_drop(g, "row", "vectors")
        after_drop = len(ed.moves)
        _gesture_reorder.on_band_drag_end(g)
        assert len(ed.moves) == after_drop, "dragend re-committed after a real drop"

    def test_end_commit_gestures_leaves_an_edit_gesture_alone(self):
        g = GestureController(_RecordingEditor(), SimpleNamespace())
        g.gesture = _Gesture(kind="edit", source="x")
        g.end_commit_gestures()
        assert g.gesture is not None and g.gesture.kind == "edit"
