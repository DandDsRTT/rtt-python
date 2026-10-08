from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

import anthropic

from rtt.bot.agent import BotError, BotSettings, Conversation, TurnListener
from rtt.bot.corpus import GuideCorpus
from rtt.bot.prompt import system_prompt
from rtt.bot.search import SearchIndex
from rtt.bot.toolbox import ToolBox, ToolOutcome

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_ROOT = REPO_ROOT / "guide"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
_DEFAULTS = BotSettings()


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

    def _line(self, text: str) -> None:
        if not self._at_line_start:
            self._write("\n")
        self._write(text + "\n")
        self._at_line_start = True

    def on_text(self, chunk: str) -> None:
        if chunk:
            self._write(chunk)
            self._at_line_start = chunk.endswith("\n")

    def on_tool_call(self, name: str, arguments: object) -> None:
        if self._show_tools:
            self._line(f"  ⚙ {name} {json.dumps(arguments, ensure_ascii=False)}")

    def on_tool_result(self, outcome: ToolOutcome) -> None:
        if self._show_tools and outcome.is_error:
            self._line("  ✗ " + outcome.text.splitlines()[0])

    def end_turn(self) -> None:
        if not self._at_line_start:
            self._write("\n")
            self._at_line_start = True


def _flushing_writer(out: TextIO) -> Callable[[str], object]:
    def write(text: str) -> None:
        out.write(text)
        out.flush()

    return write


def build_conversation(settings: BotSettings, stream=None) -> Conversation:
    corpus = GuideCorpus.load(GUIDE_ROOT)
    toolbox = ToolBox(corpus, SearchIndex(corpus), REPO_ROOT)
    stream = stream or anthropic.Anthropic().messages.stream
    return Conversation(stream, toolbox, system_prompt(corpus), settings)


def _ask(conversation: Conversation, question: str, listener: PrintingListener) -> None:
    try:
        conversation.ask(question, listener)
    except (BotError, anthropic.APIError) as error:
        listener.on_text(f"\n[error] {error}")
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
