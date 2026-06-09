"""Guard against non-D&D jargon creeping back into the codebase.

Cleaning up terminology is half the point of D&D's guide, so the code uses
descriptive names — "(prime-count) vector", "map", "multivector" — rather than the
xenharmonic jargon "monzo", "val", "wedgie". This test fails if a disavowed term
reappears in the Python sources, so a slip is caught by the normal test run instead
of being noticed by hand later (it has slipped back in more than once).

Only UNAMBIGUOUS jargon is enforced here — terms whose letters never occur inside an
ordinary English/code word. "val" and "breed" are deliberately NOT enforced: they
collide with "value"/"eval"/"interval" and with proper names (e.g. Graham Breed), so
an automatic ban would be almost entirely false positives. Review those by eye.

The one sanctioned exception is ``rtt/temperament.py``: its interval parser still
*accepts* the legacy words as input aliases (tolerated, not endorsed — see the comment
there), so that file is whitelisted for the term it documents.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCAN_DIRS = ("rtt", "tests")

# disavowed term -> repo-relative paths allowed to contain it (the documented aliases).
# Each term is matched case-insensitively as a bare substring; that is safe only because
# none of these letters appear inside an ordinary word (so "monzo" also catches "monzos",
# "tmonzo", "eigenmonzo"; "wedgie" catches "wedgies"). Add new unambiguous terms here.
BANNED = {
    "monzo": {"rtt/temperament.py"},
    "wedgie": set(),
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
        "'wedgie':\n  " + "\n  ".join(violations)
    )
