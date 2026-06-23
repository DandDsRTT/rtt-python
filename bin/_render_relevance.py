"""Which changed files can affect the app's rendered output.

Single source of truth for the render-relevance whitelist shared by
``bin/merge-safe-check`` (may I ff-merge on my prior green run?) and
``bin/merge-green-check`` (does a green render-gate token validate this tree?).
Both ask the same question — "is this delta render-orthogonal?" — so the answer
lives in exactly one place.

Render-RELEVANT (can change rendered output) = the whole ``rtt/`` tree, ``app.py``,
the rootdir ``conftest.py`` (loads the User plugin), ``pytest.ini``,
``requirements.txt`` — and, conservatively, anything not on the irrelevant
whitelist below. The default is *relevant*: when unsure, treat as relevant.

Render-IRRELEVANT (safe) whitelist:
  * ``tests/**``     — test-only; can't change shipped render output
  * ``guide/**``     — guide prose; not read by the app at render time
  * ``.claude/**``   — agent/harness config
  * ``.github/**``   — CI config
  * ``bin/**``       — these helpers
  * ``*.md``         — docs (CLAUDE.md, README, audit notes, …)
  * ``*.png``/``*.csv`` — design mockups & their transcriptions
  * a few top-level non-code files (LICENSE, .gitignore, .python-version, render.yaml)
"""


def is_irrelevant(path):
    prefixes = ("tests/", "guide/", ".claude/", ".github/", "bin/")
    if path.startswith(prefixes):
        return True
    if path.endswith((".md", ".png", ".csv")):
        return True
    if path in {"LICENSE", ".gitignore", ".python-version", "render.yaml"}:
        return True
    return False


def relevant(files):
    return sorted(p for p in files if p.strip() and not is_irrelevant(p))


def irrelevant(files):
    return sorted(p for p in files if p.strip() and is_irrelevant(p))
