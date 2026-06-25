from types import SimpleNamespace

from rtt.app.building import PageBuilder


class _FakePanel:
    def __init__(self):
        self.added = []
        self.removed = []

    def classes(self, add="", remove=""):
        if add:
            self.added.append(add)
        if remove:
            self.removed.append(remove)
        return self


def _builder(panel=None):
    host = SimpleNamespace(panelgroup=panel or _FakePanel())
    return PageBuilder(SimpleNamespace(), host)


def test_page_builder_constructs_without_a_page():
    b = _builder()
    assert b.drawer_open is False


def test_toggle_drawer_opens_then_closes_toggling_the_panel_class():
    panel = _FakePanel()
    b = _builder(panel)
    b.toggle_drawer()
    assert b.drawer_open is True
    assert panel.added == ["rtt-open"]
    b.toggle_drawer()
    assert b.drawer_open is False
    assert panel.removed == ["rtt-open"]
