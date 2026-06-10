# Preview-highlighting feature — state, design, and handoff

*Written by the previous agent (Opus 4.8) as a handoff for whoever redoes this feature. It is part
factual map, part honest post-mortem of why I could not fix the reported bugs. Read the "reproduce
FIRST" section before touching code — it's the trap I fell into.*

## What the feature does

It rings grid cells to preview what an action WOULD change before you commit it:
- **amber ring** (`rtt-preview-change`) — a cell whose *value* the action would move.
- **red ring** (`rtt-preview-remove`) — a cell the action would *remove*.

It fires on: hovering the +/− buttons, the optimize button, the history buttons (undo/redo/reset),
and dropdown options (temperament / tuning / prescaler / complexity / weight-slope / form /
established-projection / target); while *typing* in editable matrix/vector cells; while
*wheel-scrolling* a generator tuning; and while *dragging* to combine or reorder. All in
`rtt/web/app.py`.

## Architecture — and why it is fragile

There are **two different ring mechanisms** plus **~10 coordinating state flags** on `_Reconciler`:

1. **Hover previews — direct, no reflow.** `show_preview(modified, removed)` adds the ring classes
   *straight onto the cells*, bypassing `render()`, so the hovered control doesn't slide out from
   under the cursor (an add/remove would reflow the grid). `clear_preview()` strips them on
   mouse-out. Used by `_preview_control` (mouseenter/mouseleave on +/−, optimize, generator-sign,
   history buttons) and by the dropdown choosers.

2. **Edit / wheel / drag / temperament previews — baseline diff via render.** `render()` computes
   `preview = changed_cell_ids(preview_baseline, lay) - {preview_source}` and rings those.
   `preview_baseline` is a layout snapshot taken on cell focus / drag-start / wheel-hover. Cleared
   by nulling `preview_baseline`.

3. **Dropdown choosers add a client-side debounce.** `_OPTION_HOVER_DELEGATION` (a document-level
   JS string) sets a 90 ms `setTimeout` on option mouseover that dispatches an `opthover` event →
   server `on_chooser_hover` → preview. Plus `popup-hide` → clear. Plus a separate
   `_TOOLTIP_DISMISS_JS` that synthesizes a `mouseleave` on pointerdown (to dismiss tooltips),
   which *also* happens to clear `_preview_control` hovers on click.

State flags that must ALL be reset correctly at every gesture end: `preview_baseline`,
`preview_source`, `preview_shown`, `_editing`, `_control_hovering`, `_chooser_hovering`,
`_wheel_cid`, `combine_target_pred`, `_temp_token`, `_temp_baseline`, `_previewing_temperament`.

`render()` is the server-side source of truth for *clearing*: for every cell in `lay.cells` it
adds/removes the ring classes per the computed `preview` set, and drops cells that no longer exist.

**Why it's bug-prone:** two parallel mechanisms (direct class-poke vs baseline-diff), a client
debounce that can fire after a commit, a synthetic-event hack, and ~10 flags. Every
{gesture} × {commit path} × {reflow or not} is a distinct path that must clear correctly. It has
already needed repeated fixes (`c1fa5ce` stale-red strip; Enter-now-blurs; the chooser
pointerdown-clearTimeout) and *still* has reported persistence. The user's instinct that it is
"pathologically designed" is reasonable.

## Reported but UNFIXED bugs (the reason for this handoff)

The highlight PERSISTS after committing, per the user, when:
- **submitting a new held interval**,
- **clicking the reset button**,
- **selecting from the established-projection dropdown**.

(The optimize-button case was also reported, then the user confirmed it now clears — with no code
change for it, i.e. it resolved on its own.)

## Why I could not fix these — honest post-mortem

1. **I could not reproduce any of them.** I drove the real app both in-process (NiceGUI `User`
   fixture) and in a real browser (the preview tooling). In EVERY test the rings cleared:
   - reset: minimal grid, full pointer events, a *bare* `.click()` that isolates `render()` alone,
     and a wide grid with frozen panes + horizontal scroll — all went 26–94 rings → **0**.
   - held interval: filled the vector + committed on blur → **0**.
   - optimize: cleared (matches the user's "now fixed").
   The server-side `render()` demonstrably strips every ring on every commit in all these cases.

2. **So the persistence is client/session-side, which the automation can't see.** The headless
   tools have no real cursor, so they can't reproduce real-mouse timing/hover or whatever client
   state the user hits. The optimize case self-resolving (no code change) points the same way.

3. **I earlier made a wrong, confident claim.** I ran a large multi-agent "audit" that concluded
   "no other lingering bugs" — and it was WRONG; the user then found three. The audit over-trusted
   *theoretical* refutations (e.g. "the browser fires `mouseout` when a popup is removed, so the
   timer is cancelled"). **Do not trust a theoretical audit of this feature. Reproduce empirically
   with a real cursor.**

4. **I refused to ship blind fixes.** Because the server clears in every test, a server-side "fix"
   would be a no-op, and a client-side fix would be unverifiable without a repro and could break the
   live (intended) edit-preview-while-typing. Shipping either would have been theater.

## Do THIS first: get one reliable repro

Before changing any code, capture one real stuck instance. With a highlight stuck, in the browser
console:

- `document.querySelectorAll('.rtt-preview-change,.rtt-preview-remove').length`
  - `> 0` → the ring class is genuinely stuck in the DOM (a real client desync, or a server path I
    didn't exercise). Find which cells: `[...document.querySelectorAll('.rtt-preview-change,.rtt-preview-remove')].map(e=>e.dataset.eid)`.
  - `0` → it's a DIFFERENT highlight than the preview rings — likely `rtt-alert` (red on a held
    interval the current tuning no longer satisfies — *expected* until you re-optimize),
    `rtt-pending` (red draft styling), or a focus ring. Chase *that*, not the preview system.
- Does a hard refresh clear it? (yes → stale session) Which browser?

This one check would have saved me from chasing the wrong mechanism. Don't skip it.

## Recommended redesign (if you scrap it)

Collapse to ONE declarative source of truth so a client/server desync becomes structurally
impossible:

- A single `rings: dict[cell_id -> color]` computed once per `render()` from "what is the active
  gesture and what op is it previewing."
- EVERY gesture (hover / edit / wheel / drag / chooser) just sets the active-gesture state and calls
  `render()`. Delete `show_preview` / `clear_preview` and the ~10 flags; keep only "active gesture +
  its preview op + (for edits) the focused cell."
- For in-place hover previews that must not reflow, give `render()` a `suppress_reflow` flag so the
  diff rings cells *without* sliding the control — one path instead of the `show_preview`
  side-channel.
- Replace the client-side debounce with a server-side "ignore a chooser hover while its popup is
  closed" guard (track `popup-show`/`popup-hide`). That is testable in-process, unlike the JS
  debounce.
- Net: after every `render()` the client DOM is a pure function of server state → no ring can be
  stranded on the client.

It's a well-scoped job (one feature, one file). Start from a real repro, build the declarative core,
then port each gesture to it one at a time, keeping the existing `test_web_render.py` ring tests
green as the safety net.
