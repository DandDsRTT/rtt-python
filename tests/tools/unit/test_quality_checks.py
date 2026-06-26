import ast
from pathlib import Path

from tools import quality_checks as qc


def test_line_count_counts_final_unterminated_line():
    assert qc.line_count("a\nb\nc") == 3
    assert qc.line_count("a\nb\nc\n") == 3
    assert qc.line_count("") == 0


def test_file_length_violation_only_over_limit():
    under = "x = 1\n" * qc.MAX_FILE_LINES
    over = "x = 1\n" * (qc.MAX_FILE_LINES + 1)
    assert file_length_violations(under) == []
    flagged = file_length_violations(over)
    assert len(flagged) == 1
    assert "file is" in flagged[0].message


def test_file_length_exempt_data_module_is_not_flagged():
    over = "x = 1\n" * (qc.MAX_FILE_LINES + 1)
    exempt = next(iter(qc.FILE_LENGTH_EXEMPT))
    assert qc.file_length_violations(exempt, over) == []
    assert qc.file_length_violations("rtt/app/not_exempt.py", over) != []


def test_file_length_exempt_matches_nested_and_absolute_paths():
    exempt = next(iter(qc.FILE_LENGTH_EXEMPT))
    assert qc.is_file_length_exempt(exempt)
    assert qc.is_file_length_exempt("/abs/checkout/" + exempt)
    assert not qc.is_file_length_exempt("other/" + exempt.replace("/", "_"))


def test_file_length_exempt_set_is_exactly_the_documented_data_modules():
    assert qc.FILE_LENGTH_EXEMPT == frozenset(
        {
            "rtt/app/grid_tables.py",
            "rtt/app/tooltips.py",
            "rtt/app/page_assets.py",
        }
    )


def test_each_exempt_module_is_a_real_over_cap_data_file():
    root = Path(__file__).resolve().parents[3]
    for rel in qc.FILE_LENGTH_EXEMPT:
        path = root / rel
        assert path.exists(), rel
        assert qc.line_count(path.read_text()) > qc.MAX_FILE_LINES, rel


def test_logic_modules_are_not_exempt():
    for rel in ("rtt/app/rendering.py", "rtt/app/spreadsheet_geometry.py", "rtt/app/editor.py"):
        assert not qc.is_file_length_exempt(rel)


def test_function_length_violation_reports_name_and_span():
    body = "\n".join(f"    x{i} = {i}" for i in range(qc.MAX_FUNCTION_LINES + 5))
    source = f"def big():\n{body}\n"
    flagged = function_length_violations(source)
    assert len(flagged) == 1
    assert flagged[0].message.startswith("big is")


def test_short_function_is_clean():
    assert function_length_violations("def small():\n    return 1\n") == []


def test_docstring_violation_flags_module_class_function():
    source = '"""m"""\nclass C:\n    """c"""\n    def f(self):\n        """f"""\n        return 1\n'
    messages = [v.message for v in docstring_violations(source)]
    assert messages == ["docstring is banned"] * 3


def test_no_docstring_is_clean():
    assert docstring_violations("def f():\n    return 1\n") == []


def test_module_name_drops_init_and_suffix():
    assert qc.module_name(Path("pkg/sub/__init__.py")) == "pkg.sub"
    assert qc.module_name(Path("pkg/mod.py")) == "pkg.mod"


def test_efferent_coupling_counts_internal_package_imports(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "hub.py").write_text("from pkg import a\nfrom pkg import b\n")
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "b.py").write_text("y = 1\n")
    fanout = qc.efferent_coupling(qc.python_files(("pkg",)))
    assert {"pkg.a", "pkg.b"} <= fanout["pkg.hub"]
    assert fanout["pkg.a"] == set()


def test_coupling_violation_fires_when_a_module_rises_above_its_floor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qc, "COUPLING_FLOOR", 1)
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "hub.py").write_text("from pkg import a\nfrom pkg import b\n")
    (pkg / "a.py").write_text("x = 1\n")
    (pkg / "b.py").write_text("y = 1\n")
    files = qc.python_files(("pkg",))
    assert qc.coupling_violations(files, {"coupling": {"pkg.hub": 2}}) == []
    messages = [v.message for v in qc.coupling_violations(files, {"coupling": {"pkg.hub": 1}})]
    assert any("rose to 2" in m for m in messages)


def test_lcom4_one_when_methods_share_an_attribute():
    cls = ast.parse(
        "class C:\n    def a(self):\n        self.x = 1\n    def b(self):\n        return self.x\n"
    ).body[0]
    assert qc.lcom4(cls) == 1


def test_lcom4_one_when_a_method_calls_another():
    cls = ast.parse(
        "class C:\n    def a(self):\n        return self.b()\n    def b(self):\n        return 1\n"
    ).body[0]
    assert qc.lcom4(cls) == 1


def test_lcom4_two_when_methods_are_disjoint():
    cls = ast.parse(
        "class C:\n    def a(self):\n        return self.x\n    def b(self):\n        return self.y\n"
    ).body[0]
    assert qc.lcom4(cls) == 2


