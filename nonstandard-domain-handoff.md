# Chapter 9 — nonstandard domain / superspace: handoff

**Status: done + merged to `main`.** The `nonstandard_domain` Show toggle is
live (in `settings.IMPLEMENTED`). This doc summarises the whole buildout for
code-review pickup on a different machine. Delete it once the review is
finished.

The Guide goal was: "everything good through ch8, only ch9 remaining." That's
now true. This was the largest single feature in the buildout (the spike
explicitly flagged it as such), shipped across five phases plus a foundation.

---

## Status at a glance

| Phase | What | State | Commits |
|---|---|---|---|
| 0 | Foundation: state/service domain-awareness + load nonstandard via mapping box + render existing grid correctly | ✅ merged | `3b294c5`..`737892a` (7) |
| 1 | Polish: header text, comma-box preservation, target-chooser default-limit, units p↔b swap | ✅ merged | `39fc65c`, `c39faef`, `9775f50` (+ A1 bundled) |
| 2 | 3-mode radio for the tuning approach + superspace data primitives in service | ✅ merged | `01bc5f1`, `912c380`, `3449bbe`, `ea719a2` |
| 3 | Superspace columns/rows scaffolding in `build()` (empty tiles) | ✅ merged | `3b19f6f`, `5bfc698`, `b61e436` |
| 4α | Green matrices (B_L, M_L, M_jL) + cyan tuning maps (𝒈L/𝒕L/𝒋L/𝒓L) + bracket convention + plain text + units pass-through | ✅ merged | `9ef97cf`, `8b750c6`, `be57b91`, `f588a1d`, `563e266`, `106accf`, `8eb32fb` |
| 4β | Mode-gated conversion rows (B_L·T target list, X_L superspace prescaler) | ✅ merged | `34966b3`, `7808290`, `979ac78`, `4966487`, `a45d081` |
| 5 | Activate toggle + cross-feature sweep + live preview verify | ✅ merged | `e1033f9`, `6d94771`, `72f8c92` |

~30 commits total.

---

## The feature in one paragraph

A "nonstandard domain" is a temperament defined over a subgroup whose basis
elements may be **nonprime** (e.g. `2.3.13/5`, where `13/5` is a nonprime
element). Such a temperament embeds into a **superspace** — the smallest
prime-only basis containing all its primes (`(2, 3, 5, 13)`, dL=4 for that
example). The superspace temperament has rank `rL = r + (dL − d)`: the extra
primes beyond the domain are held just, so nullity is preserved. The mockup
exposes the superspace as new columns (**superspace generators**,
**superspace primes**), new rows (**superspace interval vectors**,
**superspace mapping**, plus two mode-gated **conversion rows**), and a 3-way
radio selecting which optimization mode runs (prime-based / nonprime-based /
neutral).

---

## Specs the work was driven by

- `RTT design mockup - maximized.png` (repo root) — the visual spec.
- `RTT maximized mockup - blue text transcription - Sheet3.csv` (repo root) —
  the ch9 blue-text transcription. Eight rows pinning behaviour. Every Phase 4+
  agent was pointed at this CSV.
- The library already supported nonstandard domains in the engine — `rtt/
  domain_basis.py`, `rtt/change_basis.py`, `rtt/tuning.py`'s
  `nonprime_basis_approach` and `_change_to_simplest_prime_basis`. The
  frontend was the gap.

---

## The three plan-level forks (decided up front)

1. **Order**: "Input capability first" — give state/editor real nonstandard
   support before any visualisation.
2. **Shared columns**: "Land them now" — superspace columns are infrastructure
   form/projection/identity will reuse, build once. (In practice projection
   landed in parallel during Phase 0; the timing tradeoff resolved itself.)
3. **Mode**: "Include the mode now" — wire the prime-based / nonprime-based /
   neutral selector as part of this work, not later.

---

## Phase-by-phase summary

### Phase 0 — foundation (the spike, then build)

The design spike read the mockup's green superspace region, the cyan 𝒈L/𝒕L
annotations (incl. *"if you mod 𝒈 then prime-based mode falls off"*), and the
library internals (`get_basis_a`, `change_domain_basis`,
`_change_to_simplest_prime_basis`, etc.). The plan emerged from that reading.

