# Preview rings — declarative redesign (working doc; delete before merge)

Revised after a five-lens adversarial review (gesture coverage / races / tests / performance /
regressions). The review's blockers are folded in below.

## Goal

Replace the two parallel ring mechanisms (`show_preview` direct-poke + `preview_baseline`
render-diff) and ~10 coordinating flags with ONE declarative model:

> **The ring classes on the DOM are a pure function of (document, active gesture),
> recomputed and repainted in full on every paint. Nothing else ever touches ring classes.**

Styling (classes `rtt-preview-change` amber / `rtt-preview-remove` red, the CSS, the wrap-level
application point) is unchanged. `rtt-pending` (green draft) and `rtt-alert` (red value flag)
are separate declarative systems — untouched.

## The gesture record

```python
@dataclass
class _Gesture:
    kind: str                  # 'edit' | 'wheel' | 'hover' | 'chooser' | 'temp' | 'drag'
    source: str | None = None  # focused/scrolled cell id — never rung (user is looking at it)
    apply: Callable | None = None   # hypothetical op (hover/chooser/edit candidate); None = no candidate
    baseline: Layout | None = None  # diff base for live-mutation gestures (edit/wheel/drag/temp-grow)
    target_pred: Callable | None = None  # drag-combine: also ring the dropped-on row/col's inputs
    token: tuple | None = None      # editor snapshot (incl. transients) while the DOCUMENT temporarily
                                    # holds a hypothetical state between events (drag, temp-grow)
    reflowed: bool = False          # temp: the doc currently holds an applied (reflowed) hypothetical
    prev: "_Gesture | None" = None  # one-deep suspend: the wheel gesture a gensign hover displaced
```

`rec.gesture: _Gesture | None`, plus `rec.popup_state: dict[cid -> 'open'|'closed']`.

| gesture            | kind      | source | apply                          | baseline       | token |
|--------------------|-----------|--------|--------------------------------|----------------|-------|
| typing (preview-only kinds: mapping/comma/unchanged/interest/held/target cells, element, target-limit) | edit | focused cid | candidate thunk per keystroke (None when invalid/incomplete/draft) | focus-time lay | – |
| typing (commit-per-keystroke kinds: power/prescaler/gentuning/ptext) | edit | focused cid | None | focus-time lay | – |
| gentuning wheel    | wheel     | hovered cid | None                      | hover-time lay | – |
| +/- & control hover, history buttons, approach radio, optimize-lock, gensign | hover | None | the op its click commits | – | – |
| dropdown option hover (tuning/prescaler/projection/complexity/slope/form/target-family) | chooser | None | `_candidate_apply` thunk | – | – |
| temperament option hover, SHRINK | temp | None | `edit_comma_basis(commas)` thunk | – | held (once per gesture) |
| temperament option hover, GROW (reflow) | temp | None | None | snapshot-time lay | held; reflowed=True |
| drag combine / reorder | drag  | None  | None (doc already mutated)     | pickup-time lay (None for within-list reorder) | held |

## Ring computation (the ONE function)

```python
def compute_rings(lay):                      # -> (amber: frozenset, red: frozenset)
    g = rec.gesture
    if g is None:
        return frozenset(), frozenset()
    if g.apply is not None:
        # hypothetical mode: doc unchanged; diff (focus baseline if the gesture has one, else the
        # current lay) vs would-be; paint on the current grid (no reflow). Matches today's
        # _preview_edit (baseline) and _preview_apply (current).
        base = g.baseline if g.baseline is not None else lay
        with _hypothetical():                # token+transient-safe capture/restore (guard 4)
            g.apply()
            hyp = editor.layout(prev_ids=base.identities)
            amber = spreadsheet.changed_cell_ids(base, hyp)
            red = spreadsheet.removed_cell_ids(base, hyp)
        return amber - {g.source}, red
    if g.baseline is not None:
        # live mode: doc has moved (committed keystrokes / wheel notches / temporarily-applied
        # drag or temp-grow); diff baseline-vs-current. Red never applies (removed cells are gone).
        amber = spreadsheet.changed_cell_ids(g.baseline, lay) - {g.source}
        if g.target_pred is not None:
            amber |= {cb.id for cb in lay.cells if g.target_pred(cb)}
        return amber, frozenset()
    return frozenset(), frozenset()
```

`paint_rings(lay)`: idempotent full sweep over `lay.cells` via `rec.els.get(cb.id)` — add/remove
both classes per the computed sets, nothing else ever touches them. (NiceGUI `classes()` is
change-detected, so no-op sweeps cost no socket traffic — verified in nicegui/classes.py.)

