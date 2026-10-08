import io
from types import SimpleNamespace

from rtt.bot.cli import PrintingListener, main, parse_arguments
from rtt.bot.toolbox import ToolOutcome
from tests.bot.unit.bot_fakes import FakeStream, FakeStreamer, message, text, tool_use


class TestParseArguments:
    def test_defaults_to_the_bot_settings_and_no_question(self):
        arguments = parse_arguments([])
        assert arguments.question is None
        assert arguments.model == "claude-opus-5-5"
        assert arguments.effort == "high"
        assert arguments.max_tokens == 64000
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
        assert streamer.calls[2]["messages"] == [{"role": "user", "content": "second"}]
        assert [m["role"] for m in streamer.calls[1]["messages"]] == ["user", "assistant", "user"]

    def test_an_interrupted_turn_is_reported_and_the_conversation_continues(self):
        out = io.StringIO()
        streamer = FakeStreamer(FakeStream(message(), failure=KeyboardInterrupt()), FakeStream(message(text("Fine."))))
        stdin = io.StringIO("first\nsecond\n")
        assert main([], stream=streamer, io=(stdin, out)) == 0
        assert out.getvalue().endswith("you> bot> [interrupted]\nyou> bot> Fine.\nyou> \n")
        assert streamer.calls[1]["messages"][0]["content"] == "second"

    def test_an_empty_reply_is_named_rather_than_printed_as_nothing(self):
        out = io.StringIO()
        assert main(["why?"], stream=FakeStreamer(FakeStream(message())), io=(io.StringIO(), out)) == 0
        assert out.getvalue() == "[the model returned no text]\n"

    def test_a_declined_request_is_reported_with_its_category_and_discarded_partial(self):
        out = io.StringIO()
        refused = message(text("Half an answ"), stop_reason="refusal")
        refused.stop_details = SimpleNamespace(category="cyber")
        assert main(["q"], stream=FakeStreamer(FakeStream(refused)), io=(io.StringIO(), out)) == 1
        assert out.getvalue() == "Half an answ\n[declined: cyber; the partial text above was discarded]\n"
        silent = message(stop_reason="refusal")
        out2 = io.StringIO()
        main(["q"], stream=FakeStreamer(FakeStream(silent)), io=(io.StringIO(), out2))
        assert out2.getvalue() == "[declined: unspecified]\n"

    def test_a_reply_cut_off_at_max_tokens_says_so(self):
        out = io.StringIO()
        main(["q"], stream=FakeStreamer(FakeStream(message(text("long…"), stop_reason="max_tokens"))), io=(io.StringIO(), out))
        assert out.getvalue() == "long…\n[cut off at max_tokens; raise --max-tokens]\n"

    def test_missing_credentials_print_login_guidance_instead_of_a_traceback(self):
        out = io.StringIO()
        no_auth = TypeError("Could not resolve authentication method. Expected one of api_key, auth_token, or credentials to be set.")
        main(["q"], stream=FakeStreamer(FakeStream(message(), failure=no_auth)), io=(io.StringIO(), out))
        assert out.getvalue() == "[error] no API credentials: export ANTHROPIC_API_KEY or run `ant auth login`\n"

    def test_one_shot_exit_codes_distinguish_errors_and_interrupts(self):
        out = io.StringIO()
        assert main(["q"], stream=FakeStreamer(FakeStream(message(), failure=KeyboardInterrupt())), io=(io.StringIO(), out)) == 130
        assert out.getvalue() == "[interrupted]\n"
        bad = "Unable to parse tool parameter JSON from model."
        out2 = io.StringIO()
        streamer = FakeStreamer(*[FakeStream(message(), failure=ValueError(bad)) for _ in range(3)])
        assert main(["q"], stream=streamer, io=(io.StringIO(), out2)) == 1
        assert out2.getvalue() == "[retrying: the model's tool call was malformed]\n[retrying: the model's tool call was malformed]\n[error] the model's tool-call JSON could not be parsed after 3 attempts\n"

    def test_an_interrupt_at_the_prompt_leaves_the_conversation_cleanly(self):
        class InterruptedInput(io.StringIO):
            def readline(self):
                raise KeyboardInterrupt

        out = io.StringIO()
        assert main([], stream=FakeStreamer(), io=(InterruptedInput(), out)) == 130
        assert out.getvalue().endswith("you> \n")
