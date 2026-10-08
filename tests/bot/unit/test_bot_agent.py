from pathlib import Path
from types import SimpleNamespace

import pytest

from rtt.bot.agent import BotDeclined, BotError, BotSettings, Conversation
from rtt.bot.corpus import GuideCorpus, GuideDocument
from rtt.bot.search import SearchIndex
from rtt.bot.toolbox import ToolBox
from tests.bot.unit.bot_fakes import FakeStream, FakeStreamer, RecordingListener, message, text, tool_use

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS = [GuideDocument("A", Path("A"), "== Comma ==\nMeantone tempers out 81/80.\n")]


def conversation(*scripted):
    corpus = GuideCorpus(DOCS)
    toolbox = ToolBox(corpus, SearchIndex(corpus), REPO_ROOT)
    streamer = FakeStreamer(*scripted)
    return streamer, Conversation(streamer, toolbox, "SYSTEM", BotSettings(model="m", effort="low", max_tokens=99))


class TestTextOnlyTurn:
    def test_streams_the_reply_appends_both_turns_and_sends_the_cached_system_prompt(self):
        client, chat = conversation(FakeStream(message(text("Hel"), text("lo"))))
        listener = RecordingListener()
        assert chat.ask("hi", listener) == "Hello"
        assert listener.chunks == ["Hel", "lo"]
        assert [m["role"] for m in chat.messages] == ["user", "assistant"]
        assert chat.messages[0]["content"] == "hi"
        request = client.calls[0]
        assert request["model"] == "m"
        assert request["max_tokens"] == 99
        assert request["system"] == [{"type": "text", "text": "SYSTEM", "cache_control": {"type": "ephemeral"}}]
        assert request["thinking"] == {"type": "adaptive"}
        assert request["output_config"] == {"effort": "low"}
        assert request["betas"] == ["server-side-fallback-2026-07-01"]
        assert request["fallbacks"] == "default"
        assert request["cache_control"] == {"type": "ephemeral"}
        assert [t["name"] for t in request["tools"]] == ["search_guide", "read_guide_section", "guide_contents", "run_rtt_python"]
        assert request["messages"] is chat.messages


class TestToolTurn:
    def test_runs_requested_tools_feeds_results_back_and_returns_the_final_text(self):
        first = message(text("Looking…"), tool_use("t1", "search_guide", {"query": "81/80", "limit": 2}), stop_reason="tool_use")
        second = message(text("It is the syntonic comma."))
        client, chat = conversation(FakeStream(first), FakeStream(second))
        listener = RecordingListener()
        assert chat.ask("what is 81/80?", listener) == "It is the syntonic comma."
        assert listener.tool_calls == [("search_guide", {"query": "81/80", "limit": 2})]
        assert listener.tool_results[0].text.startswith("A > Comma")
        assert [m["role"] for m in chat.messages] == ["user", "assistant", "user", "assistant"]
        assert chat.messages[2]["content"] == [
            {"type": "tool_result", "tool_use_id": "t1", "content": listener.tool_results[0].text}
        ]
        assert len(client.calls) == 2

    def test_a_failed_tool_is_reported_back_as_an_error_result(self):
        first = message(tool_use("t1", "read_guide_section", {"section_id": "A > Nowhere"}), stop_reason="tool_use")
        _client, chat = conversation(FakeStream(first), FakeStream(message(text("Sorry."))))
        chat.ask("read it")
        result = chat.messages[2]["content"][0]
        assert result["is_error"] is True
        assert "guide_contents" in result["content"]


