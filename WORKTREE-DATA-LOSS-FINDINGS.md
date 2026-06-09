# Worktree data-loss investigation — findings & recommendations

**Date:** 2026-06-08 · **Scope:** why uncommitted work in `.claude/worktrees/<name>/`
gets silently discarded and why a worktree gets switched onto `main` mid-session.
This is an environment/automation investigation — **no app code was changed.**

---

## TL;DR

The losses are caused by **automated "sync this worktree's branch up to `main`"
operations that run on a *dirty* working tree while `main` is moving underneath**, across
6+ concurrent worktrees. To sync, the automation moves the dirty changes aside (stash),
re-points the worktree at `main` (checkout/rebase/reset), then tries to restore. When this
races another agent fast-forwarding `main`, the recovery path goes wrong and the worktree is
left **clean (work stashed/reset away), or detached, or with its `claude/<name>` branch reset
onto `main` — dropping commits and uncommitted edits.**

The fix is two-fold:
1. **Never run destructive git ops (`reset --hard`, `clean -fd`, `stash`, `checkout main`,
   `rebase`) automatically against a dirty worktree, and never auto-switch a worktree off its
   own branch.**
2. **Agents commit every turn** so nothing important ever lives only in the working tree.

This was caught **happening live** during the investigation (see Evidence §2).

---

## Evidence

### 1. There are no user hooks doing this — it's automation/concurrency

- No `settings.json` / `settings.local.json` with hooks at repo, project, or user level
  (only a 1-line permission allow-list at `~/.claude/settings.local.json`).
- No git hooks (`.git/hooks` empty of non-samples; no `core.hooksPath`).
- So the git operations below are **not** coming from a user-authored hook. They come from
  harness worktree/session automation and/or agents running git commands that fight.

### 2. A worktree was caught being yanked through 3 states *live*, mid-investigation

Reading `objective-mestorf-7be5c7` three times within ~a minute returned three different,
self-changing states (I ran no writes):

| read | worktree state | branch tip | dirty files |
|------|----------------|------------|-------------|
| 1 (`git worktree list`) | **detached HEAD @ `c15a0be`** | — | — |
| 2 (HEAD file)           | on branch `claude/objective-…` | `f1d3813` | `spreadsheet.py` |
| 3 (re-sample ×5)        | on branch `claude/objective-…` | **`a80916a` (= current `main`)** | `grid_tables.py`, `spreadsheet.py` |

