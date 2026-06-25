# Code quality gate

Strict, automated quality checks for `rtt/` (the app) and `tools/`. The single
command is **`bin/lint`** (fast) / **`bin/lint --cov`** (adds the coverage gate);
the same checks run on commit via **pre-commit**.

## Setup

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pre-commit install        # optional: run the fast subset on every commit
bin/lint                            # lint + format + structural metrics + complexity
bin/lint --cov                      # + 95% branch-coverage gate (logic tiers only)
```

In a worktree (no local `.venv`), point the runner at the main checkout's
interpreter: `RTT_PY=/abs/path/.venv/bin/python bin/lint`.

## Thresholds

These are deliberately **staged**: strict now, stricter later. The end goal is
Clean-Code-grade — **functions ≤ 10 lines, files ≤ 100 lines**. We ratchet down
in lockstep with the refactors so the gate stays green at every step.

| Metric | Now | Goal | Enforced by |
|---|---|---|---|
| Cyclomatic complexity | ≤ 10 | ≤ 5 | ruff |
| Function length (lines) | ≤ 50 | ≤ 10 | `tools/quality_checks.py` |
| File length (lines) | ≤ 500 | ≤ 100 | `tools/quality_checks.py` |
| Arguments per function | ≤ 4 | ≤ 4 | ruff |
| Statements per function | ≤ 50 | ≤ 10 | ruff |
| Branches per function | ≤ 12 | ≤ 8 | ruff |
| Nesting depth | ≤ 4 | ≤ 3 | ruff |
| Efferent coupling (fan-out) | ≤ 18 | ↓ | `tools/quality_checks.py` |
| Class cohesion (LCOM4) | ≤ 10 | ↓ | `tools/quality_checks.py` |
| Depth of inheritance (DIT) | ≤ 2 | ≤ 2 | `tools/quality_checks.py` |
| Number of children (NOC) | ≤ 3 | ≤ 3 | `tools/quality_checks.py` |
| Branch coverage (logic tiers) | ≥ 95% | ≥ 95% | `coverage` (`fail_under`) |
| Docstrings | banned | banned | `tools/quality_checks.py` |

The architectural rails (coupling / LCOM4 / DIT / NOC) are calibrated to the
current worst value so they pass today and **ratchet down** as the oversized modules
split — exactly like file/function length. Afferent coupling (fan-in) is reported,
not gated: a high fan-in is the heavily-used shared core (e.g. `library.temperament`),
which is healthy, not a smell.

**The `self.page` god-handle gate (target 0, gated now).** The view controllers used to
hold the whole `_Page` and reach through it — `self.page.editor.state…` — ~498 such reaches.
After they were given injected deps (PRs #33/#34/#36/#38), that count is **0**, and
`page_reach_violations` now **fails the build on any `self.page.<x>`** (one documented
exemption: `tooltips.py`'s `GuideHelp.page` is a wiki-page-name string, not the handle).
This is the one rail set to *bite from zero* rather than calibrated to current-worst — it locks
in the decoupling instead of trailing it. The companion measure for the spreadsheet builder
(cross-file shared mutable `self` across its mixins, the ~141 census) is **not** gated yet: that
god-object is mid-dismantle by the `_GridBuilder` pipeline campaign, so gating it now would block
the in-flight migration — it lands with that campaign.

To ratchet: lower the values in `pyproject.toml` (`[tool.ruff.lint.*]`) and the
constants in `tools/quality_checks.py` (`MAX_FILE_LINES`, `MAX_FUNCTION_LINES`,
`MAX_EFFERENT_COUPLING`, `MAX_LCOM4`, `MAX_DIT`, `MAX_NOC`), after the corresponding
refactor lands.

## The metric wishlist

Status of every architectural metric requested:

- **Cyclomatic complexity, nesting depth, params, statements, branches** —
  enforced now (ruff). `radon` gives a complexity report in `bin/lint`.
- **Function length, file length, docstring ban** — enforced now
  (`tools/quality_checks.py`, our own AST checker, because ruff has no rule for
  physical line spans).
- **Afferent / efferent coupling, fan-in / fan-out (module level)** — enforced now
  (`tools/quality_checks.py`). We build the internal import graph ourselves rather
  than add an `import-linter` dependency, so the whole structural gate stays in one
  tested module. Efferent coupling (fan-out) is gated; afferent (fan-in) is reported.
- **LCOM (class cohesion)** — enforced now (`tools/quality_checks.py`, LCOM4 over the
  per-class method/attribute graph: two methods are linked when they share an instance
  attribute or one calls the other; LCOM4 is the number of connected components).
- **Depth of inheritance (DIT) / number of children (NOC)** — enforced now
  (`tools/quality_checks.py`). Trivially satisfied — the codebase's deepest hierarchy
  is one level and no class has more than one direct subclass — so these are cheap
  guard rails against an accidental inheritance sprawl.

## What is NOT auto-gated, and why

- **Comments.** `rtt/` carries ~390 comment lines; the project rule allows comments
  only for genuine language/dependency limitations, which a checker can't tell from
  the rest. So comments are report-only, not a hard gate — scrubbing them is a
  separate manual pass.
- **Docstring tools (`pydocstyle`, `interrogate`) and `pep8-naming`** are *not*
  used: they enforce the opposite of this project's rules (docstrings required;
  conventional names), which would fight the no-docstring rule and the math notation
  (`M_jL`, `B_L`, …).

## Coverage gate scope — logic tiers only

The 95% branch-coverage gate is scoped to the **logic tiers** — `rtt/library/**` and
`rtt/app/service/**` — not the whole of `rtt/`. Line coverage is a meaningful signal for
branchy **logic**; it is noise for the view layer's SVG/DOM string-assembly (`app.py`,
`render_html.py`, the `spreadsheet_*` modules, `marks.py`, `tooltips.py`).

Measuring the view layer here also forced the slow NiceGUI page-render integration tests
(`tests/app/integration/test_web_render.py`) to carry its *line* coverage, which is exactly
what made a coverage run slow and profiler-fragile (see the `coverage-gate-local-blockers`
memory: render-under-coverage is ~15 s/test on the local 3.14 venv, deadlocks in NiceGUI's
fixture teardown, and dogpiles across parallel agents). So:

- **`fail_under = 95` is computed over the logic tiers only** — set via
  `[tool.coverage.run] source = ["rtt/library", "rtt/app/service"]` in `pyproject.toml`,
  which the logic tiers' fast, deterministic **unit** tests cover.
- **The view layer carries no line-coverage requirement.** It stays guarded by the render
  integration tests as **behaviour** tests (build the page, assert it renders and behaves),
  not by a line percentage.
- **`bin/lint --cov` runs coverage with the render tests excluded from the profiler**
  (`--ignore=tests/app/integration/test_web_render.py`), so the coverage run is fast and
  reliable. The render tests still run — unprofiled — in the full `pytest` suite that gates
  a merge; coverage just no longer drives the profiler through them.

This pairs with the `app.py` logic-extraction item below — together they move the view's
*logic* into a place the scoped gate covers cheaply.

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
   - PLANNED — **extract logic out of the view layer into `service/`.** Much of `app.py`'s
     bulk is *logic* (state transitions, value derivation, event handling) entangled with
     NiceGUI wiring, with no unit-testable seam — which is why it is reachable only by the
     slow render integration tests. Pull that logic down into `service/` (fast unit tests)
     so the view files shrink to thin wiring AND the scoped coverage gate above covers the
     logic cheaply. This is the **testability** counterpart to the structural decomposition
     (which only moves view code between files); the two are orthogonal. NOT yet underway.
3. **File decomposition + coupling/cohesion metrics** — DONE. The **50/500 milestone is
   reached**: `bin/lint` is fully GREEN at functions ≤ 50, files ≤ 500, args ≤ 4
   (relaxed per-file for the math/render-dense modules), CC ≤ 10, and the architectural
   metrics (efferent coupling, LCOM4, DIT, NOC). Every logic module is ≤ 500 lines; the
   only files over the cap are the three irreducible data modules listed above, exempt by
   `FILE_LENGTH_EXEMPT`. The line-length limit and `ruff format` on the dense view modules
   are deferred together (see the section above) — that is the only part of the ruff surface
   not yet green, by design.
   - **The ratchet beyond 50/500 — files 500 → 250 → 100 and functions 50 → 25 → 10 — is
     the deliberately-deferred "later" campaign** ("50/500 now, 10/100 later"). Do NOT
     lower `MAX_FILE_LINES` / `MAX_FUNCTION_LINES` (or the ruff caps) without an explicit
     go-ahead: that campaign also decomposes the dense view modules enough to re-enable
     line-length and `ruff format` on them, so it is a coordinated effort, not a knob to nudge.

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

#### File-length exemptions for irreducible data modules

`tools/quality_checks.py` carries a `FILE_LENGTH_EXEMPT` set of paths excused from the
file-length cap, for modules that are **predominantly static data** (lookup dicts of
strings, CSS/JS/SVG asset blobs) with only thin lookup logic — splitting them buys no
readability, only an extra import hop, and the "cohesive logical module" rule has nothing
to cut along. Every other cap (function length, docstrings, coupling, cohesion) still
applies. Each exemption is listed here with its justification:

- **`rtt/app/tooltips.py`** — almost the whole file is help-text dictionaries
  (`GUIDE_HELP`, `SHOW_HELP`, `_KIND_HELP`, …) keyed by tile/control id; the handful of
  functions are one-line lookups over them. It is a data module by the same standard as
  `grid_tables.py`, and it is hot (the guide-tooltip work edits these dicts continually),
  so prying the data into a sibling file would only churn merge conflicts.
- **`rtt/app/page_assets.py`** — the page's asset bank: ~77% string-literal lines (the
  zoom/guide/busy/tour/tooltip JS, the CSS variable blocks and font face, the audio glyph
  bank) plus small spec dataclasses and a handful of pure helpers. The blobs *are* the
  module's purpose; the logic in it is minor and stays put.
- **`rtt/app/grid_tables.py`** — the per-(row, col) grid data tables (symbols, units,
  equivalences, captions, presets, form choosers, EBK conventions): one keyed entry per
  line, irreducible. It is the grid's data dictionary; there is no cohesive seam to split
  along, only an import hop. A test pins the exempt set to exactly these three data modules
  (`tests/tools/unit/test_quality_checks.py`), so a logic module can't be slipped in.

### The line-length limit + `ruff format` are deferred *together, by design*

The long lines split into groups, none of which is a mechanical reflow:

- **Comments** belong to the separate comment scrub (this project treats a comment as a
  smell; see CLAUDE.md). Reflowing lines slated for deletion is wasted work.
- **Strings** — mostly the EBK/notation lines that must **never wrap** (CLAUDE.md) and
  tooltip help text. These resolve only by value-preserving implicit-string-concatenation
  splits, done with the notation in view.
- **Code** in the dense view modules — the cell/SVG-assembly lines. Here line-length and the
  length caps **collide**: wrapping these lines to ≤100 chars (what `ruff format` does)
  pushes the module past the 500-line file cap (or a builder past the 50-line function
  cap). You cannot satisfy line-length **and** module/function length there until the code is
  decomposed further — which is the parked 500→250→100 campaign, not this milestone.

Because of that collision, **line-length and `ruff format` are deferred in lockstep**, so the
gate goes green on everything that *is* in scope:

- The **line-length limit is on ruff's ignore list** (`pyproject.toml`) — not gated yet.
- The format step's **own exclude list** (`[tool.ruff.format]` in `pyproject.toml`) names the
  render/data-dense view modules whose canonical format would wrap past a cap (`grid_tables`,
  `tooltips`, `page_assets`, `rendering`, the `spreadsheet_*` emit/geometry/layout/resolve/
  brackets/controls/decorations/models family).
  **Every other module IS `ruff format`-checked** — formatting is enforced on the library,
  service, and the non-dense app code; it is only deferred where it fights a length cap.

Both re-enable together when the 500→250→100 decomposition splits the dense view modules so
their wrapped lines fit under the caps. They are NOT closed at the 50/500 milestone.
