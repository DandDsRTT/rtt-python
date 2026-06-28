def mapping_cell(token, prime):
    return f"cell:mapping:{token}:{prime}"


def form_cell(row, col):
    return f"cell:finv:{row}:{col}"


def comma_cell(token, prime):
    return f"cell:comma:{prime}:{token}"


def interest_cell(token, prime):
    return f"cell:interest:{prime}:{token}"


def held_cell(token, prime):
    return f"cell:held:{prime}:{token}"


def unchanged_cell(column, prime):
    return f"cell:unchanged:{prime}:{column}"


def target_cell(token, prime):
    return f"cell:vector:targets:{token}:{prime}"
