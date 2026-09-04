from rtt.library.formatting import to_ebk
from rtt.library.generator_detempering import (
    get_generator_detempering,
    get_generator_preimages,
    maps_to_the_generator,
)
from rtt.library.parsing import parse_temperament_data
from rtt.library.temperament import Temperament, Variance

ROW, COL = Variance.ROW, Variance.COL
MEANTONE = Temperament(((1, 1, 0), (0, 1, 4)), ROW)
TWELVE = Temperament(((12, 19, 28),), ROW)


class TestGeneratorDetempering:
    def test_generator_detempering_mapping(self):
        t = Temperament(((1, 1, 0), (0, 1, 4)), ROW)
        assert get_generator_detempering(t) == Temperament(((1, 0, 0), (-1, 1, 0)), COL)

    def test_generator_detempering_comma_basis(self):
        t = Temperament(((4, -4, 1),), COL)
        assert get_generator_detempering(t) == Temperament(((1, 0, 0), (0, 1, 0)), COL)

    def test_generator_detempering_through_ebk(self):
        t = parse_temperament_data("[⟨1 1 0] ⟨0 1 4]⧽")
        assert to_ebk(get_generator_detempering(t)) == "[[1 0 0⟩ [-1 1 0⟩]"


class TestMapsToTheGenerator:
    def test_the_detemperings_own_vectors_map_to_their_generators(self):
        detempering = get_generator_detempering(MEANTONE).matrix
        assert all(maps_to_the_generator(MEANTONE.matrix, i, v) for i, v in enumerate(detempering))

    def test_a_vector_off_by_a_comma_still_maps_to_the_generator(self):
        assert maps_to_the_generator(MEANTONE.matrix, 1, (3, -3, 1))

    def test_a_vector_mapping_to_two_generators_at_once_does_not(self):
        assert not maps_to_the_generator(MEANTONE.matrix, 1, (0, 1, 0))

    def test_a_vector_mapping_to_the_other_generator_does_not(self):
        assert not maps_to_the_generator(MEANTONE.matrix, 1, (1, 0, 0))

    def test_a_vector_from_another_domain_does_not(self):
        assert not maps_to_the_generator(MEANTONE.matrix, 1, (-1, 1, 0, 0))

    def test_no_vector_maps_to_a_generator_that_is_not_there(self):
        assert not maps_to_the_generator(MEANTONE.matrix, 2, (-1, 1, 0))


class TestGeneratorPreimages:
    def test_preimages_start_at_the_simplest_and_all_map_to_the_generator(self):
        preimages = get_generator_preimages(MEANTONE, 1)
        assert preimages[0] == (-1, 1, 0)
        assert all(maps_to_the_generator(MEANTONE.matrix, 1, v) for v in preimages)

    def test_preimages_ascend_in_product_complexity(self):
        preimages = get_generator_preimages(TWELVE, 0)
        assert preimages[:3] == ((4, -1, -1), (-3, -1, 2), (-7, 3, 1))

    def test_preimages_are_distinct_and_capped_at_the_requested_count(self):
        preimages = get_generator_preimages(TWELVE, 0, count=5)
        assert len(preimages) == len(set(preimages)) == 5

    def test_a_rank_equals_dimensionality_temperament_has_one_preimage(self):
        just = Temperament(((1, 0, 0), (0, 1, 0), (0, 0, 1)), ROW)
        assert get_generator_preimages(just, 0) == ((1, 0, 0),)

    def test_a_comma_basis_is_read_as_its_dual_mapping(self):
        assert get_generator_preimages(Temperament(((4, -4, 1),), COL), 1)[0] == (0, 1, 0)
