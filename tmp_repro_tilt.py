"""DIAGNOSTIC repro: what does on_target_limit_preview compute when lowering TILT?
Replicates app.py's on_target_limit_preview math headlessly for several transitions."""
from rtt.web.editor import Editor
from rtt.web import spreadsheet


def preview(editor, baseline, spec):
    token = editor.capture_for_preview()
    try:
        editor.set_target_spec(spec)
        new = editor.layout(prev_ids=baseline.identities)
        modified = spreadsheet.changed_cell_ids(baseline, new) - {"preset:target"}
        removed = spreadsheet.removed_cell_ids(baseline, new)
    finally:
        editor.restore_for_preview(token)
    return new, modified, removed


def target_rows(lay):
    return sorted(c.id for c in lay.cells if c.id.startswith("retune:target:"))


for start, end in [("8-TILT", "6-TILT"), ("8-TILT", "7-TILT"), ("6-TILT", "5-TILT")]:
    ed = Editor()
    ed.set_target_spec(start)                 # establish the starting limit
    baseline = ed.layout()                    # the focus baseline (what on_cell_focus snapshots)
    new, modified, removed = preview(ed, baseline, end)
    base_rows = target_rows(baseline)
    new_rows = target_rows(new)
    print(f"\n=== {start} -> {end} ===")
    print(f"baseline target rows ({len(base_rows)}): {base_rows}")
    print(f"new      target rows ({len(new_rows)}): {new_rows}")
    print(f"REMOVED ({len(removed)}): {sorted(removed)}")
    print(f"MODIFIED ({len(modified)}): {sorted(modified)}")
