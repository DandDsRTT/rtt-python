# `_GridBuilder` pipeline split — design spike

**Status: DESIGN ONLY. No production code in this PR. Requesting review before any
implementation chip starts.**

## 0. Summary

`_GridBuilder` (`rtt/app/spreadsheet.py`) is a god-object built from ~12 mixins. Only
`_ResolveMixin` has an `__init__`; the other 11 are method-bags that presuppose its state.
A grep of every `self.<attr>` written in one of the `spreadsheet_*.py` files and read in a
*different* one finds **93 shared mutable attributes** — written in one mixin, read across
five or six others. No mixin can be instantiated or unit-tested alone; zero tests do so.

The domain layer is already clean: `resolve()` produces a frozen `Resolved` value object
(`spreadsheet_resolved.py`). The geometry and emit layers are not. This doc proposes finishing
the pipeline:

```
inputs ──► resolve(...) ──► Resolved (frozen, EXISTS)
                              │
                              ▼
                       compute_geometry(resolved, inputs) ──► Geometry (frozen, NEW)
                              │
                              ▼
            emit_x(resolved, geometry, ctx) ──► EmitResult   (PURE FUNCTIONS, one per band)
                              │
                              ▼
            assemble(...) + cell post-passes ──► Layout
```

End state: every emitter is `emit_x(resolved, geometry, …) -> EmitResult` — a pure function you
unit-test by passing a `Resolved` + `Geometry` and asserting the returned cells. No page, no
render, no `self`.

This is a direct continuation of the "delete the mirror / freeze a draft" work that produced
`Resolved`: the same draft→freeze pattern, applied to the geometry tier.

---

## 1. How it works today (verified against the code)

`_ResolveMixin._build` (`spreadsheet_resolve.py:79`) runs in three lifecycle stages on `self`:

1. **Resolve.** Build a `SimpleNamespace` `draft`, fill it with the RTT math, then
   `self.resolved = freeze(draft)` (`spreadsheet_resolve.py:101`). If `resolve_only`, return
   here — this is the `spreadsheet.resolve()` path.
2. **Geometry.** Only if not `resolve_only`. Compute all position/size/structure data **into
   `self.X`** via the `_LayoutMixin` methods, in a strict dependency order
   (`spreadsheet_resolve.py:105-121`):
   - `_define_col_bands` → matlabel widths, `etpick_w`, `row_handle_w`, `size_factor`,
     `size_rows`, `prescale_rows`, `all_interval_simplicity_weight`, `col_header`; returns
     `col_bands, content_x0`.
   - `_define_row_bands` → `present_caption_rows`; returns `row_bands`.
   - `_layout_columns` → `col_x`, `col_w`, `content_w`, `content_x`, `col_collapsible`,
     `open_col_w`, `total_w`, and the per-group origins `primes_x` … `ssprimes_x`.
   - `_resolve_tile_extras` → the tuning-panel control sizing/flags (`gtm_chart`, `lbox_ctrl`,
     `cbox_ctrl`, `opt_ctrl`, `slope_ctrl`, `show_approach`, their `*_extra` heights, etc.);
     returns `tile_extra`. **Note: this method lives in `spreadsheet_resolve.py` but runs
     after `_layout_columns` and reads `self.col_open(...)` — it is geometry-dependent, not
     part of resolve.**
   - `_init_row_geometry` → `header_y`, `col_node_y`, `branch_top_y`, `FAN`, empty `rows`,
     `row_cpick`.
   - `_resolve_ptext_strings` → `ptext_strings`.
   - `_layout_rows` → fills `rows` (`dict[str, RowBand]`), `total_h`, `fanout_y`.
   - `_init_group_geometry` → `group_elem`, `group_left`, `group_n`, `group_ratio`,
     `plus_stub_x`, `row_plus_y`.
3. **Emit.** `_GridBuilder.layout()` (`spreadsheet.py:39`) seeds `self.cells/lines/blocks`,
   calls `_emit_all()` (28 ordered emitter calls, `spreadsheet.py:67-104`) which read all of
   the above off `self` and append to the accumulators, then packs `Layout`.

`_GeometryMixin` (`spreadsheet_geometry.py`) is a 64-method grab-bag straddling stages 2 and 3:
some methods *measure* (feed stage-2 layout), some *query* frozen positions (serve stage-3
emit), and a few are not geometry at all.

### The shared-state census (93 attributes)

Classified by **semantics**, not by which file happens to write them:

