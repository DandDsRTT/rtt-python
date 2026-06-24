import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

_RTT = Path(__file__).resolve().parents[1] / "rtt"
_PY_FILES = sorted(_RTT.rglob("*.py"))

# Comments are allowed ONLY to flag a language/dependency limitation a reader would otherwise "fix"
# and break (CLAUDE.md). Every surviving comment must NAME the platform it constrains, so this regex
# can police it; extend it only for a genuinely new platform constraint, never to wave a comment past.
_PLATFORM_LIMITATION = re.compile(
    r"nicegui|quasar|\bvue\b|uvicorn|fastapi|browser|html5|\bcss\b|cpython|dnd",
    re.IGNORECASE,
)

# Per-file allowances for the platform-limitation comments that remain. This is a RATCHET, not a
# budget with slack: every count is EXACT, so a file can only ever leave this table by reaching zero
# (its entry deleted), and a comment can never be added without the diff also raising its number here
# for review. Removing a comment requires lowering its number in the same change. Drive these DOWN.
_COMMENT_ALLOWANCE = {
    "app/app.py": 13,
    "app/page_assets.py": 29,
    "app/reconciler.py": 2,
    "app/_recon_choosers.py": 9,
    "app/_recon_buttons.py": 2,
    "app/_recon_drag.py": 6,
    "app/rendering.py": 5,
    "app/editing.py": 4,
    "app/_editing_tuning.py": 3,
    "app/building.py": 1,
    "app/render_html_layout.py": 2,
    "app/render_html_text.py": 3,
    "app/service/core_vectors.py": 2,
}


def _rel(path):
    return path.relative_to(_RTT).as_posix()


def _comments(src):
    return [
        tok
        for tok in tokenize.generate_tokens(io.StringIO(src).readline)
        if tok.type == tokenize.COMMENT
    ]


def _comment_blocks(src):
    blocks: list[list] = []
    prev_full = False
    prev_row = -2
    for tok in _comments(src):
        full = tok.line.lstrip().startswith("#")
        if blocks and full and prev_full and tok.start[0] == prev_row + 1:
            blocks[-1].append(tok)
        else:
            blocks.append([tok])
        prev_full, prev_row = full, tok.start[0]
    return blocks


def _docstringed(tree):
    return [node for node in ast.walk(tree)
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and ast.get_docstring(node, clean=False) is not None]


@pytest.mark.parametrize("path", _PY_FILES, ids=_rel)
def test_no_docstrings_in_rtt(path):
    offenders = _docstringed(ast.parse(path.read_text(encoding="utf-8")))
    assert not offenders, (
        f"{_rel(path)} carries {len(offenders)} docstring(s). This project documents itself through "
        f"tests and object names only (CLAUDE.md): replace the docstring with a clearer name and a "
        f"test, not prose that drifts out of sync."
    )


@pytest.mark.parametrize(
    "path", [p for p in _PY_FILES if _rel(p) not in _COMMENT_ALLOWANCE], ids=_rel
)
def test_files_outside_the_allowance_carry_no_comments(path):
    comments = _comments(path.read_text(encoding="utf-8"))
    assert not comments, (
        f"{_rel(path)} carries {len(comments)} comment(s): "
        + " / ".join(f"L{tok.start[0]} {tok.string.strip()[:60]}" for tok in comments[:3])
        + f"\nComments are allowed ONLY to flag a language/dependency limitation a reader would "
        f"otherwise 'fix' and break (CLAUDE.md). Otherwise improve the names/tests until the comment "
        f"is unnecessary. If this is a genuine new platform limitation, add the file + its exact "
        f"comment count to _COMMENT_ALLOWANCE here (and it must name the platform — see "
        f"_PLATFORM_LIMITATION)."
    )


@pytest.mark.parametrize("rel", sorted(_COMMENT_ALLOWANCE), ids=lambda r: r)
def test_allowance_count_is_exact_and_only_ratchets_down(rel):
    path = _RTT / rel
    assert path.exists(), f"{rel} is in _COMMENT_ALLOWANCE but no longer exists; remove the entry."
    count = len(_comments(path.read_text(encoding="utf-8")))
    allowed = _COMMENT_ALLOWANCE[rel]
    assert count == allowed, (
        f"{rel} has {count} comment(s) but _COMMENT_ALLOWANCE pins it at {allowed}. "
        + (
            "You removed comment(s) — lower the number here to lock in the reduction (this table "
            "only ratchets down)."
            if count < allowed
            else "You added comment(s) — a comment is allowed ONLY to flag a platform limitation "
            "(CLAUDE.md). Remove it, or if it is a genuine platform note raise the number here for "
            "review."
        )
    )


@pytest.mark.parametrize("rel", sorted(_COMMENT_ALLOWANCE), ids=lambda r: r)
def test_surviving_comments_name_their_platform_limitation(rel):
    path = _RTT / rel
    offenders = [
        block
        for block in _comment_blocks(path.read_text(encoding="utf-8"))
        if not _PLATFORM_LIMITATION.search(" ".join(tok.string for tok in block))
    ]
    assert not offenders, (
        f"{rel} carries {len(offenders)} comment(s) that name no platform limitation: "
        + " / ".join(f"L{block[0].start[0]} {block[0].string.strip()[:60]}" for block in offenders[:3])
        + "\nA comment survives only to flag a language/dependency limitation a reader would "
        "otherwise 'fix' and break (CLAUDE.md), and must NAME the platform it constrains (NiceGUI, "
        "Quasar, Vue, uvicorn, FastAPI, the browser, HTML5 DnD, CSS, CPython). If it explains OUR "
        "behavior instead, delete it and let names + tests carry it."
    )
