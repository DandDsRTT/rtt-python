import json

from rtt.app.service.notation import spell_monzo
from rtt.app.service.pump import pump_payload

_J5 = (1200.0, 1901.955, 2786.3137)
_T5 = (1200.0, 1896.578, 2786.312)
_J7 = (1200.0, 1901.955, 2786.3137, 3368.8259)
_T7 = (1200.0, 1901.955, 2786.3137, 3355.0311)
_PORCUPINE_T = (1200.0, 1920.0, 2800.0)

_PAO_DN = "accSagittal5CommaDown"
_PAO_UP = "accSagittal5CommaUp"
_TAO_DN = "accSagittal7CommaDown"
_VAI_UP = "accSagittal11MediumDiesisUp"
_DAO_DN = "accSagittal35LargeDiesisDown"


def _score(comma, jmap, tmap, basis):
    payload = pump_payload(comma, jmap, tmap, domain_basis=basis)
    return json.loads(payload).get("score") if payload else None


class TestSpellMonzo:
    def test_unison_is_bare_middle_c(self):
        assert spell_monzo((0, 0, 0)) == {"p": "c/4", "s": 0, "g": ()}

    def test_pythagorean_spellings_walk_the_chain_of_fifths(self):
        assert spell_monzo((2, -1)) == {"p": "f/4", "s": 0, "g": ()}
        assert spell_monzo((-1, 1)) == {"p": "g/4", "s": 0, "g": ()}
        assert spell_monzo((3, -2)) == {"p": "b/3", "s": -1, "g": ()}
        assert spell_monzo((-9, 6)) == {"p": "f/4", "s": 1, "g": ()}

    def test_octaves_move_the_octave_number_only(self):
        assert spell_monzo((1, 0, 0)) == {"p": "c/5", "s": 0, "g": ()}
        assert spell_monzo((-2,)) == {"p": "c/2", "s": 0, "g": ()}

    def test_prime_5_is_pao_down_on_the_pythagorean_third(self):
        assert spell_monzo((-2, 0, 1)) == {"p": "e/4", "s": 0, "g": (_PAO_DN,)}

    def test_prime_7_is_tao_down_on_the_pythagorean_minor_seventh(self):
        assert spell_monzo((-2, 0, 0, 1)) == {"p": "b/4", "s": -1, "g": (_TAO_DN,)}

    def test_prime_11_is_vai_up_on_the_fourth(self):
        assert spell_monzo((-3, 0, 0, 0, 1)) == {"p": "f/4", "s": 0, "g": (_VAI_UP,)}

    def test_prime_13_is_dao_down_on_the_pythagorean_sixth(self):
        assert spell_monzo((-3, 0, 0, 0, 0, 1)) == {"p": "a/4", "s": 0, "g": (_DAO_DN,)}

    def test_subharmonic_factors_flip_the_symbol(self):
        assert spell_monzo((1, 1, -1)) == {"p": "e/4", "s": -1, "g": (_PAO_UP,)}

    def test_powers_repeat_the_symbol_once_per_factor(self):
        assert spell_monzo((-5, 1, 2))["g"] == (_PAO_DN, _PAO_DN)

    def test_stacks_order_smallest_alteration_first_largest_nearest_the_notehead(self):
        stacked = spell_monzo((-7, 1, 1, 1, 0, 1))
        assert stacked["g"] == (_PAO_DN, _TAO_DN, _DAO_DN)

    def test_triple_sharps_and_beyond_are_unsupported(self):
        assert spell_monzo((-31, 20)) is None
        assert spell_monzo((33, -21)) is None

    def test_primes_beyond_37_are_unsupported(self):
        assert spell_monzo((0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1)) is None
        assert spell_monzo((0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)) is not None


class TestPumpScore:
    def test_meantone_pump_notates_the_I_vi_ii_V_just_triads(self):
        score = _score([-4, 4, -1], _J5, _T5, (2, 3, 5))
        assert score["comma"] == "81/80"
        assert [s["r"] for s in score["steps"]] == ["1/1", "5/3", "10/9", "40/27"]
        tonic = score["steps"][0]["tones"]["mixed"]
        assert [t["p"] for t in tonic] == ["c/4", "e/4", "g/4", "c/5"]
        assert tonic[1]["g"] == [_PAO_DN], "the just major third rides a pao down"
        five = score["steps"][3]["tones"]["mixed"]
        assert five[0] == {"p": "g/4", "s": 0, "g": [_PAO_DN]}, "the V chord's root is the wolf-avoiding 40/27, one comma down"
        assert five[1]["g"] == [_PAO_DN, _PAO_DN], "its major third stacks two paos down"

    def test_meantone_moves_label_every_transition_and_the_wrap_home(self):
        score = _score([-4, 4, -1], _J5, _T5, (2, 3, 5))
        assert score["moves"] == ["5/3", "2/3", "4/3", "2/3"]
        assert len(score["moves"]) == len(score["steps"])

    def test_fixed_chord_types_are_spelled_per_root(self):
        score = _score([-4, 4, -1], _J5, _T5, (2, 3, 5))
        major_on_vi = score["steps"][1]["tones"]["major"]
        assert major_on_vi[1] == {"p": "c/5", "s": 1, "g": [_PAO_DN, _PAO_DN]}, "A-major's third is C sharp two commas down"
        assert set(score["steps"][0]["tones"]) >= {"mixed", "major", "minor", "fifth", "dominant seventh"}

    def test_porcupine_pump_scores_with_its_own_progression(self):
        score = _score([1, -5, 3], _J5, _PORCUPINE_T, (2, 3, 5))
        assert score["comma"] == "250/243"
        assert score["moves"][-1] == "2/3", "the wrap home is down a fifth"
        assert len(score["steps"]) == len(score["moves"]) == 7

    def test_starling_pump_scores_with_a_septimal_top(self):
        score = _score([1, 2, -3, 1], _J7, _T7, (2, 3, 5, 7))
        assert score is not None
        tops = [s["tones"]["mixed"][3] for s in score["steps"]]
        assert all(t["g"] and t["g"][-1] == _TAO_DN for t in tops), "every mixed chord tops with the harmonic seventh, a tao down"

    def test_nonoctave_equave_domains_get_no_score(self):
        payload = pump_payload([1, -5, 3], (1901.955, 2786.3137, 3368.8259), (1901.955, 2790.0, 3369.0), domain_basis=(3, 5, 7))
        assert payload == "" or "score" not in json.loads(payload)

    def test_domains_with_primes_beyond_37_get_no_score(self):
        payload = pump_payload([-4, 4, -1], _J5, _T5, domain_basis=(2, 3, 41))
        assert payload == "" or "score" not in json.loads(payload)


class TestPumpPayloadScore:
    def test_payload_carries_the_score_when_a_domain_basis_is_given(self):
        d = json.loads(pump_payload([-4, 4, -1], _J5, _T5, domain_basis=(2, 3, 5)))
        assert d["score"]["comma"] == "81/80"
        assert len(d["score"]["steps"]) == len(d["t"])

    def test_payload_omits_the_score_without_a_domain_basis(self):
        assert "score" not in json.loads(pump_payload([-4, 4, -1], _J5, _T5))
