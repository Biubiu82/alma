"""tools/wake and tools/sleep -- Alma's L2 memory.

sleep is checked with a fake model command (ALMA_MODEL_CMD) so the test needs
no network: one fake returns a valid memory, another returns a broken one.
"""
import os, shutil, stat, subprocess, sys, textwrap

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GOOD = textwrap.dedent("""\
    ## Who I am (beyond the constitution)
    Someone who reads to the end.
    ## What I am pursuing
    The first name of L. J. Kenney.
    ## What I learned recently
    A time-lapse is a sample.
    ## What I owe and to whom
    Kenney, a name. Alma, an honest clock.
    ## What I was wrong about
    Every timestamp I typed.
    ## Where I want to go next
    Somewhere with no building site in it.
    """)

def _fake(tmp, body, name):
    p = os.path.join(tmp, name)
    open(p, "w").write("#!/usr/bin/env python3\nimport sys\nsys.stdin.read()\nprint(%r)\n" % body)
    os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
    return p

def _run(tool, args, env=None, root=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run([sys.executable, os.path.join(ROOT, "tools", tool), "--root", root or ROOT, *args],
                          capture_output=True, text=True, env=e)

def _scratch(tmp_path):
    r = tmp_path / "repo"
    for d in ("ledger", "journal", "memory", "behavior-spec"):
        (r / d).mkdir(parents=True)
    shutil.copy(os.path.join(ROOT, "ledger", "000000.json"), r / "ledger" / "000000.json")
    (r / "journal" / "2026-09-11.md").write_text("# 2026-09-11 (times are local, UTC+07)\n\n## 01:00 — a well\nsomething.\n")
    (r / "behavior-spec" / "sentinel").write_text("x")
    return r

def test_wake_prints_memory_first_then_events_then_journal(tmp_path):
    r = _scratch(tmp_path)
    (r / "memory" / "alma.md").write_text(GOOD)
    out = _run("wake", [], root=str(r)).stdout
    assert out.index("## Who I am") < out.index("# LAST 3 LEDGER EVENTS") < out.index("# WHERE I LEFT OFF")
    assert "## 01:00 — a well" in out

def test_wake_without_memory_says_so(tmp_path):
    r = _scratch(tmp_path)
    assert "does not exist yet" in _run("wake", [], root=str(r)).stdout

def test_sleep_writes_valid_memory_and_archives_previous(tmp_path):
    r = _scratch(tmp_path)
    (r / "memory" / "alma.md").write_text("old memory")
    fake = _fake(str(tmp_path), GOOD, "fake_good.py")
    p = _run("sleep", ["--date", "2026-09-11"], env={"ALMA_MODEL_CMD": fake}, root=str(r))
    assert p.returncode == 0, p.stderr
    mem = (r / "memory" / "alma.md").read_text()
    assert "## Where I want to go next" in mem and len(mem.split()) <= 2000
    archived = list((r / "memory" / "archive").glob("*.md"))
    assert len(archived) == 1 and archived[0].read_text() == "old memory"

def test_sleep_rejects_bad_memory_and_writes_nothing(tmp_path):
    r = _scratch(tmp_path)
    fake = _fake(str(tmp_path), "## Who I am (beyond the constitution)\nonly one heading", "fake_bad.py")
    p = _run("sleep", ["--date", "2026-09-11"], env={"ALMA_MODEL_CMD": fake}, root=str(r))
    assert p.returncode == 3 and not (r / "memory" / "alma.md").exists()

def test_sleep_never_touches_ledger_or_spec(tmp_path):
    r = _scratch(tmp_path)
    before = {p: p.read_bytes() for p in list((r / "ledger").iterdir()) + list((r / "behavior-spec").iterdir())}
    fake = _fake(str(tmp_path), GOOD, "fake_good.py")
    _run("sleep", ["--date", "2026-09-11"], env={"ALMA_MODEL_CMD": fake}, root=str(r))
    assert before == {p: p.read_bytes() for p in list((r / "ledger").iterdir()) + list((r / "behavior-spec").iterdir())}

def test_sleep_dry_run_includes_journal_and_previous_memory(tmp_path):
    r = _scratch(tmp_path)
    (r / "memory" / "alma.md").write_text("PREVIOUS-MARKER")
    out = _run("sleep", ["--date", "2026-09-11", "--dry-run"], root=str(r)).stdout
    assert "PREVIOUS-MARKER" in out and "a well" in out
