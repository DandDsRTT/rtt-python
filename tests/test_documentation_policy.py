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

# The Python tokenizer above sees only `#` comments. The view tier also embeds JS/CSS in string
# literals, and a `//` or `/* */` comment inside one of those strings is the SAME rot through an
# unpoliced channel — invisible to tokenize. These two regexes find them, and _EMBEDDED_ALLOWANCE
# ratchets them exactly like _COMMENT_ALLOWANCE: zero outside the table, an exact down-only count
# inside it, and every survivor must still NAME its platform (_PLATFORM_LIMITATION).
_QUOTED_SPAN = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"|`[^`\n]*`")
_EMBEDDED_COMMENT = re.compile(r"(?<![:/])//|/\*")
_EMBEDDED_ALLOWANCE = {
    "app/page_assets.py": 16,
}

# Tests document through clear names and assertions, not comments (CLAUDE.md): a comment in a test
# rots into a lie exactly like one in the library. This ratchets the test suite's `#` comments the
# same way _COMMENT_ALLOWANCE does for rtt/ — zero outside the table, an exact down-only count
# inside it — but with no platform exception, because the target for a test comment is always zero.
# Drive these to zero (replacing each comment with a clearer name, a named constant, or an assertion
# message); a file leaves the table when it reaches zero.
_TESTS = Path(__file__).resolve().parent
_TEST_PY_FILES = sorted(_TESTS.rglob("*.py"))
_TEST_COMMENT_ALLOWANCE = {
    "app/integration/conftest.py": 7,
    "app/integration/test_web_integration.py": 55,
    "app/integration/test_web_render.py": 2008,
    "app/unit/test_emit_pure.py": 11,
    "app/unit/test_geometry_query.py": 2,
    "app/unit/test_web_app_smoke.py": 520,
    "app/unit/test_web_chapters.py": 23,
    "app/unit/test_web_dark_mode.py": 30,
    "app/unit/test_web_ebk.py": 44,
    "app/unit/test_web_editor.py": 1051,
    "app/unit/test_web_presets.py": 82,
    "app/unit/test_web_render_html.py": 22,
    "app/unit/test_web_resolved.py": 8,
    "app/unit/test_web_service.py": 833,
    "app/unit/test_web_spreadsheet.py": 3920,
    "app/unit/test_web_tooltips.py": 67,
    "library/unit/test_addition.py": 39,
    "library/unit/test_canonicalization.py": 5,
    "library/unit/test_change_basis.py": 5,
    "library/unit/test_comma_forms.py": 18,
    "library/unit/test_dimensions.py": 1,
    "library/unit/test_domain_basis.py": 5,
    "library/unit/test_dual.py": 2,
    "library/unit/test_equal_temperament.py": 18,
    "library/unit/test_exterior_algebra.py": 29,
    "library/unit/test_formatting.py": 15,
    "library/unit/test_generator_forms.py": 26,
    "library/unit/test_math_utils.py": 8,
    "library/unit/test_matrix_utils.py": 7,
    "library/unit/test_meet_join.py": 2,
    "library/unit/test_parsing.py": 19,
    "library/unit/test_superspace.py": 7,
    "library/unit/test_symbolic_tuning.py": 6,
    "library/unit/test_target_intervals.py": 5,
    "library/unit/test_temperament.py": 1,
    "library/unit/test_terminology.py": 24,
    "library/unit/test_tuning.py": 56,
    "library/unit/test_tuning_all_interval.py": 55,
    "library/unit/test_tuning_alt_complexities.py": 25,
    "library/unit/test_tuning_audit.py": 29,
    "library/unit/test_tuning_damage.py": 5,
    "library/unit/test_tuning_manual_weights.py": 1,
    "library/unit/test_tuning_nonstandard.py": 26,
    "library/unit/test_tuning_nonstandard_prime.py": 6,
    "library/unit/test_tuning_ranges.py": 14,
    "library/unit/test_tuning_scheme_names.py": 28,
    "library/unit/test_tuning_solvers.py": 25,
    "library/unit/test_variance_utils.py": 1,
    "render_main.py": 2,
    "test_documentation_policy.py": 18,
    "tools/unit/test_quality_checks.py": 2,
}


def _rel(path):
    return path.relative_to(_RTT).as_posix()


def _test_rel(path):
    return path.relative_to(_TESTS).as_posix()


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


def _embedded_comments(src):
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for offset, line in enumerate(node.value.splitlines()):
                if _EMBEDDED_COMMENT.search(_QUOTED_SPAN.sub("", line)):
                    out.append((node.lineno + offset, line.strip()))
    return out