Between reads, the branch `claude/objective-mestorf-7be5c7` was **reset from its real tip
`f1d3813` onto `main`’s tip `a80916a`**. That is exactly the user’s symptom 3 ("branch
switched onto main and fast-forwarded to other agents’ commits"), observed in real time.

### 3. The dropped commit is now orphaned (real work, reflog-only)

```
$ git cat-file -t f1d3813            -> commit            (valid object)
$ git log -1 f1d3813  -> "Polish the superspace rows: EBK brackets, equivalences, …"
$ git branch --contains f1d3813      -> (empty)           -> reachable from NO ref
```

`f1d3813` is a real commit an agent made on `claude/objective-mestorf-7be5c7`; it was never
merged to `main`, and the reset knocked it off the branch. It survives **only in the reflog**
and will be lost at GC. (Recovery in §6.)

### 4. The worktree HEAD reflog shows the destructive sequence

`.git/worktrees/objective-mestorf-7be5c7/logs/HEAD`, decoded (newest last):

```
… commit:  Build out the two superspace rows …          (e6c6a62)
rebase (start):  checkout main                           (-> 6376fb8)   # tree momentarily = main
rebase (continue/finish): returning to claude/objective-…(-> f3b468b)
commit:  Polish the superspace rows …                   (-> f1d3813)   # never merged
rebase (start):  checkout main                           (-> c15a0be)   # tree = main again
rebase (abort):  returning to claude/objective-…         (-> f1d3813)   # ~2.9h later
reset:  moving to main                                   (-> a80916a)   # branch dumped onto main
```

Plus, earlier in the same log: `merge main: Fast-forward`. So the automation’s repertoire
against these worktrees includes **`rebase main`, `checkout main`, `merge main`, and
`reset` to `main`** — every one of which either moves the tree onto `main` transiently or
re-points the branch, and several of which **discard** uncommitted or unmerged work.

### 5. The "clean tree, then reappear, then on main" flicker = stash-based reconcile

The user’s symptom 2 (**tree CLEAN, HEAD unchanged, edits gone, *untracked* test file gone**)
is the precise signature of `git stash --include-untracked`: it’s the only common op that
leaves HEAD untouched yet removes both tracked edits **and** untracked files. Symptom 3’s
"files reappear" is the matching `stash pop`. Corroborating: a leftover stash exists —

```
stash@{…}: On main: rogue main edits #2 (reverts cₙ⁻¹ + HLINE_PAD)
```

— machine-generated message, **on `main`**, and labeled **"#2"**: the automation has stashed
a dirty tree to reconcile against `main` before, more than once. When the stash is dropped,
fails to pop (conflict), or pops onto the wrong branch during a race, the work is gone.

### 6. Why it races here but "works fine on the other computer"

`main` absorbs a fast-forward merge **every few minutes** under load (e.g. 16:41 → 16:49 →
16:57 → 17:03 → 17:09; sometimes 2 min apart). With 6+ worktrees each trying to sync onto a
`main` that another agent is advancing mid-sync, the "stash → checkout/rebase/reset onto main
→ pop" sequence **interleaves with another agent’s merge** and the recovery path lands wrong
(detached, or branch reset to main, or stash dropped). On the other machine there are fewer
concurrent agents / `main` isn’t moving during a sync, so the same sequence completes cleanly
and you never see it. **It’s a concurrency race, not a logic bug that fires every time** —
which is why it’s intermittent and hard to reproduce.

> Note: the actor can’t be 100% pinned from refs alone — it’s either harness worktree
> auto-sync or a "stay in sync with main" loop inside the agents. The fixes are the same
> either way. **Diagnostic:** let all agents sit idle and watch the worktree HEADs/branch
> tips (`watch -n1 'git worktree list; …'`). If states still churn with agents idle, it’s
> harness automation; if only when an agent is mid-turn, it’s agent-driven git commands.

---

## Root causes

1. **Destructive git ops run against dirty worktrees automatically** — `stash`/`reset`/
   `clean`/`checkout main`/`rebase` are used to reconcile a worktree with `main` even when the
   tree has uncommitted edits and untracked files. Any of these can drop work; a stash that
   isn’t popped (or pops with conflict) loses it outright.
2. **Worktrees get auto-switched off their own branch.** A `claude/<name>` worktree is being
   put into detached HEAD on a `main` commit, and its branch ref is being **reset onto
   `main`**, discarding unmerged commits (`f1d3813`).
3. **Per-worktree sync chases a moving `main` with no serialization.** With merges into `main`
   every few minutes across 6 agents, the multi-step sync races other agents and lands in a
   bad partial state.
4. **Work lives only in the working tree / only on the branch tip for long stretches.** The
   longer edits stay uncommitted (or commits stay only on the feature branch), the bigger the
   window in which a stray reconcile destroys them.

---

## Recommendations

### A. Stop the bleeding (harness / automation owner) — highest priority

1. **Never touch a dirty worktree automatically.** If a worktree has any uncommitted or
   untracked changes, the automation must **skip** all sync/reconcile/cleanup and leave it
   exactly as-is. No `reset --hard`, no `clean -fd`, no `stash`, no `checkout`, no `rebase`.
2. **Pin each worktree to its own branch — never auto-switch to `main`.** A `claude/<name>`
   worktree should never be put in detached HEAD on `main`, and its branch ref must never be
   `reset`/`checkout`-ed onto `main`. Updating `main` is done **in the main checkout only**.
3. **Don’t auto-sync feature branches to a moving `main` mid-session at all.** If staying
   current is wanted, do it **additively** (`git merge main` *into* the branch, which never
   discards) and **only** when the tree is clean — never `rebase`/`reset` (which rewrite/drop),
   and on conflict **abort and leave the branch untouched**, never fall back to `reset`.
4. **Serialize anything that writes shared refs.** Take a repo lock around merge-into-`main`
   and any cross-worktree ref update so two agents can’t interleave a sync with a fast-forward.
5. **If a reconcile ever must stash, it must guarantee the pop** (same branch, same worktree,
   abort the whole operation and restore on any conflict) — and prefer not to stash at all.

### B. Defense in depth (agent process — adopt now, regardless of A)

1. **Commit every turn (WIP commits).** End each turn with
   `git add -A && git commit -m "wip: <turn>"`. Committed-on-branch work survives stash/reset/
   clean and is always recoverable from reflog; uncommitted work is not. This alone would have
   prevented the loss of the new test file and the edits.
2. **`git add` new files immediately.** Untracked files are the most fragile — only they are
   removed by `clean -fd` and `stash -u`. Track them the moment they’re created.
3. **Each agent stays on its own `claude/<name>` branch and never checks out `main` inside its
   worktree.** Land work the way `CLAUDE.md` already says — `git -C <main-checkout> merge
   --ff-only <branch>` — which touches `main` only in the main checkout. Never `reset`/`rebase`
   your own branch onto `main`; to refresh, `git merge main` (additive) on a clean tree only.
4. **Remove any "auto-rebase/sync onto main" step from agent loops.** The reflogs show
   `rebase (start): checkout main` cycles; on a dirty tree against a moving `main` these are
   exactly what strands the worktree. Sync by merging `main` in, deliberately, when clean.
5. **Lose a merge race? Re-merge, don’t reset.** `git fetch` + `git merge origin/main` into
   your branch, resolve, retry the ff-merge into `main`. Never `reset --hard` to recover.

### C. Safety net

- Enable reflog-friendly settings on the repo: `gc.reflogExpire=90.days`,
  `gc.reflogExpireUnreachable=30.days`, `gc.pruneExpire=14.days` so orphaned commits like
  `f1d3813` stay recoverable for weeks, and avoid `git gc --prune=now` while agents run.
- A periodic guard that just **alerts** (never mutates) when a `claude/<name>` worktree is
  detached or its branch tip equals `main`’s tip — catches a stranding immediately.

---

## Immediate cleanup (act on these now — live work is at risk)

- **`objective-mestorf-7be5c7` right now** has uncommitted edits to `grid_tables.py` and
  `spreadsheet.py` **and** its branch was just reset onto `main`, orphaning `f1d3813`. If that
  is an active session, rescue before GC:
  ```bash
  # recover the dropped commit onto a rescue branch (does not disturb the running worktree)
  git -C <main-checkout> branch rescue/objective-f1d3813 f1d3813
  ```
  The live uncommitted edits in that worktree should be **committed by its own agent** on its
  own branch — don’t reset/sync it again until it’s committed.
- Stale worktrees `eager-chaplygin-5d0457` and `zealous-hofstadter-a8f113` are "behind
  origin/main [12]/[13]" and idle — fold in or remove them so they stop participating in syncs.

*(I did not modify any worktree state; the commands above are for you to run when ready.)*
