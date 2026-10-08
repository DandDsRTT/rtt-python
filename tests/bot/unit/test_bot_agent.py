from pathlib import Path

import pytest

from rtt.bot.agent import BotError, BotSettings, Conversation
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

    def test_a_refusal_ends_the_turn_without_running_its_tools(self):
        refused = message(text("I can't help with that."), tool_use("t1", "search_guide", {"query": "x", "limit": 1}), stop_reason="refusal")
        _client, chat = conversation(FakeStream(refused))
        listener = RecordingListener()
        assert chat.ask("?", listener) == "I can't help with that."
        assert listener.tool_calls == []
        assert [m["role"] for m in chat.messages] == ["user", "assistant"]

    def test_a_paused_turn_is_resumed_by_re_sending_the_conversation(self):
        paused = message(text("partial"), stop_reason="pause_turn")
        client, chat = conversation(FakeStream(paused), FakeStream(message(text(" done"))))
        assert chat.ask("go") == " done"
        assert len(client.calls) == 2
        assert [m["role"] for m in chat.messages] == ["user", "assistant", "assistant"]

    def test_unparseable_tool_json_is_retried_twice_then_raised(self):
        broken = FakeStream(message(), failure=ValueError("bad json"))
        client, chat = conversation(broken, FakeStream(message(), failure=ValueError("bad json")), FakeStream(message(text("ok"))))
        assert chat.ask("go") == "ok"
        assert len(client.calls) == 3
        client2, chat2 = conversation(*[FakeStream(message(), failure=ValueError("bad json")) for _ in range(3)])
        with pytest.raises(ValueError):
            chat2.ask("go")
        assert len(client2.calls) == 3
