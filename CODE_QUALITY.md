# Code quality gate

Strict, automated quality checks for `rtt/` (the app) and `tools/`. The single
command is **`bin/lint`** (fast) / **`bin/lint --cov`** (adds the coverage gate);
the same checks run on commit via **pre-commit**.

## Setup

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pre-commit install        # optional: run the fast subset on every commit
bin/lint                            # lint + format + structural metrics + complexity
bin/lint --cov                      # + 97% coverage gate + per-file floors (logic tiers)
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
| Transitive efferent coupling | per-module ratchet (floor 8) | ↓ | `tools/quality_checks.py` |
| Class cohesion (LCOM4) | ≤ 10 | ↓ | `tools/quality_checks.py` |
| Depth of inheritance (DIT) | ≤ 2 | ≤ 2 | `tools/quality_checks.py` |
| Number of children (NOC) | ≤ 3 | ≤ 3 | `tools/quality_checks.py` |
| Branch coverage (logic tiers) | ≥ 97% aggregate + per-file floor | ↑ | `coverage` + `tools/coverage_floor.py` |
| Docstrings | banned | banned | `tools/quality_checks.py` |

The architectural rails (coupling / LCOM4 / DIT / NOC) are calibrated to the
current worst value so they pass today and **ratchet down** as the oversized modules
split — exactly like file/function length. Coupling is a **per-module transitive
ratchet**, not a single threshold: every module at or above `COUPLING_FLOOR` (8) gets a
floor in `tools/quality_baseline.json` (`coupling`) that can only shrink. Afferent
coupling (fan-in) is reported, not gated: a high fan-in is the heavily-used shared core
(e.g. `library.temperament`), which is healthy, not a smell.

**The reach-through gate (a ratchet to an irreducible floor).** The view/editor controllers used
to hold a whole god-object and reach through it — `self.page.editor.state…`, ~498 such reaches.
The gate that catches this is `tools/quality_metrics.py`: it counts `self.<handle>.<member>` chains
where `<handle>` is an *injected* collaborator, resolved **per inheritance component** so a class
reading its OWN state does not count (constructor-, inheritance-, and `bind()`-injected handles all
do). `tools/quality_ratchets.py` pins the results in `tools/quality_baseline.json` as **floors that
can only shrink, never grow**:

- `reach_through_total` (the whole-tree count of injected-handle reaches),
- a per-handle floor for each named handle, enforced independently of the total — a handle
  whose live reach count exceeds its floor fails the gate even when another handle shrank to
  keep the total flat,
