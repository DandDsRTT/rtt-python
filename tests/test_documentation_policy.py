import ast
import io
import tokenize
from pathlib import Path

import pytest

_RTT = Path(__file__).resolve().parents[1] / "rtt"
_PY_FILES = sorted(_RTT.rglob("*.py"))

_COMMENTS_ALLOWED = {
    "app/app.py",
    "app/page_assets.py",
    "app/reconciler.py",
    "app/_recon_value.py",
    "app/_recon_choosers.py",
    "app/_recon_buttons.py",
    "app/_recon_drag.py",
    "app/gestures.py",
    "app/rendering.py",
    "app/rendering_chrome.py",
    "app/editing.py",
    "app/_editing_vectors.py",
    "app/_editing_tuning.py",
    "app/building.py",
    "app/page.py",
    "app/render_html.py",
    "app/render_html_layout.py",
    "app/render_html_text.py",
    "app/editor.py",
    "app/service/text.py",
    "app/service/core_vectors.py",
}


def _rel(path):
    return path.relative_to(_RTT).as_posix()


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


@pytest.mark.parametrize("path", [p for p in _PY_FILES if _rel(p) not in _COMMENTS_ALLOWED], ids=_rel)
def test_no_comments_outside_the_platform_limitation_whitelist(path):
    comments = [tok for tok in tokenize.generate_tokens(io.StringIO(path.read_text(encoding="utf-8")).readline)
                if tok.type == tokenize.COMMENT]
    assert not comments, (
        f"{_rel(path)} carries {len(comments)} comment(s): "
        + " / ".join(f"L{tok.start[0]} {tok.string.strip()[:60]}" for tok in comments[:3])
        + f"\nComments are allowed ONLY to flag a language/dependency limitation a reader would "
        f"otherwise 'fix' and break, and ONLY in {sorted(_COMMENTS_ALLOWED)} (CLAUDE.md). Otherwise "
        f"improve the names/tests until the comment is unnecessary. If this is a genuine new platform "
        f"limitation in another file, add that file to _COMMENTS_ALLOWED here."
    )
