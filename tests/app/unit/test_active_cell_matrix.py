from rtt.app import service, settings, spreadsheet, tooltips
from rtt.app.service.text_conventions import EBK_CONVENTIONS, matrix_orient


def _all_on_cells():
    s = settings.defaults()
    for key in settings.IMPLEMENTED:
        s[key] = True
    return spreadsheet.build(service.from_mapping(((1, 1, 0), (0, 1, 4))), s).cells


def _stamped():
    return {c.matrix: c.matrix_orient for c in _all_on_cells() if c.matrix}


class TestActiveCellMatrix:
    def test_core_matrices_carry_their_ebk_block_identity(self):
        stamped = _stamped()
        assert stamped["mapping:primes"] == "row"
        assert stamped["vectors:commas"] == "col"
        assert stamped["projection:primes"] == "row"

    def test_identity_matrices_like_the_ji_mapping_are_stamped_when_shown(self):
        stamped = {c.matrix for c in _all_on_cells() if c.matrix}
        assert "vectors:primes" in stamped
        ji_cells = [c for c in _all_on_cells() if c.matrix == "vectors:primes"]
        assert len(ji_cells) >= 4

    def test_the_basis_listing_is_not_a_matrix(self):
        assert all(not c.matrix for c in _all_on_cells() if c.id.startswith("basis:"))

    def test_orientation_is_the_ebk_structure_not_the_emit_loop_order(self):
        assert _stamped()["projection:generators"] == "col"

    def test_every_stamped_matrix_matches_its_ebk_convention(self):
        for mx, orient in _stamped().items():
            row_key, column_key = mx.split(":", 1)
            assert (row_key, column_key) in EBK_CONVENTIONS, mx
            assert orient == matrix_orient(row_key, column_key), mx

    def test_matrix_orient_maps_list_to_col_and_row_stack_to_row(self):
        assert matrix_orient("vectors", "commas") == "col"
        assert matrix_orient("mapping", "primes") == "row"
        assert matrix_orient("tuning", "primes") == "row"

    def test_prescaling_primes_orientation_depends_on_the_superspace_flag(self):
        assert matrix_orient("prescaling", "primes") == "row"
        assert matrix_orient("prescaling", "primes", superspace=True) == "col"

    def test_value_cells_in_linked_tiles_carry_the_tile_guide_key(self):
        keyed = {c.guide_key for c in _all_on_cells() if c.guide_key is not None}
        assert ("mapping", "primes") in keyed, "a mapping-matrix value cell should point at its # guide tile so hovering the number, not just the caption, offers the deep dive"
        assert ("tuning", "generators") in keyed

    def test_guide_keys_only_name_tiles_that_actually_link_out(self):
        for c in _all_on_cells():
            if c.guide_key is not None:
                gh = tooltips.GUIDE_HELP.get(c.guide_key)
                assert gh is not None and gh.url, f"{c.id} stamped guide_key {c.guide_key} with no guide link"
