# Form feature — session handoff

This doc captures the state of the **form** Show feature (`form_controls` /
canonical-mapping row / 𝐹 matrix / `form_colorization`) at the end of a long
session, so the work can be picked up cleanly from another computer.

## TL;DR — current state on main

The form feature's CONTENT shipped and is fully wired, then was **deliberately
hidden** at the end of the session: `form_controls` is **greyed** (not in
`IMPLEMENTED`), and everything else (the canonical-mapping row, the 𝐹 matrix,
the "<choose form>" chooser, the magenta colorization swatch) is gated on it. So
the panel today shows a greyed `form controls` row with a `canonical form`
example and nothing user-toggleable underneath; flipping `form_controls` back
into `IMPLEMENTED` brings the whole built-out feature back instantly.

Latest commit on main: **`0f9b7dc` — "Hide the form feature behind a single
(greyed) form_controls toggle"**.

## What was built (then hidden)

The session landed five form-feature commits on main, in this order. Each is
fully tested and was merged via rebase + fast-forward.

1. **Service seam** — `service.canonical_mapping(M)` (defactor + HNF via
   `rtt.canonicalization.canonical_ma`) and `service.canonical_comma_basis(C)`
   (via `canonical_ca`), plus `service.form_matrix(M) = canonical_M · Gᵀ` where
   G is the generator detempering — verified `F·M == canonical_M` across
   several temperaments.
2. **Canonical-mapping row** — a new row keyed `"canon"` between `vectors` and
   `mapping`, holding the canonical 𝑀 over the primes column as a stack of
   ⟨ … ] maps framed with `matrix_frame("canon", "primes", "canon")`.
   `matrix_frame` was generalized (rkey, ckey, bid) so two framed rows can sit
   over the same column without colliding.
3. **𝐹 matrix** — the generator form matrix (r×r, units 𝒈/𝒈) over the gens
   column at the canon row, framed `{ … ]` per row via `GENMAP_BRACKETS` plus
   an enclosing `matrix_frame("canon", "gens", "form")`. Cells use a new
   `"formcell"` kind that renders as a read-only bordered label (shares the
   `prime` cell init branch in app.py).
4. **form_controls chooser** — a `"<choose form>"` q-select in the mapping
   (mapping × primes) and comma-basis (vectors × commas) boxes that stacks below
   the preselect band. Selecting `"canonical"` triggers `editor.canonicalize_mapping()`
   or `editor.canonicalize_comma_basis()` — both undoable edits that re-store
   the matrix in canonical form. New cell kind `"formchooser"`, handler
   `on_form_choose`. `form_controls`, `form`, `form_colorization` were nested per the
   mockup, and `_TINTS["form"] = "#cd9acd"` was added for the swatch.
5. **Hide it all** — `form_controls` removed from `IMPLEMENTED` (greyed); the
   separate `form` sub-toggle removed entirely; the canon row's gate changed
   from `show_form` to `show_form_controls`. `form_colorization` stays a greyed
   child of `form_controls`.

## What Douglas dictated this session

- **Trust the mockup over the brief** (the original brief came from an agent he
  didn't fully trust). I read the maximized mockup's "canonical mapping" row
  carefully and built from it — multi-matrix region with canonical-𝑀 + 𝐹.
- **Defer the magenta colorization wash** for now (no `COLORIZE_REGIONS` entry,
  `form_colorization` stays greyed). The form cell-map is HIS to dictate; do
  not guess it (per the colorization-scheme memory: he burned many attempts on
  guessed colorization maps).
- **Defer `identity_objects`** (was blocked on detempering on main; detempering
  has since landed in main's 92-commit run, so `identity_objects` is now
  UN-blocked design-wise but still hasn't been re-built — see "Open follow-ups"
  below).
- **`form_controls` is the parent**, `form` (boxes) and `colorization` are
  children — per the mockup. (Now that `form` was removed, only
  `form_colorization` is a child of `form_controls`.)
- **`<choose form>` canonicalizes the matrix on select** (undoable edit, like
  loading a preset). Specifically NOT a display-only toggle.
- **At the end of the session**: disable `form_controls` and gate the
  canonical-mapping row on it, so the whole feature is hidden for now.

## Key facts that are NOT obvious from code

- **`_TINTS["form"] = "#cd9acd"`** is the magenta tint for the eventual form
  wash. It's already in the palette (so the greyed `form_colorization` swatch
  is correct) but no `COLORIZE_REGIONS` entry exists yet. Each tint dims one
  RGB channel to `0x9a`: tuning=cyan (R), temperament=khaki (B), form=magenta
  (G). Darken crossings: form⊓temperament=`#cd9a9a`, form⊓tuning=`#9a9acd`.