Then the foundation landed across 7 commits:

- `3b294c5` **Carry a domain basis in TemperamentState** — adds the
  `domain_basis` field (tuple of ints/Fractions); standard primes by default;
  `from_temperament_data(ebk)` parses a domain-basis prefix like `"2.3.13/5
  [⟨1 2 2] ⟨0 -2 -3]}"`.
- `3e4b4e3` **Compute nonstandard-domain tunings in `service.tuning`** —
  takes `domain_basis` + `nonprime_approach` ("" / "nonprime-based" /
  "prime-based"); reference values verified against `tests.m`.
- `1f09ee7` **Express interval sets over a nonstandard domain basis** —
  `_interval_monzos` helper threads through `interval_sizes`,
  `mapped_intervals`, `target_interval_monzos`; `target_interval_set` filters
  to the subgroup via `filter_target_intervals_for_nonstandard_domain_basis`.
- `60bb4ee` **Render commas, generators and plain text in the domain basis**
  — `comma_ratios`/`generators` multiply out the (possibly nonprime) basis
  elements (the Barbados comma reads `676/675`, generator `15/13`);
  `plain_text_values` is domain-aware.
- `ca5804c` **Load nonstandard domains from the mapping box** —
  `try_edit_mapping_text` parses a domain-basis prefix (new
  `service.parse_mapping_state`); prime-walking ± controls go inert on
  nonstandard (`can_expand`/`can_shrink` false, `expand`/`shrink` no-op);
  `Editor._apply` factored out.
- `f7cfbb0` **Render a nonstandard domain across the existing grid** —
  `build()` reads every interval set over `state.domain_basis` so a loaded
  nonstandard temperament shows its actual elements; renames the domain
  header to "domain\nelements" when the basis is nonprime; passes
  `approach="prime-based" if settings["nonstandard_domain"]` into
  `service.tuning`. **This was the coherence-critical bit** — without it the
  editor could load a nonstandard temperament that the grid rendered with
  standard primes.
- `737892a` **Build the parsed mapping state via `from_temperament_data`** —
  `parse_mapping_state` delegates construction to `from_temperament_data` so
  the latter has a production caller.

This foundation was rebased onto a **15-commit-busy main** (units, full
weighting region, projection landed in parallel) and merged ff-only. The
rebase resolved conflicts in `service.py`, `editor.py`, and `build()` keeping
both sides additive; full suite 1508 green.

### Phase 1 — polish

CSV reconciliation surfaced four small gaps. Spun out as two parallel agent
chips.

- `39fc65c` **Swap p for b in domain unit labels under a nonstandard basis**
  (Agent 1b — CSV row 2). Introduced `self.domain_label = "p" if
  service.is_standard_domain(self.elements) else "b"` and threads it through
  the units cells.
- `c39faef` **Preserve a nonstandard domain basis when editing the comma
  box** (Agent 1a A2). `try_edit_comma_basis_text` now threads
  `self.state.domain_basis` through so editing commas keeps the basis.