| Class | Count | Examples | Disposition |
|---|---|---|---|
| **A. Output accumulators** | 4 | `cells`, `lines`, `blocks`, `_control_region_boxes` | Become emitter *return values* + cell post-passes; never frozen state |
| **B. Frozen domain model** | 1 | `resolved` | Exists — `Resolved` |
| **C. Raw inputs (forwarded ctor args)** | ~12 | `state`, `settings`, `collapsed`, `tuning_scheme`, `target_spec`, `range_mode`, `nonprime_approach`, `pending_element`, `pending_mapping_row`, `preview_remove`, `tuning_optimized`, `targets_in_use`, `custom_prescaler`, `custom_weights`, `held_basis_ratios`, `superspace_generator_tuning` | Bundle into a frozen `BuildContext`; pass to emitters that need them |
| **D. Resolve-extra show flags** | 10 | `show_projection`, `show_ss_projection`, `show_identity_objects`, `show_interval_vectors`, `_complexity_shown`, `_prescaling_shown`, `_lbox_show`, `_cbox_show`, `show_cell_units`, `gridded` | **Fold into `Resolved.flags`** — pure functions of settings+scheme |
| **E. Geometry: positions/sizes/structure** | ~50 | `col_x`, `rows`, `node_edge`, `group_left`, `total_w`, `declared_tiles`, … | **The new frozen `Geometry`** (§2) |
| **F. Geometry: tuning-panel control extras** | ~15 | `gtm_chart`, `lbox_ctrl`, `cbox_extra`, `opt_ctrl`, `slope_locked`, `mean_damage_caption`, … | Geometry sub-record `Geometry.controls` (§2.3) |

Classes A, C, D are *not* geometry and are pulled out separately so `Geometry` stays a pure
position/size record.

---

## 2. The `Geometry` record

`Geometry` is built by a `compute_geometry(resolved, ctx) -> Geometry` function that mirrors the
existing `freeze(draft)` pattern: the stage-2 methods write into a mutable draft namespace in
dependency order, and `Geometry(...)` is frozen **once** at the end (the geometry phase cannot
be one-shot frozen mid-way — see the DAG in §4).

Proposed split into three frozen sub-records plus the top-level record, so each emitter depends
on the narrowest slice it needs.

### 2.1 `Geometry` (top level — page-global scalars + the sub-records)

```python
@dataclass(frozen=True)
class Geometry:
    # page-global position scalars
    total_w: float
    total_h: float
    node_x: float
    node_edge: float
    header_y: float
    col_node_y: float
    branch_top_y: float
    fanout_y: float
    FAN: float

    # complexity-prescaling page scalars (read by layout + emit_tuning + decorations)
    size_factor: float
    size_rows: int
    prescale_rows: int
    all_interval_simplicity_weight: bool

    # structural: which tiles exist (read by geometry queries, controls, decorations)
    tiles: tuple              # tuple[(block_id, rkey, ckey), ...]
    declared_tiles: frozenset # {(rkey, ckey), ...}
    collapsed: frozenset      # echoed from ctx so openness predicates are pure over Geometry

    cols: ColumnGeometry
    rowsg: RowGeometry
    groups: GroupGeometry
    controls: ControlGeometry
```

`collapsed` is carried here so the openness predicates (`col_open` / `row_open` / `tile_open`)
become pure functions over `Geometry` alone (§3, group *visibility*).

### 2.2 `ColumnGeometry`, `RowGeometry`, `GroupGeometry`

```python
@dataclass(frozen=True)
class ColumnGeometry:
    col_x: Mapping[str, float]            # left edge per column key
    col_w: Mapping[str, float]            # hug width per column key
    content_x: Mapping[str, float]        # centered content left per key
    content_w: Mapping[str, float]        # natural content width per key
    open_col_w: Mapping[str, float]       # width if not collapsed
    col_collapsible: Mapping[str, bool]
    col_header: Mapping[str, str]
    present_caption_rows: frozenset
    # gutter widths (currently matlabel_*/row_handle_w/etpick_w)
    matlabel_primes_w: float
    matlabel_ssprimes_w: float
    matlabel_other_w: Mapping[str, float]
    row_handle_w: float
    etpick_w: float
    # per-group x-origins (today: primes_x, commas_x, …; all are content_x.get(key))
    # KEEP as a convenience map rather than 9 named fields:
    group_x: Mapping[str, float]          # {"primes","commas","targets","interest","held",
                                          #  "detempering","canongens","ssgens","ssprimes"}

@dataclass(frozen=True)
class RowGeometry:
    rows: Mapping[str, RowBand]           # RowBand already exists (spreadsheet_models.py)
    row_cpick: Mapping[str, float]
    row_plus_y: Mapping[str, float]

@dataclass(frozen=True)
class GroupGeometry:
    group_elem: Mapping[str, str]
    group_n: Mapping[str, int]
    plus_stub_x: Mapping[str, float]
    # callable dicts -> precomputed DATA (see §2.4)
    group_left: Mapping[str, tuple[float, ...]]   # left x per index, precomputed
    group_ratio: Mapping[str, tuple]              # ratio per index, precomputed
```

