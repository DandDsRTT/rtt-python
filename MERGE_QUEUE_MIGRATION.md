# Cutover: from the bespoke local coordination layer to GitHub CI + merge queue

This change retires the homegrown multi-agent landing machinery (analyzed in
`WORKFLOW_CONSOLIDATION.md`) and replaces it with a **GitHub merge queue** gated by the existing
CI workflow. Agents stop merging into the local `main` checkout; they push a branch, open a PR,
and enqueue it. The queue runs the full suite on the candidate merge and fast-forwards `main` only
when green.

## What this commit deletes

- `bin/land`, `bin/persistent-land`, `bin/land-selftest`
- `bin/with-merge-lock`, `bin/with-merge-lock-selftest`
- `bin/gate-load`, `bin/reap-orphan-gates`, `bin/governance-selftest`
- `bin/merge-safe-check`, `bin/merge-green-check`, `bin/merge-guard-hook`,
  `bin/install-merge-guard-hook`, `bin/merge-guard-selftest`, `bin/_render_relevance.py`
- `tests/app/integration/conftest.py` (the render-gate semaphore + green-token minting)
- `tests/app/unit/test_render_gate_bypass.py` (tested the deleted gate)

`bin/lint` stays (it is the linter, not coordination). The render tests themselves
(`test_web_render.py`) are unchanged — they now run in CI, not behind a local semaphore.

## What it changes

- `.github/workflows/merge-gate.yml` — now also triggers on `merge_group` (the queue event), so it
  is the queue's required check. Same full-suite run.
- `CLAUDE.md` — the landing protocol is rewritten to "push a branch, open a PR, enqueue."

---

## ⚠️ Ordering — do the GitHub setup BEFORE this commit lands

This commit deletes the only local landing path. **If it reaches `main` before the merge queue is
enabled, no agent (including the one landing it) can land anything.** So:

1. Do the **one-time GitHub setup** below first.
2. Then land this commit **last**, through the existing `bin/land` flow (the final use of it).
3. From then on, everyone uses the queue.

### One-time GitHub setup (repo admin — must be done in GitHub's UI/API, not from the box)

These require admin on `DandDsRTT/rtt-python` and cannot be done from an agent shell.

1. **Branch protection for `main`** (Settings → Branches → Add rule, or Rulesets):
   - Require a pull request before merging.
   - Require status checks to pass → select **`merge gate (full suite) / full-suite`**.
   - Require branches to be up to date before merging.
   - (Recommended) Require linear history.
2. **Enable the merge queue for `main`** (in the same branch rule / ruleset → "Require merge
   queue"):
   - Merge method: **Squash** or **Rebase** (keeps the linear history this repo prefers).
   - Required check for the queue: the same **`full-suite`** check.
   - Build concurrency: 1 (serial) is the simplest faithful replacement for the old single-holder
     lock; raise it later if CI throughput warrants and the suite is parallel-safe.

### One-time tooling on the dev box

Agents enqueue via the GitHub CLI. Install and authenticate it once (the auth step is interactive
and must be done by the user):

```bash
brew install gh
gh auth login        # choose GitHub.com → SSH or HTTPS → authenticate in browser
```

All agents on this machine share that credential.

---

## After the cutover

### The local guard hook must be removed (or it blocks your `git pull`)

A `reference-transaction` hook was installed at `<git-common-dir>/hooks/reference-transaction`
(here: `.git/hooks/reference-transaction`). It refuses an ungated render-relevant advance of
`main` — including the fast-forward a plain `git pull` performs. With landing gone remote, that
hook would **block the user's `git pull`**. Remove it once the fleet is off `bin/land` (any
still-running `bin/land` reinstalls it):

```bash
rm -f "$(git rev-parse --git-common-dir)/hooks/reference-transaction"
```

### Refreshing the live app on 8137

Landing now happens on remote `main`, so the local `python app.py` on 8137 no longer auto-updates.
Refresh it yourself whenever you want the newest landed work:

```bash
git -C <main-checkout> pull
```

(`<main-checkout>` is the worktree that has `main` checked out — the one serving 8137.) The app
hot-reloads on the pulled changes. Alternatively, the deployed site `danddsrtt-app.onrender.com`
auto-updates a few minutes after each merge.

## Rollback

If the queue needs to be backed out: revert this commit (restores `bin/land` and the whole local
layer), disable the merge queue + branch protection in GitHub, and reinstall the guard hook with
the restored `bin/install-merge-guard-hook`. Nothing here is one-way.
