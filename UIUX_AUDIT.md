# D&D's RTT App — UI/UX & Front-End Audit: consolidated remediation plan

_A living backlog. Two independent multi-agent audits (a UI/UX + front-end pass and a consistency + simplicity pass) read the actual `rtt/app/` source; every finding below was adversarially re-verified against its cited `file:line` before it survived. 16 candidate findings were refuted on that check and are listed at the end so they are not re-raised._

**Verified findings: 116** — 0 critical · 6 high · 23 medium · 57 low · 30 nit. Each is tagged with an effort estimate (S ≈ minutes, M ≈ an hour or two, L ≈ a focused day).

## Guardrails every fix must respect

These are hard project rules; a "fix" that breaks one is worse than the finding.
- **No code comments and no docstrings.** Tests + names are the only documentation. Never add prose to explain a change — improve the name, add a test, or restructure until it's unnecessary.
- **The PNG design mockups are the authoritative spec for what UI exists.** Do not add, remove, or "restore to the mockup" any row/column/tile/control. These fixes touch craft, code, and copy — not the feature set. Documented deliberate deviations (optimize button removed, custom-weights Show toggle, tuning-panel nesting, "tile features" title, decimals toggle, "interval ratios" naming) are NOT bugs.
- **No coupling / god-object refactoring.** That campaign is complete and gated. Stay at local simplicity: dedup, rename, delete, tokenize, escape.
- **Reuse the existing shared widget vocabulary;** never fork a parallel snowflake. "box" is a deliberate formal term — do not "de-jargon" it.
- **Terminology default is D&D systematic names;** never introduce TE/TOP/CTE/POTE names.
- **Workflow:** TDD (lock behavior with a test first/alongside), run the fast suite `.venv/bin/python -m pytest -q --ignore=tests/app/integration/test_web_render.py`, then land via PR + the merge queue. Rename-heavy PRs trip the 50/500-line size gates — fold a small extraction in or split, and run the full local gate (ruff check + format + quality_checks).

## Suggested order

Do **WP1 first** (security). Then the P1 tier (WP2–WP5) — the accessibility and delivery/performance work that actually gates wide distribution. The P2 tier (WP6–WP9) is the consistency/simplicity bulk and is largely mechanical; **WP6 (tokens) unblocks the most other cleanups** and should lead that tier. P3 (WP10–WP12) is polish and copy. WPs are scoped to mostly-disjoint files so several can run in parallel; the notable overlap is `page_assets.py` (WP1/WP4/WP6) and `rtt.css` (WP3/WP6/WP10) — sequence those or expect a small rebase.


---

## WP1 · [P0] Security hardening

**Goal.** Close the share-link DoS and bring the two stray raw-HTML sinks + the wheel coercion onto the escaping/robustness convention every sibling path follows.

**Owns.** `rtt/app/page_assets.py, rtt/app/editor_codec.py, rtt/app/app.py, rtt/app/_recon_display.py, rtt/app/render_html_text.py`

**Scope.** 5 findings (1 high · 3 low · 1 nit).

