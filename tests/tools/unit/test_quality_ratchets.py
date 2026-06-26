import ast

from tools import quality_checks as qc
from tools import quality_metrics as qm
from tools import quality_ratchets as qr
from tools._quality_common import parse_files, python_files


def trees_under(tmp_path):
    return parse_files(python_files((str(tmp_path),)))


def write(tmp_path, name, source):
    (tmp_path / name).write_text(source)


REACH_THROUGH = (
    "class Controller:\n"
    "    def __init__(self, host, editor):\n"
    "        self._host = host\n"
    "        self._editor = editor\n"
    "    def render(self):\n"
    "        self._host.renderer.render()\n"
    "        return self._editor.state\n"
)


def test_injected_handle_names_detect_constructor_params(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    assert qm.injected_handle_names(trees_under(tmp_path)) == {"_host", "_editor"}


def test_reach_through_gate_is_a_ratchet_floor(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    trees = trees_under(tmp_path)
    assert sum(qm.reach_through_by_handle(trees).values()) == 2
    assert qr.reach_through_violations(trees, {"reach_through_total": 2}) == []
    assert qr.reach_through_violations(trees, {"reach_through_total": 1}) != []


ALIASED_REACH = (
    "class C:\n"
    "    def __init__(self, host):\n"
    "        self._host = host\n"
    "    def f(self):\n"
    "        local = self._host\n"
    "        return local.renderer.render() + self._host.editor.x\n"
)


def test_reach_through_counts_handle_aliased_locals(tmp_path):
    write(tmp_path, "m.py", ALIASED_REACH)
    assert qm.reach_through_by_handle(trees_under(tmp_path))["_host"] == 2


DEMETER = (
    "class C:\n"
    "    def __init__(self, r):\n"
    "        self.r = r\n"
    "    def f(self):\n"
    "        return self.r._editor.state.domain_basis\n"
)

SHALLOW = (
    "class C:\n"
    "    def __init__(self, r):\n"
    "        self.r = r\n"
    "    def f(self):\n"
    "        return self.r.state.value\n"
)


def test_demeter_flags_only_depth_four_chains_off_a_handle(tmp_path):
    write(tmp_path, "deep.py", DEMETER)
    write(tmp_path, "shallow.py", SHALLOW)
    chains = qm.demeter_chains(trees_under(tmp_path))
    assert [c.split("::", 1)[1] for c in chains] == ["self.r._editor.state.domain_basis"]


def test_demeter_gate_bans_new_chains_but_grandfathers_baseline(tmp_path):
    write(tmp_path, "deep.py", DEMETER)
    trees = trees_under(tmp_path)
    chains = sorted(qm.demeter_chains(trees))
    assert qr.demeter_violations(trees, {"demeter_chains": []}) != []
    assert qr.demeter_violations(trees, {"demeter_chains": chains}) == []


BAG_BUILDER = (
    "from types import SimpleNamespace\n"
    "def build():\n"
    "    draft = SimpleNamespace()\n"
    "    draft.shared = 1\n"
    "    draft.local_only = 2\n"
    "    return draft\n"
)

BAG_READER = "def consume(draft):\n    return draft.shared\n"


def test_bag_cross_file_counts_only_attrs_read_in_another_file(tmp_path):
    write(tmp_path, "build.py", BAG_BUILDER)
    write(tmp_path, "read.py", BAG_READER)
    crossing, accumulators = qm.bag_cross_file(trees_under(tmp_path))
    assert crossing == {"draft.shared"}
    assert accumulators == {"draft"}


def test_bag_gate_bans_new_simplenamespace_accumulator(tmp_path):
    write(tmp_path, "build.py", BAG_BUILDER)
    write(tmp_path, "read.py", BAG_READER)
    trees = trees_under(tmp_path)
    clean = {"bag_cross_file_total": 1, "bag_cross_file_accumulators": ["draft"]}
    assert qr.bag_violations(trees, clean) == []
    grew = {"bag_cross_file_total": 0, "bag_cross_file_accumulators": ["draft"]}
    assert any("rose to 1" in v.message for v in qr.bag_violations(trees, grew))
    fresh = {"bag_cross_file_total": 9, "bag_cross_file_accumulators": []}
    assert any("new SimpleNamespace" in v.message for v in qr.bag_violations(trees, fresh))


def klass(name, methods, attrs=0):
    body = "".join(f"    def m{i}(self):\n        return {i}\n" for i in range(methods))
    setters = "".join(f"        self.a{i} = {i}\n" for i in range(attrs))
    init = f"    def __init__(self):\n{setters}" if attrs else ""
    return f"class {name}:\n{init}{body or '    pass\n'}"


def test_class_surface_flags_methods_or_attrs_over_floor(tmp_path):
    write(tmp_path, "wide.py", klass("Wide", qm.CLASS_METHOD_FLOOR + 1))
    write(tmp_path, "fat.py", klass("Fat", 1, qm.CLASS_ATTR_FLOOR + 1))
    write(tmp_path, "small.py", klass("Small", 3, 3))
    oversized = qm.oversized_classes(qm.class_surface(trees_under(tmp_path)))
    assert set(oversized) == {"Wide", "Fat"}


def test_class_surface_gate_bans_growth_and_new_god_objects(tmp_path):
    write(tmp_path, "wide.py", klass("Wide", qm.CLASS_METHOD_FLOOR + 1))
    trees = trees_under(tmp_path)
    floor = {"Wide": {"methods": qm.CLASS_METHOD_FLOOR + 1, "attrs": 0}}
    assert qr.class_surface_violations(trees, {"class_surface": floor}) == []
    assert any(
        "crosses the class-surface floor" in v.message
        for v in qr.class_surface_violations(trees, {"class_surface": {}})
    )
    lower = {"Wide": {"methods": qm.CLASS_METHOD_FLOOR, "attrs": 0}}
    assert any(
        "grew to" in v.message for v in qr.class_surface_violations(trees, {"class_surface": lower})
    )


def test_comment_gate_passes_platform_notes_but_bans_explanatory(tmp_path):
    write(tmp_path, "platform.py", "x = 1  # NiceGUI re-imports on reload\n")
    write(tmp_path, "explain.py", "y = 2  # this re-derives the identity\n")
    files = python_files((str(tmp_path),))
    base = {"explanatory_comment_blocks": 0}
    messages = [v.message for v in qr.comment_violations(files, base)]
    assert len(messages) == 1
    assert "names no platform constraint" in messages[0]


FACADE = "from a import x\nfrom b import y\n__all__ = ['x', 'y']\n"
LOGIC = "from a import x\ndef f():\n    return x\n"


def test_reexport_facade_detection(tmp_path):
    assert qm.is_reexport_facade(ast.parse(FACADE)) is True
    assert qm.is_reexport_facade(ast.parse(LOGIC)) is False


def _package(tmp_path, leaves):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("".join(f"from pkg import s{i}\n" for i in range(leaves)))
    (pkg / "big.py").write_text(
        "".join(f"from pkg import s{i}\n" for i in range(leaves)) + "def run():\n    return 1\n"
    )
    for i in range(leaves):
        (pkg / f"s{i}.py").write_text("value = 1\n")
    return python_files((str(tmp_path),))


def test_coupling_cap_bites_logic_modules_but_exempts_facades(tmp_path, monkeypatch):
    monkeypatch.setattr(qc, "MAX_EFFERENT_COUPLING", 15)
    monkeypatch.chdir(tmp_path)
    _package(tmp_path, qc.MAX_EFFERENT_COUPLING + 1)
    flagged = {v.path for v in qc.coupling_violations(python_files(("pkg",)))}
    assert "pkg.big" in flagged
    assert "pkg" not in flagged


def test_write_baseline_round_trips_through_load(tmp_path, monkeypatch):
    path = tmp_path / "baseline.json"
    monkeypatch.setattr(qc, "BASELINE_PATH", path)
    monkeypatch.setattr(qr, "BASELINE_PATH", path)
    write(tmp_path, "m.py", REACH_THROUGH)
    written = qc.write_baseline((str(tmp_path),))
    assert qr.load_baseline() == written
    assert written["reach_through_total"] == 2
