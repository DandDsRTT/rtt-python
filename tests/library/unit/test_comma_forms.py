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

# commas stored as rows (each tuple element is one comma's prime-count vector)
MEANTONE = ((4, -4, 1),)                          # canonical [⟨4 -4 1⟩] = 80/81 (downward)
SEPTIMAL_MEANTONE = ((4, -4, 1, 0), (13, -10, 0, 1))   # canonical [80/81, 57344/59049]
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


def test_positive_ratio_matches_the_guide():
    # the guide's worked example: meantone's canonical comma 80/81 (downward) flips to 81/80
    assert cf.positive_ratio_ca(MEANTONE, JIP3) == ((-4, 4, -1),)
    assert _ratios(cf.positive_ratio_ca(MEANTONE, JIP3)) == [Fraction(81, 80)]
    # "The positive ratio form of septimal meantone is [81/80, 59049/57344]."
    assert _ratios(cf.positive_ratio_ca(SEPTIMAL_MEANTONE, JIP4)) == [
        Fraction(81, 80), Fraction(59049, 57344)]


def test_minimal_matches_the_wiki_comma_lists():
    # a single comma is already minimal — just made positive in pitch
    assert _ratios(cf.minimal_ca(MEANTONE, JIP3)) == [Fraction(81, 80)]
    # septimal meantone's wiki comma list is [81/80, 126/125], simpler than the canonical
    # [81/80, 57344/59049] — LLL alone would pick the L2-shorter 225/224, but the log-product
    # (L1) minimum is 126/125
    assert _ratios(cf.minimal_ca(SEPTIMAL_MEANTONE, JIP4)) == [Fraction(81, 80), Fraction(126, 125)]


def test_minimal_is_simpler_than_canonical():
    # the whole point of the minimal form: no comma is more complex than the canonical's
    minimal = cf.minimal_ca(SEPTIMAL_MEANTONE, JIP4)
    worst_minimal = max(cf._complexity(c, JIP4) for c in minimal)
    worst_canonical = max(cf._complexity(c, JIP4) for c in SEPTIMAL_MEANTONE)
    assert worst_minimal < worst_canonical


def test_every_form_preserves_the_temperament():
    # a form is only a re-expression: it must canonicalize back to the same comma basis
    for matrix, jip in [(MEANTONE, JIP3), (SEPTIMAL_MEANTONE, JIP4),
                        (((1, -5, 3),), JIP3),                       # porcupine 250/243
                        (((-11, 7, 0, 0), (4, -4, 1, 0)), JIP4)]:    # 2-comma, 7-limit
        canon = canonical_ca(matrix)
        for form in (cf.positive_ratio_ca, cf.minimal_ca):
            assert canonical_ca(form(matrix, jip)) == canon, (form.__name__, matrix)


def test_forms_are_idempotent_and_input_independent():
    # a form of a form is itself; and equivalent inputs (same canonical) give the same form
    for form in (cf.positive_ratio_ca, cf.minimal_ca):
        once = form(SEPTIMAL_MEANTONE, JIP4)
        assert form(once, JIP4) == once                                  # idempotent
        # a non-canonical but equivalent basis (second comma replaced by a combination) → same form
        assert form(((4, -4, 1, 0), (17, -14, 1, 1)), JIP4) == once
