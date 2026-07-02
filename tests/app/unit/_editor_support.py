from rtt.app import service

BARBADOS = "2.3.13/5 [⟨1 2 2] ⟨0 -2 -3]}"
BARBADOS_ALT = "2.3.13/5 [⟨1 0 -1] ⟨0 2 3]}"


def _mapping_form_cell(editor) -> str:
    editor.settings["form_controls"] = True
    editor.settings["presets"] = True
    return {c.id: c for c in editor.layout().cells}["formchooser:mapping"].text


def _comma_form_cell(editor) -> str:
    editor.settings["form_controls"] = True
    editor.settings["presets"] = True
    return {c.id: c for c in editor.layout().cells}["formchooser:comma_basis"].text


def _cents_map(values):
    return tuple(service.cents(v) for v in values)


def _cents_close(a, b):
    return a is not None and b is not None and all(abs(x - y) < 1e-9 for x, y in zip(a, b))


def _has_targets(ed):
    return any(c.id.startswith(("target:", "cell:target")) for c in ed.layout().cells)