- a Demeter-depth ceiling (no `self.a.b.c.d` chains),
- a `SimpleNamespace`-bag ban (no untyped mutable bag shared across files — the spreadsheet
  builder's old census, since replaced by frozen `resolved` / `geometry` records), and
- a class-surface ceiling (per-class method and attribute counts).

This replaced the original **name-matching** gates (a literal `self.page.<x>` check and a
`spreadsheet_shared_state` census) once an audit showed a god-object could dodge them by simply
renaming the handle. That finding *became* this metric — the canonical worked example of the audit
loop documented at the end of this file. The live floors are whatever `quality_baseline.json` holds;
to ratchet, reduce a real count, then lower its floor in the same PR (the gate confirms it shrank).

To ratchet: lower the values in `pyproject.toml` (`[tool.ruff.lint.*]`) and the
constants in `tools/quality_checks.py` (`MAX_FILE_LINES`, `MAX_FUNCTION_LINES`,
`MAX_LCOM4`, `MAX_DIT`, `MAX_NOC`), after the corresponding refactor lands. Transitive
coupling has no single `MAX` constant: cut a module's internal deps, then lower its
floor in `tools/quality_baseline.json` (`coupling`) in the same PR — the same
shrink-only ratchet as the reach-through floors (`COUPLING_FLOOR` is only the threshold
at which a new module first gets a floor, not a global cap).

**The param-form reach-through gate (the reach-through gate's companion).** Decomposing the
view/editor controllers into free functions moved the very reaches the self-form gate counts out of
its sight: `self._editor.state` inside a method became `ec._editor.state` inside a module-level shard
free function (`_recon_*`, `_editing_*`, `_gesture_ops`, `_page_parts`, `_rendering_ops`). The
self-form gate scores `param._editor.state` as zero, so the *same* coupling re-expressed through a
parameter is invisible to it. `param_reach_by_handle` in `tools/quality_metrics.py` closes that blind
spot. A module-level shard free function **binds** a controller iff its **first parameter name** is a
known shard handle (`rec`→`_Reconciler`, `ec`→`EditController`, `te`→`_TuningEdits`,
`gc`→`GestureController`, `pb`→`PageBuilder`, `r`→`Renderer`); it then counts every
`param.<injected_handle>.<member>` reach (Load *and* Store, local aliases included) against the
**same** `handles_by_class` set and through the **same** alias-tracking visitor (`_ReachVisitor`, now
the shared base of both the self-form `_HandleVisitor` and the param-form `_ParamReachVisitor`). A
function whose first parameter is not a handle (`def f(state, mapping): …`) binds nothing → 0; a bare
`param.<own_member>` is the function reading its own argument, not a reach-through → 0. (`te` binds
`_TuningEdits`, whose handle `e` *is* the EditController, so the `_editing_tuning` shards reach it as
`ec = te.e; ec._runtime.…`, counted under handle `e`.) The result is pinned in `quality_baseline.json`
as `param_reach_through_total` + `param_reach_through_by_handle`, **kept separate from** the self-form
floors so a future self→param relocation cannot trade one gate's count for the other's; both ratchet
down-only, total and per-handle, exactly like the self-form gate.

**Known under-count path (a *known* gap, not a silent one).** Binding is checked only on module-level
`tree.body` functions, so a shard helper *nested* inside a non-binding outer is never bound — e.g.
`_recon_value.py`'s `label_builder(cls)` returns a nested `build(rec, …)`. Today this misses nothing
(`build` only touches `rec.cells`, an own-member), and `tests/tools/unit/test_quality_ratchets.py`
pins a `label_builder→build` fixture at 0 so the gap stays visible. The general fix (binding every
nested `FunctionDef`) carries a double-count subtlety not worth its risk for a zero-impact gap, so the
path is documented rather than hardened.

**This floor is deep on purpose — it bottoms out near ~360, and that depth is correct, not debt.**
The seeded total is 480, and most of it is irreducible:

- **232 are `param._editor.<member>` — dispatches *into the store*** (the `Editor(Document)` facade).
  A controller calling the store is the **north-star goal**, not coupling to cut. Replacing one store
  handle with N store-method parameters would *raise* coupling by surface count. **Leave every
  `_editor` reach untouched.**
- **~136 are wide multi-handle orchestrators.** They genuinely touch many collaborators; the only ways
  to lower their count are to explode the signature past four parameters (these shards are
  PLR0913-exempt, so nothing forces it) or to re-bundle the handles into one record parameter — which
  is the whole-controller-as-parameter dodge again, merely renamed. Both are worse than the reach.
  **Irreducible.**
- **~91 are genuinely removable** — single-sibling-handle reaches that can take a narrow dependency,
  plus ~23 build-time `_chrome` slot writes and ~8 `_rec` cache writes that can route through a single
  owner. Clearing these is the *only* sanctioned reduction; it lowers the floor toward ~384 → ~360.

**Stop-condition — do not chase the store-dispatch or the wide set to zero.** Once the removable ~91
are gone the gate is *done*: its job is to stop the count from silently **growing**, not to drive it
to zero. Exploding a signature or bundling handles into a record to beat the number is exactly the
theater this gate philosophy refuses — it swaps a legible reach for an illegible one while the
coupling is unchanged. To ratchet, remove a *real* reach (narrow a dep or route a write through its
owner), regenerate the baseline, and let the gate confirm the count shrank.

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

The 97% branch-coverage gate is scoped to the **logic tiers** — `rtt/library/**` and
`rtt/app/service/**` — not the whole of `rtt/`. Line coverage is a meaningful signal for
branchy **logic**; it is noise for the view layer's SVG/DOM string-assembly (`app.py`,
`render_html.py`, the `spreadsheet_*` modules, `marks.py`, `tooltips.py`).

Measuring the view layer here also forced the slow NiceGUI page-render integration tests
(`tests/app/integration/test_web_render.py`) to carry its *line* coverage, which is exactly
what made a coverage run slow and profiler-fragile (see the `coverage-gate-local-blockers`
memory: render-under-coverage is ~15 s/test on the local 3.14 venv, deadlocks in NiceGUI's
fixture teardown, and dogpiles across parallel agents). So:

- **`fail_under = 97` is computed over the logic tiers only** — set via
  `[tool.coverage.run] source = ["rtt/library", "rtt/app/service"]` in `pyproject.toml`,
  which the logic tiers' fast, deterministic **unit** tests cover.
- **A per-file floor stops the aggregate from hiding a weak file.** The aggregate alone is
  blind: a few logic-tier files sit well below it (e.g. `service/projection.py` ~89%,
  `service/superspace.py` ~90%, `library/tuning_solvers.py` ~93%) while the whole tier
  averages ~98%. `tools/coverage_floor.py` pins each logic-tier file's current branch
  coverage (floored to 2 dp) in `tools/coverage_baseline.json` and fails the gate if any
  file drops below its floor — a shrink-only ratchet, like the structural floors. To raise
  a floor after adding tests, regenerate it: `python -m tools.coverage_floor coverage.json
  --update-baseline`.
- **The view layer carries no line-coverage requirement.** It stays guarded by the render
  integration tests as **behaviour** tests (build the page, assert it renders and behaves),
  not by a line percentage.
- **`bin/lint --cov` runs coverage with the render tests excluded from the profiler**
  (`--ignore=tests/app/integration/test_web_render.py`), then `coverage report` (the 97%
  aggregate gate) and `tools.coverage_floor` (the per-file floors). The render tests still
  run — unprofiled — in the full `pytest` suite that gates a merge; coverage just no longer
  drives the profiler through them.

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

## When is this "done"? — north-star, stop condition, and the audit loop

A quality gate with no defined finish invites either endless polishing or quiet rot. Three
things keep this gate convergent.

### Architecture north-star

The app is a **unidirectional data flow with an event shell**, not a two-way-bound framework.
State lives in `Document` (the store: temperament/tuning state + undo/redo, alongside
`pending` / `history` / view-settings); the render path is forward-only and pure —
`state → resolve() → frozen Resolved → frozen Geometry → assemble()/emit → render` — with
`_Reconciler` as the diff step. There is essentially no two-way binding (a handful of `.bind*`
calls total). This is the React-Redux shape adapted to a **server-rendered** NiceGUI app: the
"render loop" is the hand-built reconciler, not a virtual DOM. The data/render core is already
where it should be. **The remaining coupling debt is entirely in the event/controller shell**
(`GestureController`, `EditController`, `PageBuilder`, `Renderer`, `_Reconciler`) — controllers
that reach *through* each other instead of dispatching into the store. The endgame is to
converge that shell onto the store-and-pipeline core that already exists; do **not**
re-architect the data flow toward something else.

### The stop condition

Stop auditing for structure when **(1)** every gate is green **at its floor**, and **(2)** each
remaining floor is **demonstrably irreducible** — lowering it further would require breaking a
unit that legitimately should exist. A proven-irreducible floor is a STOP signal, not a TODO.
(Worked example: a design spike established that `Document`'s ~20-attr state core — undo/redo
plus the state-transition invariants — cannot be safely split; that state *is* the document's
identity.) At that point you switch from "auditing for improvements" to **the gate is the
standing guard**: you touch coupling again only when a gate goes **red** (a regression) or a
real feature forces it. Re-running an open-ended "what's wrong here?" audit on a codebase
already at its floors **manufactures** findings — that is thrash, a property of the method, not
the code.

### The audit loop — gate the gap, don't polish the code

A non-adversarial "does this look ok?" returns false comfort and misses real debt, so audits
should stay adversarial. What keeps an adversarial audit from thrashing is **what its findings
are allowed to become** — and "go fix it by hand" is not one of the options. Every finding
routes to exactly one of:

1. **Moves an existing gate** toward its floor → act; it is measured debt.
2. **Becomes a new gate** → if it is a real, recurring, load-bearing invariant no current gate
   catches, encode it as a metric + floor. (This is how the reach-through metric was born: an
   audit found the god-object the size/coverage gates missed, and it became
   `tools/quality_metrics.py`.)
3. **Discarded** → if it cannot be stated as a measurable invariant with a target, it is taste,
   not debt. Let it go.

The materiality test is one question: **"Can I state this as a number with a target?"** If not,
it is almost always subjective polish.

The sharpest form is to point the adversary at the gate **coverage**, not the code: *"what real,
measurable coupling or structural debt exists that no current gate would catch?"* Still
adversarial — it forces finding blind spots, no false "looks fine" — but it **converges**,
because the set of load-bearing measurable invariants is finite. When that prompt returns
nothing you can trust the nothing: it is a checkable claim about the measurement system's
coverage, unlike "is the code clean?", whose "nothing" is just the adversary giving up.

Two riders:

- **Trigger on events, not a calendar.** Run after a *large structural change* (to catch what
  it just exposed — fixing one layer reveals the next; the layers are finite), or when a gate
  keeps fighting you (a missing or miscalibrated invariant). A scheduled audit reintroduces
  "it's audit time, find something."
- **Taste is out of scope.** A misleading name or a conceptually leaky-but-uncoupled
  abstraction is real but low-stakes and infinitely fundable. Handle it with a *time-boxed,
  explicitly non-recurring* readability pass under a "diminishing returns → stop" rule. Never
  put taste on repeat, and never let it pass as debt.
