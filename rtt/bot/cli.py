from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

import anthropic

from rtt.bot.agent import BotDeclined, BotError, BotSettings, Conversation, TurnListener
from rtt.bot.corpus import GuideCorpus
from rtt.bot.prompt import system_prompt
from rtt.bot.search import SearchIndex
from rtt.bot.toolbox import ToolBox, ToolOutcome

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_ROOT = REPO_ROOT / "guide"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
_DEFAULTS = BotSettings()
_NO_CREDENTIALS = "Could not resolve authentication method"
_LOGIN_GUIDANCE = "[error] no API credentials: export ANTHROPIC_API_KEY or run `ant auth login`"


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m rtt.bot",
        description="Ask the RTT expert; with no question, start a conversation.",
    )
    parser.add_argument("question", nargs="?")
    parser.add_argument("--model", default=_DEFAULTS.model)
    parser.add_argument("--effort", choices=EFFORT_LEVELS, default=_DEFAULTS.effort)
    parser.add_argument("--max-tokens", type=int, default=_DEFAULTS.max_tokens)
    parser.add_argument(
        "--quiet-tools", dest="show_tools", action="store_false", help="hide tool activity"
    )
    return parser.parse_args(argv)


class PrintingListener(TurnListener):
    def __init__(self, write: Callable[[str], object], show_tools: bool) -> None:
        self._write = write
        self._show_tools = show_tools
        self._at_line_start = True
        self.turn_had_text = False

    def note(self, text: str) -> None:
        if not self._at_line_start:
            self._write("\n")
        self._write(text + "\n")
        self._at_line_start = True

    def on_text(self, chunk: str) -> None:
        if chunk:
            self._write(chunk)
            self._at_line_start = chunk.endswith("\n")
            self.turn_had_text = True

    def on_tool_call(self, name: str, arguments: object) -> None:
        if self._show_tools:
            self.note(f"  ⚙ {name} {json.dumps(arguments, ensure_ascii=False)}")

    def on_tool_result(self, outcome: ToolOutcome) -> None:
        if self._show_tools and outcome.is_error:
            self.note("  ✗ " + outcome.text.splitlines()[0])

    def end_turn(self) -> None:
        if not self._at_line_start:
            self._write("\n")
            self._at_line_start = True
        self.turn_had_text = False


def _flushing_writer(out: TextIO) -> Callable[[str], object]:
    def write(text: str) -> None:
        out.write(text)
        out.flush()

    return write


def build_conversation(settings: BotSettings, stream=None) -> Conversation:
    corpus = GuideCorpus.load(GUIDE_ROOT)
    toolbox = ToolBox(corpus, SearchIndex(corpus), REPO_ROOT)
    stream = stream or anthropic.Anthropic().beta.messages.stream
    return Conversation(stream, toolbox, system_prompt(corpus), settings)


def _api_error_note(error: Exception) -> str:
    if isinstance(error, TypeError):
        if _NO_CREDENTIALS not in str(error):
            raise error
        return _LOGIN_GUIDANCE
    if isinstance(error, anthropic.AuthenticationError):
        return _LOGIN_GUIDANCE
    if isinstance(error, anthropic.RateLimitError):
        wait = error.response.headers.get("retry-after", "60")
        return f"[error] rate limited; retry after {wait}s"
    if isinstance(error, anthropic.APIStatusError):
        return f"[error] the API answered {error.status_code}: {error.message}"
    return "[error] could not reach the API; check the network and retry"


def _ask(conversation: Conversation, question: str, listener: PrintingListener) -> None:
    try:
        if not conversation.ask(question, listener):
            listener.note("[the model returned no text]")
        elif conversation.last_stop_reason == "max_tokens":
            listener.note("[cut off at max_tokens; raise --max-tokens]")
    except KeyboardInterrupt:
        listener.note("[interrupted]")
    except BotDeclined as declined:
        discarded = "; the partial text above was discarded" if listener.turn_had_text else ""
        listener.note(f"[declined: {declined.category}{discarded}]")
    except BotError as error:
        listener.note(f"[error] {error}")
    except (anthropic.APIError, TypeError) as error:
        listener.note(_api_error_note(error))
    listener.end_turn()


def run_repl(conversation: Conversation, listener: PrintingListener, io: tuple[TextIO, TextIO]):
    stdin, out = io
    out.write("RTT expert ready. Ask away; /reset clears the conversation, /quit leaves.\n")
    while True:
        out.write("you> ")
        out.flush()
        line = stdin.readline()
        if not line or line.strip() == "/quit":
            out.write("\n")
            return
        question = line.strip()
        if question == "/reset":
            conversation.messages.clear()
        elif question:
            out.write("bot> ")
            _ask(conversation, question, listener)


def main(
    argv: list[str] | None = None, stream=None, io: tuple[TextIO, TextIO] | None = None
) -> int:
    stdin, out = io or (sys.stdin, sys.stdout)
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    settings = BotSettings(arguments.model, arguments.effort, arguments.max_tokens)
    conversation = build_conversation(settings, stream)
    listener = PrintingListener(_flushing_writer(out), arguments.show_tools)
    if arguments.question:
        _ask(conversation, arguments.question, listener)
    else:
        run_repl(conversation, listener, (stdin, out))
    return 0