- **The canon row sits INSIDE the temperament band's vertical span** (between
  `vectors` and `mapping`, both inside temperament's primes/commas bounding
  box on the old `COLORIZE_REGIONS` scheme — main has since replaced that with
  by-content `CELL_FACTORS`, but the spatial situation is still relevant). When
  the form wash is eventually built, decide whether the canon row's
  primes/commas cells read as pure magenta, magenta×yellow crossing, or
  something else — Douglas's call.
- **`CELL_FACTORS[("canon", "primes")] = {"M"}`** is already on main (yellow,
  M family) — when `form_controls` is on, the canon row's primes cells colour
  yellow under the new by-content scheme. There is NO `("canon", "gens")`
  entry for the 𝐹 matrix yet.
- **`identity_objects` is currently still deferred and hasn't been touched
  this session** — main's detempering work unblocked one of its tiles (𝑀𝐷=I)
  but no one has gone back to build it. The other two tiles (the r×r self-map
  and the d×d domain-basis identity) need restoring per
  `memory/project_identity_objects.md`.

## Files of interest

- `rtt/web/settings.py` — `form_controls` (greyed, not in IMPLEMENTED),
  `form_colorization` (greyed child of `form_controls`).
- `rtt/web/spreadsheet.py` — `show_form_controls` flag, the `"canon"` row in
  `row_bands` (gated on `show_form_controls`), `FORM_CHOOSERS` constant, the
  formchooser band reservation (`formctrl`), the canon/𝐹 cell + bracket +
  `matrix_frame` emission, `CELL_FACTORS[("canon","primes")]`.
- `rtt/web/app.py` — `_TINTS["form"]`, the `"formchooser"` init/render
  branches, `on_form_choose` handler, the `"prime"`/`"formcell"` shared init,
  `_EXAMPLE_TEXT["form_controls"] = "canonical form"`.
- `rtt/web/editor.py` — `Editor.canonicalize_mapping()`,
  `Editor.canonicalize_comma_basis()` (both undoable via `_apply`).
- `rtt/web/service.py` — `canonical_mapping`, `canonical_comma_basis`,
  `form_matrix`.
- Tests pinning the above: `tests/test_web_service.py`,
  `tests/test_web_editor.py`, `tests/test_web_spreadsheet.py`,
  `tests/test_web_render.py`.

## Open follow-ups

These were known when this session ended; pick whichever the user wants next.

1. **Form colorization (magenta wash)** — implement when Douglas dictates the
   form cell-map. Likely needs a new `("form", …)` entry analogous to the
   current by-content scheme, plus a sensible interaction with the temperament
   band over the canon row. Douglas dictates colorization maps explicitly per
   the memory; do not derive them from the mockup pixel-by-pixel.
2. **Re-enable the form feature** — when Douglas is ready, simply add
   `form_controls` (and possibly `form_colorization` once #1 is built) back to
   `IMPLEMENTED` in `rtt/web/settings.py`. All the code, tests, and rendering
   wiring are already in place; flipping the toggle's status restores the
   feature.
3. **`identity_objects`** — still deferred. With detempering on main, its 𝑀𝐷
   tile is now buildable; the other two tiles (self-map, domain-basis
   identity) also need restoring. See `memory/project_identity_objects.md`.
4. **The form\_controls panel example glyph** is currently the text
   `"canonical form"`; if Douglas wants a glyph (mockup says 𝐹), trivial to
   swap in `_EXAMPLE_TEXT`.

## How to resume in a new session

1. `cd` to the rtt-python repo and confirm `git log -1` shows commit
   `0f9b7dc` (or a descendant) — that's the "hide the form feature" commit.
2. Read this file and `memory/project_identity_objects.md` for context.
3. Decide which open follow-up to tackle first (form colorization usually
   needs an explicit map from Douglas before building).
4. Project rules: strict TDD, full suite green before every commit, refactor
   while green, small single-purpose commits, rebase onto current main + check
   `git diff main` is additions-only before merging (main moves ~30
   commits/session in this repo).
5. The .venv lives at `…/rtt-python/.venv/Scripts/python.exe`; the worktree
   workflow lives in `WORKTREES.md`.
