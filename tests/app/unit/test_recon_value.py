import types

from rtt.app import _recon_value as rv
from rtt.app import _recon_value_kinds as rvk


class _El:
    def __init__(self):
        self.value = None
        self.fracmode = None

    def props(self, s):
        key, _, val = s.partition("=")
        if key == "data-fracmode":
            self.fracmode = val
        return self

    def style(self, _s):
        return self


def _run_update_fraction(monkeypatch, text, pending=False):
    monkeypatch.setattr(rv, "_fit_fraction", lambda *a, **k: None)
    monkeypatch.setattr(rv, "_sync_ratio_ops", lambda *a, **k: None)
    val = types.SimpleNamespace(input=_El(), denominator_input=_El(), frac_edit=_El())
    recon = types.SimpleNamespace(cells={"x": types.SimpleNamespace(value=val)})
    cell = types.SimpleNamespace(id="x", pending=pending, width=40.0)
    rv._update_fraction(recon, cell, text)
    return val


class TestUpdateFraction:
    def test_a_dashed_ratio_input_renders_as_an_empty_ratio_not_a_whole_number(self, monkeypatch):
        val = _run_update_fraction(monkeypatch, rv._DASH)
        assert val.frac_edit.fracmode == "ratio", (
            "a dashed value must render as a ratio (vinculum shown, caret in the numerator), "
            "not int mode — int mode dropped the vinculum and put the caret in the whole-number slot"
        )
        assert val.input.value == "" and val.denominator_input.value == ""

    def test_a_real_ratio_stays_a_ratio(self, monkeypatch):
        val = _run_update_fraction(monkeypatch, "3/2")
        assert val.frac_edit.fracmode == "ratio"
        assert val.input.value == "3" and val.denominator_input.value == "2"

    def test_a_whole_number_renders_in_int_mode(self, monkeypatch):
        val = _run_update_fraction(monkeypatch, "2")
        assert val.frac_edit.fracmode == "int"
        assert val.input.value == "2" and val.denominator_input.value == ""


_BIG = "79654595556622613851444019888385590279555227759630"
_BIG2 = "15340917079055395478424287359332111384297548476560"


class TestRadicalCollapse:
    def test_small_fraction_root_is_kept(self):
        assert rvk._collapsed_decimal("4√5/4") is None
        assert "<path" in rvk._radical_svg("4", "5/4")

    def test_small_single_root_is_kept(self):
        assert rvk._collapsed_decimal("4√5") is None
        assert "<path" in rvk._radical_svg("4", "5")

    def test_big_fraction_root_collapses_to_a_decimal(self):
        d = rvk._collapsed_decimal("151√472449251718551785649675383/796545955566226138514440198")
        assert d is not None and "√" not in d

    def test_big_single_integer_root_collapses(self):
        assert rvk._collapsed_decimal("19√313600000000000000000000000000") is not None


class TestPlainRatioCollapse:
    def test_short_plain_ratio_stays(self):
        assert rvk._collapsed_decimal("3/2") is None

    def test_short_plain_integer_stays(self):
        assert rvk._collapsed_decimal("2") is None

    def test_non_numeric_stays(self):
        assert rvk._collapsed_decimal("—") is None

    def test_big_plain_ratio_collapses(self):
        assert rvk._collapsed_decimal(f"{_BIG}/{_BIG2}") is not None

    def test_big_plain_integer_collapses(self):
        assert rvk._collapsed_decimal("12345678901234567890") is not None


class TestCollapsedDecimalFormat:
    def test_collapsed_decimal_is_marked_approximate(self):
        assert rvk._collapsed_decimal(f"{_BIG}/{_BIG2}").startswith("~")

    def test_collapsed_decimal_uses_three_places_not_four(self):
        d = rvk._collapsed_decimal(f"{_BIG}/{_BIG2}")
        assert len(d.split(".")[1]) == 3, "every other decimal in the app goes to 3 places"

    def test_exact_small_root_is_not_marked_approximate(self):
        assert rvk._collapsed_decimal("4√5") is None
