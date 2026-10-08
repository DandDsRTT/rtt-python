from __future__ import annotations

import argparse
import json
import mailbox
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header, make_header
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from html import unescape
from pathlib import Path

KNOWN_ADDRESSES = {
    "d.keenan7@gmail.com": "Dave Keenan",
    "douglas.blumeyer@gmail.com": "Douglas Blumeyer",
    "kingwoodchuckii@gmail.com": "Douglas Blumeyer",
}

_QUOTED_LINE_RE = re.compile(r"^\s*>")
_ATTRIBUTION_RE = re.compile(r"^On .{0,200}wrote:\s*$")
_SUBJECT_PREFIX_RE = re.compile(r"^\s*(?:(?:re|fwd?|aw)\s*:\s*)+", re.IGNORECASE)
_BLOCK_TAG_RE = re.compile(r"</p\s*>|<br\s*/?>|</div\s*>|</li\s*>|</h\d\s*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BLANK_RUN_RE = re.compile(r"\n{3,}")
_UNSAFE_NAME_RE = re.compile(r"[/\\:\n\r\t]+")
_NAME_CHARS = 90


@dataclass(frozen=True)
class Email:
    thread: str
    subject: str
    sender: str
    sent: datetime
    body: str


def _decoded(value: str | None) -> str:
    return str(make_header(decode_header(value or "")))


def _html_to_text(html: str) -> str:
    text = _BLOCK_TAG_RE.sub("\n\n", html)
    text = unescape(_TAG_RE.sub("", text))
    return _BLANK_RUN_RE.sub("\n\n", text).strip()


def _part_text(part: Message) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")


def _body(message: Message) -> str:
    parts = [p for p in message.walk() if not p.is_multipart()]
    plain = [p for p in parts if p.get_content_type() == "text/plain"]
    if plain:
        return "\n".join(_part_text(p) for p in plain)
    html = [p for p in parts if p.get_content_type() == "text/html"]
    return "\n".join(_html_to_text(_part_text(p)) for p in html)


def _without_quotes(text: str) -> str:
    kept = [
        line
        for line in text.splitlines()
        if not _QUOTED_LINE_RE.match(line) and not _ATTRIBUTION_RE.match(line)
    ]
    return _BLANK_RUN_RE.sub("\n\n", "\n".join(kept)).strip()


def _subject(message: Message) -> str:
    return _SUBJECT_PREFIX_RE.sub("", _decoded(message["Subject"])).strip() or "(no subject)"


def _email(message: Message) -> Email | None:
    try:
        sent = parsedate_to_datetime(message["Date"])
    except (TypeError, ValueError):
        return None
    name, address = parseaddr(_decoded(message["From"]))
    subject = _subject(message)
    return Email(
        message["X-GM-THRID"] or subject.lower(),
        subject,
        name or address,
        sent,
        _without_quotes(_body(message)),
    )


def _threads(mbox_path: Path) -> list[list[Email]]:
    by_thread: dict[str, list[Email]] = {}
    for message in mailbox.mbox(mbox_path):
        email = _email(message)
        if email is not None:
            by_thread.setdefault(email.thread, []).append(email)
    return [sorted(thread, key=lambda e: e.sent.timestamp()) for thread in by_thread.values()]


def _render(thread: list[Email]) -> str:
    first, last = thread[0], thread[-1]
    participants = ", ".join(sorted({e.sender for e in thread}))
    lines = [
        f"Email thread: {first.subject}",
        f"Participants: {participants}",
        f"Messages: {len(thread)} ({first.sent:%Y-%m-%d} to {last.sent:%Y-%m-%d})",
        f"Thread id: {first.thread}",
        "",
    ]
    for email in thread:
        lines += [f"== {email.sent:%Y-%m-%d} {email.sender} ==", email.body, ""]
    return "\n".join(lines)


def _file_name(thread: list[Email]) -> str:
    subject = _UNSAFE_NAME_RE.sub("-", thread[0].subject)[:_NAME_CHARS].strip()
    return f"{thread[0].sent:%Y-%m-%d} {subject}"


def _already_written(thread_id: str, out_dir: Path) -> Path | None:
    marker = f"Thread id: {thread_id}\n"
    for path in out_dir.iterdir():
        if path.is_file() and marker in path.read_text(encoding="utf-8")[:600]:
            return path
    return None


def _write_thread(thread: list[Email], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = _already_written(thread[0].thread, out_dir)
    if existing is not None:
        return existing
    target = out_dir / _file_name(thread)
    while target.exists():
        target = target.with_name(target.name + " (more)")
    target.write_text(_render(thread), encoding="utf-8")
    return target


def import_mbox(mbox_path: Path, out_dir: Path) -> list[Path]:
    return [_write_thread(thread, out_dir) for thread in _threads(mbox_path)]


def _exported_email(message: dict, thread: str) -> Email:
    address = parseaddr(message.get("sender", ""))[1] or message.get("sender", "")
    subject = _SUBJECT_PREFIX_RE.sub("", message.get("subject", "")).strip() or "(no subject)"
    sent = datetime.fromisoformat(message["date"].replace("Z", "+00:00"))
    sender = KNOWN_ADDRESSES.get(address.lower(), address)
    return Email(thread, subject, sender, sent, _without_quotes(message.get("plaintext_body", "")))


def import_thread_json(json_path: Path, out_dir: Path) -> Path:
    exported = json.loads(json_path.read_text(encoding="utf-8"))
    emails = [_exported_email(m, exported["id"]) for m in exported["messages"] if m.get("date")]
    return _write_thread(sorted(emails, key=lambda e: e.sent.timestamp()), out_dir)


def parse_arguments(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m rtt.bot.correspondence_import")
    parser.add_argument("source", choices=("thread", "mbox"))
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("paths", nargs="+", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(sys.argv[1:] if argv is None else argv)
    for path in arguments.paths:
        if arguments.source == "mbox":
            import_mbox(path, arguments.out_dir)
        else:
            import_thread_json(path, arguments.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
