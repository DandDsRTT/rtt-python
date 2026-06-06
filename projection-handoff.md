# Projection feature — handoff

Mid-task handoff. Library spike is **done + merged to main**; the frontend rows
("scaling factors", "projection") are still **blocked** on parallel agents.
Delete this file once a fresh session picks up step 2 and internalises it.

---

## Status at a glance

| Step | What | State |
|---|---|---|
| 1 | Library: rational embedding/projection engine | ✅ DONE, merged (`a051d69`) |
| 2 | Frontend: `scaling factors` + `projection` rows in `build()` | ⏸ BLOCKED on deps |

---

## Step 1 — what landed

Two new files added by commit `a051d69` on `main`:

- [`rtt/generator_embedding.py`](rtt/generator_embedding.py) — 30 lines
  - `get_generator_embedding(mapping, held)` → **G = H·(M·H)⁻¹**
    (rational d×r right-inverse of the mapping; columns are the held intervals'
    fractional vectors)
  - `get_tempering_projection(mapping, held)` → **P = G·M**
    (rational d×d projection; idempotent; kernel = comma space; image = held-prime
    subspace)
- [`tests/test_generator_embedding.py`](tests/test_generator_embedding.py) — 4 tests

It is **convention-free**: the caller supplies the held intervals (a `Temperament`
with `COL` variance, rows are vectors). Nothing about which primes are
"canonical" is baked in.

### Verified against the quarter-comma meantone target

For `mapping = Temperament(((1,1,0),(0,1,4)), ROW)` and `held = Temperament(((1,0,0),(0,0,1)), COL)`
(i.e. holding 2/1 and 5/1):

```
G_c = ((1, 0), (0, 0), (0, Fraction(1,4)))                   # generators: 2/1 and 5^(1/4)
P   = ((1, 1, 0), (0, 0, 0), (0, Fraction(1,4), 1))           # the canonical projection
j·P = ⟨1200.000  1896.578  2786.314]                          # the mockup's exact tuning map
      (the 696.578¢ fifth is quarter-comma's defining generator)
```

Contrast: holding `{2/1, 3/1}` instead reproduces the existing integer
`get_generator_detempering`'s projection `((1,0,-4),(0,1,4),(0,0,0))` — which
holds the *wrong* primes (2 & 3 rather than 2 & 5). This is the whole point of
adding the rational engine.

### The math (one paragraph)

The projection P = G·M is the **oblique** projection onto the held-prime
coordinate subspace, *along* the comma space (the kernel of M). It is rational
whenever the mapping and held intervals are integer. The wiki documents it
under **Fractional monzo** / **Eigenmonzo** / **Unchanged interval** — the held
intervals are P's eigenmonzos (Pu = u). Not to be confused with the wiki's
orthogonal projection `P = I − N(NᵀN)⁻¹Nᵀ`, which is least-squares (irrational)
and gives TE-style tunings, not quarter-comma.

---

## Step 2 — what's blocked

Add the "scaling factors" + "projection" rows to `rtt/web/spreadsheet.py`'s
`build()`, gated on `settings["projection"]`; add `"projection"` to
`rtt/web/settings.py`'s `IMPLEMENTED`.

### Blockers

1. **Columns agent's detempering (G) row.** Not in main yet (last check). The
   projection box reuses G conceptually ("box MG" per the mockup blue note).
2. **Weighting agent's rows.** Not in main yet. Sequence the projection row
   additions **after** weighting's so the row list in `build()` doesn't
   conflict-merge.
3. **The default-embedding rule.** See below — needs Douglas.

### Mockup spec (the spec)

`RTT design mockup - maximized.png` at the repo root (5084 × 8190, READ-ONLY,
never commit). Read its blue notes before coding. Use PIL to crop & upscale
into a temp dir.

- Show toggle: `projection` (glyph 𝑃), sub-control of `tuning_boxes`
  (`rtt/web/settings.py`).