The nine `*_x` origins (`primes_x`, `commas_x`, … `ssprimes_x`, set at
`spreadsheet_layout.py:299-307`) are all just `content_x.get(key)`. Collapsing them into one
`group_x` map removes nine near-duplicate fields and nine `self.<g>_x` reads; the `*_left`
coordinate functions index `group_x[key]` instead of a bespoke attribute.

### 2.3 `ControlGeometry` (the tuning-panel extras — class F)

These are computed in `_resolve_tile_extras` (`spreadsheet_resolve.py:448`), depend on column
geometry (`col_open`), and are read only by `emit_tuning`:

```python
@dataclass(frozen=True)
class ControlGeometry:
    gtm_chart: bool;       gtm_extra: float
    lbox_ctrl: bool;       lbox_extra: float
    cbox_ctrl: bool;       cbox_extra: float
    opt_ctrl: bool;        opt_extra: float;   opt_cap_lines: int
    show_approach: bool;   approach_extra: float
    slope_ctrl: bool;      slope_extra: float; slope_locked: bool
    mean_damage_caption: str
```

(The `approach_box` attribute that `emit_tuning` *writes* and `layout()` reads is an output, not
input — it rides on `EmitResult` from `emit_tuning`, see §3.)

### 2.4 Decisions on the tricky fields

- **`group_left`, `group_ratio` are dicts of callables today** (`spreadsheet_layout.py:392,399`
  hold `self.gen_left`, lambdas closing over `_r`). A frozen record *can* hold callables, but
  they'd close over `self`, defeating the split. **Recommendation: precompute to data.** Since
  `group_n[key]` is known at geometry time, store
  `group_left[key] = tuple(left_fn(i) for i in range(group_n[key]))` and likewise for
  `group_ratio`. Coordinate queries then index a tuple. This removes the last `self`-closure and
  is the single change most likely to shift a float — guard it with the snapshot net (§4).
- **`superspace_tun()` memoizes on `self._ss_tun`** (`spreadsheet_geometry.py:61`) and
  `freeze()` deliberately stores `Tuning.ss_tun=None` (`spreadsheet_resolved.py:237`). This lazy
  hole is read by both ptext-building and `emit_tuning`. **Recommendation: compute it once during
  resolve and store it in `Resolved.tuning.ss_tun`** (eliminating the lazy `self` cache), or, if
  the cost matters on the resolve-only path, compute once in `compute_geometry` and store on
  `ControlGeometry`. Either kills the mutable cache.
- **`show_*` flags (class D)** are pure functions of `settings`/`tuning_scheme`/`collapsed`.
  They belong in `Resolved.flags`, not `Geometry`. `_complexity_shown`/`_prescaling_shown`
  rename to `complexity_shown`/`prescaling_shown`. This is an independent, low-risk move that
  shrinks the census before the geometry work.
- **`col_header`, `present_caption_rows`, `tiles`, `declared_tiles`** are *structural* (what
  exists), not positional, but they're produced in the geometry phase and read by geometry
  queries / controls / decorations. Keep them in `Geometry` (the structural slice) rather than
  splitting a fourth tier — they have no consumers before geometry runs.

### 2.5 Transient / not promoted

Attributes written and read only *within one file* are not shared and stay local (already
excluded from the 93). The geometry draft will also hold purely intermediate values
(`col_bands`, `content_x0`, `tile_extra`, `rows_top_y`, loop scratch in `_layout_columns` /
`_layout_rows`) that are consumed during `compute_geometry` and **not** copied into the frozen
`Geometry`.

---

## 3. Emitter target signatures

Each emitter becomes a module-level pure function returning its contributions instead of
appending to `self`. Shared return type:

```python
@dataclass(frozen=True)
class EmitResult:
    cells: tuple[CellBox, ...] = ()
    lines: tuple[Line, ...] = ()
    blocks: tuple[Block, ...] = ()
    region_boxes: tuple[Block, ...] = ()   # today's _control_region_boxes
    extra: object = None                    # emitter-specific (e.g. approach_box, chart_indicators)
```

