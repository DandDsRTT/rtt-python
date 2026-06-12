# RTT Code Quality Audit — 2026-06-11

## How this audit was produced

A ten-dimension review (complexity, god modules, duplication, dead code, abstraction,
style, spaghetti/coupling, test quality, hygiene, coverage), run as 67 independent agents:
nine parallel dimension reviewers, then an **independent adversarial verifier per finding**
whose job was to refute it against the actual code. Findings below survived that check;
one was refuted and is listed at the end. Mechanical inputs: radon (cyclomatic
complexity + maintainability index), vulture (dead code), pylint (textual duplication),
and a full-suite coverage run (**2,634 tests, all passing, 95% line coverage**).

Line citations reference the audit snapshot (`ef2ba35`). Commits landed the same
afternoon (`9efa67a`…`789e394`) shift some line numbers by a few dozen lines and fixed
one finding outright (noted in Cluster A).

## Verdict

The codebase is in much better shape than the "deep audit before the home stretch" worry
suggests — in most places audits find rot, this repo is unusually clean. The debt is
**concentrated, not diffuse**: it lives almost entirely in three god blocks in `rtt/app`
(`_GridBuilder.__init__`, `_GridBuilder.layout`, and `app.py`'s `index()` page closure)
plus a handful of cross-file patterns that grew out of the parallel-agent build process
(clone handler families, hand-mirrored signatures, stringly id protocols). Critically,
the verifiers found these monoliths are **seam-rich rather than tangled** — linear
sequences of separable phases that communicate through `self`, with banner comments
already marking the seams — and they are pinned by an unusually strong test suite. So
the cleanup is largely mechanical, low-risk, and parallelizable.

| Dimension | State |
|---|---|
| Cyclomatic complexity | Floor-grade in 4 app files (`layout()` CC≈650 is the repo's worst block); library hotspots are honest textbook algorithms — leave them |
| God classes | 3 god blocks: `_GridBuilder.__init__` (1,051 lines, 200 attrs), `layout()` (2,101 lines), `index()` (1,872 lines, 77 closures) |
| Duplication | Zero textual duplication even at 6 lines; real duplication is **structural** — one algorithm instantiated 5–6× with different id strings |
| Dead code | Remarkably scarce: a handful of test-only members, 4 dead stores, a few unused imports |
| Feature envy | Mild: inline linear algebra in `service.py` that belongs in `rtt/library`; one private cross-module helper read |
| Abstraction | Library/app boundary genuinely healthy; debt is primitive obsession at the app pipeline's joints (26-param bus, 27 parallel dicts, stringly cell ids) |
| Style | Strong, distinctive house style; drift is bimodal type-hint/docstring coverage concentrated in `app.py`/`spreadsheet.py`/`marks.py` |
| Spaghetti | Module import graph is a clean DAG, no cycles; the tangle is *inside* the god blocks and the untyped 42-callback bridge |
| Test quality | High intrinsic quality (targeted assertions, zero skips); structural issues: one 8,596-line file, ~34–44s of byte-identical duplicate builds, zero parametrize |
| Coverage | 95% overall; the only real gap is `index()`'s interactive closures (see Coverage section) |
| Hygiene | Zero TODO/FIXME, prints, eval/exec, commented-out code; clean pins; the one systemic weakness is **zero logging** + ~19 silent exception-swallow sites |

## What is healthy — and should be left alone

The plan below deliberately does **not** touch these. Churning them would be negative value.

- **`rtt/library`** — every file maintainability grade A, 95–100% covered by ~1,260 unit
  tests. The complexity hotspots (`smith_normal_form_with_transforms` CC=35,
  `hnf_with_transform` CC=15, `resolve_target_intervals`, `get_complexity`) were each
  verified to be honest, documented, textbook-shaped algorithms; decomposition would
  obscure them.
- **The module dependency graph** — a clean DAG: `app → {editor, spreadsheet, service,
  presets, settings, tooltips, marks}`, `service → library` only. No cycles anywhere.
- **`layout.py`** — clean frozen-dataclass model boundary (this is also what makes the
  refactor pin-tests possible: `Layout` equality is exact).
- **`grid_tables.py`** — a successful prior extraction with a re-export facade; the plan
  reuses this exact pattern for `service.py`.
- **Undo/redo and persistence discipline** — single owner (`Editor`, immutable `_Doc`
  snapshots); storage access confined to `_doc_store()`.
- **The gesture machine's design** — the current single-`_Gesture` design is the
  documented good rewrite of a worse 10-flag system. The plan relocates it; it does not
  redesign it.
- **House hygiene** — zero TODO/FIXME/HACK, zero prints, zero eval/exec, disciplined
  `html.escape` at every text-into-HTML site, ~60 documented named layout constants, a
  six-line `requirements.txt` where every pin is used.
- **Refuted finding, for the record**: "Block/panel/tile are three names for one entity"
  — the verifier showed they are three *different* entities (content group / grey rect
  behind it / generic rect also used for washes and frames). No rename.

---

## Findings, clustered by root cause

41 confirmed findings collapse into nine clusters. Severity/effort/risk are the
verifier-adjusted values.

### A. The twice-derived display model — `plain_text_values` *(high → the drift is now fixed; structure remains, medium)*

`service.plain_text_values` (CC=35) re-derives every quantity `_GridBuilder.__init__`
derives — targets, tuning (a second optimizer solve), weights, sizes, complexities,
unchanged data — held in sync only by comments saying the two views "can't diverge."
They **had** diverged: verifiers reproduced four live numeric divergences (custom
prescaler shifting the tuning map 1201.434→1201.699¢; domain-basis vs standard-primes
complexity showing 2.322 where the grid shows 6.022; weights and unchanged-data drift).

**Status:** the drift itself was fixed on main the same afternoon
(`9efa67a` threads `custom_prescaler`/`nonprime_approach`/domain-basis complexity
through). What remains is the *structural* hazard: two parallel derivations that the next
feature can de-sync again, plus a doubled optimizer solve whenever the plain-text band is
on.

**Refactor:** invert the dependency. `_GridBuilder.__init__` already computes everything;
pass the derived bundle (a small frozen `DerivedQuantities` dataclass: tun, targets,
sizes, weights, complexities, unchanged data) into `plain_text_values`, which becomes a
pure formatter. Keep its self-deriving path as a fallback so `test_web_service.py`'s
direct calls are untouched. Verify by asserting `ptext_strings` equality across all
presets before/after.

### B. `spreadsheet.py` — the `_GridBuilder` god class *(high)*

One class is the whole file. Three compounding problems, all verified seam-rich:

1. **`layout()` is a 2,101-line method, CC≈650** (`spreadsheet.py:2555-4655`) — the worst
   block in the repo, emitting all 151 cell-append sites in one pass. AST dataflow
   confirmed it is ~20 banner-commented, independently-gated sections where only **four**
   locals cross section boundaries (`gtm_box`, `opt_box`, `approach_frame`,
   `chart_indicators`); everything else flows through `self`. Split is mechanical.
2. **`__init__` is a 1,051-line constructor, CC≈183, assigning exactly 200 self-attributes**
   (`:699-1749`). The first two phases are *already extracted*
   (`_resolve_show_flags`, `_resolve_prescaler_labels` — the file proves its own pattern);
   six more phases stay inline: derived-model resolution (59 `service.*` calls), tile
   declaration, column-band walk, control-height reserves, row-band walk, group geometry.
   The model/geometry seam at ~line 1326 is real but unlabeled.
3. **State is 27 parallel string-keyed dicts** (17 row dicts at `:1574-1582`, 6 column,
   4 group) backed by 9 clone `*_left(i)` accessor methods. The code documents its own
   failure mode: `group_n` is "keyed identically to group_left/group_elem so a column…
   can never be left out of the fan (the generators-column bug)."

Plus four intra-file clone families (the structural duplication pylint can't see):

- **The interval-list column family** (commas/targets/held/interest + detempering + U) is
  re-implemented per list at **five layers** of the builder — `__init__` scaffolding,
  quantities row, vec-minus re-homing, mapped/projection tiles, vectors row. The file
  already proves the table-driven cure in-house (`ss_lists`, `tuning_data`,
  `group_left/elem/n`). One `IntervalListSpec` descriptor table collapses them.
- **Units row/column: 15 clone emission loops** (`:2641-2717`), six column + nine row,
  differing only in (key, count, position fn, label); `const_units` just below already
  shows the table form. *(Verifier caution: row counts must use `d/k/mi/nh`, not the
  `*_shown` variants, or a unit cell appears over draft columns.)*
- **Eight near-identical projection-band grid loops** (`:3053-3147`) → one
  `_emit_mapped_grid()` helper (the P·V eigenvalue block stays bespoke). Net ~50–70 lines.
- **Tile caption/symbol/equivalence text is resolved in three places that override each
  other** (`_resolve_prescaler_labels` → `__init__` string-replaces → `layout()`'s
  caption pass with order-sensitive `.replace()` chains). Consolidate into one
  `_resolve_tile_text()` phase. *(Verifier caution: the width-floor helpers deliberately
  measure the **base** text while emission overrides it — feed the consolidated text to
  emission only, or geometry shifts → mockup violation.)*

### C. `app.py` — the god page *(high)*

1. **`index()` is a 1,872-line page closure with 77 nested defs** sharing 8 mutable
   one-element-list cells (63–80 `[0]` accesses) standing in for object attributes
   (`app.py:2741-4612`). Its 42 handlers are handed to the long-lived `_Reconciler` as an
   **untyped SimpleNamespace** back-filled after construction (`rec._cb = SimpleNamespace(…)`
   at `:4064-4107` into the `_cb = None` slot at `:1312`); for gridvalue cells the
   reconciler resolves handlers by **string name** via `getattr`. Nothing type-checks the
   contract; no handler is unit-testable without building the whole page. (Git shows the
   `_cb` bridge is residue of a prior partial extraction, not a deliberate pattern.)
2. **Six structurally-cloned ~40-line vector-list edit handlers** (`on_mapping/comma/
   unchanged/interest/held/target_cells_change`, `:2958-3190`, ~230 lines) — one 8-step
   algorithm instantiated six times, varying only in id template, dims, pending/commit
   setters, and validator. The replication cost is *proven in git*: one bugfix commit
   (`26d9459`) had to thread the identical `_rebase_edit_gesture()` line through all
   five; `_GRIDVALUE_SPECS` (`:221-234`) already half-declares the table.
   *(Verifier cautions: the factory needs hooks for real asymmetries — mapping's
   `temperament_boxes` guard, unchanged's silent variant, targets' reversed id order.)*
3. **The gesture lifecycle is split**: the `_Gesture` record lives on `_Reconciler`, but
   every transition is an `index()` closure (~20 closures mutate `rec.gesture`), crossed
   through the untyped `_cb` bridge. Two parallel **drag mechanisms** keep their state in
   different homes (closure boxes vs `_Reconciler` fields) — each lane's comments claim to
   mirror the other "EXACTLY", confirming drift-not-design.
4. **The `building[0]` reentrancy flag** is consulted at ~26 guard sites and hand-toggled
   mid-handler; `render()`'s wrap has **no try/finally**, so an exception mid-render
   strands the flag True and silently deadens every subsequent handler — a latent hang the
   refactor fixes for free with a `programmatic()` context manager.

### D. The 26-parameter build bus and the `_Doc` shotgun *(medium, cheap, high value)*

The same 26-field parameter list is hand-spelled at three sites (`_GridBuilder.__init__`,
`build()`, `Editor.layout`) and `build()` forwards **25 of them positionally** — with
adjacent same-typed pairs (`pending_interest`/`pending_held`, both `None`-default) where a
transposition is silent. A document field is additionally mirrored by hand in up to 9
places (`_Doc`, `_capture`, `_restore`, `serialize`, `load`, `_initial_doc`, plus the
three signatures; the preview snapshot packs 9 transients into a positional tuple).
Git confirms the list grew one parameter per feature, every time touching all sites.

**Refactor (graduated):** (1) *now:* make `build()` forward by keyword — mechanical,
zero-risk; (2) a frozen `GridInputs` dataclass built in `Editor.layout`, with
`build(state, settings=None, collapsed=None, **kw)` kept as a shim because ~300 test call
sites pass `state`/`settings` positionally; (3) derive `_capture`/`_restore`/`serialize`/
`load` from `dataclasses.fields(_Doc)` loops (preserving `_restore`'s deliberate
property bypass).

### E. `service.py` — five modules in one, plus feature envy *(medium)*

2,199 lines, 141 top-level functions: the state facade + edit ops, superspace/projection
math, 27 scheme-trait helpers, the text/EBK formatters, and 9 parsers — while the
docstring still claims it is just "the sole seam between the web UI and the RTT library."
Real linear algebra is hand-rolled inline (triple-loop matrix products at `:285-288`,
`:324-327`, rank loops, a pinv) while `matrix_utils.matrix_multiply` is imported *in the
same file* and the healthy grade-A library owns the vocabulary.

**Refactor:** split into a `service/` package using the proven `grid_tables` re-export
facade so `service.<NAME>` stays the public surface and **zero callers or tests change**
(`state.py`, `schemes.py`, `text.py`, `parse.py`, `projection.py`, `superspace.py`).
Move the superspace/held-basis math into a new `rtt/library/superspace.py` with thin
tuple-converting service wrappers, and move its tests down to `tests/library/unit/`.

### F. Stringly-typed protocols between the layers *(medium)*

- **Cell ids:** `spreadsheet.py` mints ~47 distinct `f"cell:…"` templates; `app.py`
  independently re-spells 21 of them and parses ids back at 11 `split(":")` sites. The
  templates drifted between parallel lanes: targets is `cell:vec:targets:{token}:{prime}`
  while held/interest are `cell:{group}:{prime}:{token}` — axis order flipped. A spelling
  drift produces **silent** cells-missing early-returns, not errors.
  **Refactor:** one `ids.py` owning typed mint + parse helpers; strings stay
  byte-identical (~390 references pin them in tests).
- **Per-interval-group dispatch data** is re-declared piecemeal in 8+ dict/tuple literals
  across three files — including a *verbatim duplicated dict* (`pending_idx` at
  `spreadsheet.py:2217` == `:3633`) and five copy-paste `_build_*_plus` builders.
  **Refactor:** one `INTERVAL_GROUPS` registry; derive the literals from it (assert
  equality with today's dicts in a unit test).

### G. Observability: silent failure everywhere *(medium, cheap)*

There is **no logging in the repo** (never has been, per git) while ~19 sites deliberately
swallow exceptions into `None`/`False`/dashed tiles. Consequences, verified:

- A genuine bug (e.g. the known pending optimizer crash) renders as a dashed tile,
  indistinguishable from "legitimately undefined," leaving zero trace.
- Ten bare `except Exception` sites trace to one root cause: `rtt/library/parsing.py` has
  **no error contract** (zero raises/validation — malformed text escapes as whatever
  builtin errors occur), so every caller defensively catches everything. One of those
  catches wraps a *state-mutating commit* (`editor.py:735-742`), so a bug in the dual
  computation reads as "invalid input, box reddened."
- The persisted document load is `except Exception: pass` (`app.py:2787-2792`) — a
  serialize/load regression would silently reset every returning user's document.
  *(Verifier caution: do NOT narrow this catch — `settings.from_persisted` raises
  `AttributeError` on old non-dict blobs and would crash every refresh. Keep the broad
  catch; add `logger.exception` + truncated `repr(stored)`.)*

**Refactor:** additive logging at every swallow site (UI untouched, suite stays green);
give `parse_temperament_data` a `ParseError` contract and narrow the parser catches; hoist
the copy-pasted validation block (`app.py:3447/3679`); optionally later, drop
`IndexError`/`TypeError` from catch tuples site-by-site so shape bugs fail loudly.

### H. The test suite: high quality, structural friction *(medium)*

- **~34–44s of the fast pass is byte-identical duplicate `spreadsheet.build` calls**
  (measured: 857 calls, 465 exact-duplicate args; `Layout` is frozen, nothing mutates it).
  A memoizing **in-file** autouse fixture wins ~45% of the whole fast pass.
  *(Verifier caution: in-file, not a `tests/app` conftest — the render tests re-import
  `rtt.*` and would hold stale references.)*
- **`test_web_spreadsheet.py` is 8,596 lines / 611 tests** (~40% of all suite lines),
  organized by historical build phase ("Phase 4E.1") rather than feature, with
  section-local helpers that lift out cleanly → split into a `tests/app/unit/spreadsheet/`
  package + local conftest. Pure moves; prove with `--collect-only` count (611).
- **Zero `parametrize` in that file** (134 uses elsewhere in the repo) — parametrize only
  the genuinely table-shaped clusters; keep narrative tests as documentation.
- **523 copies** of `{c.id: c for c in lay.cells}`, **176 meantone literals**, 31 inline
  settings spreads, and no `tests/app` conftest → tiny shared helpers.

### I. Style and small cleanups *(low–medium, mostly mechanical)*

- **Bimodal type hints** (returns annotated / total): `editor.py` 128/131, `presets.py`
  12/12 — vs `app.py` 30/246, `spreadsheet.py` 29/113, `marks.py` 0/13; `_GridBuilder`
  4/78. Every module already has `from __future__ import annotations`, so annotating is
  pure-string, zero-runtime. Land module-by-module to limit merge conflicts.
- **`_GridBuilder` uses leading-`#` comment blocks where the file's own convention is
  docstrings** (67/78 methods undocstringed); mechanical conversion, plus rejoining one
  comment that was *split in half* across lines 1581/1858 by the repo reorg.
- **`marks.py`'s entire 24-name API is underscore-private** yet exists to be imported
  (`app.py` imports 14 of the names); de-underscore the consumed names (touches ~2 test
  files that reach them via `app.*`); `_qbez` is a dead import.
- **Dead code** (all verified zero-caller): `service.parse_mapping` (superseded by
  `parse_mapping_state`; behavior-identical, tests portable), `Editor.clear_custom_prescaler`
  (docstring falsely claims live dependents) + `Editor.can_remove_comma` (test-only), four
  dead `self.X = X` stores in `__init__` (`:718,726-728`), unused imports
  (`math.lcm`, duplicate `replace`), unused `is_row` parameter, `ROW_LABELED_TILES`.
- **Stale handoff docs at repo root** (`projection-handoff.md`,
  `nonstandard-domain-handoff.md`, likely `FORM_FEATURE_HANDOFF.md`) — self-described
  "delete me when done" docs whose features have landed. Confirm and remove.
- Noted, deliberately **not** planned: cell-kind token naming normalization (load-bearing
  strings, low value), `fold`/`collapsed` vocabulary, callback-name prefixes, hosted-mode
  cookie-secret fallback (worth a one-line startup warning, nothing more).

---

## Coverage analysis

95% overall (7,719 statements, 372 missed). Per-file: everything ≥95% except
**`app.py` at 89%**.

- **229 of `app.py`'s 270 missed lines sit inside `index()`'s closures** — precisely the
  interactive paths (drag handlers, hover/preview branches, pending-draft and invalid-commit
  arms of the edit handlers, keyboard shortcuts) that in-process render tests structurally
  cannot trigger. This is the known client-JS blind spot; the practical mitigations are
  (a) the Phase-2 extraction of handler logic into testable units, and (b) the established
  real-browser probe for wiring.
- **The six clone edit handlers are only partially covered** (commit paths yes;
  pending-draft/preview/invalid arms patchy) — which is why the plan adds tests *before*
  consolidating them.
- `service.py` (96%) and `editor.py` (96%) gaps are almost exactly the **silent `except`
  arms** from Cluster G — the swallowed paths are also the untested paths.
- `spreadsheet.py` is 99% covered despite being the complexity worst-case: the layout
  refactors are exceptionally well pinned (611 tests asserting exact ids/geometry/text,
  plus 170+ render tests).

---

## The refactoring plan

**Ground rules** (apply to every item):

- Behavior-preserving: same cells, same ids, same strings, same pixel geometry. The mockup
  stays the spec; nothing here adds or removes UI.
- Gate per landing: fast pass while iterating; **full suite (incl. render tests) before
  every ff-merge**; a real-browser probe after any event-wiring change.
- For `spreadsheet.py` phases: add a temporary **pin harness** first — build `Layout` for
  every preset × settings combination, assert frozen-dataclass equality before/after
  (cheap, exact, deletable afterwards).
- One agent lane per file at a time; the lanes below are chosen to be disjoint.

### Phase 0 — Quick wins (independent small tasks, parallelizable now)

| # | Task | Effort | Risk |
|---|---|---|---|
| 0.1 | `build()` forwards all args **by keyword** (kills the silent-transposition hazard) | minutes | none |
| 0.2 | Test-speed: in-file memoizing build fixture in `test_web_spreadsheet.py` (~75s fast pass → ~40s) | small | low |
| 0.3 | Logging: `logging.getLogger` in service/editor/app; log at every swallow site; `logger.exception` + truncated blob repr at the doc-load catch (keep the broad catch) | small | low |
| 0.4 | Dead-code sweep: `parse_mapping` (port its round-trip asserts to `parse_mapping_state`), `clear_custom_prescaler` + `can_remove_comma`, 4 dead stores, unused imports/params, `ROW_LABELED_TILES` | small | low |
| 0.5 | Confirm + remove stale root handoff docs (user sign-off — they're the user's notes) | trivial | — |

### Phase 1 — Single derivation pipeline (one focused task)

Build the `DerivedQuantities` bundle in `_GridBuilder.__init__` and pass it into
`plain_text_values` (self-derivation kept as fallback for direct test callers). Assert
`ptext_strings` equality across all presets. Removes the divergence *class* (the instance
was fixed by `9efa67a`) and halves the optimizer solves when the plain-text band is on.
*Effort: 1 session. Risk: medium (the equality assert + service tests gate it).*

### Phase 2 — The three god blocks (three parallel lanes, the bulk of the work)

**Lane A — `spreadsheet.py`** *(serialized within the file; ~4–6 sessions)*
1. Pin harness, then split `layout()` into ~20 ordered `_emit_*` methods (verbatim cuts;
   the four cross-section locals become returns/fields; 5 section-local closures move with
   their sections). The CC≈650 block becomes a ~40-line table of contents.
2. Collapse the clone families inside the now-small emitters: units-row/col tables,
   `_emit_mapped_grid`, the `IntervalListSpec` descriptor table, `_resolve_tile_text`
   (emission-only — width floors keep reading base text).
3. Split `__init__` along its phase seams (`_resolve_interval_sets`, `_declare_tiles`,
   `_layout_columns`, `_layout_rows`, `_init_group_geometry`…), continuing the file's own
   extracted-phase pattern; thread the cross-phase locals explicitly.
4. Introduce `GridInputs` (Phase D step 2) and, last and optional because largest,
   promote the 27 parallel dicts to `RowBand`/`ColumnGroup` dataclasses (~242 mechanical
   call-site edits; converts mid-layout KeyErrors into construction-time errors).

**Lane B — `app.py`** *(serialized within the file; ~5–7 sessions)*
1. Low-risk peels: pure HTML/SVG/font string builders → `render_html.py`; the settings
   drawer / Show-panel build → `show_panel.py` (returns its element refs; re-export from
   `app` for the two test files that import via `app.*`).
2. **Add the missing handler tests first** (pending-draft, preview, invalid-commit arms —
   the coverage gaps), then consolidate the six clone handlers into one parameterized
   `_grid_edit(spec, preview)` + per-group spec table, preserving the verified
   asymmetries. Browser-probe the edit flows.
3. Reify the page: `index()` closures → a `_Page` class (list-boxes become attributes;
   `rec._cb = page` replaces the SimpleNamespace — the method names already match);
   `building[0]` → a `programmatic()` context manager **with try/finally** (fixes the
   latent stuck-flag hang). Browser-probe.
4. `GestureController`: relocate (don't redesign) the `_Gesture` record + ~20 transition
   closures into one home with injected render/paint callables; `rec.gesture` stays as a
   delegating property. Then unify the two drag lanes' state into it, routing the reorder
   lane through the existing `combine_*` choreography (preserve the dragenter dedupe and
   no-op-drop render). Browser-probe.

**Lane C — `service.py` + library** *(independent of A/B; ~2–3 sessions)*
1. Split into a `service/` package behind the re-export facade (zero caller changes);
   one placement decision needed for the schemes↔text mutual calls.
2. Move the superspace/projection/held-basis linear algebra to
   `rtt/library/superspace.py` (+ move its tests to `tests/library/unit/`); service keeps
   thin tuple-converting wrappers.
3. `ParseError` contract in `rtt/library/parsing.py`; narrow the ten bare excepts
   (excluding the deliberate doc-load fallback); hoist the duplicated validation block.

### Phase 3 — Cross-file protocols (after Phase 2 lanes settle; ~2 sessions)

- `ids.py`: typed mint/parse for the cell-id vocabulary, used at both ends
  (strings byte-identical). Document the targets-axis-order quirk in one place.
- `INTERVAL_GROUPS` registry deriving the scattered dispatch literals (equality-asserted).
- `_Doc` shotgun: derive `_capture`/`_restore`/`serialize`/`load` from
  `dataclasses.fields(_Doc)`; transients tuple → small dataclass.

### Phase 4 — Polish (rideable, any time, low priority)

- Type hints module-by-module toward the `editor.py` standard (pure-string; consider
  adopting pyright/mypy once the `_Page`/Protocol refactor gives it something to verify).
- `_GridBuilder` `#`-comments → docstrings (+ rejoin the split orphan).
- `marks.py` de-underscore; drop the dead `_qbez` import.
- Test-file split into `tests/app/unit/spreadsheet/` package + shared helpers
  (`MEANTONE`, `cells_by_id`) + targeted parametrize. **Schedule this in a quiet window**
  — it is the repo's largest merge surface, so do it when no production lanes are in
  flight, or last.

### Sequencing rationale

Phase 0 is risk-free and makes every later loop faster and observable. Phase 1 closes the
only correctness-class issue. Phase 2's three lanes are file-disjoint, matching the
parallel-agent workflow; within each file the steps are ordered so each one makes the next
smaller (split first, then dedupe inside the pieces). Phase 3 needs the Phase-2 shapes to
exist. Estimated total: **roughly 15–20 focused agent sessions**, every one independently
landable behind a green full suite.

---

## Appendix — audit inventory

**Confirmed (41 findings → 9 clusters above).** Verifier-rejected: 1 (Block/panel/tile,
see "What is healthy"). Unverified low-priority notes retained for opportunistic cleanup:
`_Reconciler`'s 29 parallel handle dicts (medium candidate — revisit during Lane B step 3),
layout-diff/column-token utilities stranded in the builder module, two parallel
text-measurement systems, `_Reconciler` micro-motifs, EBK mark-builder unused parameters,
test-only service helpers (`unchanged_interval_ratios`, `is_euclidean`), cell-kind token
naming, callback naming, import wrinkles (star-import `__all__`), solve-failure exception
tuple constant, out-of-repo comment references, `fold`/`collapsed` vocabulary, unit-scope
tests inside integration files, lazy-import inconsistency in render tests, inline-JS
consolidation, cookie-secret startup warning.

**Method stats:** 67 agents, ~5.3M tokens, 1,570 tool calls; every confirmed finding
re-verified against the code by an independent skeptic agent; coverage from a full
2,634-test run (420s) with per-line annotation.