def test_lcom4_one_for_single_method_class():
    cls = ast.parse("class C:\n    def a(self):\n        return self.x\n").body[0]
    assert qc.lcom4(cls) == 1


def test_cohesion_violation_fires_above_threshold(tmp_path, monkeypatch):
    monkeypatch.setattr(qc, "MAX_LCOM4", 1)
    (tmp_path / "m.py").write_text(
        "class C:\n    def a(self):\n        return self.x\n    def b(self):\n        return self.y\n"
    )
    messages = [v.message for v in qc.cohesion_violations(qc.python_files((str(tmp_path),)))]
    assert any("LCOM4 2" in m for m in messages)


def test_depth_of_inheritance_follows_internal_bases():
    bases = {"A": [], "B": ["A"], "C": ["B"], "D": ["A", "Outside"]}
    assert qc.depth_of_inheritance("A", bases) == 0
    assert qc.depth_of_inheritance("C", bases) == 2
    assert qc.depth_of_inheritance("D", bases) == 1


def test_number_of_children_counts_internal_subclasses():
    children = qc.number_of_children({"A": [], "B": ["A"], "C": ["A"], "D": ["B"]})
    assert children["A"] == 2
    assert children["B"] == 1


def test_inheritance_violation_flags_deep_dit(tmp_path, monkeypatch):
    monkeypatch.setattr(qc, "MAX_DIT", 1)
    (tmp_path / "m.py").write_text(
        "class A:\n    pass\n\n\nclass B(A):\n    pass\n\n\nclass C(B):\n    pass\n"
    )
    messages = [v.message for v in qc.inheritance_violations(qc.python_files((str(tmp_path),)))]
    assert any("DIT 2" in m for m in messages)


def test_inheritance_violation_flags_high_noc(tmp_path, monkeypatch):
    monkeypatch.setattr(qc, "MAX_NOC", 1)
    (tmp_path / "m.py").write_text(
        "class P:\n    pass\n\n\nclass X(P):\n    pass\n\n\nclass Y(P):\n    pass\n"
    )
    messages = [v.message for v in qc.inheritance_violations(qc.python_files((str(tmp_path),)))]
    assert any("NOC 2" in m for m in messages)


def test_live_tree_passes_the_architectural_guard_rails():
    files = qc.python_files(qc._DEFAULT_ROOTS)
    assert qc.cohesion_violations(files) == []
    assert qc.inheritance_violations(files) == []


def test_service_barrel_is_invisible_to_transitive_coupling():
    coupling = qc.transitive_coupling(qc.python_files(qc._DEFAULT_ROOTS))
    assert coupling["rtt.app.service"] == 0
    assert max(coupling.values()) < 20


def test_live_tree_sits_exactly_on_its_ratchet_floors():
    files = qc.python_files(qc._DEFAULT_ROOTS)
    assert qc.collect(qc._DEFAULT_ROOTS) == []
    assert qc.compute_baseline(files) == qc.load_baseline()


def test_spreadsheet_shared_state_within_cap():
    files = qc.python_files(qc._DEFAULT_ROOTS)
    assert qc.spreadsheet_shared_state_violations(files) == []


def test_spreadsheet_shared_state_fires_when_over_cap(monkeypatch):
    monkeypatch.setattr(qc, "MAX_SPREADSHEET_SHARED_STATE", 0)
    files = qc.python_files(qc._DEFAULT_ROOTS)
    messages = [v.message for v in qc.spreadsheet_shared_state_violations(files)]
    assert any("cross-file shared mutable self" in m for m in messages)


_RENAMED_HANDLE = (
    "class C:\n"
    "    def __init__(self, host):\n"
    "        self._host = host\n"
    "    def f(self):\n"
    "        return self._host.editor.state\n"
    "    def g(self):\n"
    "        return self._host.renderer.render()\n"
)


def test_reach_through_counts_every_injected_handle_not_just_page(tmp_path):
    (tmp_path / "m.py").write_text(_RENAMED_HANDLE)
    trees = qc.parse_files(qc.python_files((str(tmp_path),)))
    assert sum(qc.reach_through_by_handle(trees).values()) == 2
    assert qc.reach_through_violations(trees, {"reach_through_total": 1}) != []
    assert qc.reach_through_violations(trees, {"reach_through_total": 2}) == []


def test_collect_and_main_over_a_tree(tmp_path, capsys):
    bad = tmp_path / "pkg"
    bad.mkdir()
    (bad / "m.py").write_text('"""doc"""\ndef f():\n    return 1\n')
    assert qc.main(["prog", str(tmp_path)]) == 1
    assert "docstring is banned" in capsys.readouterr().out


def test_main_clean_tree_returns_zero(tmp_path):
    (tmp_path / "m.py").write_text("def f():\n    return 1\n")
    assert qc.main(["prog", str(tmp_path)]) == 0


def file_length_violations(text):
    return qc.file_length_violations("m.py", text)


def function_length_violations(source):
    return qc.function_length_violations("m.py", ast.parse(source))


def docstring_violations(source):
    return qc.docstring_violations("m.py", ast.parse(source))
