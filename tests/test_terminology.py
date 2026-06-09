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
