from rtt.web import grid


def _cells(d=3, rank=2, n=1):
    return grid.build(d, rank, n, (2, 3, 5, 7, 11)[:d])


def test_content_cells_present():
    kinds = [c.kind for c in _cells()]
    assert kinds.count("prime") == 3
    assert kinds.count("mapping") == 6  # rank x d
    assert kinds.count("comma") == 3  # n x d
    assert kinds.count("minus") == 1
    assert kinds.count("plus") == 1
    assert kinds.count("name") == 2  # "mapping" and "comma basis" labels


def test_header_sits_directly_above_the_mapping_columns():
    cs = _cells()
    prime_cols = sorted({c.col for c in cs if c.kind == "prime"})
    mapping_cols = sorted({c.col for c in cs if c.kind == "mapping"})
    assert prime_cols == mapping_cols
    assert max(c.row for c in cs if c.kind == "prime") < min(
        c.row for c in cs if c.kind == "mapping"
    )


def test_comma_basis_is_right_of_and_above_the_mapping():
    cs = _cells()
    comma_cols = [c.col for c in cs if c.kind == "comma"]
    mapping_cols = [c.col for c in cs if c.kind == "mapping"]
    comma_rows = [c.row for c in cs if c.kind == "comma"]
    mapping_rows = [c.row for c in cs if c.kind == "mapping"]
    assert min(comma_cols) > max(mapping_cols)  # to the right
    assert max(comma_rows) < min(mapping_rows)  # above


def test_minus_sits_over_the_last_prime_with_plus_to_its_right():
    cs = _cells()
    last_prime_col = max(c.col for c in cs if c.kind == "prime")
    minus = next(c for c in cs if c.kind == "minus")
    plus = next(c for c in cs if c.kind == "plus")
    assert minus.col == last_prime_col
    assert plus.col == minus.col + 1
    assert minus.row < min(c.row for c in cs if c.kind == "prime")  # above the header


def test_shared_axis_square_has_crossing_grid_lines():
    cs = _cells()
    prime_cols = {c.col for c in cs if c.kind == "prime"}
    square = [
        c for c in cs
        if c.css == "empty-box-element" and c.hline and c.vline and c.col in prime_cols
    ]
    assert len(square) == 9  # the d x d shared-axis square (under the prime columns)


def test_prime_columns_carry_vertical_grid_lines_beyond_the_square():
    cs = _cells()
    for col in {c.col for c in cs if c.kind == "prime"}:
        vline_rows = [c.row for c in cs if c.vline and c.col == col]
        assert len(vline_rows) >= 6  # extends above and below the d x d square
