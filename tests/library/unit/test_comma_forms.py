"""The comma-basis normal forms (positive-ratio / minimal), the column-vector counterpart to
``test_generator_forms``.

Expected values are taken from the Xen wiki "Normal lists" page (snapshotted at
``guide/other/Normal lists``), "Normal forms for commas" section."""

from fractions import Fraction

from rtt.library import comma_forms as cf
from rtt.library.canonicalization import canonical_ca
from rtt.library.generator_forms import standard_jip_octaves

JIP3 = standard_jip_octaves(3)
JIP4 = standard_jip_octaves(4)

MEANTONE = ((4, -4, 1),)
SEPTIMAL_MEANTONE = ((4, -4, 1, 0), (13, -10, 0, 1))
PRIMES = (2, 3, 5, 7, 11, 13)


def _ratio(vector) -> Fraction:
    """The ratio a stored comma row represents, for asserting against the wiki's ratio lists."""
    n = d = 1
    for e, p in zip(vector, PRIMES):
        if e > 0:
            n *= p ** e
        elif e < 0:
            d *= p ** (-e)
    return Fraction(n, d)


def _ratios(matrix):
    return [_ratio(v) for v in matrix]


class TestCommaForms:
    def test_positive_ratio_matches_the_guide(self):
        assert cf.positive_ratio_ca(MEANTONE, JIP3) == ((-4, 4, -1),)
        assert _ratios(cf.positive_ratio_ca(MEANTONE, JIP3)) == [Fraction(81, 80)]
        assert _ratios(cf.positive_ratio_ca(SEPTIMAL_MEANTONE, JIP4)) == [
            Fraction(81, 80), Fraction(59049, 57344)]

    def test_minimal_matches_the_wiki_comma_lists(self):
        assert _ratios(cf.minimal_ca(MEANTONE, JIP3)) == [Fraction(81, 80)]
        assert _ratios(cf.minimal_ca(SEPTIMAL_MEANTONE, JIP4)) == [Fraction(81, 80), Fraction(126, 125)]

    def test_minimal_ca_of_a_commaless_basis_short_circuits(self):
        assert cf.minimal_ca((), JIP3) == ()
        assert cf.minimal_ca(((0, 0, 0),), JIP3) == ((0, 0, 0),)

    def test_minimal_is_simpler_than_canonical(self):
        minimal = cf.minimal_ca(SEPTIMAL_MEANTONE, JIP4)
        worst_minimal = max(cf._complexity(c, JIP4) for c in minimal)
        worst_canonical = max(cf._complexity(c, JIP4) for c in SEPTIMAL_MEANTONE)
        assert worst_minimal < worst_canonical

    def test_every_form_preserves_the_temperament(self):
        for matrix, jip in [(MEANTONE, JIP3), (SEPTIMAL_MEANTONE, JIP4),
                            (((1, -5, 3),), JIP3),
                            (((-11, 7, 0, 0), (4, -4, 1, 0)), JIP4)]:
            canonical = canonical_ca(matrix)
            for form in (cf.positive_ratio_ca, cf.minimal_ca):
                assert canonical_ca(form(matrix, jip)) == canonical, (form.__name__, matrix)

    def test_forms_are_idempotent_and_input_independent(self):
        for form in (cf.positive_ratio_ca, cf.minimal_ca):
            once = form(SEPTIMAL_MEANTONE, JIP4)
            assert form(once, JIP4) == once
            assert form(((4, -4, 1, 0), (17, -14, 1, 1)), JIP4) == once
