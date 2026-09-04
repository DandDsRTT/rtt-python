from rtt.app import preview_engine as pe
from rtt.app import service
from rtt.app.editor import Editor
from rtt.app.grid_tables import RINGABLE_KINDS


def _ed(mapping, *, projection=False):
    ed = Editor()
    ed.apply_state(service.from_mapping(mapping))
    ed.set_all_show(True)
    ed.settings["preview_highlighting"] = True
    if projection:
        ed.settings["nonstandard_domain"] = False
        ed.set_established_projection("1/4-comma")
    return ed


def _tiles(ids):
    return {":".join(i.split(":")[:-2]) for i in ids if i.startswith("cell:")}


class TestDraftRingsComma:
    def test_comma_draft_reds_the_form_matrices_and_detempering(self):
        ed = _ed(((1, 1, 0), (0, 1, 4)), projection=True)
        ed.add_comma()
        ed.set_pending_comma([None, None, None])
        layout = ed.layout()
        _green, _amber, red = pe.draft_rings(ed, layout, RINGABLE_KINDS)
        reds = _tiles(red)
        for t in ("cell:form", "cell:inverse_form", "cell:vector:detempering"):
            assert t in reds, f"{t} should go red (2x2 -> 1x1) on a comma draft"

    def test_no_draft_gives_no_rings(self):
        ed = _ed(((1, 1, 0), (0, 1, 4)))
        assert pe.draft_rings(ed, ed.layout(), RINGABLE_KINDS) == pe.NO_RINGS

    def test_row_headers_never_go_red_on_a_comma_draft(self):
        ed = _ed(((1, 1, 0), (0, 1, 4)))
        ed.add_comma()
        ed.set_pending_comma([None, None, None])
        layout = ed.layout()
        kinds = {c.id: c.kind for c in layout.cells}
        _green, _amber, red = pe.draft_rings(ed, layout, RINGABLE_KINDS)
        assert all(kinds.get(i) in RINGABLE_KINDS for i in red)


class TestDraftRingsPrescaling:
    def test_full_rank_temperament_with_prescaling_band_renders(self):
        ed = _ed(((1, 0, 0), (0, 1, 0), (0, 0, 1)))
        ed.set_tuning_scheme("minimax-S")
        assert ed.layout().cells, "full-rank comma_basis carries a phantom zero vector; the prescaling band must not overrun its 0 comma columns"

    def test_rank_increasing_draft_with_prescaling_band_computes_rings(self):
        ed = _ed(((1, 1, 0), (0, 1, 4)))
        ed.set_tuning_scheme("minimax-S")
        ed.add_mapping_row()
        ed.set_pending_mapping_row([None, None, None])
        pe.draft_rings(ed, ed.layout(), RINGABLE_KINDS)