- `render()` ends with `paint_rings(lay)`.
- Paint-only transitions (hover arm/disarm, keystroke candidate update, blur) call
  `paint_rings(last_lay[0])` directly — no layout rebuild, no reflow.
- Doc-moving transitions (drag enter, temp-grow option, commits) call `render()`.

## end_gesture() — the ONE way a gesture dies

```python
def end_gesture():
    g, rec.gesture = rec.gesture, None
    if g is not None and g.token is not None:
        _restore_snapshot(g.token)   # doc + transients back to real — BEFORE anything else
    return g                         # caller decides: paint (no reflow) or render (was reflowed)
```

Never bare `rec.gesture = None`. This makes "Ctrl+Z while a temp-grow popup is open" safe:
act(undo) → render → the structural guard below ends the gesture, restoring the real doc first,
THEN the undo applies to it.

## Structural guards

1. **Source-cell-gone guard** (generalizes the kind-flip guard): in render's cell pass, if
   `g.source` is set and the new layout lacks that id or changes its kind, end the gesture
   before rings are computed. *This is the held-interval bug:* committing the `held:pending`
   ratio cell deletes that id (replaced by `held:{tok}`), its blur never reaches the server,
   and today the baseline strands. Same render, structural end.
2. **Renders end gestures that don't render** (replaces "enumerate every commit path"): a
   render arriving while a hover / chooser / temp / drag gesture is active — and NOT initiated
   by that gesture's own handler (a `gesture_render()` wrapper marks those) — ends it via
   end_gesture() at the top of render(). hover/chooser never render; temp/drag render only
   through their own handlers; so any unmarked render is by definition an external commit or
   unrelated rebuild. edit/wheel survive renders (their commits render mid-gesture) and end on
   blur/mouseleave/guard 1. act() also ends hover-family gestures up front (redundant but keeps
   the commit snapshot clean for temp).
   Additionally: any doc-moving render NULLS `g.apply` on a surviving edit gesture — the
   candidate is consumed/stale once the doc moves (wheel-notch commit, debounced target-limit
   commit, blur-commit). compute_rings then falls to the baseline diff, exactly today's
   post-commit rings — and no hypothetical solve is wasted inside commit renders.
3. **Server-side popup gate, tri-state per chooser**: `popup_state[cid]` ∈ {absent, 'open',
   'closed'}; set by `sel.on('popup-show')` / `('popup-hide')`. A positive opthover ARM is
   dropped iff `popup_state.get(cid) == 'closed'` — absent defaults to ALLOW (keeps all
   existing fixture tests green; a real browser always emits popup-show before an option can
   be hovered, and the FIFO socket guarantees a stale post-close arm sees 'closed').
   `opthover -1` and `popup-hide` are UNGATED end events. popup-hide only marks its OWN cid
   closed (an out-of-order hide from chooser A can't close chooser B's session). The client JS
   (`_OPTION_HOVER_DELEGATION` debounce + pointerdown-clearTimeout, `_TOOLTIP_DISMISS_JS`)
   stays verbatim as a rate-limiter; it is no longer load-bearing for correctness.
   Verify popup-show forwarding in a real browser during the live-app check.
4. **Transient-safe snapshots**: `_snapshot_doc()` / `_restore_snapshot()` wrap
   `capture_for_preview`/`restore_for_preview` and additionally save/restore
   `pending_comma/interest/held/target/element`, `_nudging_generator`,
   `superspace_generator_tuning`, and `nonprime_basis_approach` (restore wipes the first
   three families; the approach is mutated by hover ops and never restored). Used by BOTH the
   `_hypothetical()` runner and the token gestures (drag/temp). Fixes today's real bugs: a
   control hover destroying an open draft / a manual 𝒈L / wheel-undo coalescing; the
   approach-radio hover permanently committing the hovered approach.
5. **Persist-guard**: render skips `_doc_store()[...] = editor.serialize()` while
   `g.token is not None` (the document is temporarily hypothetical). Guard 2 bounds the skip
   window structurally (a stranded token gesture dies on the next render, restoring the doc),
   and `on_disconnect` also ends a token-holding gesture. Today a temp-grow/drag hover
   persists the hypothetical doc — a refresh mid-hover would resurrect a never-committed
   document.

## Gesture lifecycles

- **edit**: focus → gesture(edit, cid, baseline=last_lay) — replaces any hover/wheel gesture.
  Keystroke handlers parse and set `gesture.apply` (None if invalid/draft) → paint. Blur →
  builder's commit handler first (unchanged listener order; commit+render — render nulls apply
  per guard 2) → `on_cell_blur` ends the gesture (if kind=='edit') → paint. Enter→js-blur stays.