`BuildContext` bundles the raw inputs (class C) so signatures stay short:

```python
@dataclass(frozen=True)
class BuildContext:
    state: object
    settings: Mapping
    tuning_scheme: object
    target_spec: object
    range_mode: str
    nonprime_approach: str
    pending_element: object
    pending_mapping_row: object
    preview_remove: object
    tuning_optimized: bool
    targets_in_use: bool
    # forwarded tuning/prescaler inputs read by closed_form/emit_tuning:
    custom_prescaler: object
    custom_weights: object
    held_basis_ratios: object
    superspace_generator_tuning: object
```

Signatures, derived from each file's measured cross-file read-set (see the census script in §6):

| Emitter (current mixin) | reads | Proposed signature |
|---|---|---|
| `emit_vectors` (10) | resolved, geometry, ctx(state, pending_element) | `emit_vectors(resolved, geometry, ctx) -> EmitResult` |
| `brackets` (7) | resolved, geometry, ctx(pending_mapping_row) | `emit_brackets(resolved, geometry, ctx) -> EmitResult` |
| `closed_form` (7) | resolved, geometry(group_ratio), ctx(state, tuning_scheme, custom_*) | `emit_closed_form(resolved, geometry, ctx) -> EmitResult` |
| `emit_mapping` (12) | resolved, geometry, ctx(state, settings, pending_mapping_row) | `emit_mapping(resolved, geometry, ctx) -> EmitResult` |
| `emit_matrix` (18) | resolved, geometry, ctx(state, pending_element) | `emit_matrix(resolved, geometry, ctx) -> EmitResult` |
| `controls` (18) | resolved, geometry, ctx(state, settings, target_spec, preview_remove, pending_mapping_row), **prior cells** | `emit_controls(resolved, geometry, ctx, cells) -> EmitResult` |
| `emit_tuning` (29) | resolved, geometry(.controls), ctx(state, tuning_scheme, range_mode, tuning_optimized) | `emit_tuning(resolved, geometry, ctx) -> EmitResult` (extra=`(approach_box, chart_indicators)`) |
| `decorations` (31) | resolved, geometry, ctx(settings, tuning_scheme), **prior cells/blocks** | `emit_decorations(resolved, geometry, ctx, accum) -> EmitResult` |

**Ordering / read-back dependencies (must be preserved):**

- `controls` and `decorations` *read the accumulated cells*, not just append. `controls` runs
  whole-list rewrite passes — filter `GRIDDED_KINDS`, blank numbers, `preview_remove`, dual
  preview (`spreadsheet_controls.py:242-297`) — and `decorations` frames regions around already
  emitted cells. These take the growing accumulator as an argument.
- `emit_tuning` returns `chart_indicators` and `approach_box` as `extra`; the orchestrator
  threads `chart_indicators` into `emit_charts`/`emit_damage_row` and `approach_box` into both
  `emit_panels` and the final `Layout(...)`.
- `_emit_all`'s 28-call order (`spreadsheet.py:67-104`) is significant and is preserved verbatim
  by the orchestrator; the refactor changes *who owns the data*, never the call sequence.

**Cell post-passes (class A, not emitters).** `_apply_value_display_filters` and the
preview/gridded rewrites become `transform_cells(cells, resolved, ctx) -> tuple[CellBox, ...]`,
applied by the orchestrator after the emit loop. They are pure list→list transforms and are the
easiest piece to test in isolation.

---

## 4. Re-grouping `_GeometryMixin`'s 64 methods

"Geometry" today conflates **three different lifecycle roles**. The regrouping sorts every
method into one, which is what makes the split tractable:

### Role 1 — MEASURE (build-time; feeds `compute_geometry`, not query-time)

These compute widths/heights that *size* columns and rows. They run during stage 2 and must move
into the geometry **builder** module (alongside `_define_col_bands` / `_layout_*`), not the
query API. Sub-concern **`measure/`**:

- band sizing: `_commas_band_w`, `_caption_wrap_w`, `caption_band`, `control_dims`,
  `control_band_h`, `preset_cap`, `preset_band_h`, `formchooser_band_h`, `ptext_band`,
  `ptext_height`, `ptext_editable`
- column floors: `_caption_floor`, `_symbol_floor`, `_control_floor`, `_form_subscripted`,
  `_projection_superspace_tail`, `_weight_simplicity_header`

### Role 2 — QUERY (read-time; pure functions over frozen `Geometry` + `Resolved`)

