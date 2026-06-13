"""Guard against non-D&D jargon creeping back into the codebase.

Cleaning up terminology is half the point of D&D's guide, so the code uses
descriptive names — "(prime-count) vector", "map", "multivector" — rather than the
xenharmonic jargon "monzo", "val", "wedgie", "breed". This test fails if a disavowed
term reappears in the Python sources, so a slip is caught by the normal test run
instead of being noticed by hand later (it has slipped back in more than once).

Two matching styles, both case-insensitive:

* "monzo" and "wedgie" are matched as bare SUBSTRINGS. That is safe only because their
  letters never occur inside an ordinary English/code word, so the same pattern also
  catches "monzos"/"eigenmonzo"/"wedgies" with no false positives.

* "val" and "breed" need WHOLE-WORD matching (``\\bvals?\\b``, ``\\bbreeds?\\b``): a
  naive substring ban drowns in false positives — "val" hides inside value/eval/
  interval/valid/retrieval, "breed" inside the surname Breed. Word boundaries match
  only the standalone jargon (singular or plural) and skip all of those. The old
  "vals" = "values" abbreviation has been reworded to "values" throughout, so a bare
  "vals" now means only the jargon; don't reintroduce it as a shorthand or this guard
  will flag it.

The one sanctioned exception is ``rtt/temperament.py``: its interval parser still
*accepts* the legacy words "monzo"/"monzos" and "val"/"vals" as input aliases
(tolerated, not endorsed — see the comment there), so that file is whitelisted for
those terms.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("rtt", "tests")

# disavowed term (used directly as the search regex) -> repo-relative paths allowed to
# contain it (the documented aliases). "monzo"/"wedgie" are bare substrings — none of
# their letters fall inside an ordinary word, so they also catch "monzos"/"wedgies".
# "val"/"breed" carry \b word boundaries so they match only the standalone jargon, not
# value/eval/interval/valid/Breed/etc. Add new unambiguous terms here.
BANNED = {
    "monzo": {"rtt/temperament.py"},
    "wedgie": set(),
    r"\bvals?\b": {"rtt/temperament.py"},
    r"\bbreeds?\b": set(),
}


def _python_files():
    for d in SCAN_DIRS:
        yield from (ROOT / d).rglob("*.py")
    yield from ROOT.glob("*.py")


def test_no_disavowed_jargon_in_sources():
    this_file = Path(__file__).resolve()
    violations = []
    for path in _python_files():
        if path.resolve() == this_file:
            continue  # this guard necessarily names the banned terms in its own literals
        rel = path.relative_to(ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for term, allowed in BANNED.items():
                if rel not in allowed and re.search(term, line, re.IGNORECASE):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
    assert not violations, (
        "Disavowed (non-D&D) jargon found in the codebase. Use the descriptive D&D term "
        "instead — '(prime-count) vector' not 'monzo', 'map' not 'val', 'multivector' not "
        "'wedgie'/'breed':\n  " + "\n  ".join(violations)
    )


# --- Non-systematic tuning-scheme names ----------------------------------------------------------
#
# D&D's guide names every tuning scheme systematically (minimax-S, held-octave minimax-ES,
# minimax-sopfr-S, …). The historical / community names (TOP, TE, CTE, POTE, BOP, Weil, Kees,
# Frobenius, Tenney, …) are banned in this codebase — they used to live in a translation table in
# tuning_scheme_names.py, which has been removed so those names no longer resolve. This guard fails
# if any reappears in the library/app source, so a regression is caught by the normal test run.
#
# REPO_ROOT is computed correctly here (three parents up: unit -> library -> tests -> repo) so the
# scan actually reaches rtt/.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Banned scheme-name tokens. Spelled-out names are matched case-insensitively as substrings (their
# letters never occur inside an ordinary English/code word). The distinctive uppercase acronyms are
# matched as whole words, case-SENSITIVELY, so they catch the scheme name without flagging ordinary
# prose. The two-letter acronyms (TE/BE/WE/KE) and bare "TOP" are deliberately omitted: they false-
# positive too easily (TOP = "top of", BE = "must BE") — the distinctive tokens below plus
# test_tuning_scheme_names.test_non_systematic_scheme_names_are_rejected cover the ban. "least
# squares" is NOT banned: it is pervasive, legitimate linear-algebra terminology (the pseudoinverse
# least-squares factor), unrelated to the tuning scheme of that old name.
BANNED_SCHEME_NAME_PATTERNS = (
    re.compile(r"tenney", re.IGNORECASE),
    re.compile(r"benedetti", re.IGNORECASE),
    re.compile(r"frobenius", re.IGNORECASE),
    re.compile(r"weil", re.IGNORECASE),
    re.compile(r"kees", re.IGNORECASE),
    re.compile(r"\bTIPTOP\b"),
    re.compile(r"\bTOP-max\b"),
    re.compile(r"\bTOP-RMS\b"),
    re.compile(r"\bCTE\b"),
    re.compile(r"\bCWE\b"),
    re.compile(r"\bBOP\b"),
    re.compile(r"\bWOP\b"),
    re.compile(r"\bKOP\b"),
    re.compile(r"\bPOTE\b"),
    re.compile(r"\bPOTOP\b"),
    re.compile(r"\bPOTT\b"),
    re.compile(r"\bPOWE\b"),
    re.compile(r"\bPOWOP\b"),
)


def test_no_non_systematic_scheme_names_in_rtt_sources():
    violations = []
    for path in (REPO_ROOT / "rtt").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern in BANNED_SCHEME_NAME_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{lineno}: {line.strip()}")
    assert not violations, (
        "Non-systematic / historical / community tuning-scheme names found in rtt/ source. Use "
        "only D&D's systematic names (minimax-S, held-octave minimax-ES, minimax-sopfr-S, …):\n  "
        + "\n  ".join(violations)
    )