class TestStopReasons:
    def test_a_truncated_tool_call_is_never_run_and_raises(self):
        truncated = message(tool_use("t1", "run_rtt_python", {"code": "print("}), stop_reason="max_tokens")
        _client, chat = conversation(FakeStream(truncated))
        listener = RecordingListener()
        with pytest.raises(BotError, match="max_tokens"):
            chat.ask("compute", listener)
        assert listener.tool_calls == []

    def test_a_refusal_raises_with_its_category_runs_no_tools_and_leaves_no_trace(self):
        refused = message(text("I can't"), tool_use("t1", "search_guide", {"query": "x", "limit": 1}), stop_reason="refusal")
        refused.stop_details = SimpleNamespace(category="bio")
        _client, chat = conversation(FakeStream(refused))
        listener = RecordingListener()
        with pytest.raises(BotDeclined) as declined:
            chat.ask("?", listener)
        assert declined.value.category == "bio"
        assert listener.tool_calls == []
        assert chat.messages == []

    def test_a_refusal_without_details_reports_an_unspecified_category(self):
        _client, chat = conversation(FakeStream(message(stop_reason="refusal")))
        with pytest.raises(BotDeclined, match="unspecified"):
            chat.ask("?")

    def test_a_text_answer_cut_off_at_max_tokens_is_returned_and_flagged(self):
        _client, chat = conversation(FakeStream(message(text("partial ans"), stop_reason="max_tokens")))
        assert chat.ask("?") == "partial ans"
        assert chat.last_stop_reason == "max_tokens"

    def test_endless_paused_turns_are_capped(self):
        _client, chat = conversation(*[FakeStream(message(text("…"), stop_reason="pause_turn")) for _ in range(7)])
        with pytest.raises(BotError, match="paused"):
            chat.ask("go")

    def test_a_paused_turn_is_resumed_by_re_sending_the_conversation(self):
        paused = message(text("partial"), stop_reason="pause_turn")
        client, chat = conversation(FakeStream(paused), FakeStream(message(text(" done"))))
        assert chat.ask("go") == " done"
        assert len(client.calls) == 2
        assert [m["role"] for m in chat.messages] == ["user", "assistant", "assistant"]

    def test_unparseable_tool_json_is_retried_twice_then_raised(self):
        bad = "Unable to parse tool parameter JSON from model. Please retry your request."
        client, chat = conversation(FakeStream(message(), failure=ValueError(bad)), FakeStream(message(), failure=ValueError(bad)), FakeStream(message(text("ok"))))
        assert chat.ask("go") == "ok"
        assert len(client.calls) == 3
        client2, chat2 = conversation(*[FakeStream(message(), failure=ValueError(bad)) for _ in range(3)])
        with pytest.raises(ValueError):
            chat2.ask("go")
        assert len(client2.calls) == 3

    def test_any_other_value_error_propagates_without_a_retry(self):
        client, chat = conversation(FakeStream(message(), failure=ValueError("surrogates not allowed")), FakeStream(message(text("never"))))
        with pytest.raises(ValueError, match="surrogates"):
            chat.ask("go")
        assert len(client.calls) == 1


class TestFallbackEcho:
    def test_blocks_before_a_mid_output_fallback_boundary_are_not_echoed_except_text(self):
        boundary = SimpleNamespace(type="fallback")
        first = message(
            SimpleNamespace(type="thinking", thinking=""),
            text("partial"),
            tool_use("t0", "guide_contents", {"document": ""}),
            boundary,
            SimpleNamespace(type="thinking", thinking=""),
            tool_use("t1", "guide_contents", {"document": ""}),
            stop_reason="tool_use",
        )
        _client, chat = conversation(FakeStream(first), FakeStream(message(text("done"))))
        listener = RecordingListener()
        assert chat.ask("go", listener) == "done"
        echoed = chat.messages[1]["content"]
        assert [getattr(b, "type", None) for b in echoed] == ["text", "fallback", "thinking", "tool_use"]
        assert listener.tool_calls == [("guide_contents", {"document": ""})]
        assert [r["tool_use_id"] for r in chat.messages[2]["content"]] == ["t1"]


class TestFailedTurnsLeaveNoTrace:
    def test_an_interrupt_mid_turn_rolls_the_conversation_back_and_propagates(self):
        _client, chat = conversation(FakeStream(message(text("ok"))), FakeStream(message(), failure=KeyboardInterrupt()))
        chat.ask("first")
        with pytest.raises(KeyboardInterrupt):
            chat.ask("second")
        assert [m["role"] for m in chat.messages] == ["user", "assistant"]

    def test_an_api_failure_after_a_tool_round_rolls_back_the_whole_turn(self):
        first = message(tool_use("t1", "guide_contents", {"document": ""}), stop_reason="tool_use")
        _client, chat = conversation(FakeStream(first), FakeStream(message(), failure=RuntimeError("boom")))
        with pytest.raises(RuntimeError):
            chat.ask("go")
        assert chat.messages == []