- **wheel**: mouseenter (refuse if edit/drag/hover active) → gesture(wheel, cid, baseline).
  Notch commits+renders (rings vs baseline). mouseleave (only if still the wheel owner for
  this cid) → end+paint.
- **hover**: mouseenter (refuse if edit/drag active; if a WHEEL gesture is active, suspend it
  in `prev`) → gesture(hover, apply=op) → paint. mouseleave/synthetic mouseleave (only if
  kind=='hover') → end; if `prev` held a wheel gesture, re-arm it as-is → paint. Any render
  (guard 2) ends it.
- **chooser**: opthover idx (gated per guard 3; refuse if edit/drag) → gesture(chooser, apply)
  → paint. opthover -1 / popup-hide (ungated) / any render → end+paint.
- **temp**: token captured ONCE per gesture (first option), lives until end/commit. Per option:
  (a) restore the token if held (doc back to real); (b) if the PRIOR option reflowed
  (`g.reflowed`), `gesture_render()` back to the real grid first; (c) classify grow/shrink by
  STATE DIMENSIONS only — apply `edit_comma_basis` to the live doc, compare d/r/n to the base
  (no probe layout); (d) shrink: restore again, arm apply-thunk (token kept) → paint red in
  place; grow: keep applied, set baseline+reflowed → `gesture_render()` (reflow).
  Option leave (-1) / popup-hide → end_gesture() (restores token) → render if reflowed else
  paint. Commit (on_preset): end_gesture() (restores token) → commit → render. The temperament
  chooser's displayed value stays frozen while `gesture.kind=='temp' and gesture.reflowed`
  (re-homes `_previewing_temperament` / `_update_preset`'s early return).
- **drag** (combine + reorder): dragstart → end any stale token gesture, then token +
  gesture(drag, baseline). dragenter → restore token, apply hypothetical move, set
  baseline/target_pred per validity → `gesture_render()`. drop → end_gesture() (restores) →
  commit via act() → render. dragend → end_gesture() → render.

End-event ownership: EVERY end handler no-ops unless the live gesture matches its kind (and
source where applicable) — the structural form of today's `_control_hovering`/`_chooser_hovering`
/`_wheel_cid` ownership flags.

Arm priority (parity with today): edit and drag refuse nothing (they take over, ending what
they replace via end_gesture); hover refuses edit/drag (suspends wheel); chooser refuses
edit/drag; wheel refuses edit/drag/hover.

## What gets deleted

`show_preview`, `clear_preview`, `preview_shown`, `preview_baseline`, `preview_source`,
`combine_target_pred`, `_editing`, `_wheel_cid`, `_control_hovering`, `_chooser_hovering`,
`_temp_token`, `_temp_baseline`, `_previewing_temperament`, `_preview_apply`, `_preview_edit`,
the per-handler `rec.clear_preview()` calls. ~10 flags → 1 record + 1 popup dict.

## What stays exactly as-is

CSS / colors / class names / wrap application point; `changed_cell_ids` / `removed_cell_ids` /
`RINGABLE_KINDS` / `assign_column_tokens` + prev_ids threading (the smart diff — reorders ring
nothing, insertions match by content); `_OPTION_HOVER_DELEGATION` and `_TOOLTIP_DISMISS_JS`
verbatim; Enter→blur commit routing; blur-handler ordering; draft columns preview nothing; the
no-reflow rule for hover previews; temperament grow-reflow / shrink-redden split; within-list
reorder rings nothing; rtt-pending / rtt-alert.

## Performance parity (per the review)

- Edit keystroke: 1 hypothetical layout (same as today). Commit render: 1 layout (apply nulled
  — today also 1). Wheel notch: 1 layout (baseline diff is pure Python). Chooser hover: 1
  hypothetical layout behind the kept 90ms debounce (same). Temp shrink: 1 layout (vs 2 today);
  temp grow: 1 (vs 2 today). Drag enter: 1 (same). Paint sweeps: socket-silent no-ops.

## Test impact (corrected)

- The 46 intended-UX ring tests stay green: opthover tests pass because absent popup_state
  defaults to allow; 2512 passes via guard 2's structural form (on_show_toggle's render ends
  the hover gesture); 2434/2454/2472/2495/2530 map to guards 1-2; mechanism tests 1950/2177
  keep their wiring verbatim.
- 16 diff-helper unit tests: untouched core.
- NEW tests: held-ratio-cell commit clears rings (the id-swap bug); stale opthover after
  popup-hide is dropped while a fresh popup-show re-allows; popup-hide for cid A doesn't close
  B; reset/projection/held commit-clears; control hover with an open draft preserves the draft;
  approach-radio hover doesn't commit the approach; temp-grow hover doesn't persist the
  hypothetical doc; gensign hover suspends and restores the wheel gesture.
