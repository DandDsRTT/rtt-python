import io

from rtt.bot.cli import PrintingListener, main, parse_arguments
from rtt.bot.toolbox import ToolOutcome
from tests.bot.unit.bot_fakes import FakeStream, FakeStreamer, message, text, tool_use


class TestParseArguments:
    def test_defaults_to_the_bot_settings_and_no_question(self):
        arguments = parse_arguments([])
        assert arguments.question is None
        assert arguments.model == "claude-opus-5-5"
        assert arguments.effort == "high"
        assert arguments.max_tokens == 32000
        assert arguments.show_tools is True

    def test_one_shot_question_and_overrides(self):
        arguments = parse_arguments(["--model", "m", "--effort", "low", "--max-tokens", "7", "--quiet-tools", "what is 81/80?"])
        assert arguments.question == "what is 81/80?"
        assert (arguments.model, arguments.effort, arguments.max_tokens, arguments.show_tools) == ("m", "low", 7, False)


class TestPrintingListener:
    def test_writes_text_chunks_and_announces_tool_calls_and_errors(self):
        out = io.StringIO()
        listener = PrintingListener(out.write, show_tools=True)
        listener.on_text("Hel")
        listener.on_text("lo")
        listener.on_tool_call("search_guide", {"query": "81/80", "limit": 3})
        listener.on_tool_result(ToolOutcome("fine"))
        listener.on_tool_result(ToolOutcome("boom", is_error=True))
        assert out.getvalue() == 'Hello\n  ⚙ search_guide {"query": "81/80", "limit": 3}\n  ✗ boom\n'

    def test_can_hide_tool_activity(self):
        out = io.StringIO()
        listener = PrintingListener(out.write, show_tools=False)
        listener.on_tool_call("search_guide", {"query": "x", "limit": 1})
        listener.on_tool_result(ToolOutcome("boom", is_error=True))
        assert out.getvalue() == ""


class TestMain:
    def test_one_shot_question_streams_the_answer_and_exits_zero(self):
        out = io.StringIO()
        streamer = FakeStreamer(FakeStream(message(text("The syntonic comma."))))
        assert main(["what is 81/80?"], stream=streamer, io=(io.StringIO(), out)) == 0
        assert out.getvalue() == "The syntonic comma.\n"
        assert streamer.calls[0]["messages"][0] == {"role": "user", "content": "what is 81/80?"}
        assert streamer.calls[0]["model"] == "claude-opus-5-5"
        assert "# Knowledge base documents" in streamer.calls[0]["system"][0]["text"]

    def test_conversation_mode_answers_each_line_resets_on_command_and_quits(self):
        out = io.StringIO()
        streamer = FakeStreamer(
            FakeStream(message(text("One."), tool_use("t1", "guide_contents", {"document": ""}), stop_reason="tool_use")),
            FakeStream(message(text("Done."))),
            FakeStream(message(text("Two."))),
        )
        stdin = io.StringIO("first\n\n/reset\nsecond\n/quit\n")
        assert main(["--quiet-tools"], stream=streamer, io=(stdin, out)) == 0
        assert out.getvalue() == (
            "RTT expert ready. Ask away; /reset clears the conversation, /quit leaves.\n"
            "you> bot> One.Done.\nyou> you> you> bot> Two.\nyou> \n"
        )
        assert [m["role"] for m in streamer.calls[2]["messages"]] == ["user", "assistant"]
        assert streamer.calls[2]["messages"][0]["content"] == "second"

    def test_an_interrupted_turn_is_reported_and_the_conversation_continues(self):
        out = io.StringIO()
        streamer = FakeStreamer(FakeStream(message(), failure=KeyboardInterrupt()), FakeStream(message(text("Fine."))))
        stdin = io.StringIO("first\nsecond\n")
        assert main([], stream=streamer, io=(stdin, out)) == 0
        assert out.getvalue().endswith("you> bot> [interrupted]\nyou> bot> Fine.\nyou> \n")
        assert streamer.calls[1]["messages"][0]["content"] == "second"

    def test_an_empty_reply_is_named_rather_than_printed_as_nothing(self):
        out = io.StringIO()
        assert main(["why?"], stream=FakeStreamer(FakeStream(message(stop_reason="refusal"))), io=(io.StringIO(), out)) == 0
        assert out.getvalue() == "[the model returned no text]\n"
