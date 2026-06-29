"""The alternate mapping generator forms (mingen / equave-reduced / positive-generator).

Expected values are taken verbatim from the Xen wiki "Normal lists" page (snapshotted at
``guide/other/Normal lists``) and "Generator form manipulation"."""

from rtt.library import generator_forms as gf
from rtt.library.canonicalization import canonical_ma

JIP3 = gf.standard_jip_octaves(3)
JIP4 = gf.standard_jip_octaves(4)

MEANTONE = ((1, 1, 0), (0, 1, 4))
SEPTIMAL_MEANTONE = ((1, 0, -4, -13), (0, 1, 4, 10))
PORCUPINE = ((1, 2, 3), (0, 3, 5))
SENSI = ((1, 6, 8), (0, 7, 9))
NEGRI = ((1, 2, 2), (0, 4, -3))
MYNA = ((1, 9, 9, 8), (0, 10, 9, 7))


ALL_FORMS = (gf.minimal_generator_ma, gf.equave_reduced_ma,
             gf.positive_generator_ma, gf.positive_generator_shift_ma)


class TestGeneratorForms:
    def test_mingen_matches_the_guide(self):
        assert gf.minimal_generator_ma(MEANTONE, JIP3) == ((1, 2, 4), (0, -1, -4))
        assert gf.minimal_generator_ma(SEPTIMAL_MEANTONE, JIP4) == ((1, 2, 4, 7), (0, -1, -4, -10))

    def test_equave_reduced_matches_the_guide(self):
        assert gf.equave_reduced_ma(MEANTONE, JIP3) == ((1, 1, 0), (0, 1, 4)), "meantone equave-reduced is the octave + fifth — and so equals the app default"
        assert gf.equave_reduced_ma(SEPTIMAL_MEANTONE, JIP4) == ((1, 1, 0, -3), (0, 1, 4, 10))

    def test_positive_generator_flip_matches_the_guide(self):
        assert gf.positive_generator_ma(SEPTIMAL_MEANTONE, JIP4) == SEPTIMAL_MEANTONE, "'flip': sign-change a row whose generator is negative. Septimal meantone's generators are # already positive, so positive-gen == defactored Hermite (canonical)"
        assert gf.positive_generator_ma(PORCUPINE, JIP3) == ((1, 2, 3), (0, -3, -5)), "porcupine's canonical generator is negative (~−163¢), so its row flips sign"

    def test_positive_generator_shift_matches_the_temperament_evaluator(self):

        assert gf.positive_generator_shift_ma(SEPTIMAL_MEANTONE, JIP4) == SEPTIMAL_MEANTONE, "septimal meantone's generators are already positive, so shift == flip == canonical"

        assert gf.positive_generator_shift_ma(SENSI, JIP3) == ((1, -1, -1), (0, 7, 9)), "sensi's generator is negative but NOT (c−p)-sheared, so shift differs from flip: it shifts to # the wiki's ~9/7-generator form ⟨⟨1 -1 -1] ⟨0 7 9]] rather than negating the row"
        assert gf.positive_generator_ma(SENSI, JIP3) == ((1, 6, 8), (0, -7, -9))

        assert gf.positive_generator_shift_ma(MYNA, JIP4) == ((1, -1, 0, 1), (0, 10, 9, 7)), "myna (7-limit), likewise not sheared: shift → the wiki's ⟨⟨1 -1 0 1] ⟨0 10 9 7]]"
        assert gf.positive_generator_ma(MYNA, JIP4) == ((1, 9, 9, 8), (0, -10, -9, -7))

        assert gf.positive_generator_shift_ma(PORCUPINE, JIP3) == gf.positive_generator_ma(PORCUPINE, JIP3), "porcupine and negri ARE (c−p)-sheared, so shift falls back to flip (they coincide)"
        assert gf.positive_generator_shift_ma(PORCUPINE, JIP3) == ((1, 2, 3), (0, -3, -5))
        assert gf.positive_generator_shift_ma(NEGRI, JIP3) == gf.positive_generator_ma(NEGRI, JIP3)
        assert gf.positive_generator_shift_ma(NEGRI, JIP3) == ((1, 2, 2), (0, -4, 3))

    def test_every_form_preserves_the_temperament(self):
        for matrix, jip in [(MEANTONE, JIP3), (SEPTIMAL_MEANTONE, JIP4), (PORCUPINE, JIP3),
                            (SENSI, JIP3), (NEGRI, JIP3), (MYNA, JIP4),
                            (((1, 0, 0, -5), (0, 1, 0, 2), (0, 0, 1, 2)), JIP4),
                            (((5, 8, 0), (0, 0, 1)), JIP3)]:
            canon = canonical_ma(matrix)
            for form in ALL_FORMS:
                assert canonical_ma(form(matrix, jip)) == canon, (form.__name__, matrix)

    def test_forms_are_idempotent_and_input_independent(self):
        for form in ALL_FORMS:
            once = form(MEANTONE, JIP3)
            assert form(once, JIP3) == once
            assert form(((1, 0, -4), (0, 1, 4)), JIP3) == once
            assert form(((1, 2, 4), (0, -1, -4)), JIP3) == once