- **[high·S]** Share-link state decoder zlib-decompresses an attacker-controlled URL token with no size limit (DoS / zip bomb)  
  `rtt/app/page_assets.py:79-81`  
  *Problem:* The decompression and subsequent json.loads run synchronously on the page-render path before any validation.  
  *Fix:* Bound both stages before doing the work: reject tokens over a sane length (e.g. a few KB — real serialized docs are tiny) and use zlib.decompressobj().decompress(data, max_length=CAP) with a hard cap (e.g.

- **[low·S]** Pending plain-text cells interpolate prefix/draft/suffix into raw HTML without escaping  
  `rtt/app/_recon_display.py:202-204`  
  *Problem:* Every other display sink in this file routes user-influenced text through an escaping helper (_math_html, _units_html, _underline_html);  
  *Fix:* Run prefix/draft/suffix through the same escaping helper the committed cells use (e.g. _run_html, which already preserves the SUB tags these strings rely on) before wrapping draft in the rtt-pending-q span, so this path obeys the single escaping chokepoint.

- **[low·M]** Loaded share-state runs the full RTT render outside the load try/except  
  `rtt/app/app.py:75-93`  
  *Problem:* A share token can deserialize into a structurally-valid-but-pathological document (e.g.  
  *Fix:* Cap the deserialized collection sizes in codec.load (reject documents whose rank/vector-count/target-count exceed what the UI realistically shows) so an oversized share-state falls back to defaults via the existing guard, and consider extending the guard to wrap the initial render. Add a test that an over-large interest_vectors payload is rejected by load().

- **[low·S]** Math-expression cell builds line <div>s by raw f-string interpolation, bypassing the escape chokepoint  
  `rtt/app/render_html_text.py:40-45`  
  *Problem:* Same class as the pending-text sink: the closed-form math-expression text (e.g.  
  *Fix:* Escape line (html.escape) before interpolation in _mathexpr_html — the font-size style is the only intended markup, the operand text should be inert. Pin with a test that a < in an expression line renders escaped.

- **[nit·S]** wheel_step coerces deserialized/typed text via float() including an ∞→inf substitution with a silent 0.0 fallback  
  `rtt/app/render_html_text.py:59-71`  
  *Problem:* Minor robustness, not security: any unparseable wheel value silently becomes 0.0 rather than no-op'ing on the current text, so a scroll on a malformed cell can jump the value to ±step from zero instead of being ignored;  
  *Fix:* Return text unchanged on the ValueError branch instead of treating a malformed value as 0.0, and assert/guard step > 0 (or pin both via tests). No comment needed — a named guard or a test carries it.


---

## WP2 · [P1] Accessibility — grid semantics, keyboard focus & targets

**Goal.** Make the spreadsheet reachable and announceable: ARIA grid roles + accessible names, real DOM focus with roving tabindex, ≥24px hit areas, accessible SVG glyphs.

**Owns.** `rtt/app/building.py, rtt/app/_page_parts.py, rtt/app/reconciler.py, rtt/app/assets/activecell.js, rtt/app/render_html_glyphs.py, rtt/app/spreadsheet_constants.py`

**Scope.** 4 findings (3 high · 1 medium).

- **[high·L]** Grid cells are not focusable and keyboard nav never sets DOM focus — keyboard/AT users cannot reach the grid  
  `rtt/app/assets/activecell.js:71`  
  *Problem:* Tab from the page chrome is hijacked (activecell.js:208 blurs any non-grid focus), but the grid cells themselves are not in the tab order and carry no focus, so a keyboard-only or screen-reader user has no focusable, announce-able position in the grid.  
  *Fix:* Make value cells real focus stops (roving tabindex: active cell tabindex=0, others -1) and call element.focus() in moveTo() instead of only a class toggle, so AT focus and the visual highlight stay in lockstep; keep the synthetic hover events for the hover-features.

- **[high·L]** Entire data grid is unlabeled div-soup — no table/grid semantics, zero ARIA, invisible to screen readers  
  `rtt/app/building.py:80`  
  *Problem:* A screen-reader user gets no table structure, no row/column headers, no cell coordinates, and no accessible names for any value — the app's entire reason for existing (a labeled RTT spreadsheet) is completely opaque to assistive tech.  
  *Fix:* Expose the grid relationships with ARIA on the existing divs (no markup-shape change needed): role="grid" on the board, role="row"/role="columnheader"/role="rowheader"/role="gridcell" on the bands and cells, and aria-label on each value cell carrying its row-label + column-label + bracket value (the data is already computed server-side). Pin it with a render test asserting the roles/labels are present.

- **[high·M]** In-grid checkbox/toggle marks are 16px touch targets — below the WCAG 2.2 minimum and unusable on touch  
  `rtt/app/spreadsheet_constants.py:55`  
  *Problem:* The row/column-header and tile 'marks' that drive the whole feature-selection UX are 16px squares packed into a dense grid.  
  *Fix:* Give checkboxes/marks a larger invisible hit area (padding or a transparent ::before extending the clickable region to ≥24px, ≥44px under the coarse-pointer media query) while keeping the 16px visual, so density is preserved but the target meets the minimum.

- **[medium·S]** Icon-only SVG glyphs (audio waveform, mode matrix, controls) have no accessible name  
  `rtt/app/render_html_glyphs.py:31`  
  *Problem:* To a screen reader these interactive glyph controls are empty/unlabeled, so a user can't tell sine from square from sawtooth or know what a control button does — the audio settings are operable by sighted users only.  
  *Fix:* Add `role="img"` + `<title>` (or aria-label on the wrapping clickable element) naming each waveform/mode/control; the kind string is already in scope at emit time, so the name is free.


---

## WP3 · [P1] Accessibility — motion, theme, contrast & responsive

**Goal.** Honor OS preferences and adapt to viewport: prefers-reduced-motion, prefers-color-scheme, contrast fixes, a width breakpoint / narrow-viewport affordance, lang attribute.

**Owns.** `rtt/app/assets/rtt.css, rtt/app/assets/rtt-dark.css, rtt/app/app.py, rtt/app/spreadsheet_constants.py`

**Scope.** 7 findings (5 medium · 2 low).

**Status — shipped (PR #189), with one accepted limitation on the two `rendered:mobile-375px` items.** The responsive fix is CSS-only (it collapses the wordmark rail). A *genuine* mobile grid reflow is deliberately **out of scope**: `LABEL_WIDTH`/`freeze_x` are Python-computed and synced against by `freeze.js`, so a media query cannot narrow the board without desyncing it. **Mobile is fixed-width horizontal-scroll by design** — a true phone explorer is a layout-engine change *and* a design decision (with Dave), not a CSS follow-up, so don't rediscover it as a bug. WP12 covers the graceful "best on a wider screen" degradation.

- **[medium·L]** No responsive layout: fixed-width grid forces dual-axis scrolling and wastes ~30% of width on mobile  
  `rendered:mobile-375px`  
  *Problem:* On phones the app is effectively unusable for browsing values: the always-pinned rail eats a third of the screen and the user must scroll two axes to read a single mapping row.  
  *Fix:* Add a narrow-viewport CSS path (the CSS is already a single string you control) that shrinks/collapses the wordmark rail and the row-label width below ~600px, and consider not building columns that can't be reached. No mockup change is implied — this is craft within the existing surface.

- **[medium·L]** No responsive layout at all — single fixed grid, only media query is a hover feature-query, not a width breakpoint  
  `rtt/app/assets/rtt.css:178`  
  *Problem:* At 375px the fixed left rail (rotated wordmark + bold row labels) eats ~30% of width and only ~1 data column is visible, forcing simultaneous horizontal+vertical scrolling (rendered:mobile-375px).  
  *Fix:* Add width breakpoints that at minimum collapse/narrow the left rail on small viewports and let the grid pane reclaim its width; consider a mobile affordance to temporarily hide the rotated wordmark band.

- **[medium·S]** No prefers-reduced-motion support; ~41 animated rules + auto-starting tour run regardless of OS setting  
  `rtt/app/assets/rtt.css:219`  
  *Problem:* Users who set 'reduce motion' for vestibular reasons still get the full structural-reflow slides, fade-ins, drawer animation, and an auto-running guided tour with moving spotlight on first load.  
  *Fix:* Add `@media (prefers-reduced-motion: reduce){ :root{ --t:0s } }` (or default the `animations` setting from that media query at page build) and skip tour autostart when reduce-motion is set. The `--t` kill-switch already exists, so this is mostly one media block.

- **[medium·S]** Muted text fails contrast: 7px #555 unit on #e0e0e0 tiles and #999 disabled captions on #c0c0c0  
  `rtt/app/assets/rtt.css:415`  
  *Problem:* Cell unit labels (the cents/units sub-text) and disabled captions are illegible to low-vision users and fail AA, in a UI whose whole pedagogical value is reading these small annotations.  
  *Fix:* Darken #555 cell units toward #333 (and raise the 7px size or weight) and lift #999 disabled captions to meet 4.5:1 against #c0c0c0 (≈#595959 or darker); mirror in rtt-dark.css.

- **[medium·M]** Core affordances are hover-only with no touch/focus fallback  
  `rtt/app/assets/rtt.css:561`  
  *Problem:* Touch users lose the zoom loupe, the reduce/reciprocate ratio operations, all guide tooltips, and the mapping-demo trace — a substantial slice of the app's explanatory/editing affordances is simply unavailable without a mouse.  
  *Fix:* Provide a tap/long-press or focus path to these hover-gated features (e.g. surface reduce/reciprocate on focus-within as well as hover, and a tap-to-toggle loupe under the coarse-pointer query), reusing the existing controls rather than new widgets.

- **[low·S]** No lang attribute and dark mode ignores prefers-color-scheme  
  `rtt/app/app.py:209`  
  *Problem:* Missing `lang` means screen readers may use the wrong pronunciation/voice;  
  *Fix:* Set `lang="en"` on the document (NiceGUI page config) and default the dark setting from `window.matchMedia('(prefers-color-scheme: dark)')` on first load when the user hasn't explicitly chosen.

- **[low·S]** The wordmark animates a skew/rotate mid-drawer-slide with no reduced-motion guard  
  `rtt/app/assets/rtt.css:76`  
  *Problem:* A large 22px title visibly rotating/translating on every settings open is exactly the kind of motion vestibular users want suppressed, and the transient skew reads as jank.  
  *Fix:* Covered partly by adding the prefers-reduced-motion --t:0s rule; additionally consider crossfading the two title orientations rather than rotating a single element to remove the mid-skew artifact.


---

## WP4 · [P1] Performance — cacheable asset & font delivery

**Goal.** Stop re-shipping ~187KB CSS+JS uncached per visit and ~490KB of full STIX faces: serve fingerprinted static assets with long cache, defer JS, subset + preload fonts.

**Owns.** `rtt/app/_page_parts.py, rtt/app/page_assets.py`

**Scope.** 7 findings (1 high · 4 medium · 2 low).

- **[high·M]** ~187 KB of CSS+JS is inlined per client (shared=False), never browser-cacheable  
  `rtt/app/_page_parts.py:35`  
  *Problem:* Every visit (and every hard refresh) re-downloads the full ~187 KB of CSS+JS as part of the page payload instead of as cacheable `<link>`/`<script src>` static files.  
  *Fix:* Serve rtt.css and the JS modules as real static assets: register them under the existing app.add_static_files('/rtt-fonts', ...) pattern (e.g. '/rtt-assets') with a long max_cache_age and a content-hash in the URL, then reference via ui.add_head_html('<link rel=stylesheet href=...>') / '<script defer src=...>'.

- **[medium·S]** @font-face lives in a late <style> with no <link rel=preload>, so face download starts only after CSS parse  
  `rtt/app/_page_parts.py:35`  
  *Problem:* Because the @font-face rules are discovered only after the big ~102 KB rtt.css string is downloaded and parsed, the browser cannot begin fetching the STIX faces early.  
  *Fix:* Emit <link rel="preload" as="font" type="font/woff2" href="/rtt-fonts/STIXTwoText-Regular.woff2" crossorigin> (and the italic/bold faces the first paint needs) via ui.add_head_html before the stylesheet, so the fetch starts in parallel with CSS. Same-origin self-hosted fonts still need crossorigin on the preload to match the CORS-anonymous font fetch.

- **[medium·M]** All 7 JS modules load synchronously up front with no defer/async or code-splitting  
  `rtt/app/_page_parts.py:40`  
  *Problem:* ~64 KB of JS is parsed/executed before the grid is interactive, including features most first-load users never trigger.  
  *Fix:* When the modules move to static files (first finding), load them with `defer`, and lazy-load the optional ones (audio.js, mapping_demo.js, tour.js) on first use (first speaker click / first demo toggle / tour start) instead of at head time. Keep only freeze.js/the busy/zoom hooks eager.

- **[medium·M]** ~490 KB of four FULL (un-subset) STIX Two Text faces are shipped; only Math is subset  
  `rtt/app/page_assets.py:356-368`  
  *Problem:* The grid uses a small, known glyph repertoire (Latin letters, digits, basic punctuation, a handful of symbols).  
  *Fix:* Subset the four STIX Two Text faces to the actual codepoint set the app renders (Latin A–Z/a–z, 0–9, the punctuation/operator glyphs used by _math_html, EBK chars) the same way STIXTwoMath-subset was produced; this should cut each ~120 KB face by an order of magnitude.

- **[medium·S]** Static fonts/assets served with only 1-hour cache (max_cache_age not raised)  
  `rtt/app/page_assets.py:49`  
  *Problem:* The ~490 KB of immutable woff2 fonts re-validate every hour, so a user returning the next day re-downloads all faces.  
  *Fix:* Pass max_cache_age=31536000 (and ideally hash the font filenames so a face swap busts the cache) to add_static_files for the font mount. Same when the CSS/JS move to a static mount per the finding above.

- **[low·M]** font-display:swap + metrically-mismatched Georgia fallback guarantees a layout shift on a math-dense grid _(plausible — needs a live check)_  
  `rtt/app/page_assets.py:358`  
  *Problem:* swap paints Georgia first, then re-paints in STIX.  
  *Fix:* Add a metric-matched fallback @font-face (size-adjust/ascent-override/descent-override tuned so Georgia approximates STIX advance) and reference it in the stack, or switch the body face to font-display:optional for the first paint to avoid the swap reflow entirely. At minimum measure CLS before/after on a cold load.

- **[low·S]** Module-level disk reads of all CSS/JS at import (per worker process)  
  `rtt/app/page_assets.py:376`  
  *Problem:* Minor in production (read once per worker), but it couples asset bytes to import time and multiplies under reload/test re-import.  
  *Fix:* Folds into the static-asset migration (first finding): once CSS/JS are served from a static mount, the import no longer needs to slurp them into memory at all — Starlette streams them from disk with caching.


---

## WP5 · [P1] Performance — render & client runtime cost

**Goal.** Cut the per-load build cost: kill the double layout compute, tame the cold render, and remove O(n)-per-event reflow loops and the blind boot drumbeat.

**Owns.** `rtt/app/rendering.py, rtt/app/_rendering_ops.py, rtt/app/assets/activecell.js, rtt/app/assets/freeze.js, rtt/app/assets/mapping_demo.js`

**Scope.** 6 findings (1 high · 3 medium · 2 low).

- **[high·L]** Full grid rebuilt as 330–1100 NiceGUI elements server-side on every load (~0.8 s, event loop blocked)  
  `rtt/app/rendering.py:112`  
  *Problem:* There is one page route with no caching of the built element tree, so each fresh connection re-pays the full server-side build, and render() runs on the event loop (building_guard) — a heavy state can stall other clients' websockets.  
  *Fix:* Push more of the cold build through the same off-screen path the hot path already has: virtualization only trims body cells (render_cells body-visible gate), but frozen rows/columns and all on-screen cells build synchronously. Consider deferring non-visible frozen-band cells into _fill_offscreen on cold render too, and/or chunking the initial render with asyncio.sleep(0) yields so a large grid doesn't monopolize the loop.

- **[medium·M]** paint() forces a full layout reflow over every grid cell on every throttled scroll/mutation  
  `rtt/app/assets/activecell.js:47-69`  
  *Problem:* Each getBoundingClientRect in a loop after any style write forces synchronous layout;  
  *Fix:* Batch the reads: snapshot all rects in one pass into an array, then do all the --rtt-hl writes in a second pass (read-then-write split) to avoid layout thrashing; and short-circuit paint() to a no-op when active is null and no cell currently carries --rtt-hl.

- **[medium·M]** mapping_demo draw() measures every [data-eid] cell in the board on each new hover  
  `rtt/app/assets/mapping_demo.js:133-153`  
  *Problem:* Every time the cursor moves to a new column segment with mapping-demos on, the overlay re-queries and re-measures a large fraction of the grid via getBoundingClientRect — a full reflow per hover transition.  
  *Fix:* Cache board() once per draw, and scope the querySelectorAll to the band's source/matrix/result classes rather than all [data-eid]; consider measuring only the columns actually involved (filter by eid before measuring rather than measuring then filtering with inCol).

- **[medium·M]** _commit_render computes the layout twice per render; the off-thread 'warm-up' yields no speedup  
  `rtt/app/rendering.py:93`  
  *Problem:* Every edit-driven render pays ~2x the layout cost (~24 ms instead of ~12 ms), and the on-loop second layout still blocks the event loop — the off-thread call's only justification (warming caches so the loop pass is cheap) doesn't hold, so it's wasted CPU on the hot path of every interaction.  
  *Fix:* Either make layout() actually memoize on (state, prev_ids) so the warm-up's result is reused by render() (pass the computed Layout into render instead of recomputing), or drop the off-thread warm-up. Add a test pinning that a render triggers exactly one layout() computation.

- **[low·S]** Keyboard move triggers a synthetic mouseover that re-enters setActive and double-paints  
  `rtt/app/assets/activecell.js:158-172`  
  *Problem:* Every arrow/Tab keystroke runs the O(cells) paint() twice and immediately flips the just-set keyboard state (fromHover=false) back to hover state (fromHover=true), defeating the fromHover distinction the code maintains;  
  *Fix:* Have hoverSync dispatch a non-recognized signal, or set a reentrancy flag while dispatching the synthetic mouseover so the mouseover handler ignores it (e.g. skip setActive when a `synthetic` guard is set), so keyboard moves paint once and keep fromHover=false.

- **[low·S]** freeze boot() runs 12 full fit()+update() reflow cycles over 1.2s on every load  
  `rtt/app/assets/freeze.js:141-142`  
  *Problem:* On every page load the layout is force-reflowed and re-written 12 times across the first 1.2 seconds even when nothing is changing, competing with the ~0.8s server render and font swap for main-thread time.  
  *Fix:* Replace the fixed 12x poll with a settle condition (stop early once data-base-w/-h are present and a render has emitted), or drive the late re-fit off the existing transitionend listener and a single load event rather than a blind 1.2s drumbeat.


---

## WP6 · [P2] CSS design tokens & Python→CSS variable routing

**Goal.** Finish the token system: palette anchors, a spacing scale, ring/wash tokens, and route the Python colour/size constants into CSS vars so every value is written once. Widen the inset-box contrast.

**Owns.** `rtt/app/assets/rtt.css, rtt/app/assets/rtt-dark.css, rtt/app/assets/tour.css, rtt/app/page_assets.py, rtt/app/marks.py`

**Scope.** 23 findings (2 medium · 13 low · 8 nit).

- **[medium·L]** The documented dark palette has 14 named anchors but none are CSS variables — they are repeated raw 5–20× each  
  `rtt/app/assets/rtt-dark.css:24`  
  *Problem:* The palette exists conceptually but not structurally, so retuning any role (e.g.  
  *Fix:* Promote the anchors to custom properties (--rtt-pane, --rtt-panel, --rtt-cell, --rtt-text, --rtt-muted, --rtt-mark …) defined once on :root and once on body.rtt-dark, the way the accent subsystem already is, then reference them everywhere. This also lets the anchor 'documentation' live in code (a name) instead of a comment, satisfying the no-comments house rule.

- **[medium·S]** The two tile greys are imperceptibly different (ratio 1.077) so depth hierarchy collapses  
  `rtt/app/assets/rtt.css:277`  
  *Problem:* Inset control boxes (tuning-ranges frame, complexity box, dummy-tile control box) are meant to read as a distinct, recessed layer but are indistinguishable from the tile;  
  *Fix:* Widen the step between the tile fill and the inset-box fill (e.g. push the inset toward #ededed/#f1f1f1 or pull the tile slightly darker) so the recessed layer is perceptible without relying solely on the hairline border;

- **[low·S]** Show-panel grid uses raw 160px column and 26px row-height literals on parallel rules  
  `rtt/app/assets/rtt.css:1063,1108,1125`  
  *Problem:* The header and the rows must share the same 160px first-column width to align, but it's a magic literal duplicated on two rules — change one and the columns silently misalign.  
  *Fix:* Hoist `--show-col1:160px` and `--show-row-h:26px` into _CSS_VARS and reference them, so the header/row column widths and the row/cell heights are single-sourced.

- **[low·S]** Settings control-box look (#e8e8e8/#8a8a8a) duplicated across rtt-block-boxed and rtt-tile-complexity-box  
  `rtt/app/assets/rtt.css:277 and 1159-1161`  
  *Problem:* The dummy-tile's control box is a deliberate clone of the real tile's control box (the comment at 1158 even says so), yet the shared #e8e8e8/#8a8a8a look is hand-duplicated, while their dark counterparts are already merged — an inconsistency between the two sheets.  
  *Fix:* Either group the light fill/border into one selector list `.rtt-block-boxed,.rtt-tile-complexity-box{background:#e8e8e8;border:1px solid #8a8a8a}` (mirroring the dark rule), or tokenize the control-box surface as `--control-box-bg`/`--control-box-border`.

- **[low·M]** #8a8a8a tile-border literal repeated 6× instead of a token  
  `rtt/app/assets/rtt.css:277,371,842,911,1137,1160`  
  *Problem:* #8a8a8a is the app's standard light tile/input border, but it's a raw hex repeated 6 times in light and re-targeted per-selector in dark, so the border colour has no single source of truth (unlike --cell-border, which is tokenized).  
  *Fix:* Add `--tile-border:#8a8a8a` (retinted to #454c54/#4e555d in body.rtt-dark) and use `1px solid var(--tile-border)`; lets several dark per-selector border-color overrides collapse the way --cell-border already does.

- **[low·S]** Exact-duplicate rule blocks for the disabled target-number field (4 lines repeated verbatim)  
  `rtt/app/assets/rtt.css:592`  
  *Problem:* Dead duplication: a future change to the disabled-chooser palette must be made in two places or the two copies silently diverge, and the second block's neighboring comment re-explains logic already stated at 441-450.  
  *Fix:* Delete the second copy (lines 592-596) and, if a test pins the disabled-chooser appearance, leave it as the single source; if not, add one so the behavior is documented by the test rather than re-stated CSS.

- **[low·S]** rtt-fraction-cell and rtt-decimal-cell families duplicate base box, control reset, and pending ring verbatim  
  `rtt/app/assets/rtt.css:691 vs 728; 700-702 vs 733-735; 714-715 vs 749-750`  
  *Problem:* The two editable stacked-cell families (ratio vs cents) share their box chrome but each declares it separately, so a change to the editable-cell box has to be made twice and can silently diverge.  
  *Fix:* Merge the identical rules into selector lists, e.g. `.rtt-fraction-cell,.rtt-decimal-cell{…}` for the base box and the control reset, and `.rtt-fraction-cell.rtt-pending,.rtt-decimal-cell.rtt-pending{…}` for the ring.

- **[low·M]** The "inset 2px ring + 14% color-mix wash" pair is hand-repeated ~9× with magic 2px/14% baked in  
  `rtt/app/assets/rtt.css:714,749,762,771,786,803,808,824,826 (plus keyframes 1025-1031)`  
  *Problem:* The pending/change/remove ring+wash is one visual concept ("highlight this cell in accent X") but is expressed as ~9 copies of the same two declarations, parameterized only by which accent var.  
  *Fix:* Introduce `--hl-ring-w` and `--hl-wash` (e.g. 2px / 14%) tokens in _CSS_VARS, and factor the ring+wash pair into a shared selector list driven by a single `--accent` custom property each state sets (e.g.

- **[low·S]** Raw 16px used for the option-box size where --option-box (==OPTION_BOX_PX=16) already exists  
  `rtt/app/assets/rtt.css:993-999`  
  *Problem:* The visual/audio settings grid pins its control squares to the option-box size but does it with a magic literal instead of the existing token, so the two ways to express the same size can drift if OPTION_BOX_PX changes.  
  *Fix:* Replace the seven 16px literals in the .rtt-visual-grid / .rtt-audio-box / .rtt-vis-ctrl / .rtt-darktoggle rules with `var(--option-box)` to match the rest of the sheet.

- **[low·S]** BR_COLOR / PENDING_COLOR re-stated as raw hex in the stylesheets  
  `rtt/app/marks.py:3-4`  
  *Problem:* The mark color exists both as a Python constant fed into the SVG fills and as duplicated literals in two CSS files;  
  *Fix:* Replace the raw #2e9e3f in rtt.css:312 with var(--pending-color); for the dark retint selectors keyed on the literal #1a1a1a, key them on a shared token or document the coupling via the var rather than a bare hex (no comment needed — the var name carries it).

- **[low·M]** Dark-palette hex values duplicated between page_assets.py and the dark CSS they style  
  `rtt/app/page_assets.py:123-127`  
  *Problem:* A dark-theme color change has to be made twice (Python + CSS) with nothing tying them together;  
  *Fix:* Drive the dark option-box SVGs from CSS custom properties already defined in rtt-dark.css (the file defines --cell-bg etc.), or emit these four hexes into _CSS_DARK_VARS as variables the dark CSS then consumes, so each value is written once.

- **[low·M]** No spacing scale: ~14 distinct magic px values for padding/margin/gap with no token  
  `rtt/app/page_assets.py:339`  
  *Problem:* Rhythm is set by eyeballed one-off pixels (e.g.  
  *Fix:* Introduce a small spacing scale (e.g. --space-1..4 = 2/4/8/12px) on :root alongside the existing --pad, and migrate the high-traffic panel/tile rules to it;

- **[low·L]** Single 102KB CSS string with 58% comment volume is hard to navigate and ships every byte  
  `rtt/app/page_assets.py:376`  
  *Problem:* The stylesheet is majority prose, much of it change-narration and re-derivation the project's own guide should own, and it is delivered uncompressed on every ~0.8s server render.  
  *Fix:* Split rtt.css into a few topically-named files (surfaces, cells, choosers, audio, preview-states) concatenated the same way, and strip the heaviest explanatory/history comments in favor of clearer selector names + the guide (per the no-comments house rule); serve the concatenated CSS minified/gzipped so the prose never reaches the client.

- **[low·M]** tour.css injects a third, un-reconciled grey palette into the same 102KB string  
  `rtt/app/page_assets.py:382`  
  *Problem:* The app now has three parallel hand-tuned grey ramps with no shared source.  
  *Fix:* Once the anchors are tokenized (finding above), re-express tour.css against the same custom properties so the tour inherits the theme instead of carrying its own ramp; at minimum, align its greys to the nearest existing anchors.

- **[low·S]** Inter-box 8px gap is a bare literal repeated four times  
  `rtt/app/spreadsheet_constants.py:53`  
  *Problem:* This box-to-box gap is a real layout quantity sitting as a magic 8 amid named neighbors;  
  *Fix:* Name it once (e.g. BOX_GAP = 8) and substitute it in all four expressions.

- **[nit·S]** Dark sheet introduces speaker -dim/-hover flash styling that has no light-mode counterpart _(plausible — needs a live check)_  
  `rtt/app/assets/rtt-dark.css:176-178 vs rtt/app/assets/rtt.css:905`  
  *Problem:* The dark overlay's stated contract is to restate surfaces rtt.css already paints, but here it adds two flash backgrounds (-dim, -hover) that light mode never draws — so the same JS state produces a visible cell tint in dark and nothing in light.  
  *Fix:* If the -dim/-hover flashes are wanted in both themes, add the light `::after` backgrounds to rtt.css (with --speaker-flash-* tokens retinted in dark); if light deliberately only flashes the sounding cell, the dark -dim/-hover rules are dead and should be removed for symmetry.

- **[nit·S]** Flat icon-button reset duplicated between rtt-icon-button and rtt-hamburger  
  `rtt/app/assets/rtt.css:28-31 and 66-69`  
  *Problem:* The two chrome icon buttons share a flat-square reset written out twice;  
  *Fix:* Group the shared `padding/background/border-radius/box-shadow` reset into a `.rtt-icon-button,.rtt-hamburger{…}` selector list, leaving each rule only its size+border-colour deltas.

- **[nit·S]** q-field __control ::before/::after reset repeated on four chooser/input rules  
  `rtt/app/assets/rtt.css:372,436,597,680`  
  *Problem:* Every Quasar input in the app neutralizes the same two pseudo-element underlines, but the rule is copy-pasted per field family instead of stated once.  
  *Fix:* Collapse into a single selector list `.rtt-plain-text-edit .q-field__control::before, .rtt-preset …, .rtt-preset-number …, .rtt-cell-input-field .q-field__control::after{display:none!important}` (or one broader `.rtt-cell .q-field__control::before/::after`).

- **[nit·S]** Preset height 30px is a magic literal repeated 5× across the chooser rules  
  `rtt/app/assets/rtt.css:434,438,439,547,550,599`  
  *Problem:* All preset/target chooser parts must share one box height to line up, but 30px is hand-written six times;  
  *Fix:* Tokenize as `--preset-h:30px` (ideally derived from the same ROW_HEIGHT the comment references) and reference it across the .rtt-preset/.rtt-preset-number rules.

- **[nit·S]** scheme-button-idle hover/active rule restates the idle base declarations verbatim  
  `rtt/app/assets/rtt.css:878-880 vs 882-883`  
  *Problem:* The idle button's hover/active suppression is implemented by re-declaring the exact resting look, duplicating two long !important gradients/shadows;  
  *Fix:* Since the active idle gradient/box-shadow already win on the base rule, drop the redundant `:hover,:active` restatement (verify hover doesn't inherit a Quasar default first) or, if a real reset is needed, point both at a shared `--idle-face` so they can't drift; align light and dark to the same approach.

- **[nit·S]** Wash-tint hexes live only as a Python dict, re-listed by hand into CSS vars  
  `rtt/app/page_assets.py:121`  
  *Problem:* Adding or renaming a wash tint requires editing both the dict and the hand-written var list in parallel;  
  *Fix:* Generate the --wash-* declarations by iterating _TINTS so the dict is the single source.

- **[nit·S]** 4px viewport-clamp margin is an unnamed literal repeated across two JS overlays  
  `rtt/app/page_assets.py:544`  
  *Problem:* Two near-identical floating-card placers each hard-code the same 4px viewport margin;  
  *Fix:* Introduce a single named JS const (e.g. const MARGIN = 4) per overlay, or factor the shared place()-clamp, so the edge margin is stated once.

- **[nit·S]** OPTIMIZATION_PAD_T/B/L/R are four separate constants all equal to 8  
  `rtt/app/spreadsheet_constants.py:79-82`  
  *Problem:* Four names for one symmetric padding value is more surface than the uniformity warrants;  
  *Fix:* Collapse to a single OPTIMIZATION_PAD = 8 (keep the four call sites referencing it) unless the sides are genuinely intended to vary independently.


---

## WP7 · [P2] Dead code, structural simplicity & render-pipeline DRY

**Goal.** Delete what is inert and collapse what is copy-pasted: unused aliases, always-true plumbing, shadow-copy constants, single-use wrappers, and the duplicated emit-pipeline formulas.

**Owns.** `rtt/app/grid_tables.py, rtt/app/spreadsheet_layout.py, rtt/app/spreadsheet_decorations.py, rtt/app/spreadsheet_geometry_query.py, rtt/app/spreadsheet_emit_*.py, rtt/app/spreadsheet_constants.py, rtt/app/marks.py, rtt/app/service/text_conventions.py`

**Scope.** 21 findings (10 low · 11 nit).

- **[low·S]** Seven module-level row-set aliases are dead code (only FRAMED_ROWS is used)  
  `rtt/app/grid_tables.py:625-632`  
  *Problem:* Eight aliases were created as a convenience layer but seven are never consumed, so they read as live API while being inert;  
  *Fix:* Delete the seven unused alias assignments (lines 625, 626, 627, 628, 630, 631, 632), keeping only FRAMED_ROWS (629) which has a real importer.

- **[low·S]** "—" dash literal is defined twice (DASH and _DASH)  
  `rtt/app/service/text_conventions.py:9`  
  *Problem:* The same sentinel glyph is hand-duplicated in two modules;  
  *Fix:* Import DASH from spreadsheet_constants into text_conventions.py (or a shared low-level module) and drop the local _DASH.

- **[low·M]** MAP_BRACKETS / LIST_BRACKETS / GENMAP_BRACKETS are a shadow copy of the EBK convention glyphs that production never reads  
  `rtt/app/spreadsheet_constants.py:120-122`  
  *Problem:* Two parallel sources of truth for the same glyphs: the live EBK convention table and a hand-maintained constants tuple.  
  *Fix:* Either delete the three constants and have the tests assert against ebk_convention(...).outer_open/close (the real source), or make bracket()/matrix_frame() actually consume the constants for the non-EBK fallback path so there is one source. Do not keep both.

- **[low·S]** Em-dash glyph defined under two names plus a raw literal across module families  
  `rtt/app/spreadsheet_constants.py:123`  
  *Problem:* The same dash placeholder has three spellings in three places;  
  *Fix:* Pick one canonical name in one module and have the service text family import it instead of redefining _DASH; replace the raw "—" in service/display.py:8 with that constant.

- **[low·M]** _emit_mapped_tile and _emit_canon_mapped_tile are near-identical emitters differing only in top-fn and id shape  
  `rtt/app/spreadsheet_emit_mapping.py:321`  
  *Problem:* The canon path re-implements the mapped-tile loop instead of reusing the _MappedTile descriptor that the mapping path already uses, so the two can diverge (e.g.  
  *Fix:* Fold _emit_canon_mapped_tile into _emit_mapped_tile by parametrizing the top-fn (map_top vs canon_top), the id index (rt vs i), and the unit context — passing canon tiles through the same _MappedTile descriptor.

- **[low·S]** full_u predicate duplicated across matrix and vectors emitters  
  `rtt/app/spreadsheet_emit_matrix.py:236`  
  *Problem:* The 'is the unchanged basis fully resolved' check is computed in two files by hand;  
  *Fix:* Expose it once (e.g. resolved.unchanged.full or a helper on the resolved model) and reference it from both call sites.

- **[low·M]** Four superspace quantity/matrix blocks repeat the same row_open-and-tile_open guard plus basis loop  
  `rtt/app/spreadsheet_emit_vectors.py:149`  
  *Problem:* The superspace prime-basis column is emitted by three structurally identical guarded loops differing only in row key / id prefix, so adding or changing the basis cell shape means editing three sites.  
  *Fix:* Extract a helper emit_superspace_basis_column(cells, resolved, geometry, context, row_key, id_prefix, top_fn) and call it for superspace_vectors and superspace_projection (and reuse for the matrix.py quantity-prime copy).

- **[low·S]** "center a column inside the quantities column" formula is hand-inlined four times  
  `rtt/app/spreadsheet_emit_vectors.py:59`  
  *Problem:* The same centering geometry is repeated four times;  
  *Fix:* Extract a single basis_col_x(geometry) (or reuse _basis_col_x's first return value) and call it from _emit_superspace_quantity_rows and _emit_projection_basis.

- **[low·M]** target_left / interest_left / held_left are three near-identical functions  
  `rtt/app/spreadsheet_geometry_query.py:224-233`  
  *Problem:* Three copies of `geometry.X_x + BRACKET_WIDTH + i * (COLUMN_WIDTH + interval_col_gap("X"))` must be kept in sync;  
  *Fix:* Collapse into one `interval_left(geometry, column_key, i)` keyed off a {column_key: x-attr} lookup (or the already-present content_x), since every call site already knows the column key; update the ~25 lambdas (e.g.

- **[low·M]** `collapsible` is a constant True threaded through bands, Geometry, RowBand, and two dead guards  
  `rtt/app/spreadsheet_layout.py:144-156`  
  *Problem:* A field that is always True pretends to be per-band data: it widens the band tuples, occupies a Geometry/RowBand slot, and makes two emit_headers branches look conditional when they always run, so a reader cannot tell collapsibility is universal without grepping all 31 tuples.  
  *Fix:* Drop the `collapsible` element from the column/row band tuples and the column_collapsible/RowBand.collapsible plumbing, and unwrap the two `if ...collapsible:` guards in emit_matrix to run unconditionally (every column header and row label always gets a fold toggle).

- **[nit·S]** Brace control offsets 2.0/3.2/5.5 duplicated between brace() and curly_bracket()  
  `rtt/app/marks.py:117`  
  *Problem:* The brace geometry is authored twice as raw numbers;  
  *Fix:* Name the triple once (e.g. _BR_BRACE_END, _BR_BRACE_SERIF, _BR_BRACE_CUSP_DX) alongside the existing _BR_BRACE_* primitives and reference it in both functions.

- **[nit·S]** Quadratic-bezier sample count n=10 (and n=8) repeated as a bare literal across bracket functions  
  `rtt/app/marks.py:95`  
  *Problem:* The curve-tessellation resolution is a single conceptual parameter scattered as four bare numbers;  
  *Fix:* Hoist a module-level BEZIER_SAMPLES (and, if the foot is intentionally coarser, a named variant) so the resolution is set once.

- **[nit·S]** Inline cell-frame CSS "border:1px solid #555;background:#fff" duplicated in tile builders  
  `rtt/app/render_html_tiles.py:157`  
  *Problem:* The example-tile cell frame is restated as a raw inline style in two places instead of a shared token/snippet, so the dummy-tile cell can visually drift from the real grid cell.  
  *Fix:* Pull the cell-frame fill/border into one small constant or CSS class and reference it from both example-HTML builders.

- **[nit·S]** `prescale_top` is a named closure where every sibling row uses a lambda  
  `rtt/app/spreadsheet_decorations.py:124-141`  
  *Problem:* One entry uses a different mechanism (named inner def) than its eleven peers for no functional reason, breaking the uniform lambda table and forcing the reader to scroll up to see what prescale_top is.  
  *Fix:* Replace the named closure with an inline `lambda i: query.subrow_top(geometry, "prescaling", i)` for both prescaling entries to match the rest of the dict.

- **[nit·S]** `_panel` is a single-use guard wrapper that could fold into its only caller  
  `rtt/app/spreadsheet_decorations.py:202-211`  
  *Problem:* The extra function only relocates a guard-and-append out of a 3-line loop, adding a parameter-shuffle (note the column_key/row_key argument-order swap between the loop variables and the call) without reuse.  
  *Fix:* Inline the guard and Block append into the `for bid, row_key, column_key in geometry.tiles` loop in _emit_panels and drop _panel.

- **[nit·S]** FAN bus-x and gen-right formulas duplicated between gens row and draft row  
  `rtt/app/spreadsheet_emit_mapping.py:93`  
  *Problem:* The map-bus and gen-right geometry are copy-pasted across the real-row and draft-row emitters in the same file, so the two map_minus boxes can drift.  
  *Fix:* Extract a small helper (e.g. map_minus_span(geometry)) returning (bus_x, gen_right) and call it from both _emit_mapping_gens and _emit_mapping_draft_row.

- **[nit·S]** superspace_generators(context.state) fetched and indexed in two emitters _(plausible — needs a live check)_  
  `rtt/app/spreadsheet_emit_vectors.py:157`  
  *Problem:* Two emitters independently fetch the superspace generators and re-implement the same bounds-guarded indexing to fill the genratio column.  
  *Fix:* Factor the guarded fetch (returning the padded list or a left/text closure) into one helper both call sites use.

- **[nit·S]** Six hand-written "DASH if x is None else str(x)" expressions for unchanged-cell text  
  `rtt/app/spreadsheet_emit_vectors.py:256`  
  *Problem:* The same None→DASH text formatting is open-coded six times across the two emitters;  
  *Fix:* Add a tiny dash_or_str(v) helper in spreadsheet_emit_model.py (next to voice/element_cell_kind) and use it at all six sites.

- **[nit·S]** `content_box` is a single-use one-line wrapper used only inside matrix_span  
  `rtt/app/spreadsheet_geometry_query.py:137-138`  
  *Problem:* A named public helper for a two-attribute tuple read adds an indirection with no reuse, so a reader must jump to its definition to confirm it is trivial.  
  *Fix:* Inline the two attribute reads into matrix_span and delete content_box.

- **[nit·S]** Inconsistent row/column lookup styles inside tile_of (next() vs manual loop)  
  `rtt/app/spreadsheet_geometry_query.py:141-154`  
  *Problem:* Two different idioms for the same point-in-interval scan in one tiny function;  
  *Fix:* Use the same `next((ck for ck, cx in geometry.content_x.items() if cx - 0.5 <= x < cx + geometry.content_width[ck] + 0.5), None)` form for ckey so both axes read identically.

- **[nit·S]** `_define_col_bands` and `_init_row_geometry` take a constant-only parameter  
  `rtt/app/spreadsheet_layout.py:119`  
  *Problem:* Parameterizing on a value that is always the same imported constant adds a false degree of freedom — a reader may think the caller can vary the label width / header height, but there is exactly one call site passing the constant.  
  *Fix:* Drop the label_width/header_height parameters and reference LABEL_WIDTH / HEADER_HEIGHT directly inside the two functions.


---

## WP8 · [P2] Naming uniformity

**Goal.** One spelling per concept: canonical-generator, generator-index, matrix-label, cell-kind tags, the build_/make_ verb, the finv token, and derive the cell-kind frozensets from one source. Mind the rename size-gate.

**Owns.** `rtt/app/spreadsheet_geometry_query.py, rtt/app/spreadsheet_emit_*.py, rtt/app/_recon_*.py, rtt/app/ids.py, rtt/app/reconciler.py, rtt/app/spreadsheet_constants.py, rtt/app/page_assets.py`

**Scope.** 10 findings (6 low · 4 nit).

- **[low·L]** Cell-kind tag strings mix run-together and snake_case for the same kind of identifier  
  `rtt/app/_recon_kinds.py:20,46,55,78,95,102 vs 19,72,83,96; spreadsheet_constants.py:5-30 (VALUE_KINDS)`  
  *Problem:* There is no single rule for how a multi-word cell-kind tag is spelled, so the same class of string-literal identifier reads two ways depending on which register function or constant set you land in, and adding a kind invites guessing.  
  *Fix:* Choose one convention for cell-kind tags (snake_case is already dominant in the control/button registers) and normalize the run-together value/label kinds to match; these strings are matched in tests, so update kinds and tests together.

- **[low·M]** ids.py cell-id factories disagree on token/prime order, forcing a special-cased parser  
  `rtt/app/ids.py:1-27; page_assets.py:194-200 (_vgroup_key)`  
  *Problem:* Two argument-to-segment conventions for sibling factories in one tiny file means the id grammar isn't uniform, and downstream parsing pays for it with a kind-keyed special case that is easy to get wrong when a new cell kind is added.  
  *Fix:* Standardize all five on one segment order (e.g. cell:{kind}:{prime}:{token}), drop target_cell's anomalous vector:targets prefix to cell:targets:..., and collapse _vgroup_key to a single uniform parse.

- **[low·M]** Three overlapping cell-kind frozensets defined in three different modules  
  `rtt/app/page_assets.py:394`  
  *Problem:* The kind taxonomy is spelled out three+ times with no shared base;  
  *Fix:* Derive GRIDVALUE_KINDS from _GRIDVALUE_SPECS.keys() (or vice-versa) so the editable set has one source, and co-locate the value-kind frozensets so their relationship is expressible (e.g. define them as named subsets/supersets of one another) rather than as parallel hand-maintained literals.

- **[low·S]** matrix-label constants abbreviated MATLABEL_* / _SS / _W while the concept is spelled matrix_label everywhere it is consumed  
  `spreadsheet_constants.py:67-71 (MATLABEL_HEIGHT/PAD/WIDTH/W_SS/W_SSPRIMES); _recon_kinds.py:20 (cell_kinds["matrix_label"]); spreadsheet_layout.py:124-126 (matrix_label_primes_width)`  
  *Problem:* MAT/W/SS are three abbreviation styles the rest of the module deliberately avoids;  
  *Fix:* Rename to MATRIX_LABEL_HEIGHT/PAD/WIDTH and MATRIX_LABEL_SUPERSPACE_WIDTH / MATRIX_LABEL_SUPERSPACE_PRIMES_WIDTH so the constants match the matrix_label kind and the *_width fields they feed.

- **[low·S]** Same "generator index" concept named gen_idx in one module and gen_index in another  
  `spreadsheet_emit_vectors.py:183-188 (gen_idx); _recon_value.py:299-318 and _recon_value_kinds.py:95 (gen_index)`  
  *Problem:* A reader can't rely on one spelling for index variables;  
  *Fix:* Settle on one suffix (the spelled-out _index aligns with the campaign direction) and rename the gen_idx / elem_idx / *_idx locals to *_index, starting with the gen_idx/gen_index pair that names one concept.

- **[low·M]** "Canonical generator" is spelled three different ways: canongen, canon_gen, and the cell-id token cangen  
  `spreadsheet_geometry_query.py:249 (canongen_left); spreadsheet_resolve_intervals.py:64 (canon_gens); spreadsheet_emit_matrix.py:187 ("cangen:{g}"); spreadsheet_emit_tuning.py:169,172 ("tuning:cangen")`  
  *Problem:* A reader grepping canongen misses the cangen cell ids and the canon_gen fields and vice versa, so the full picture of one concept is split across three spellings;  
  *Fix:* Pick one spelling for the concept (canon_gen, matching the codebase's spelled-out direction) and apply it to the function names, fields, and id tokens so canongen_left, canon_gens, and the cangen tokens all read canon_gen. Pin the chosen id tokens with the existing emit/id tests.

- **[nit·S]** Lone hyphenated mark() name breaks the otherwise run-together mark convention  
  `_page_parts.py:352 (opt.mark(f"{ref}-{key or label}"))`  
  *Problem:* One mark joins its parts with a hyphen where every sibling uses concatenation or a colon, so the mark grammar is not uniform and a test author guessing the handle format for this control will guess wrong.  
  *Fix:* Join with a colon to match the visctrl:{key} family (f"{ref}:{key or label}"), or concatenate, whichever the consuming test prefers; update that test in lockstep.

- **[nit·S]** BR_COLOR's value #1a1a1a is also hard-coded raw in CSS rather than fed from the one named source  
  `marks.py:3 (BR_COLOR = "#1a1a1a"); assets/rtt.css:310; assets/rtt-dark.css:63,67,68`  
  *Problem:* The mark color has a name (BR_COLOR) in Python but is duplicated as a bare hex in CSS, so the concept is named in one place and magic in another;  
  *Fix:* Expose BR_COLOR as a CSS custom property (as the pending/preview colors already are in page_assets.py) and reference var(--...) at rtt.css:310 and the rtt-dark.css sites so the value has exactly one named home.

- **[nit·S]** make_cell / make_cell_if_new use make_ where the package's dominant cell-construction verb is build_  
  `reconciler.py:171 (make_cell); _rendering_ops.py:128 (make_cell_if_new); vs _recon_*.py build_* (64 build_ defs)`  
  *Problem:* make_ is a third verb for the same build-a-cell action, so the construction vocabulary isn't uniform;  
  *Fix:* Rename make_cell -> build_cell and make_cell_if_new -> build_cell_if_new to fold them into the build_ family (update the few call sites and any tests referencing the method name).

- **[nit·S]** form_cell() emits token finv, matching neither its name nor its cell-kind formcell _(plausible — needs a live check)_  
  `rtt/app/ids.py:5-6 (form_cell -> cell:finv); page_assets.py:197-198 (formcell -> "cell:finv"); spreadsheet_emit_mapping.py:317 (f"cell:finv:{i}:{j}")`  
  *Problem:* finv is an undocumented abbreviation that breaks the otherwise 1:1 mapping between a factory's name/kind and its id token (mapping_cell->mapping, comma_cell->comma), so a reader can't predict the form cell's id from its kind and the magic literal must be repeated by hand.  
  *Fix:* Rename the token to form (cell:form:{row}:{column}) so form_cell, formcell, and the token all agree, or if finv is a deliberate formal term, name the factory finv_cell to match. Update the page_assets.py:198 literal in lockstep and pin with tests.


---

## WP9 · [P2] JavaScript consistency & dedup

**Goal.** Merge the fraction/decimal twin, unify the idempotency-guard scheme (and guard tour.js), share the boot-retry, and name the repeated JS magic literals / reuse the serif token.

**Owns.** `rtt/app/assets/fraction.js, rtt/app/assets/decimal.js, rtt/app/assets/audio.js, rtt/app/assets/freeze.js, rtt/app/assets/activecell.js, rtt/app/assets/tour.js, rtt/app/assets/mapping_demo.js`

**Scope.** 15 findings (1 medium · 8 low · 6 nit).

- **[medium·M]** fraction.js and decimal.js are an 80%-identical twin pair that should share one parameterized helper  
  `rtt/app/assets/fraction.js:13-86 and rtt/app/assets/decimal.js:15-76`  
  *Problem:* Two ~80-line files that must be edited in lockstep.  
  *Fix:* Extract one factory, e.g. stackedEditMode({ boxSel, modeAttr, modeOn, modeOff, openKey, opener, isFilled }), and have fraction.js and decimal.js each call it with their 4-5 differing literals.

- **[low·S]** Idempotency-guard convention is non-uniform across the 7 modules (three different schemes)  
  `rtt/app/assets/audio.js:1, rtt/app/assets/freeze.js:1, rtt/app/assets/activecell.js:17, rtt/app/assets/tour.js:16`  
  *Problem:* A reader can't tell at a glance whether a module is re-injection-safe, and the convention split is arbitrary (the four __rtt modules are not meaningfully different in kind from audio/freeze).  
  *Fix:* Pick one scheme for all 7 (the `if (window.__rttX) return; window.__rttX = true;` boolean is the clearest and already the majority), and add the missing guard to tour.js.

- **[low·S]** The speaker query selector is hand-concatenated 4-5 times in audio.js instead of one builder  
  `rtt/app/assets/audio.js:18, 22, 169, 191, 222`  
  *Problem:* segCells (169) and the body of hl (18) construct the exact same selector — segCells could just call a shared builder.  
  *Fix:* Add two tiny local helpers, e.g. `seg(tile, idx)` and `tiles(tile)`, returning the querySelectorAll, and call them at the 18/22/169/191/222 sites.

- **[low·S]** audio.js gain-floor literal 0.0001 repeated 4× as an un-named magic value  
  `rtt/app/assets/audio.js:31, 41, 42`  
  *Problem:* The module already names BASE, STEP, WAVES at the top (audio.js:3) but this acoustically-meaningful constant is scattered;  
  *Fix:* Hoist a `const GAIN_FLOOR = 0.0001;` (and optionally the ramp durations) next to BASE/STEP, and reference it at the three sites.

- **[low·S]** fraction.js hard-codes '13px' duplicating a Python-side _RATIO_MAX_FONT constant  
  `rtt/app/assets/fraction.js:50`  
  *Problem:* The font size that governs the ratio view lives authoritatively in Python but is re-typed as a raw literal in JS, kept in sync only by a comment — precisely the drift the project bans comments for.  
  *Fix:* Inject the value the same way audio's glyphs and tour's steps are injected (a small `window.rttFraction = {ratioFont: _RATIO_MAX_FONT}` stamped from page_assets.py), so there is one source. At minimum, since decimal.js does NOT do this font hack, confirm the asymmetry is intended and not a missed case.

- **[low·S]** freeze.js and audio.js register global listeners with no idempotency guard  
  `rtt/app/assets/freeze.js:1,106-140`  
  *Problem:* These rely entirely on add_body_html running the script exactly once.  
  *Fix:* Wrap freeze.js and audio.js in the same `if (window.rttFreeze) return;` / `if (window.rttAudio) return;` guard the sibling modules use, so the whole suite is uniformly re-injection-safe.

- **[low·S]** The 12-line boot-retry IIFE is duplicated verbatim in freeze.js and activecell.js  
  `rtt/app/assets/freeze.js:141-142 and rtt/app/assets/activecell.js:251-252`  
  *Problem:* The retry count (12) and interval (100ms) are a tuning decision duplicated by hand in two files;  
  *Fix:* Either factor a tiny shared `rttBoot(fn)` util (one of the few genuinely-shared utilities worth one place), or at minimum name the 12 and 100 as shared constants so the two copies can't drift.

- **[low·S]** tour.js viewport-clamp margin 12 is a magic literal repeated 6×  
  `rtt/app/assets/tour.js:88, 90, 91, 108, 109`  
  *Problem:* Inconsistent with the file's own constant-naming (PAD/GAP are named one line away), and the clamp inset is duplicated six times — change it and you must hit all six.  
  *Fix:* Add `var EDGE = 12;` beside PAD/GAP and use it at all six sites.

- **[low·M]** Fragile reliance on Quasar/Vue-internal DOM contracts that an upgrade can silently break  
  `rtt/app/page_assets.py:760-762`  
  *Problem:* These are all undocumented Quasar structural assumptions (class names, the teleport target, the no-change-event commit behavior, single-input-per-q-input).  
  *Fix:* Add render-level integration tests (User plugin) that assert the busy scrim arms on a checkbox click and that opthover/fraction selectors still match the rendered tree, so a dependency bump that breaks the contract fails CI rather than degrading silently in production.

- **[nit·S]** navLine() local var named e2 breaks the file's el naming convention  
  `rtt/app/assets/activecell.js:127`  
  *Problem:* A one-off variable name (`e2`) inconsistent with the `el` used everywhere else in the same file — reads as a leftover from avoiding a shadow that no longer exists (the branch has no outer `el` in scope here).  
  *Fix:* Rename `e2` to `el` for consistency with the rest of the file.

- **[nit·S]** Float/card re-anchor-on-scroll logic duplicated across audio.js, mapping_demo.js, and tour.js _(plausible — needs a live check)_  
  `rtt/app/assets/audio.js:253, rtt/app/assets/mapping_demo.js:221, rtt/app/assets/tour.js:164`  
  *Problem:* Three hand-rolled 'overlay rides the scroll' bindings with slightly different shapes (document vs window target, passive flag present in only one).  
  *Fix:* At minimum align the listener options (target + passive) across the three; longer-term these overlay-anchoring helpers are candidates for the same shared positioning util.

- **[nit·S]** decimal.js sync()'s comment mislabels the cell as 'fraction' — stale name in the twin _(plausible — needs a live check)_  
  `rtt/app/assets/decimal.js:22-23`  
  *Problem:* Minor naming/wording drift between the twin files;  
  *Fix:* Folding decimal.js and fraction.js into one shared factory (first finding) removes this duplicated/misworded comment outright; no standalone comment edit needed.

- **[nit·M]** Mixed var / const-let / arrow-only code style with no per-file rationale  
  `rtt/app/assets/freeze.js:2, rtt/app/assets/activecell.js:16, rtt/app/assets/fraction.js:23, rtt/app/assets/mapping_demo.js:1`  
  *Problem:* Seven sibling files in the same directory, loaded the same way, in three different dialects.  
  *Fix:* Settle on one convention (const/let + named function, which the newest files use) and bring the var-based files over the next time they're touched; at minimum, stop introducing a fourth style.

- **[nit·M]** Two parallel scroll-coalescing timer idioms re-implemented per module instead of one throttle  
  `rtt/app/assets/freeze.js:30-41, rtt/app/assets/freeze.js:94-105, rtt/app/assets/activecell.js:236-240`  
  *Problem:* The same 'collapse a burst of scroll events into one deferred call' need is solved three different ways with hand-rolled timer vars, so a reader must re-derive each module's coalescing semantics.  
  *Fix:* A single shared `trailing(fn, ms)` / `idle(fn, ms)` helper (the two shapes actually in use) would collapse these to one-liners and make the leading-vs-trailing choice explicit per call. Behavior-preserving;

- **[nit·S]** STIX serif font stack hard-coded in mapping_demo.js instead of reusing the --rtt-serif token  
  `rtt/app/assets/mapping_demo.js:94`  
  *Problem:* The serif stack is duplicated and already diverges (no 'STIX Two Math');  
  *Fix:* Reference var(--rtt-serif) in the SVG text's font-family (SVG honors CSS custom properties) instead of restating the stack.


---

## WP10 · [P3] Typography rendering polish

**Goal.** Centralize the per-glyph em-width model behind one tested source and give every <sub> the tuned optical treatment.

**Owns.** `rtt/app/render_html_text.py, rtt/app/render_html_glyphs.py, rtt/app/assets/rtt.css`

**Scope.** 3 findings (1 medium · 2 low).

- **[medium·L]** Font sizes are a sprawl of untokenized magic constants across five files  
  `rtt/app/page_assets.py:118-120`  
  *Problem:* There is no single type scale;  
  *Fix:* Lift the recurring sizes into named tokens — extend the existing spreadsheet_constants pattern (it already holds SYMBOL_FONT=15, CAPTION_FONT=9, MATLABEL_HEIGHT) so SYMBOL/CAPTION/STACKED/SUB/RANGE are defined once and both the CSS-var block and the SVG emitters read them — and pin the scale with a test, removing the duplicated literals.

- **[low·M]** Hand-maintained per-glyph em-width table is a fragile snowflake tied to one specific face  
  `rtt/app/render_html_text.py:104-127`  
  *Problem:* In-process there is no browser to measure text, so width estimation is unavoidable, but the truth lives in three different char-width numbers (0.59 / 0.62 / 0.52) keyed to STIX.  
  *Fix:* Centralize the char-width model in one place keyed to the (subset) STIX metrics and have the ratio/chart/caption estimators read from it instead of restating 0.59/0.62/0.52, and add a test that every glyph any renderer can emit has an entry (defaulting is the spill risk).

- **[low·S]** Numeric/letter subscripts in unit strings render via raw <sub> with no size/baseline control, unlike the tuned matrix-label <sub>  
  `rtt/app/render_html_text.py:68-77`  
  *Problem:* Default <sub> shrinks to ~smaller-but-unspecified size and shifts the line-box/baseline, so subscripted units (e.g.  
  *Fix:* Apply one shared sub rule (the .rtt-matrix-label sub treatment: explicit font-size %, vertical-align, line-height:0) to all <sub> inside value/symbol/unit faces so every subscript across the grid shares one optical size and baseline.


---

## WP11 · [P3] Information architecture & settings UX

**Goal.** Disambiguate the repeated labels (colorization×3, units×3), surface the preset choosers, distinguish grouping parents from leaves, and cue the refinement dependencies.

**Owns.** `rtt/app/settings.py, rtt/app/_page_parts.py, rtt/app/spreadsheet_controls.py, rtt/app/terminology.py`

**Scope.** 6 findings (5 medium · 1 low).

- **[medium·M]** Deep nesting (3 levels, 54px indent) is carried entirely by left-margin, with no connecting structure  
  `rtt/app/_page_parts.py:418-421, rtt/app/settings.py:79-98`  
  *Problem:* The tuning subtree nests three deep (tuning ▸ optimization ▸ weighting ▸ all-interval/alt-complexity/custom-weights).  
  *Fix:* Add a lightweight visual nesting cue beyond margin (a faint vertical guide line per level, or alternating subtle section tint for the two GROUPING_PARENTS subtrees) so depth is legible without counting pixels. CSS-only;

- **[medium·M]** The preset choosers — the primary way to LOAD a temperament/tuning/target — are hidden behind a default-OFF Show toggle  
  `rtt/app/settings.py:15, rtt/app/spreadsheet_controls.py:205-206`  
  *Problem:* Loading a named temperament ('Meantone'), picking a tuning scheme ('minimax-S'), or choosing a target set are the highest-intent first actions for almost any visitor, yet the dropdowns that expose them are gated by a 'presets' toggle that defaults False and is buried mid-list in the general show-group.  
  *Fix:* This is a defaults/IA judgment, not a mockup change: strongly consider defaulting 'presets' ON (or surfacing the three choosers outside the toggle-gated region) so the first-load grid is operable. If the mockup mandates default-off, at minimum the guided tour / an empty-state hint should point at it.

- **[medium·S]** Two different show-keys are both labeled "units", a third is "per-cell units" — the word 'units' means three things  
  `rtt/app/settings.py:18,19,34`  
  *Problem:* 'units' (general, key=units) shows each box's 'units: …' line;  
  *Fix:* Rename the app-features 'units' (domain_units) to 'domain-basis units' (its tooltip already says exactly this) and consider 'box units' for the general 'units' to pair cleanly with 'per-cell units'. Label-string-only edit.

- **[medium·M]** Grouping-parent toggles look identical to leaf toggles, so users toggle a 'temperament'/'tuning' checkbox expecting visible output and get none  
  `rtt/app/settings.py:32,40, rtt/app/_page_parts.py:403-417`  
  *Problem:* 'temperament' and 'tuning' are pure expand/collapse parents that 'show nothing of their own', but in the tree they are checkboxes visually indistinguishable from real leaf toggles like 'temperament tiles'.  
  *Fix:* Give grouping parents a distinct affordance from leaf toggles — e.g. a disclosure-triangle / section-header style for the two GROUPING_PARENTS keys (the set already exists) rather than a value checkbox, so 'expand a section' reads differently from 'turn a feature on'.

- **[medium·S]** Three different controls share the bare label "colorization", with no scent once the parent collapses  
  `rtt/app/settings.py:34,39,49`  
  *Problem:* The app-features tree has three rows whose visible label is identical — "colorization".  
  *Fix:* Make each label self-identifying without relying on indent: 'temperament colorization', 'form colorization', 'tuning colorization' (or a shared suffix pattern). This is a data-only change to the label strings in SHOW_GROUPS;

- **[low·S]** 'mnemonics' and 'decimals' are refinements of a parent but presented as peer leaf rows, so toggling them with the parent off is a silent no-op  
  `rtt/app/settings.py:8,17,79-82`  
  *Problem:* 'mnemonics' only refines 'names' and 'decimals' only refines 'quantities' (tooltips say 'Refines …'), and the row hides when the parent is off.  
  *Fix:* Surface the parent dependency in the label or a subtle inline cue (e.g. render refinement children with a small '↳' or 'refines names' affordance) rather than relying on indent + tooltip alone.


---

## WP12 · [P3] Pedagogy & onboarding copy

**Goal.** Tighten the teaching path: first-run chapter, tour copy/jargon/interactivity, guide-link coverage, reset re-onboarding — all copy/flag level, no structural UI change.

**Owns.** `rtt/app/assets/tour.js, rtt/app/page_assets.py, rtt/app/tooltips.py, rtt/app/settings.py, rtt/app/_recon_cells.py`

**Scope.** 9 findings (1 medium · 8 low).

- **[medium·M]** Computed value cells never offer a guide link — the deep-dive affordance is only on names/symbols  
  `rtt/app/_recon_cells.py:69`  
  *Problem:* A learner's attention is on the numbers (a tuning value, a mapped count), and hovering one gives only a terse one-liner with no path into the guide.  
  *Fix:* When a value cell's (row,column) has a GUIDE_HELP entry, surface the same guide link from the zoom-hover loupe caption (rtt-zoom-help already renders below the loupe per rtt.css:240). Reuse the existing hover-card data-attrs rather than a new widget;

- **[low·M]** Mobile learners get no tour and an unusable grid — onboarding is desktop-only by omission _(plausible — needs a live check)_  
  `rendered:mobile 375px`  
  *Problem:* A learner arriving on a phone (a large share of first-touch web traffic) cannot follow the "follow a column down" reading model the tour teaches — they can see one column at a time.  
  *Fix:* Within the existing surface (no layout invention): detect a narrow viewport and either show a one-card "best viewed on a wider screen to see the grid relationships" note before the tour, or skip autostart on very narrow viewports so the broken spotlight sequence doesn't run. Document the desktop-first stance in a test rather than leaving it implicit.

- **[low·S]** Tour-seen flag is per-browser-localStorage, so the tour never returns even after a reset  
  `rtt/app/assets/tour.js:19`  
  *Problem:* A learner who skips the tour on first glance — common — has permanently opted out of autostart even after hitting Reset to "start over," and a shared link to a teaching state never re-onboards the recipient.  
  *Fix:* Have Reset also clear rttTourSeen (one ui.run_javascript in reset_everything) so "reset to defaults" genuinely restores the first-run experience, and consider a subtle persistent hint pointing at the ? replay button for users who skipped. Add a test asserting reset clears the seen flag.

- **[low·S]** The tour introduces undefined jargon in its very first content slide  
  `rtt/app/page_assets.py:255-259`  
  *Problem:* This is the orientation slide for an absolute newcomer (autostart on first load), yet it leans on four undefined RTT terms and a matrix equation.  
  *Fix:* Soften the first content slide to motivate before naming (e.g. "the mapping decides how many steps of each generator approximate each prime;

- **[low·M]** Tour is purely descriptive — it never lets the learner *do* anything, the core way this app teaches  
  `rtt/app/page_assets.py:262-266`  
  *Problem:* The app's pedagogical thesis is that you learn temperament by manipulating the live grid and watching everything recompute — but the onboarding moment teaches entirely by telling.  
  *Fix:* Add one optional "try it" step that prompts the learner to edit a highlighted mapping cell (or pick a temperament preset) and observe the recompute, using the existing spotlight on a real editable cell. Reuse openDrawer's click pattern;

- **[low·S]** Tour step 8 describes dummy-tile parts (closed form, units) that don't exist at the default chapter  
  `rtt/app/page_assets.py:301-307`  
  *Problem:* At first run (chapter 4) the dummy tile has no "units" line and no closed-form part, so the tour points at features the learner cannot see or click.  
  *Fix:* Either phrase the step to only name parts present at the tour's chapter ("the name, the symbol, the value"), or have the tour temporarily raise the chapter while it runs so every named part is visible. Pin the claim with a render test asserting the dummy tile exposes each part the step names at the chapter the tour runs in.

- **[low·S]** Default chapter 4 skips a beginner past the foundational scaffolding the tour just promised  
  `rtt/app/settings.py:155`  
  *Problem:* A first-run learner lands two chapters deep (past Mappings ch.2 and Tuning fundamentals ch.3 as the *starting* simplification point), seeing tuning/optimization/charts/drag-to-combine all at once — the opposite of the "start small and build up" advice the tour's final Show-toggles step gives (page_assets.py:316).  
  *Fix:* Default a genuinely-new browser to CHAPTER_MIN (2) so first-run matches the tour's "start small" framing, and let the chapter persist upward as they explore; keep 4 only for returning users (the _CHAPTER_KEY doc-store already persists per browser).

- **[low·S]** "start small and build up" advice contradicts the all-on default Show state _(plausible — needs a live check)_  
  `rtt/app/settings.py:64`  
  *Problem:* The closing tour advice tells learners to enable features incrementally, but the app ships them with a dense default (ratios + vectors + symbols + equivalences simultaneously) — the most information-rich reading of every tile.  
  *Fix:* Either align the copy (acknowledge the rich default and frame the toggles as a way to *simplify*, e.g. "turn things off to declutter"), or ship a leaner first-run default within the chapter-2 set.

- **[low·M]** 19 of ~66 guide tooltips silently have no guide link — coverage holes a learner can't predict  
  `rtt/app/tooltips.py:98`  
  *Problem:* The hover-card on these tiles shows explanatory text but, unlike its neighbors, offers no "read more in the guide" link.  
  *Fix:* Add the chapter/section (or page/anchor) to every GUIDE_HELP entry that has a guide home — most do (target-mapping → Mappings, interest → Tuning fundamentals/Target-intervals analog). For the genuine few with no guide section, add a test enumerating GUIDE_HELP and asserting either a non-empty .url or membership in an explicit NO_GUIDE_SECTION set, so the gap is a deliberate, reviewed list rather than an accident.


---

## Appendix — verified NON-issues (do not re-raise)

_These were checked against source and refuted; several are deliberate, documented design._

- **Light-mode gridlines are the exact same color as the tiles they separate (contrast ratio 1.0)** — The two cited facts are literally true: page_assets.py:342 sets --c-gridline:#e0e0e0 and rtt.css:273 sets .rtt-block background:#e0e0e0, and the gridlines (.rtt-line-v/h, rtt.css:261-262) use that var.

- **Editable cells barely read as editable in light mode (fill #f4f6f9 vs tile #e0e0e0, ratio 1.219)** — The finding's evidence is materially wrong, undercutting its premise.

- **169 !important declarations in rtt.css indicate a specificity war with Quasar fought ad hoc** — Verified rtt/app/assets/rtt.css and rtt-dark.css directly.

- **The vertical wordmark uses transform:rotate(90deg), which is caught skewed mid-slide and is the wrong tool for vertical text** — Source confirms the mechanism (rtt.css:76-80: .rtt-sidetitle uses transform:rotate(90deg) closed, rotate(0deg) open, with transition:transform var(--t)), so glyphs do interpolate through intermediate angles during the slide.

- **In-grid 'mark' checkboxes and drawer Show toggles are two redundant control surfaces for overlapping state, with no cross-reference** — The finding conflates two unrelated mechanisms and is factually wrong on its central claim.

- **14-item flat 'general' group mixes display-format, value-format, and interaction toggles with no sub-headers** — Read rtt/app/settings.py:3-98 and rtt/app/_page_parts.py:397-421.

- **select-all/none has no indeterminate (mixed) state — a partially-on group reads as fully off** — The finding cites _page_parts.py:385, which is only the INITIAL build-time value of the select-all box.

- **Chapter slider can hide controls a user already enabled, with no warning that they still apply** — The finding's central claim — that lowering the chapter slider hides a control while its effect persists in the grid — is false.

- **equivalences default-on shows the defining equation but the tour assumes bare symbols** — The two factual anchors hold: equivalences defaults True (settings.py:11) and its SHOW_HELP says it shows the defining equation "instead of the bare glyph.

- **hl() highlight clears via untracked setTimeout that survives re-render, stranding 'on' state** — Verified rtt/app/assets/audio.js:36-45 plus the hl/clearHl helpers (lines 17-24) and freeze.js.

- **_GUIDE_JS / _ZOOM_JS append a singleton overlay to body but never remove it** — Read page_assets.py:520-659 (_ZOOM_JS, _GUIDE_JS), audio.js:205-225, mapping_demo.js:40-60.

- **update_cell_content recomputes a content signature for every cell on every render** — The finding's central claim is false.

- **Wordmark skews/janks mid-animation during drawer slide** — The "skew/jank" is a deliberately designed animation, not an artifact.

- **("col",...) axis literals and arm_col_target retain col after the col->column campaign** — The cited code exists exactly as described (page_assets.py:173-189 arm tuples use "col"/"row";

- **Mapping-demo example SVG hardcodes the mapping highlight palette as raw hexes** — The central claim is false.

- **0.62 glyph em-width magic constant inlined in chart indicator width math** — The code claim is accurate: render_html_glyphs.py:144 reads `lbl_width = 3 * lbl_font * 0.62 + len(indicator_label) * sub_font * 0.62 + 3`, with the bare 0.62 em-per-char factor repeated twice in one expression, and a separate 0.34 baseline factor at line 156.
