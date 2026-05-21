"""Integration tests mirroring the original rtt-app ``spec/integration.test.tsx``.

The original rendered the React app and drove DOM events against a *mocked*
Wolfram API. Here the same user scenarios run through the Editor (service + undo
state), and the expected duals are the library's real canonical values — which
differ in sign from the original's hand-written mocks (e.g. the syntonic comma is
``[4 -4 1⟩`` here vs ``[-4 4 -1⟩`` there). Same scenarios, real arithmetic.
"""

from rtt.web import service
from rtt.web.app import _parse_int
from rtt.web.editor import INITIAL_MAPPING, Editor


def _domain(editor):
    return list(service.standard_primes(editor.state.d))


def _mapping(editor):
    return [list(row) for row in editor.state.mapping]


def _comma_basis(editor):
    return [list(comma) for comma in editor.state.comma_basis]


# --- expanding the domain ---

def test_expanding_grows_the_domain():
    editor = Editor()
    assert _domain(editor) == [2, 3, 5]
    editor.expand()
    assert _domain(editor) == [2, 3, 5, 7]


def test_expanding_grows_the_mapping():
    editor = Editor()
    assert _mapping(editor) == [[1, 1, 0], [0, 1, 4]]
    editor.expand()
    assert _mapping(editor) == [[1, 0, -4, 0], [0, 1, 4, 0], [0, 0, 0, 1]]


def test_expanding_grows_the_comma_basis():
    editor = Editor()
    assert _comma_basis(editor) == [[4, -4, 1]]
    editor.expand()
    assert _comma_basis(editor) == [[4, -4, 1, 0]]


# --- shrinking the domain ---

def test_shrinking_shrinks_the_domain():
    editor = Editor()
    assert _domain(editor) == [2, 3, 5]
    editor.shrink()
    assert _domain(editor) == [2, 3]


def test_shrinking_shrinks_the_mapping():
    editor = Editor()
    editor.shrink()
    assert _mapping(editor) == [[1, 1]]


def test_shrinking_shrinks_the_comma_basis():
    editor = Editor()
    editor.shrink()
    assert _comma_basis(editor) == [[4, -4]]


# --- changing the mapping updates the comma basis ---

def test_changing_the_mapping_updates_the_comma_basis():
    editor = Editor()
    assert _comma_basis(editor) == [[4, -4, 1]]
    editor.edit_mapping([[1, 1, 0], [0, 1, 5]])  # the prime-5 cell of generator 1: 4 -> 5
    assert _comma_basis(editor) == [[5, -5, 1]]


# --- changing the comma basis updates the mapping ---

def test_changing_the_comma_basis_updates_the_mapping():
    editor = Editor()
    assert _mapping(editor) == [[1, 1, 0], [0, 1, 4]]
    editor.edit_comma_basis([[4, -5, 1]])  # the prime-3 coefficient: -4 -> -5
    assert _mapping(editor) == [[1, 0, -4], [0, 1, 5]]


# --- undoing ---

def test_undo_reverts_the_latest_mapping_change():
    editor = Editor()
    original = [list(row) for row in INITIAL_MAPPING]
    editor.edit_mapping([[1, 1, 0], [0, 1, 5]])
    assert _mapping(editor) != original
    editor.undo()
    assert _mapping(editor) == original


def test_undo_reverts_the_latest_comma_basis_change():
    editor = Editor()
    original = _comma_basis(editor)
    editor.edit_comma_basis([[4, -5, 1]])
    assert _comma_basis(editor) != original
    editor.undo()
    assert _comma_basis(editor) == original


# --- inputting ---

def test_a_temporarily_invalid_cell_value_does_not_recompute():
    # While typing, a lone "-" is not a number: the UI parses it to None and skips
    # the recompute (no crash). A complete value like "-3" parses to drive an edit.
    assert _parse_int("-") is None
    assert _parse_int("-3") == -3