- Blue note on the toggle: **"toggle rows 'scaling factors', 'projection'; box 'MG'"**.
- A separate **`<choose embedding>`** dropdown exists in the mockup (distinct
  from the `<choose tuning>` scheme selector that's already wired). Still
  unbuilt.
- "Scaling factors" row semantics: read the row directly when building. Likely
  candidates: the diagonal entries of `(M·H)⁻¹` (the per-generator scaling — for
  meantone {1, 1/4}), or the eigenvalues `diag(λ) = (1, …, 1, 0, …, 0)` from
  `P = V·diag(λ)·V⁻¹`. **Confirm via the mockup before building.**
- The mockup also pairs projection with PD / PV / superspace variants — all
  aspirational. Defer.

### The open design decision

The frontend default needs to pick the held intervals automatically (until the
`<choose embedding>` dropdown is built). I asked Douglas; he redirected to the
wiki. After mining it I have a strong **nullity-1 recommendation** but
**nullity-2+ is genuinely open** (Douglas's own note in memory says so).

- **Recommended (nullity 1):** derive the **non-octave prime with the largest
  absolute exponent in the canonical comma basis**; hold the rest. The octave
  (prime 2) is always preferentially held. The "scaling factor" = `1 /
  (that exponent)`.
  - Meantone comma `[-4, 4, -1⟩` → non-octave |exps| are 4 (on 3) and 1 (on 5)
    → derive 3, hold {2, 5}, scaling ¼ = 1/4. Reproduces the target.
- **Nullity ≥ 2:** undecided. Confirm with Douglas when picking up step 2.

---

## Concrete pickup steps (for the next session)

1. **Re-check main** for the dependency commits — has the detempering row
   landed? Has weighting landed? Look at:
   - `git log --oneline main -30`
   - `rtt/web/settings.py` — is `generator_detempering` and/or `weighting` in
     `IMPLEMENTED`?
   - `rtt/web/spreadsheet.py` — search `row_open("generator_detempering")` and
     `row_open("weighting")` (or the equivalent — names may differ).
   - If either is missing, the task is still blocked. Tell Douglas and stop.
2. **Read the mockup's "scaling factors" and "projection" rows directly** via
   PIL. They are below the existing tuning rows (`𝒕`, `𝒋`, `𝒓`). Note the
   exact framing, the `<choose embedding>` dropdown's location and options, and
   the "MG" box label.
3. **Settle the default-embedding rule with Douglas.** Present the recommended
   nullity-1 rule above; ask what to do for nullity ≥ 2 (probably the simplest
   move is to extend it: derive the (d−r) non-octave primes with the largest
   |exponents| in the canonical comma basis).
4. **TDD step 2 from a build()-level test**: enable `settings["projection"]`
   on a `5-limit meantone` editor state, call `spreadsheet.build`, and assert
   the projection row's cells contain the expected fractions (the `¼` entry
   in particular). Then implement gated on `settings["projection"]`. The new
   rows must be sequenced **after** the weighting rows in `build()`'s row
   list to merge cleanly with the weighting agent's work.
5. **Use the library engine** — import from `rtt.generator_embedding`:
   ```python
   from rtt.generator_embedding import get_tempering_projection
   p = get_tempering_projection(mapping_t, held_t)   # rational d×d matrix
   ```
   Build `held_t` from the canonical rule (step 3).
6. **Add `"projection"` to `settings.IMPLEMENTED`.**
7. **Verify via the in-process render tests** — `tests/test_web_render.py` uses
   NiceGUI's `User` simulation; toggling `projection` on should not 500 the
   page. Extend it with a `projection`-specific test.
8. **Delete this `projection-handoff.md` file** in the same commit that lands
   step 2 — it's session scaffolding, not project documentation.

---

## Things to remember (project conventions)

Repo CLAUDE.md (committed, will travel with the repo on the other computer)
has the full rules. Highlights:

- **Strict TDD.** One test at a time, red → green → refactor while green.
  Full suite must be green (zero failures, errors, skips, xfails — collection
  errors count) before every commit. Never ask to run unit tests, just run
  them.
- **Run pytest with the worktree's absolute path** — the worktree is *nested*
  inside the main repo and main is pytest's rootdir, so omitting the path
  silently tests main, not your edits. Example:
  `<venv>/python -m pytest <WORKTREE_ABS_PATH> -q`
- **The `.venv` lives in the main repo:**
  `C:/Users/Douglas/workspace/DandDsRTT/rtt-python/.venv/Scripts/python.exe`.
  (Confirm path on the new computer.)
- **NEVER launch the web app on port 8137** — that's the user's running
  session. Use 8200+, `reload=False`. Avoid 8188 / 8189 (ComfyUI).
- **Mockup is the spec.** `RTT design mockup - maximized.png` (repo root, READ-ONLY).
  Crop + upscale with PIL. Blue text annotations ARE the behaviour spec.
- **WebFetch is 403-blocked on en.xen.wiki AND the fandom mirror** (raw-action
  too). Use WebSearch instead — it returns useful article summaries.
- **Fast-moving main + parallel agents.** Before merging, rebase onto current
  main and verify `git diff main` is additions-only. Don't revert teammates.
- **No "monzo" terminology** in new prose — D&D abandoned it; use
  "vector"/"map". (The library still has historical `monzo` in some names;
  don't extend the usage.)
- **No eponymous tuning names** (TOP/TE/CTE/POTE/etc. — banned by D&D);
  use systematic names like `minimax-S`, `minimax-ES`, etc.

---

## Useful references

- Library code: [`rtt/generator_embedding.py`](rtt/generator_embedding.py) (30 lines, read it).
- Existing integer detempering for comparison: [`rtt/generator_detempering.py`](rtt/generator_detempering.py).
- Tuning math (held-intervals machinery): [`rtt/tuning.py`](rtt/tuning.py), see
  `_constrained_solve` and the `held_intervals` trait.
- Frontend settings: [`rtt/web/settings.py`](rtt/web/settings.py).
- Layout builder: [`rtt/web/spreadsheet.py`](rtt/web/spreadsheet.py) — `build()` ~line 373.
- App entry (renders `index`): [`rtt/web/app.py`](rtt/web/app.py).
- Render-coverage tests (the ones to extend): [`tests/test_web_render.py`](tests/test_web_render.py).
- Mockup: [`RTT design mockup - maximized.png`](RTT%20design%20mockup%20-%20maximized.png) (repo root).
- Mockup blue-text transcriptions (in CSVs at repo root) — useful to grep for
  spec terms without re-cropping the PNG.
- Wiki (search-only): `Eigenmonzo`, `Fractional monzo`, `Quarter-comma meantone`,
  `Dave Keenan & Douglas Blumeyer's guide to RTT`.