Serve the emitters. Become free functions `f(geometry, …)` / `f(resolved, geometry, …)`:

- **coordinates** (cell origins): `prime_left`, `comma_left`, `target_left`, `interest_left`,
  `held_left`, `detempering_left`, `gen_left`, `canongen_left`, `ss_gen_left`, `ss_prime_left`,
  `comma_value_pos`, `sub_axis_x`, `col_plus_x`, `map_top`, `proj_top`, `canon_top`, `vec_top`,
  `ss_vec_top`, `ss_map_top`, `ss_proj_top`
- **rects / spans**: `content_box`, `tile_box`, `tile_span_box`, `matrix_span`, `panel_rect`,
  `cpick_band_y`, `ptext_band_y`, `frame_top_y`, `frame_brace_y`
- **gutters**: `matlabel_gutter_w`, `handle_gutter_w`, `etpick_left_pad`, `outer_gutter_w`
- **visibility / openness**: `col_open`, `row_open`, `tile_open`, `_plus_shows`
- **units**: `tile_unit`, `cell_unit`
- **column identity**: `col_token`, `pending_col_token`, `_pending_draft_idx`

(The Role-2 *coordinate* functions are also what feed the §2.4 precompute of `group_left` /
`group_ratio` — once those are data, most coordinate functions reduce to a tuple index.)

### Role 3 — MISFILED (not geometry at all; relocate)

- `superspace_tun` → resolve/tuning (memoized service call on `state`; fold per §2.4)
- `displayed_optimization_power`, `displayed_mean_damage_power` → tuning-scheme query helpers
  (thin `service` passthroughs; belong with `emit_tuning` or a `service` shim)
- `_element_cell_kind` → cell-construction helper (emit layer)
- `_voice` → emit helper; it *mutates* `self.cells[-1]` (`spreadsheet_geometry.py:406`), pure
  emit-time audio attachment, has no place in a frozen geometry API

This is the core insight for the regrouping: the "junk drawer" is junk precisely because it mixes
*functions that build layout* with *functions that read it* with *functions that do neither*.

---

## 5. Incremental migration sequence

Each step lands behind the full render suite
(`.venv/bin/python -m pytest -q`; `tests/app/integration/test_web_render.py` is the behavioral
gate — 171 in-process page renders) and must produce a **byte-identical `Layout`**. Steps are
ordered so each is small and independently revertible.

**Step 0 — Snapshot net (test-only, no prod change).** Add golden `Layout` snapshot tests for a
spread of representative configs — default, maximized, superspace/nonstandard domain,
all-interval, projection on, custom weights, a collapsed-column state. Serialize the full
`Layout` (sizes, every `CellBox`, lines, blocks) and assert equality. This is the safety net that
makes "byte-identical" a *checked* invariant for every later step. `build()` is already exercised
by 700+ `test_web_spreadsheet.py` cases; the snapshot adds whole-`Layout` equality on top.

**Step 1 — Fold class-D show flags into `Resolved.flags`.** Move `show_projection`,
`show_ss_projection`, `show_identity_objects`, `show_interval_vectors`, `complexity_shown`,
`prescaling_shown`, `_lbox_show`→`lbox_shown`, `_cbox_show`→`cbox_shown`, `show_cell_units`,
`gridded` into `Resolved.flags`. Pure data move; update the ~handful of layout/geometry reads.
Independent of the geometry record; shrinks the census first.

**Step 2 — Introduce `Geometry` as a parallel structure, delegating.** Add the dataclasses (§2)
and `compute_geometry(resolved, ctx)`. Have the geometry phase build a draft and `freeze` it into
`self.geometry`, then make the existing `self.<attr>` *read-through properties* onto
`self.geometry.<…>`. No emitter changes yet; behavior identical. This proves `Geometry` captures
every field. (Mirrors how `Resolved` was introduced beside the draft before consumers migrated.)

**Step 3 — Precompute the callable dicts to data (§2.4).** Convert `group_left` / `group_ratio`
to tuples and `superspace_tun` to a stored value. Highest float-drift risk → do it as its own
step so the snapshot pinpoints any regression.

**Step 4 — Split `_GeometryMixin` by role (§4).** Move Role-1 *measure* methods into the
geometry-builder module; move Role-2 *query* methods into a `geometry_query` module of pure
functions over `Geometry`/`Resolved`; relocate Role-3 misfits. Do it one sub-concern at a time
(coordinates, then rects, then gutters, …), each its own commit + gate. Methods stay callable via
thin shims on `_GridBuilder` until their emitter migrates.

