import json

from rtt.app import audio_config, page_assets
from rtt.app.editor import Editor
from rtt.app.rendering import Renderer


class TestAudioConfigModule:
    def test_defaults_match_the_bank_and_pump_starting_state(self):
        assert audio_config.defaults() == {
            "wave": 0, "mode": 0, "hold": 0, "root": 0, "muted": 0,
            "pump_size": 1, "pump_tempo": 75,
        }

    def test_from_persisted_clamps_every_field_into_range(self):
        cleaned = audio_config.from_persisted(
            {"wave": 99, "mode": -3, "hold": "x", "root": 1, "muted": True,
             "pump_size": 0, "pump_tempo": 9999}
        )
        assert cleaned == {"wave": 3, "mode": 0, "hold": 1, "root": 1, "muted": 1,
                           "pump_size": 1, "pump_tempo": 150}

    def test_from_persisted_fills_missing_keys_with_defaults(self):
        assert audio_config.from_persisted({"wave": 2}) == {**audio_config.defaults(), "wave": 2}

    def test_from_persisted_tolerates_a_non_mapping(self):
        assert audio_config.from_persisted(None) == audio_config.defaults()
        assert audio_config.from_persisted("garbage") == audio_config.defaults()


class TestAudioIsDocumentState:
    def test_a_fresh_editor_starts_at_the_audio_defaults(self):
        assert Editor().audio == audio_config.defaults()

    def test_recording_a_change_updates_state_and_is_undoable(self):
        editor = Editor()
        assert editor.record_audio({"wave": 1, "muted": True}) is True
        assert editor.audio["wave"] == 1 and editor.audio["muted"] == 1
        assert editor.can_undo is True
        editor.undo()
        assert editor.audio == audio_config.defaults()
        editor.redo()
        assert editor.audio["wave"] == 1

    def test_recording_the_same_config_is_a_no_op(self):
        editor = Editor()
        assert editor.record_audio(dict(editor.audio)) is False
        assert editor.can_undo is False

    def test_serialize_load_round_trips_the_audio_config(self):
        editor = Editor()
        editor.record_audio({"wave": 2, "mode": 3, "hold": True, "root": True,
                             "muted": True, "pump_size": 4, "pump_tempo": 120})
        restored = Editor()
        restored.load(editor.serialize())
        assert restored.audio == editor.audio
        assert restored.can_undo is False, "a load is a fresh start, not an undoable step"

    def test_load_tolerates_a_state_saved_before_audio_existed(self):
        editor = Editor()
        data = editor.serialize()
        del data["audio"]
        restored = Editor()
        restored.load(data)
        assert restored.audio == audio_config.defaults()

    def test_reset_restores_the_default_audio_as_one_undoable_action(self):
        editor = Editor()
        editor.record_audio({"wave": 3})
        assert editor.can_reset is True
        editor.reset()
        assert editor.audio == audio_config.defaults()
        editor.undo()
        assert editor.audio["wave"] == 3

    def test_preview_capture_round_trips_the_audio_config(self):
        editor = Editor()
        editor.record_audio({"wave": 1})
        token = editor.capture_for_preview()
        editor.record_audio({"wave": 3})
        editor.restore_for_preview(token)
        assert editor.audio["wave"] == 1


class TestAudioPushJs:
    def test_push_emits_apply_audio_once_then_dedupes(self):
        editor = Editor()
        editor.record_audio({"wave": 1})
        renderer = Renderer.__new__(Renderer)
        renderer._editor = editor
        renderer._last_audio_push = None
        js = renderer._audio_push_js()
        assert "window.rttAudio && window.rttAudio.applyAudio(" in js
        assert json.loads(js[js.index("{"):js.rindex("}") + 1])["wave"] == 1
        assert renderer._audio_push_js() == "", "unchanged config is not re-pushed"

    def test_an_already_pushed_config_is_not_resent(self):
        editor = Editor()
        editor.record_audio({"wave": 2})
        renderer = Renderer.__new__(Renderer)
        renderer._editor = editor
        renderer._last_audio_push = dict(editor.audio)
        assert renderer._audio_push_js() == ""


class TestAudioClientContract:
    def test_every_user_change_reports_its_config_to_the_server(self):
        js = page_assets._AUDIO_JS
        assert "emitEvent('rtt_audio', api.config())" in js
        for toggle in ("cycleWave", "cycleMode", "toggleHold", "toggleRoot", "toggleMute"):
            body = js.split(f"api.{toggle} = function")[1].split("};")[0]
            assert "report()" in body, f"{toggle} must report its new config"
        for slider in ("setPumpSize", "setPumpTempo"):
            body = js.split(f"api.{slider} = function")[1].split("};")[0]
            assert "reportSoon()" in body, f"{slider} must report (debounced) its new value"

    def test_apply_audio_is_the_server_to_client_entry_point_and_never_reports(self):
        js = page_assets._AUDIO_JS
        body = js.split("api.applyAudio = function")[1].split("\n  };")[0]
        assert "syncControls()" in body
        assert "report()" not in body, "applying a server config must not echo back a report (a loop)"

    def test_bank_glyphs_are_restated_from_state_in_one_place(self):
        js = page_assets._AUDIO_JS
        assert "function syncControls()" in js
        assert js.count("e.innerHTML = api.glyphs.wave[S.wave]") == 1