def _embedded_comment_blocks(src):
    blocks: list[list] = []
    prev_row = -2
    for row, text in _embedded_comments(src):
        if blocks and row == prev_row + 1:
            blocks[-1].append((row, text))
        else:
            blocks.append([(row, text)])
        prev_row = row
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


@pytest.mark.parametrize(
    "path", [p for p in _PY_FILES if _rel(p) not in _EMBEDDED_ALLOWANCE], ids=_rel
)
def test_files_outside_the_allowance_carry_no_embedded_comments(path):
    embedded = _embedded_comments(path.read_text(encoding="utf-8"))
    assert not embedded, (
        f"{_rel(path)} carries {len(embedded)} JS/CSS comment(s) inside string literal(s): "
        + " / ".join(f"L{row} {text[:60]}" for row, text in embedded[:3])
        + "\nA `//` or `/* */` comment embedded in a JS/CSS string is policed exactly like a `#` "
        "comment (CLAUDE.md): allowed ONLY to flag a platform limitation. Delete it, or if it is a "
        "genuine platform note add the file + its exact count to _EMBEDDED_ALLOWANCE here."
    )


@pytest.mark.parametrize("rel", sorted(_EMBEDDED_ALLOWANCE), ids=lambda r: r)
def test_embedded_allowance_count_is_exact_and_only_ratchets_down(rel):
    path = _RTT / rel
    assert path.exists(), f"{rel} is in _EMBEDDED_ALLOWANCE but no longer exists; remove the entry."
    count = len(_embedded_comments(path.read_text(encoding="utf-8")))
    allowed = _EMBEDDED_ALLOWANCE[rel]
    assert count == allowed, (
        f"{rel} has {count} embedded JS/CSS comment(s) but _EMBEDDED_ALLOWANCE pins it at {allowed}. "
        + (
            "You removed comment(s) — lower the number here to lock in the reduction (this table "
            "only ratchets down)."
            if count < allowed
            else "You added comment(s) — an embedded comment is allowed ONLY to flag a platform "
            "limitation (CLAUDE.md). Remove it, or if it is a genuine platform note raise the number "
            "here for review."
        )
    )


@pytest.mark.parametrize("rel", sorted(_EMBEDDED_ALLOWANCE), ids=lambda r: r)
def test_surviving_embedded_comments_name_their_platform_limitation(rel):
    path = _RTT / rel
    offenders = [
        block
        for block in _embedded_comment_blocks(path.read_text(encoding="utf-8"))
        if not _PLATFORM_LIMITATION.search(" ".join(text for _row, text in block))
    ]
    assert not offenders, (
        f"{rel} carries {len(offenders)} embedded comment(s) that name no platform limitation: "
        + " / ".join(f"L{block[0][0]} {block[0][1][:60]}" for block in offenders[:3])
        + "\nAn embedded JS/CSS comment survives only to flag a platform limitation (CLAUDE.md) and "
        "must NAME the platform it constrains. If it explains OUR behavior instead, delete it and let "
        "names + tests carry it."
    )


@pytest.mark.parametrize(
    "path",
    [p for p in _TEST_PY_FILES if _test_rel(p) not in _TEST_COMMENT_ALLOWANCE],
    ids=_test_rel,
)
def test_files_under_tests_outside_the_allowance_carry_no_comments(path):
    comments = _comments(path.read_text(encoding="utf-8"))
    assert not comments, (
        f"{_test_rel(path)} carries {len(comments)} comment(s): "
        + " / ".join(f"L{tok.start[0]} {tok.string.strip()[:60]}" for tok in comments[:3])
        + "\nTests document through clear names and assertions, not comments (CLAUDE.md): a comment in "
        "a test rots into a lie just like one in the library. Replace it with a clearer name, a named "
        "constant, or an assertion message. If you must keep it for now, add the file + its exact count "
        "to _TEST_COMMENT_ALLOWANCE here (which only ratchets down)."
    )


@pytest.mark.parametrize("rel", sorted(_TEST_COMMENT_ALLOWANCE), ids=lambda r: r)
def test_test_comment_allowance_is_exact_and_only_ratchets_down(rel):
    path = _TESTS / rel
    assert path.exists(), f"{rel} is in _TEST_COMMENT_ALLOWANCE but no longer exists; remove the entry."
    count = len(_comments(path.read_text(encoding="utf-8")))
    allowed = _TEST_COMMENT_ALLOWANCE[rel]
    assert count == allowed, (
        f"{rel} has {count} comment(s) but _TEST_COMMENT_ALLOWANCE pins it at {allowed}. "
        + (
            "You removed comment(s) — lower the number here to lock in the reduction (this table "
            "only ratchets down)."
            if count < allowed
            else "You added comment(s) — tests document through names and assertions, not comments "
            "(CLAUDE.md). Remove it, or replace it with a clearer name."
        )
    )
