from __future__ import annotations

import argparse
import sys
from typing import TextIO

from rtt.bot.corpus import GuideCorpus
from rtt.bot.library_reference import library_reference
from rtt.bot.paths import GUIDE_ROOT
from rtt.bot.search import SearchIndex
from rtt.bot.tools import ToolError, guide_contents, read_guide_section, search_guide


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m rtt.bot.guide",
        description="Search and read the mirrored guide, or print the rtt.library reference.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="rank guide sections against a query")
    search.add_argument("query")
    search.add_argument("-n", "--limit", type=int, default=8)
    commands.add_parser("read", help="print one section by identifier").add_argument("identifier")
    contents = commands.add_parser("contents", help="list documents, or one document's sections")
    contents.add_argument("document", nargs="?", default="")
    commands.add_parser("reference", help="print every public rtt.library signature")
    return parser.parse_args(argv)


def _answer(arguments: argparse.Namespace) -> str:
    if arguments.command == "reference":
        return library_reference()
    corpus = GuideCorpus.load(GUIDE_ROOT)
    if arguments.command == "search":
        return search_guide(SearchIndex(corpus), arguments.query, arguments.limit)
    if arguments.command == "read":
        return read_guide_section(corpus, arguments.identifier)
    return guide_contents(corpus, arguments.document)


def main(argv: list[str] | None = None, out: TextIO = sys.stdout) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    try:
        text = _answer(arguments)
    except ToolError as error:
        out.write(f"{error}\n")
        return 1
    out.write(text.rstrip("\n") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
