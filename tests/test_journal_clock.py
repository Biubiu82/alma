"""The journal must read the clock, not assert one.

On 2026-09-11 Alma headed roughly twenty journal entries with times she had
invented, and wrote inside the fiction. Over the same period every timestamp in
her ledger was correct, because tools/append calls the clock and she does not
get a vote. These tests give the journal the same discipline.
"""

import os
import re
import subprocess
import sys
from datetime import datetime

from conftest import REPO

JOURNAL_RE = re.compile(r"^## (\d{2}):(\d{2}) — ")
GUIDANCE_RE = re.compile(r"^## Guidance (\d{2}):(\d{2})\s*$")
TZ_RE = re.compile(r"^# (\d{4}-\d{2}-\d{2}) \(times are local, UTC[+-]\d{1,2}(?::\d{2})?\)$")


def run_tool(name, *args):
    return subprocess.run(
        [sys.executable, os.path.join(REPO, "tools", name), *args],
        capture_output=True, text=True)


def test_journal_refuses_a_supplied_time(tmp_path):
    """The point of the tool is that the caller cannot state the time."""
    for flag, value in (("--time", "09:00"), ("--date", "2026-01-01"),
                        ("--timestamp", "2026-01-01T00:00:00Z"), ("--at", "noon")):
        r = run_tool("journal", "--root", str(tmp_path), "--title", "x", flag, value)
        assert r.returncode != 0, "%s was accepted" % flag
        assert flag in r.stderr


def test_journal_stamps_from_the_clock(tmp_path):
    before = datetime.now().astimezone()
    r = run_tool("journal", "--root", str(tmp_path), "--title", "a place I went",
                 "--body", "what I saw there.")
    after = datetime.now().astimezone()
    assert r.returncode == 0, r.stderr

    path = os.path.join(str(tmp_path), "journal", "%s.md" % before.strftime("%Y-%m-%d"))
    assert os.path.exists(path), "journal file not named for today"

    text = open(path, encoding="utf-8").read()
    m = None
    for line in text.splitlines():
        m = JOURNAL_RE.match(line) or m
    assert m, "no timestamped entry heading was written"

    stamped = int(m.group(1)) * 60 + int(m.group(2))
    lo = before.hour * 60 + before.minute
    hi = after.hour * 60 + after.minute
    assert lo <= stamped <= hi or (hi < lo and (stamped >= lo or stamped <= hi)), \
        "heading %s is outside the window the tool actually ran in" % m.group(0)


def test_journal_declares_its_timezone_on_line_one(tmp_path):
    assert run_tool("journal", "--root", str(tmp_path), "--title", "x").returncode == 0
    date = datetime.now().astimezone().strftime("%Y-%m-%d")
    path = os.path.join(str(tmp_path), "journal", "%s.md" % date)
    first = open(path, encoding="utf-8").read().splitlines()[0]
    m = TZ_RE.match(first)
    assert m, "line 1 must declare the date and timezone, got: %r" % first
    assert m.group(1) == date, "line 1 date disagrees with the filename"


def test_journal_filename_matches_its_own_headings(tmp_path):
    """A file named for one day must not carry headings stamped on another."""
    assert run_tool("journal", "--root", str(tmp_path), "--title", "one").returncode == 0
    assert run_tool("journal", "--root", str(tmp_path), "--guidance",
                    "--body", "three to five lines.").returncode == 0
    date = datetime.now().astimezone().strftime("%Y-%m-%d")
    path = os.path.join(str(tmp_path), "journal", "%s.md" % date)
    text = open(path, encoding="utf-8").read()
    assert TZ_RE.match(text.splitlines()[0]).group(1) == date
    assert any(GUIDANCE_RE.match(l) for l in text.splitlines()), "no guidance heading"
    # exactly one timezone header, however many entries are appended
    assert sum(1 for l in text.splitlines() if TZ_RE.match(l)) == 1


def test_journal_cannot_write_to_ledger_or_behavior_spec(tmp_path):
    """CLAUDE.md 2.2a: a routine never writes to ledger/ or behavior-spec/."""
    root = str(tmp_path)
    for d in ("ledger", "behavior-spec"):
        os.makedirs(os.path.join(root, d), exist_ok=True)

    def snapshot():
        acc = {}
        for d in ("ledger", "behavior-spec"):
            for dp, _dirs, files in os.walk(os.path.join(root, d)):
                for fn in files:
                    fp = os.path.join(dp, fn)
                    acc[fp] = open(fp, "rb").read()
        return acc

    before = snapshot()
    assert run_tool("journal", "--root", root, "--title", "somewhere",
                    "--body", "text").returncode == 0
    assert snapshot() == before

    src = open(os.path.join(REPO, "tools", "journal"), encoding="utf-8").read()
    assert '"ledger"' not in src and '"behavior-spec"' not in src
