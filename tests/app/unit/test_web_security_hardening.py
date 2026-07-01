"""WP1 security hardening: share-link DoS caps, raw-HTML escaping, wheel coercion."""

import base64
import zlib

import pytest

from rtt.app import editor_codec as codec
from rtt.app import grid_tables
from rtt.app._recon_display import _pending_html
from rtt.app.editor import Editor
from rtt.app.page_assets import (
    _MAX_STATE_TOKEN,
    _decode_state,
    _encode_state,
)
from rtt.app.render_html_text import _math_expression_html, _wheel_step


def _default_data() -> dict:
    return Editor().serialize()


class TestShareLinkDecode:
    def test_decode_round_trips_a_normal_state(self):
        data = _default_data()
        assert _decode_state(_encode_state(data)) == data

    def test_decode_rejects_an_over_long_token_before_decompressing(self):
        with pytest.raises(ValueError):
            _decode_state("A" * (_MAX_STATE_TOKEN + 1))

    def test_decode_rejects_a_zip_bomb_via_the_decompression_cap(self):
        bomb = base64.urlsafe_b64encode(zlib.compress(b"0" * (4 * 1024 * 1024), 9)).decode("ascii")
        assert len(bomb) <= _MAX_STATE_TOKEN
        with pytest.raises(ValueError):
            _decode_state(bomb)


class TestCodecLoadCaps:
    def test_load_accepts_a_normal_document(self):
        assert codec.load(_default_data()) is not None

    def test_load_rejects_too_many_interest_vectors(self):
        data = _default_data()
        data["interest_vectors"] = [[0, 0, 0]] * (codec._MAX_COLLECTION + 1)
        assert codec.load(data) is None

    def test_load_rejects_an_over_wide_vector(self):
        data = _default_data()
        data["interest_vectors"] = [[0] * (codec._MAX_DIMENSIONALITY + 1)]
        assert codec.load(data) is None

    def test_load_rejects_too_many_target_overrides(self):
        data = _default_data()
        data["target_override"] = ["3/2"] * (codec._MAX_COLLECTION + 1)
        assert codec.load(data) is None


class TestPendingHtmlEscaping:
    def test_escapes_angle_brackets_while_keeping_the_pending_marker(self):
        out = _pending_html("<a", "b<c>", "]d>")
        assert "<span class='rtt-pending-q'>" in out
        assert "&lt;a" in out
        assert "b&lt;c&gt;" in out
        assert "b<c>" not in out

    def test_preserves_subscript_sentinels_as_sub_tags(self):
        out = _pending_html(grid_tables.SUB_OPEN + "L" + grid_tables.SUB_CLOSE, "", "")
        assert "<sub>L</sub>" in out


class TestMathexprEscaping:
    def test_escapes_an_angle_bracket_in_an_expression_line(self):
        out = _math_expression_html("a < b", 200)
        assert "a &lt; b" in out
        assert ">a < b<" not in out


class TestWheelStep:
    def test_increments_and_decrements_an_integer(self):
        assert _wheel_step("5", -1) == "6"
        assert _wheel_step("5", 1) == "4"

    def test_honours_a_fractional_step(self):
        assert _wheel_step("0.001", -1, 0.001) == "0.002"

    def test_leaves_malformed_text_unchanged(self):
        assert _wheel_step("abc", -1) == "abc"
        assert _wheel_step("1/2x", -1) == "1/2x"

    def test_seeds_a_fresh_empty_cell_from_zero(self):
        assert _wheel_step("", -1) == "1"
        assert _wheel_step("", 1) == "-1"

    def test_leaves_an_infinite_value_unchanged(self):
        assert _wheel_step("∞", -1) == "∞"

    def test_guards_a_nonpositive_step(self):
        assert _wheel_step("5", -1, 0) == "5"
        assert _wheel_step("5", -1, -0.5) == "5"
