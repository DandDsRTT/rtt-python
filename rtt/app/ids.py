"""The cell-id vocabulary for the six EDITABLE interval grids — the ids that cross the
spreadsheet→page boundary. Each is minted twice: the builder (``rtt/app/spreadsheet.py``)
emits the cell with this id, and the page's edit handlers (``rtt/app/app.py``) reconstruct
the SAME id to read the widget's typed value back out of ``rec.inputs``. The two sides must
agree character-for-character — a mismatch silently drops the edit as "folded away" — so
each grid's id shape lives here ONCE.

Every formatter takes the column identifier first (a per-column token, or a plain index for
the unchanged grid) and the domain-prime index second — the grid's natural "which column,
which prime" order — and returns the id string. The id STRINGS themselves are NOT uniform:
the interval-vector grids (comma, interest, held, unchanged) put the prime before the column,
while the mapping rows and the target columns put their token first. That historical axis
split is preserved here deliberately — the strings are load-bearing in the DOM ``data-eid``
and pinned across the test suite — and naming it in one place is the point. Read-only
emission ids (the projected/mapped grids, superspace tiles, brackets, gridlines, …) never
cross back to a handler and stay inline in the builder."""


def mapping_cell(token, prime):
    """A mapping covector cell ⟨…] — the row token before the prime (row-major)."""
    return f"cell:mapping:{token}:{prime}"


def form_cell(row, col):
    """A generator form matrix 𝐹 cell { … ] — stored-generator row, canonical-generator column (the
    EDITABLE 𝐹, 𝑀 = 𝐹𝑀_C, which rides the mapping row's canonical-generators column). The id keeps
    the historical "cell:finv" prefix from before the 𝐹/𝐹⁻¹ tiles were swapped to match the convention."""
    return f"cell:finv:{row}:{col}"


def comma_cell(token, prime):
    """A comma-basis vector cell [..⟩ — prime down the rows, comma column across."""
    return f"cell:comma:{prime}:{token}"


def interest_cell(token, prime):
    """An interval-of-interest vector cell — prime down the rows, like the comma basis."""
    return f"cell:interest:{prime}:{token}"


def held_cell(token, prime):
    """A held-interval vector cell — prime down the rows, like the comma basis."""
    return f"cell:held:{prime}:{token}"


def unchanged_cell(column, prime):
    """An unchanged-basis (U) vector cell — prime down the rows; ``column`` is a plain index
    (0…r-1), not a token, since U is derived from the projection, not user-curated."""
    return f"cell:unchanged:{prime}:{column}"


def target_cell(token, prime):
    """A target vector cell — the column token BEFORE the prime, the reversed axis order
    (the targets grid is the lone outlier from the interval-vector convention above)."""
    return f"cell:vec:targets:{token}:{prime}"
