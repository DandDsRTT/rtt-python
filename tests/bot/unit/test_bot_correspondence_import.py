import json
import mailbox
from email.message import EmailMessage

from rtt.bot.correspondence_import import import_mbox, import_thread_json, main


def _message(subject, sender, date, body, thread, message_id, html=False):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = "Douglas Blumeyer <douglas@example.com>"
    message["Date"] = date
    message["Message-ID"] = message_id
    message["X-GM-THRID"] = thread
    if html:
        message.set_content(f"<html><body><p>{body}</p><p>second &amp; para</p></body></html>", subtype="html")
    else:
        message.set_content(body)
    return message


def _mbox(tmp_path):
    box = mailbox.mbox(tmp_path / "rtt.mbox")
    box.add(_message("Re: held-intervals", "Dave Keenan <dave@example.com>", "Tue, 02 Mar 2021 10:00:00 +1000", "I think held is better than constrained.\n\nOn Mon, Douglas wrote:\n> what about constrained?\n> or fixed?\n", "111", "<a@example.com>"))
    box.add(_message("held-intervals", "Douglas Blumeyer <douglas@example.com>", "Mon, 01 Mar 2021 09:00:00 -0800", "what about constrained?\nor fixed?\n", "111", "<b@example.com>"))
    box.add(_message("TILT idea", "Douglas Blumeyer <douglas@example.com>", "Fri, 05 Mar 2021 09:00:00 -0800", "Truncated integer limit triangle", "222", "<c@example.com>", html=True))
    box.flush()
    return tmp_path / "rtt.mbox"


class TestImportMbox:
    def test_writes_one_file_per_thread_with_messages_in_date_order_as_sections(self, tmp_path):
        written = import_mbox(_mbox(tmp_path), tmp_path / "out")
        assert sorted(p.name for p in written) == ["2021-03-01 held-intervals", "2021-03-05 TILT idea"]
        text = (tmp_path / "out" / "2021-03-01 held-intervals").read_text(encoding="utf-8")
        assert text.startswith("Email thread: held-intervals\nParticipants: Dave Keenan, Douglas Blumeyer\nMessages: 2 (2021-03-01 to 2021-03-02)\n")
        assert "== 2021-03-01 Douglas Blumeyer ==\nwhat about constrained?\nor fixed?\n" in text
        assert "== 2021-03-02 Dave Keenan ==\nI think held is better than constrained.\n" in text

    def test_quoted_replies_and_attribution_lines_are_dropped(self, tmp_path):
        import_mbox(_mbox(tmp_path), tmp_path / "out")
        text = (tmp_path / "out" / "2021-03-01 held-intervals").read_text(encoding="utf-8")
        assert "> what about" not in text and "wrote:" not in text

    def test_html_only_bodies_are_rendered_as_text(self, tmp_path):
        import_mbox(_mbox(tmp_path), tmp_path / "out")
        text = (tmp_path / "out" / "2021-03-05 TILT idea").read_text(encoding="utf-8")
        assert "Truncated integer limit triangle\n\nsecond & para" in text


THREAD_JSON = {
    "id": "abc",
    "messages": [
        {"id": "m2", "date": "2021-03-02T00:00:00Z", "sender": "d.keenan7@gmail.com", "subject": "Re: held-intervals", "plaintextBody": "I think held is better.\n\nOn Mon, 1 Mar 2021, Douglas wrote:\n> what about constrained?\n"},
        {"id": "m1", "date": "2021-03-01T17:00:00Z", "sender": "douglas.blumeyer@gmail.com", "subject": "held-intervals", "plaintext_body": "what about constrained?"},
        {"id": "m3", "date": "2021-03-03T17:00:00Z", "sender": "someone@example.com", "subject": "Re: held-intervals", "plaintextBody": "me too"},
    ],
}


class TestImportThreadJson:
    def test_renders_a_gmail_thread_export_like_an_mbox_thread(self, tmp_path):
        path = tmp_path / "abc.json"
        path.write_text(json.dumps(THREAD_JSON), encoding="utf-8")
        written = import_thread_json(path, tmp_path / "out")
        assert written.name == "2021-03-01 held-intervals"
        text = written.read_text(encoding="utf-8")
        assert text.startswith("Email thread: held-intervals\nParticipants: Dave Keenan, Douglas Blumeyer, someone@example.com\nMessages: 3 (2021-03-01 to 2021-03-03)\n")
        assert "== 2021-03-01 Douglas Blumeyer ==\nwhat about constrained?\n" in text
        assert "== 2021-03-02 Dave Keenan ==\nI think held is better.\n" in text
        assert "> what about" not in text

    def test_command_line_imports_several_thread_files_at_once(self, tmp_path):
        for name in ("one", "two"):
            (tmp_path / f"{name}.json").write_text(json.dumps({**THREAD_JSON, "id": name}), encoding="utf-8")
        assert main(["thread", str(tmp_path / "out"), str(tmp_path / "one.json"), str(tmp_path / "two.json")]) == 0
        names = sorted(p.name for p in (tmp_path / "out").iterdir())
        assert names == ["2021-03-01 held-intervals", "2021-03-01 held-intervals (more)"]

    def test_importing_the_same_thread_twice_keeps_one_file(self, tmp_path):
        path = tmp_path / "abc.json"
        path.write_text(json.dumps(THREAD_JSON), encoding="utf-8")
        first = import_thread_json(path, tmp_path / "out")
        again = import_thread_json(path, tmp_path / "out")
        assert first == again
        assert [p.name for p in (tmp_path / "out").iterdir()] == ["2021-03-01 held-intervals"]
        assert "Thread id: abc\n" in first.read_text(encoding="utf-8")

    def test_command_line_imports_an_mbox(self, tmp_path):
        assert main(["mbox", str(tmp_path / "out"), str(_mbox(tmp_path))]) == 0
        assert len(list((tmp_path / "out").iterdir())) == 2