- `9775f50` **Default the target chooser limit to the loaded basis, not
  standard primes** (Agent 1a A3). `app.py`'s two `service.standard_primes
  (editor.state.d)` sites switched to `editor.state.domain_basis`.
- **A1 header rename** ("domain elements" → "basis elements", to match the
  CSV row 8 terminology) landed as part of one of the above (probably
  c39faef) — confirmed in `spreadsheet.py` (the literal now reads
  `"basis\nelements"`).

### Phase 2 — mode model + superspace data primitives

Two parallel agent chips, structurally independent.

**Agent B** — 3-mode radio (replaces the binary toggle's hijacked role):
- `01bc5f1` **Wire the chapter-9 nonprime-basis-approach through editor +
  build** — `Editor.nonprime_basis_approach` field, setter, reset-on-domain-
  change; `build()` reads it (parameter, not the Show toggle).
- `912c380` **Render the chapter-9 nonprime-basis-approach radio** —
  3-radio control in the damage region; visibility gated on
  `service.domain_has_nonprimes(state.domain_basis)` so it appears only when
  the basis actually has nonprimes.
- `3449bbe` Edge cases (reset on domain change away from nonprime,
  persistence, etc.).

**Agent C** — superspace data primitives (pure service additions):
- `ea719a2` **Add the superspace data primitives** — `superspace_primes`,
  `superspace_dimension` (dL), `superspace_rank` (rL), `basis_in_superspace`
  (B_L, dL×d), `superspace_mapping` (M_L, rL×dL, derived via
  `change_domain_basis_for_c` + `dual`), `superspace_just_mapping` (M_jL = I,
  dL×dL), `superspace_tuning` (gL/tL/jL/rL). BARBADOS-anchored TDD.

### Phase 3 — superspace columns/rows scaffolding (empty tiles)

Single serial agent because `build()` is the most-contended file in the repo.

- `3b19f6f` **Add the chapter-9 superspace generators/primes columns** —
  `ssgens` (rL wide) and `ssprimes` (dL wide) inserted between `gens` and
  `primes`; counts row gains `rL` and `dL`.
- `5bfc698` **Add the chapter-9 superspace rows, counts, panels, axes, and
  spine basis** — `ss_vectors` (dL × ROW_H, basis index α β γ δ ε in the
  spine) and `ss_mapping` (rL × ROW_H), with axes/panels/fold-toggles.
- `b61e436` **Caption the superspace mapping and basis-embedding tiles** —
  CAPTIONS/SYMBOLS for the new tiles ("superspace mapping" 𝑀L,
  "basis-embedding" B_L, etc.).

Scaffolding only — no content cells yet. Toggle stays out of IMPLEMENTED.
Tests pass `{"nonstandard_domain": True}` directly into `build()`.

### Phase 4 — content fan-out (two parallel agents)

Phase 3's scaffolding had reserved tiles. Phase 4 filled them with cells.

**Agent α (green + cyan + brackets):**
- `9ef97cf` **Render the chapter-9 B_L basis-embedding cells** — domain
  elements as monzos over superspace primes in `(ss_vectors, primes)`. For
  BARBADOS: element `13/5` shows as the monzo `(0, 0, −1, +1)` over `(2, 3,
  5, 13)`.
- `8b750c6` **Render the chapter-9 M_L superspace mapping cells** — the
  rL×dL matrix in `(ss_mapping, ssprimes)`.
- `be57b91` **Render the chapter-9 ss_just_mapping row with M_jL = I cells**
  — the mockup labels M_jL = I as its own matrix tile; Agent α added a
  new `ss_just_mapping` row (dL × ROW_H) parallel to `ss_mapping` to host it.
- `f588a1d` **Render the chapter-9 cyan superspace tuning maps** — 𝒈L
  (tuning × ssgens), 𝒕L (tuning × ssprimes), 𝒋L (just × ssprimes), 𝒓L
  (retune × ssprimes). Numbers from `superspace_tuning`.
- `563e266` **Plain-text values** for the new tiles.
- `106accf` **Lock the superspace bracket convention via tests** — per CSV
  row 7 ("`{` for generators/rank, `(` for primes/dimensionality whether
  superspace or not"). New constants for the superspace tile brackets;
  existing-grid brackets untouched.
- `8eb32fb` **Pass units through the chapter-9 superspace cells.**

**Agent β (mode-gated conversion rows):**
- `34966b3` **Add `service.targets_in_superspace`** — expresses each target
  ratio over the superspace primes (a dL × k matrix).
- `7808290` **Add `service.complexity_prescaler_in_superspace`** — the
  prescaler converted to superspace coords (dL × dL).
- `979ac78` **Reserve the ss_targets / ss_prescaler rows, mode-gated** — the
  two rows appear in `row_bands` only when the toggle is on AND the mode is
  `""` (neutral) or `"prime-based"` — NOT `"nonprime-based"` (per CSV row
  6).
- `4966487` **Render the ss_targets B_L·T and ss_prescaler X_L cells.**
- `a45d081` **Caption the superspace target list and prescaler tiles.**

### Phase 5 — activate + sweep + verify

Single serial agent.

- `e1033f9` **Activate the chapter-9 `nonstandard_domain` Show toggle** —
  adds to `settings.IMPLEMENTED`. The toggle goes live.
- `6d94771` **Refresh `nonstandard_domain`'s Show example + tooltip** —
  the `_EXAMPLE_TEXT["nonstandard_domain"]` value updated (was
  `"prime-based"`, which became wrong once that lived on the 3-radio).
- `72f8c92` **Render the chapter-9 M_L / M_jL cells as read-only "mapped"**
  — Phase-5 sweep caught the M_L/M_jL cells using a kind that allowed
  editing affordances. Switched to the read-only "mapped" kind that
  matches their semantics.

---

## Design decisions worth flagging for review

1. **Where the optimization mode lives.** Initially I wired
   `nonstandard_domain` (the Show toggle) to hardcode `nonprime_approach =
   "prime-based"`. The CSV (row 3) corrected this: the mode is its own 3-way
   control in the damage region, and the Show toggle reverts to its real
   role (revealing rows/cols). Phase 2 detached them. Verify: editing in the
   damage radio changes optimization numbers; toggling
   `nonstandard_domain` only affects visibility.

2. **Header rename target is "basis elements", not "domain elements".** My
   initial Stage-3a render used "domain elements"; CSV row 8 pinned the
   correct rename target. Phase 1 fixed it.

3. **Standard-domain superspace renders trivial identity.** Toggling
   `nonstandard_domain` ON with a standard domain shows the superspace
   columns/rows as trivial-identity duplicates (M_L = M, B_L = I, etc.).
   This was a deliberate Phase-3 choice rather than gating the cols/rows on
   `domain_has_nonprimes`. Worth a look during review — if it reads as
   noisy in practice, consider tightening the gate. The 3-mode radio
   already does hide itself for standard domains (Phase 2B), so the radio
   is consistent; only the columns/rows are visible.

4. **M_jL = I gets its own row (`ss_just_mapping`).** Phase 3 didn't reserve
   a tile for M_jL; Phase 4α added the row in `be57b91`. It's parallel to
   `ss_mapping`, dL × ROW_H. Verify the row order in `row_bands`
   (`mapping`, `ss_vectors`, `ss_mapping`, `ss_just_mapping`, `ss_targets`,
   `ss_prescaler`, `tuning`, …).

5. **EBK bracket convention for superspace.** Per CSV row 7: `{` for
   rank/generator-shaped tiles, `(` for prime/dimensionality-shaped tiles —
   **only in superspace tiles**; existing-grid bracket constants are
   untouched. Test-locked in `106accf`.

6. **Mode-gated conversion rows.** `ss_targets` and `ss_prescaler` appear
   only when mode is `""` or `"prime-based"`. The "nonprime-based" mode
   hides them. CSV row 6 is the source of truth.

7. **`generators`/`comma_ratios` for nonstandard.** These multiply out the
   (possibly nonprime) basis elements as `∏ element_i ** monzo_i`, not the
   prime-monzo reading. The Barbados comma's prime-monzo reading would be
   `100/27`; the correct basis-reading is `676/675`. Locked by tests.

8. **Subgroup filtering of target sets.** `target_interval_set` for a
   nonstandard basis filters via
   `filter_target_intervals_for_nonstandard_domain_basis`. So `5/4` is
   absent for `2.3.13/5` (5 alone isn't reachable). Without this filter,
   the existing `_monzos` helper would fail on unreachable intervals or
   silently truncate.

---

## Known minor gaps / follow-ups (not blockers)

- **Standard-domain superspace visual.** Trivial-identity columns/rows
  appear when the toggle is on for a 2.3.5 domain. Acceptable as a
  preview/teaching mode; flag if Douglas wants it tightened.
- **`mod 𝒈 → prime-based mode falls off`** (CSV row 4): when 𝒈 (the
  regular generator-tuning row) becomes interactive — mouse-wheel
  editable — editing it should auto-flip `nonprime_basis_approach` away
  from `"prime-based"`. There's likely a `TODO` comment Phase 4α left
  near the tval emission. Not built; 𝒈 isn't yet editable in this way.
- **`projection × nonstandard_domain`.** The `projection` toggle is still
  greyed (per the project_projection_box memory: still blocked on the
  unbuilt rational embedding chooser). Phase 5 verified the
  cross-feature sweep doesn't crash; the actual superspace projection
  variants (P_L = G_L M_L etc., per the mockup) are not built.
- **`identity_objects × nonstandard_domain`.** Greyed; no interaction
  built. Cross-sweep confirmed no crash.

---

## How to verify it's live

```
# from the repo root
python -c "
from rtt.web.editor import Editor
from rtt.web import spreadsheet, settings
e = Editor()
e.try_edit_mapping_text('2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}')
lay = spreadsheet.build(e.state, {**settings.defaults(), 'nonstandard_domain': True})
print('header:primes ->', next(c.text for c in lay.cells if c.id=='header:primes'))
print('domain elements ->', [c.text for c in lay.cells if c.id.startswith('prime:')])
print('superspace primes ->', e.state.domain_basis, '->',
      __import__('rtt.web.service', fromlist=['superspace_primes']).superspace_primes(e.state.domain_basis))
"
```

Expected: header is `basis\nelements`, prime cells are `['2', '3', '13/5']`,
superspace primes are `(2, 3, 5, 13)`.

For the live UI: launch on an 8200+ port with `reload=False` (NEVER 8137 —
that's the user's running app; never 8188/8189 — ComfyUI), load BARBADOS in
the mapping box, flip `nonstandard_domain` on in the Show panel.

---

## Review-mode pointers (where to look first)

1. **`rtt/web/service.py`** — every signature with `domain_basis=...`,
   plus the superspace exposers (`superspace_primes`,
   `superspace_dimension`, `superspace_rank`, `basis_in_superspace`,
   `superspace_mapping`, `superspace_just_mapping`, `superspace_tuning`,
   `targets_in_superspace`, `complexity_prescaler_in_superspace`,
   `domain_has_nonprimes`, `is_standard_domain`). These are the contract
   the layout consumes.
2. **`rtt/web/spreadsheet.py`** — the `build()` data block (where
   `elements = state.domain_basis` and `approach` enter), the
   `col_bands` extension for `ssgens`/`ssprimes`, the `row_bands`
   extension for `ss_vectors` / `ss_mapping` / `ss_just_mapping` / the
   two mode-gated rows, the new TILES / CAPTIONS / SYMBOLS /
   EQUIVALENCES / FRAMED_ROWS entries, and the new bracket constants.
3. **`rtt/web/editor.py`** — the `nonprime_basis_approach` field +
   setter + the `expand`/`shrink`/`can_expand`/`can_shrink` gating + the
   `try_edit_*_text` parse paths.
4. **`rtt/web/settings.py`** — `nonstandard_domain` in IMPLEMENTED.
5. **`rtt/web/app.py`** — the 3-radio render in the damage region,
   `_EXAMPLE_TEXT["nonstandard_domain"]`, the
   target-chooser default-limit sites.
6. **The CSV** — `RTT maximized mockup - blue text transcription -
   Sheet3.csv` is the spec. Each row maps to one or two commits.
7. **Tests** — `tests/test_web_service.py`, `tests/test_web_editor.py`,
   `tests/test_web_spreadsheet.py`, possibly
   `tests/test_web_render.py` for any cross-feature render coverage the
   sweep added.

---

## Architecture notes Douglas might want in memory after review

- Service is now fully domain-aware — every interval-set, tuning, and
  size function threads `domain_basis`. Future features over a
  nonstandard domain should follow this pattern, not add a new seam.
- The superspace columns/rows scaffolding is reusable. When `projection`
  (and its superspace variants P_L = G_L M_L) are eventually built,
  they should be content drops into already-existing columns, not new
  structural work.
- The 3-mode radio (`nonprime_basis_approach`) is a generic
  Editor-state field, not a setting. Future analysis selections should
  follow this pattern (parallel to `tuning_scheme`, `range_mode`).
