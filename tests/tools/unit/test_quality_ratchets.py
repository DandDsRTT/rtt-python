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


def test_handles_by_class_detect_constructor_params(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    assert qm.handles_by_class(trees_under(tmp_path))["Controller"] == {"_host", "_editor"}


OWN_STATE = (
    "class Document:\n"
    "    def __init__(self):\n"
    "        self.state = _build_state()\n"
    "    def f(self):\n"
    "        return self.state.mapping + self.state.n\n"
)

INJECTED_STATE = (
    "class Resolver:\n"
    "    def __init__(self, state):\n"
    "        self.state = state\n"
    "    def g(self):\n"
    "        return self.state.mapping + self.state.n\n"
)

ALIASED_STATE = (
    "class Resolver:\n"
    "    def __init__(self, state):\n"
    "        self.state = state\n"
    "    def g(self):\n"
    "        s = self.state\n"
    "        return s.mapping + s.n\n"
)


def test_internally_assigned_state_is_not_an_injected_handle(tmp_path):
    write(tmp_path, "document.py", OWN_STATE)
    write(tmp_path, "resolver.py", INJECTED_STATE)
    hbc = qm.handles_by_class(trees_under(tmp_path))
    assert "state" not in hbc["Document"]
    assert "state" in hbc["Resolver"]


def test_a_class_reading_its_own_state_is_not_counted_as_reach_through(tmp_path):
    write(tmp_path, "document.py", OWN_STATE)
    assert qm.reach_through_by_handle(trees_under(tmp_path)).get("state", 0) == 0


def test_an_injected_state_handle_is_counted(tmp_path):
    write(tmp_path, "resolver.py", INJECTED_STATE)
    assert qm.reach_through_by_handle(trees_under(tmp_path))["state"] == 2


def test_aliased_injected_state_local_still_counts(tmp_path):
    write(tmp_path, "resolver.py", ALIASED_STATE)
    assert qm.reach_through_by_handle(trees_under(tmp_path))["state"] == 2


def test_own_state_uncounted_even_when_a_peer_class_injects_that_name(tmp_path):
    write(tmp_path, "document.py", OWN_STATE)
    write(tmp_path, "resolver.py", INJECTED_STATE)
    counts = qm.reach_through_by_handle(trees_under(tmp_path))
    assert counts["state"] == 2


INHERITED_HANDLE = (
    "class _Mixin:\n"
    "    def sync(self):\n"
    "        return self._editor.tuning + self._editor.scheme\n"
    "class View(_Mixin):\n"
    "    def __init__(self, editor):\n"
    "        self._editor = editor\n"
)


def test_base_class_counts_a_handle_injected_by_its_subclass(tmp_path):
    write(tmp_path, "m.py", INHERITED_HANDLE)
    trees = trees_under(tmp_path)
    assert "_editor" in qm.handles_by_class(trees)["_Mixin"]
    assert qm.reach_through_by_handle(trees)["_editor"] == 2


SHARED_BASE_INJECTOR_AND_OWNER = (
    "class Base:\n"
    "    pass\n"
    "class Injector(Base):\n"
    "    def __init__(self, dep):\n"
    "        self._dep = dep\n"
    "    def use(self):\n"
    "        return self._dep.a + self._dep.b\n"
    "class Owner(Base):\n"
    "    def __init__(self):\n"
    "        self._dep = _build()\n"
    "    def read(self):\n"
    "        return self._dep.c\n"
)


def test_a_shared_base_never_drops_the_injectors_reach_throughs(tmp_path):
    write(tmp_path, "m.py", SHARED_BASE_INJECTOR_AND_OWNER)
    trees = trees_under(tmp_path)
    assert "_dep" in qm.handles_by_class(trees)["Injector"]
    assert qm.reach_through_by_handle(trees)["_dep"] >= 2


TWO_PHASE_BIND = (
    "class Owner:\n"
    "    def __init__(self, rec):\n"
    "        self._rec = rec\n"
    "class Ctl:\n"
    "    def __init__(self):\n"
    "        self._rec = None\n"
    "    def bind(self, rec):\n"
    "        self._rec = rec\n"
    "    def run(self):\n"
    "        return self._rec.entity + self._rec.cells\n"
)


def test_two_phase_bind_injection_counts_when_the_name_is_a_known_handle(tmp_path):
    write(tmp_path, "m.py", TWO_PHASE_BIND)
    trees = trees_under(tmp_path)
    assert "_rec" in qm.handles_by_class(trees)["Ctl"]
    assert qm.reach_through_by_handle(trees)["_rec"] == 2


SETTER_CACHE = (
    "class Runtime:\n"
    "    def __init__(self):\n"
    "        self.last_lay = None\n"
    "    def set_last(self, lay):\n"
    "        self.last_lay = lay\n"
    "    def read(self):\n"
    "        return self.last_lay.identities\n"
)


def test_setter_cached_value_is_not_a_handle_when_never_constructor_injected(tmp_path):
    write(tmp_path, "m.py", SETTER_CACHE)
    trees = trees_under(tmp_path)
    assert "last_lay" not in qm.handles_by_class(trees)["Runtime"]
    assert qm.reach_through_by_handle(trees).get("last_lay", 0) == 0


DEFAULT_FALLBACK = (
    "class R:\n"
    "    def __init__(self, settings=None):\n"
    "        self.settings = settings\n"
    "        if settings is None:\n"
    "            self.settings = _defaults()\n"
    "    def f(self):\n"
    "        return self.settings.get('x')\n"
)


def test_constructor_injected_handle_survives_a_default_fallback_reassignment(tmp_path):
    write(tmp_path, "m.py", DEFAULT_FALLBACK)
    trees = trees_under(tmp_path)
    assert "settings" in qm.handles_by_class(trees)["R"]
    assert qm.reach_through_by_handle(trees)["settings"] == 1


def test_reach_through_gate_is_a_ratchet_floor(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    trees = trees_under(tmp_path)
    assert sum(qm.reach_through_by_handle(trees).values()) == 2
    assert qr.reach_through_violations(trees, {"reach_through_total": 2}) == []
    assert qr.reach_through_violations(trees, {"reach_through_total": 1}) != []


def test_per_handle_floors_at_baseline_pass(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    trees = trees_under(tmp_path)
    at_floor = {"reach_through_total": 2, "reach_through_by_handle": {"_host": 1, "_editor": 1}}
    assert qr.reach_through_violations(trees, at_floor) == []


def test_a_handle_rising_above_its_floor_fails_even_when_total_stays_flat(tmp_path):
    write(tmp_path, "m.py", REACH_THROUGH)
    trees = trees_under(tmp_path)
    floors = {"reach_through_total": 2, "reach_through_by_handle": {"_host": 0, "_editor": 2}}
    violations = qr.reach_through_violations(trees, floors)
    assert any("self._host rose to 1 (per-handle floor 0)" in v.message for v in violations)
    assert not any("injected-handle reach-throughs rose" in v.message for v in violations)


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


SELF_ATTR_ALIAS = (
    "class C:\n"
    "    def __init__(self, host):\n"
    "        self._host = host\n"
    "        self._g = self._host\n"
    "    def f(self):\n"
    "        return self._g.a + self._g.b + self._g.c\n"
)


def test_self_attribute_alias_of_a_handle_is_itself_a_handle(tmp_path):
    write(tmp_path, "m.py", SELF_ATTR_ALIAS)
    trees = trees_under(tmp_path)
    assert "_g" in qm.handles_by_class(trees)["C"]
    assert qm.reach_through_by_handle(trees)["_g"] == 3


EXTENDED_ALIASES = (
    "class C:\n"
    "    def __init__(self, host):\n"
    "        self._host = host\n"
    "    def ann(self):\n"
    "        h: object = self._host\n"
    "        return h.a + h.b\n"
    "    def walrus(self):\n"
    "        return (w := self._host).a + w.b\n"
    "    def chained(self):\n"
    "        h = k = self._host\n"
    "        return h.a + k.b\n"
)


def test_extended_local_alias_syntaxes_do_not_evade(tmp_path):
    write(tmp_path, "m.py", EXTENDED_ALIASES)
    assert qm.reach_through_by_handle(trees_under(tmp_path))["_host"] == 6


def test_aliased_deep_chain_is_flagged_by_demeter(tmp_path):
    write(
        tmp_path,
        "m.py",
        "class C:\n"
        "    def __init__(self, r):\n"
        "        self.r = r\n"
        "    def f(self):\n"
        "        local = self.r\n"
        "        return local._editor.state.domain_basis\n",
    )
    chains = qm.demeter_chains(trees_under(tmp_path))
    assert [c.split("::", 1)[1] for c in chains] == ["self.r._editor.state.domain_basis"]


ALIAS_IMPORT_BAG = (
    "from types import SimpleNamespace as NS\n"
    "def build():\n"
    "    draft = NS()\n"
    "    draft.shared = 1\n"
    "    return draft\n"
)


def test_simplenamespace_import_alias_is_still_detected(tmp_path):
    write(tmp_path, "build.py", ALIAS_IMPORT_BAG)
    write(tmp_path, "read.py", "def use(draft):\n    return draft.shared\n")
    crossing, accumulators = qm.bag_cross_file(trees_under(tmp_path))
    assert crossing == {"draft.shared"}
    assert accumulators == {"draft"}


def test_cross_file_read_modify_write_bag_attr_counts(tmp_path):
    write(
        tmp_path,
        "a.py",
        "from types import SimpleNamespace\n"
        "def build():\n"
        "    draft = SimpleNamespace()\n"
        "    draft.acc = []\n"
        "    return draft\n",
    )
    write(tmp_path, "b.py", "def step(draft):\n    draft.acc = draft.acc + [1]\n")
    crossing, _accumulators = qm.bag_cross_file(trees_under(tmp_path))
    assert "draft.acc" in crossing


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
    members = body or "    pass\n"
    return f"class {name}:\n{init}{members}"


WRAPPED_METHOD = (
    "import typing\n"
    "class Hidden:\n"
    "    if typing.TYPE_CHECKING:\n"
    "        def wrapped(self):\n"
    "            return 1\n"
)


def test_class_surface_counts_block_wrapped_methods_and_keys_by_file(tmp_path):
    write(tmp_path, "wide.py", klass("Wide", qm.CLASS_METHOD_FLOOR + 1))
    write(tmp_path, "fat.py", klass("Fat", 1, qm.CLASS_ATTR_FLOOR + 1))
    write(tmp_path, "small.py", klass("Small", 3, 3))
    oversized = qm.oversized_classes(qm.class_surface(trees_under(tmp_path)))
    assert {key.split("::")[-1] for key in oversized} == {"Wide", "Fat"}
    assert all("::" in key for key in oversized)


def test_class_surface_sees_methods_hidden_in_a_block(tmp_path):
    write(tmp_path, "hidden.py", WRAPPED_METHOD)
    surface = qm.class_surface(trees_under(tmp_path))
    assert next(c for k, c in surface.items() if k.endswith("::Hidden"))["methods"] == 1


def test_class_surface_gate_bans_growth_and_new_god_objects(tmp_path):
    write(tmp_path, "wide.py", klass("Wide", qm.CLASS_METHOD_FLOOR + 1))
    trees = trees_under(tmp_path)
    key = next(k for k in qm.class_surface(trees) if k.endswith("::Wide"))
    floor = {key: {"methods": qm.CLASS_METHOD_FLOOR + 1, "attrs": 0}}
    assert qr.class_surface_violations(trees, {"class_surface": floor}) == []
    assert any(
        "crosses the class-surface floor" in v.message
        for v in qr.class_surface_violations(trees, {"class_surface": {}})
    )
    lower = {key: {"methods": qm.CLASS_METHOD_FLOOR, "attrs": 0}}
    assert any(
        "grew to" in v.message for v in qr.class_surface_violations(trees, {"class_surface": lower})
    )


def test_class_surface_floor_is_checked_when_class_drops_below_oversized(tmp_path):
    write(tmp_path, "g.py", klass("G", qm.CLASS_METHOD_FLOOR - 1, qm.CLASS_ATTR_FLOOR))
    trees = trees_under(tmp_path)
    surface = qm.class_surface(trees)
    key = next(k for k in surface if k.endswith("::G"))
    assert key not in qm.oversized_classes(surface)
    floor = {key: {"methods": qm.CLASS_METHOD_FLOOR - 2, "attrs": qm.CLASS_ATTR_FLOOR + 1}}
    violations = qr.class_surface_violations(trees, {"class_surface": floor})
    assert any(f"grew to {qm.CLASS_METHOD_FLOOR} methods" in v.message for v in violations)


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


def _barrel_package(tmp_path, leaves):
    svc = tmp_path / "svc"
    svc.mkdir()
    (svc / "__init__.py").write_text("".join(f"from svc.s{i} import f{i}\n" for i in range(leaves)))
    for i in range(leaves):
        (svc / f"s{i}.py").write_text(f"def f{i}():\n    return {i}\n")
    uses = " + ".join(f"svc.f{i}()" for i in range(leaves))
    (tmp_path / "consumer.py").write_text(f"import svc\ndef use():\n    return {uses}\n")


def test_transitive_coupling_resolves_barrel_names_to_submodules(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _barrel_package(tmp_path, 3)
    coupling = qc.transitive_coupling(python_files((".",)))
    assert coupling["svc"] == 0
    assert coupling["consumer"] == 3


def test_coupling_gate_bites_a_new_over_floor_module_past_the_barrel(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(qc, "COUPLING_FLOOR", 3)
    _barrel_package(tmp_path, 3)
    files = python_files((".",))
    assert qc.coupling_violations(files, {"coupling": {"consumer": 3}}) == []
    flagged = {v.path for v in qc.coupling_violations(files, {"coupling": {}})}
    assert "consumer" in flagged
    assert "svc" not in flagged


def test_write_baseline_round_trips_through_load(tmp_path, monkeypatch):
    path = tmp_path / "baseline.json"
    monkeypatch.setattr(qc, "BASELINE_PATH", path)
    monkeypatch.setattr(qr, "BASELINE_PATH", path)
    write(tmp_path, "m.py", REACH_THROUGH)
    written = qc.write_baseline((str(tmp_path),))
    assert qr.load_baseline() == written
    assert written["reach_through_total"] == 2