**Step 5 — Migrate `_resolve_tile_extras` into the geometry phase.** It currently lives in
`spreadsheet_resolve.py` but is geometry-dependent; move it into `compute_geometry` producing
`ControlGeometry`. (Crosses the current module boundary — call out in review.)

**Step 6 — Convert emitters to pure functions, smallest read-set first.** Order:
`emit_vectors` (10) → `brackets` (7) → `closed_form` (7) → `emit_mapping` (12) →
`emit_matrix` (18) → `controls` (18) → `emit_tuning` (29) → `decorations` (31). For each: change
the method to a free `emit_x(resolved, geometry, ctx[, accum]) -> EmitResult`, return cells/lines
instead of appending, and have the orchestrator accumulate. Gate after every single emitter — the
leaves are nearly mechanical; `controls`/`decorations` need the accumulator threaded.

**Step 7 — Extract cell post-passes.** Turn the `controls` rewrite passes and
`_apply_value_display_filters` into `transform_cells(...)` pure functions applied by the
orchestrator after the emit loop.

**Step 8 — Collapse the god-object.** `_GridBuilder.layout()` becomes a thin orchestrator:
`resolved = resolve(...)`, `geometry = compute_geometry(resolved, ctx)`, run the 28 emitters in
the existing order accumulating `EmitResult`s, apply post-passes, pack `Layout`. Delete the mixin
composition. `spreadsheet.build()` / `spreadsheet.resolve()` public API is unchanged throughout
(`editor_layout.py` + tests call only those two).

---

## 6. Risks & call-outs

- **Geometry interdependency DAG.** The stage-2 order is load-bearing and must be reproduced
  exactly inside `compute_geometry`:
  `floors/measure → col_x/col_w → (col_open) → tile_extras + ptext_strings + row_bands → rows →
  group geometry`. `group_left`/`group_ratio` need every `*_x` **and** `rows`; `_resolve_tile_extras`
  needs `col_open` (column geometry); `_layout_rows` needs `tile_extra`. Because of this, the
  geometry record cannot be frozen incrementally — build a mutable draft and `freeze` once at the
  end, exactly like `Resolved`.
- **Float-identical output.** The §2.4 precompute and any reordering can perturb floats. The
  Step-0 snapshot is the gate; treat any snapshot diff as a regression, not an "acceptable"
  rounding change.
- **Cell read-back ordering.** `controls`/`decorations` consume previously emitted cells and
  `emit_tuning` feeds later emitters via `chart_indicators`/`approach_box`. The orchestrator must
  preserve `_emit_all`'s exact 28-call sequence and thread the accumulator/extras; reordering
  emitters is out of scope for this refactor.
- **`_resolve_tile_extras` lives on the wrong side of the resolve/geometry boundary today.**
  Moving it (Step 5) is the one step that relocates logic across the existing
  resolve↔layout module line; flag for careful review.
- **The render path is live.** Per CLAUDE.md, the user runs `python app.py` on 8137 and the merge
  queue runs the full suite in CI. Validation is: fast suite locally while iterating, full suite
  (incl. `test_web_render.py`) before pushing, CI as the merge gate. No agent launches a server on
  8137; render verification is in-process via the snapshot + render tests.
- **Render tests check the Python element tree, not the DOM.** They will catch `Layout`/cell
  drift (which is exactly what this refactor must not introduce) but not client-JS regressions —
  none of which this refactor touches, since it changes only how `Layout` is *assembled*.

### The census script (reproducible)

```python
import ast, os, collections
DIR = "rtt/app"
files = [f for f in os.listdir(DIR) if f.startswith("spreadsheet_") and f.endswith(".py")]
files.append("spreadsheet.py")
writes, reads = collections.defaultdict(set), collections.defaultdict(set)
for fn in files:
    tree = ast.parse(open(os.path.join(DIR, fn)).read())
    class V(ast.NodeVisitor):
        def visit_Attribute(self, n):
            if isinstance(n.value, ast.Name) and n.value.id == "self":
                (writes if isinstance(n.ctx, ast.Store) else reads)[n.attr].add(fn)
            self.generic_visit(n)
    V().visit(tree)
shared = {a for a in set(writes) | set(reads)
          if writes.get(a) and (reads.get(a, set()) - writes.get(a, set()))}
print(len(shared))  # -> 93
```

Run with `/Users/douglasblumeyer/workspace/DandDsRTT/rtt-python/.venv/bin/python`.
