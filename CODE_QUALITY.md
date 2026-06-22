# Code quality gate

Strict, automated quality checks for `rtt/` (the app) and `tools/`. The single
command is **`bin/lint`** (fast) / **`bin/lint --cov`** (adds the coverage gate);
the same checks run on commit via **pre-commit**.

## Setup

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pre-commit install        # optional: run the fast subset on every commit
bin/lint                            # lint + format + structural metrics + complexity
bin/lint --cov                      # + 95% branch-coverage gate (runs the full suite)
```

In a worktree (no local `.venv`), point the runner at the main checkout's
interpreter: `RTT_PY=/abs/path/.venv/bin/python bin/lint`.

## Thresholds

These are deliberately **staged**: strict now, stricter later. The end goal is
Clean-Code-grade — **functions ≤ 10 lines, files ≤ 100 lines**. We ratchet down
in lockstep with the refactors so the gate stays green at every step.

| Metric | Now | Goal | Enforced by |
|---|---|---|---|
| Cyclomatic complexity | ≤ 10 | ≤ 5 | ruff `C901` |
| Function length (lines) | ≤ 50 | ≤ 10 | `tools/quality_checks.py` |
| File length (lines) | ≤ 500 | ≤ 100 | `tools/quality_checks.py` |
| Arguments per function | ≤ 4 | ≤ 4 | ruff `PLR0913` |
| Statements per function | ≤ 50 | ≤ 10 | ruff `PLR0915` |
| Branches per function | ≤ 12 | ≤ 8 | ruff `PLR0912` |
| Nesting depth | ≤ 4 | ≤ 3 | ruff `PLR1702` |
| Branch coverage | ≥ 95% | ≥ 95% | `coverage` (`fail_under`) |
| Docstrings | banned | banned | `tools/quality_checks.py` |

To ratchet: lower the values in `pyproject.toml` (`[tool.ruff.lint.*]`) and the
two constants in `tools/quality_checks.py`, after the corresponding refactor lands.

## The metric wishlist

Status of every architectural metric requested:

- **Cyclomatic complexity, nesting depth, params, statements, branches** —
  enforced now (ruff). `radon` gives a complexity report in `bin/lint`.
- **Function length, file length, docstring ban** — enforced now
  (`tools/quality_checks.py`, our own AST checker, because ruff has no rule for
  physical line spans).
- **Afferent / efferent coupling, fan-in / fan-out (module level)** — planned for
  Phase 3 via `import-linter` contracts (clean module-dependency boundaries) plus a
  fan-in/out report. Deferred because it only becomes meaningful after the oversized
  modules are split.
- **LCOM (class cohesion)** — planned for Phase 3 in `tools/quality_checks.py`
  (LCOM4 over the method/attribute graph). No mature off-the-shelf gating tool, so
  we own it.
- **Depth of inheritance (DIT) / number of children (NOC)** — trivially satisfied
  today (the codebase barely uses inheritance); a cheap guard rail in Phase 3.

## What is NOT auto-gated, and why

- **Comments.** `rtt/` carries ~390 comment lines; the project rule allows comments
  only for genuine language/dependency limitations, which a checker can't tell from
  the rest. So comments are report-only, not a hard gate — scrubbing them is a
  separate manual pass.
- **Docstring tools (`pydocstyle`, `interrogate`) and `pep8-naming`** are *not*
  used: they enforce the opposite of this project's rules (docstrings required;
  conventional names), which would fight the no-docstring rule and the math notation
  (`M_jL`, `B_L`, …).

## Cleanup status

The gate is being driven to green in phases (tooling first):

1. **Tooling + mechanical fixes** — DONE. Config, `bin/lint`, checker, `ruff format`,
   explicit imports, and every non-structural ruff rule cleared (lint went from
   ~2,592 → ~336). `args<=4` is met (relaxed per-file for the math/render-dense modules).
2. **Complexity / function length** — IN PROGRESS. Real extractions.
   - DONE: the whole library (`get_complexity`, `smith_normal_form_with_transforms` via
     a `_SmithReduction` class, `_complexity_traits_from_name` via a token table) and
     `rtt/app/render_html.py` (dispatch functions → data tables).
   - TODO: `rtt/app/service/text.py` (`plain_text_values`, ~370 lines), `rtt/app/app.py`
     (35 items), `rtt/app/spreadsheet.py` (85 items, the bulk).
   - Note for extractions: ruff's mccabe counts **nested** functions toward the parent,
     so reduce CC by extracting **module-level functions or class methods**, not closures.
3. **File decomposition + coupling/cohesion metrics**, then ratchet to 10 / 100.

### Phase 3 file decomposition — architecture, not line-count chopping

`ruff format` inflated the data-dense modules ~2× by exploding tuples/dicts to one item
per line (`spreadsheet.py` 3,648 → 7,166; `app.py` 4,036 → 4,702). That growth is a
symptom: these files were already doing too much. Phase 3 must **decompose them into
cohesive, well-named logical modules** — by concern, not by line count. A pure data-table
module (`grid_tables`, the EBK conventions) still groups by *what the tables describe*,
never sliced arbitrarily to hit a number. If a file cannot be organized into clean modules
by extraction, prefer a **clean rewrite against the existing tests** over mechanical
splitting. The cap is the goal; readable architecture is the constraint — a split that
makes the app harder to follow is wrong even if it passes the gate. (For genuinely
irreducible data modules, an explicit per-file exemption is acceptable, documented here.)

### E501 (line length) is deferred *by design*, not skipped

The 255 long lines split into three groups, none of which is a mechanical reflow:

- **~113 are comments.** They belong to the separate comment scrub (this project
  treats a comment as a smell; see CLAUDE.md). Reflowing lines that are slated for
  deletion is wasted work, so E501-in-comments closes *with* that scrub.
- **~108 are inside strings** — mostly the EBK/notation lines that must **never
  wrap** (CLAUDE.md) and tooltip help text. These resolve by value-preserving
  implicit-string-concatenation splits, handled with the notation in view.
- **~34 are code** — these shorten naturally as the oversized functions in phase 2
  are extracted, so they are folded into that refactor rather than touched twice.

So E501 reaches zero alongside phases 2–3 and the comment scrub, not before.
