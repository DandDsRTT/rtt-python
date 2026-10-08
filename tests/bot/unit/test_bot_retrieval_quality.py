from pathlib import Path

from rtt.bot.corpus import GuideCorpus
from rtt.bot.search import SearchIndex

INDEX = SearchIndex(GuideCorpus.load(Path(__file__).resolve().parents[3] / "guide"))
TOP = 8

QUESTIONS = {
    "What is a mapping in regular temperament theory?": ("2. Mappings > Mappings", "1. Introductions > Dave > Dave's brief introduction to RTT"),
    "How do I find the commas that a temperament tempers out?": ("4. Exploring temperaments > Duality, nullspace, commas, bases, canonicalization", "2. Mappings > Maps > Making commas vanish"),
    "What is the systematic name for TE tuning?": ("10. Conventions for names, variables, units, and notations > Intermediate > Tuning schemes", "10. Conventions for names, variables, units, and notations > Advanced > Tuning schemes", "7. All-interval tuning schemes > Concepts > Example all-interval tuning schemes > Minimax-ES"),
    "How are held-intervals different from destretching?": ("3. Tuning fundamentals > Held-intervals > Destretching vs. holding",),
    "What does defactoring mean, and what is enfactoring?": ("Defactoring terminology proposal", "Defactoring algorithms", "Saturation, torsion, and contorsion", "Pathology of enfactoring"),
    "How do I read extended bra-ket notation like [<12 19 28], <7 11 16]}?": ("Extended bra–ket notation",),
    "How do I compute the optimal tuning of a temperament like meantone?": ("6. Tuning computation", "Generator embedding optimization"),
    "What is the TILT?": ("3. Tuning fundamentals > Target-intervals > Truncated integer limit triangle (TILT)",),
    "What is a projection matrix?": ("Projection",),
    "What does temperament addition do?": ("Temperament addition",),
    "What do warts like 17c mean in ET names?": ("2. Mappings > Maps > A multitude of maps",),
    "What is a patent val?": ("Uniform map",),
    "Why do we weight damage by the simplicity of the interval?": ("3. Tuning fundamentals > Damage > Weight slope", "7. All-interval tuning schemes > Concepts > The two conditions > Condition two: Simplicity-weighting"),
    "How do I tune a temperament on a subgroup like 2.3.7?": ("9. Tuning in nonstandard domains", "Domain basis > Nonstandard domains"),
    "What's the difference between minimax and miniRMS tunings?": ("3. Tuning fundamentals > Optimization > The problem > Rationales for choosing your interpretation", "3. Tuning fundamentals > Tuning > Systematic tuning scheme names > Optimization"),
}


def _rank(question):
    hits = [h.section.identifier for h in INDEX.search(question, limit=TOP)]
    accepted = QUESTIONS[question]
    answers = (i for i, identifier in enumerate(hits, 1) if identifier in accepted or identifier.startswith(tuple(a + " > " for a in accepted)))
    return next(answers, 0), hits


class TestCommunityQuestionsReachTheirSections:
    def test_every_question_surfaces_an_answering_section_in_the_top_results(self):
        misses = {q: hits for q in QUESTIONS for rank, hits in [_rank(q)] if rank == 0}
        assert not misses, misses

    def test_most_questions_surface_one_in_the_top_three(self):
        ranks = {q: _rank(q)[0] for q in QUESTIONS}
        assert sum(1 for r in ranks.values() if 0 < r <= 3) >= 11, ranks
