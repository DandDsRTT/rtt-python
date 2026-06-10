#!/usr/bin/env python3
"""PreToolUse guard: stop a worktree session from editing the MAIN checkout.

This repo keeps the main checkout AND every agent's linked worktree on disk, with
identical sub-paths (``<main>/rtt/web/app.py`` vs
``<main>/.claude/worktrees/<name>/rtt/web/app.py``). Search/explore tooling and
subagents routinely surface the *main-checkout* absolute path, ``Edit``/``Write``
faithfully write to whatever absolute path they are handed, and the result —
silently dirtying ``main`` — is invisible until someone notices. Prose rules in
CLAUDE.md / memory have not stopped it (every agent makes the same slip), so the
harness enforces it here.

Behaviour (fail-open by design — never block a legitimate edit):
  * ALLOW edits inside the current worktree.
  * ALLOW edits entirely OUTSIDE the repo (e.g. ``~/.claude`` memory, ``/tmp``,
    other projects) — not our concern.
  * DENY edits that land under the repo root but outside this worktree (the main
    checkout, or a sibling worktree), returning the corrected worktree path so the
    agent can immediately retry against the right file.
  * If anything is unexpected (not a git repo, git missing, bad input) -> allow.

Wired up from .claude/settings.json as a PreToolUse hook on Edit|Write|NotebookEdit.
"""
import json
import os
import subprocess
import sys


def _allow():
    # exit 0 with no JSON on stdout == allow (default).
    sys.exit(0)


def _deny(reason):
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.exit(0)


def _git(cwd, *args):
    out = subprocess.run(
        ["git", "-C", cwd, *args],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or "git failed")
    return out.stdout.strip()


def _under(path, root):
    root = root.rstrip(os.sep)
    return path == root or path.startswith(root + os.sep)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        _allow()

    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        _allow()

    cwd = data.get("cwd") or os.getcwd()

    # Resolve the edit target to an absolute, symlink-free path. os.path.realpath
    # works even for a not-yet-created file (Write). An absolute file_path makes
    # the join ignore cwd; a relative one resolves against the session cwd.
    target = os.path.realpath(os.path.join(cwd, os.path.expanduser(file_path)))

    try:
        worktree_root = os.path.realpath(_git(cwd, "rev-parse", "--show-toplevel"))
        # <main>/.git — its parent is the main checkout root, shared by every worktree.
        common_dir = _git(cwd, "rev-parse", "--git-common-dir")
    except Exception:
        _allow()  # not a git repo / git unavailable -> don't interfere

    common_dir = os.path.realpath(os.path.join(cwd, common_dir))
    main_root = os.path.dirname(common_dir)

    # 1) Inside the current worktree -> fine. (worktree_root lives under main_root,
    #    so this must be checked BEFORE the repo-root test below.)
    if _under(target, worktree_root):
        _allow()

    # 2) Entirely outside the repo (memory, /tmp, other projects) -> not our concern.
    if not _under(target, main_root):
        _allow()

    # 3) Under the repo root but outside this worktree -> the mistake. Block, and
    #    point at the right file so the agent can retry immediately.
    rel = os.path.relpath(target, main_root)
    wt_prefix = os.path.join(".claude", "worktrees") + os.sep
    if rel.startswith(wt_prefix):
        _deny(
            "Blocked: this edit targets a DIFFERENT worktree, not yours.\n"
            f"  target:        {target}\n"
            f"  your worktree: {worktree_root}\n"
            "Re-issue the edit against a path inside your own worktree."
        )

    corrected = os.path.join(worktree_root, rel)
    _deny(
        "Blocked: this path is in the MAIN checkout, not your worktree — editing it "
        "would silently dirty main.\n"
        f"  you tried:   {target}\n"
        f"  use instead: {corrected}\n"
        "Re-issue the same edit with the worktree path above. (All edits must go in "
        "the worktree; main only ever receives a git ff-merge.)"
    )


if __name__ == "__main__":
    main()
