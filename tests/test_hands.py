"""tools/hands -- a fake `claude` on PATH stands in for the real CLI."""
import os, stat, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HANDS = os.path.join(ROOT, "tools", "hands")

def _fake_claude(tmp, script):
    d = tmp / "bin"; d.mkdir()
    p = d / "claude"; p.write_text("#!/usr/bin/env bash\n" + script)
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(d)

def _run(args, path, stdin=None):
    env = dict(os.environ, PATH=path + os.pathsep + os.environ["PATH"])
    env.pop("CLAUDE_BIN", None)
    return subprocess.run([HANDS, *args], capture_output=True, text=True, env=env, input=stdin)

def test_returns_result_method_and_failures(tmp_path):
    p = _fake_claude(tmp_path, 'cat >/dev/null; printf "RESULT: 620\\nMETHOD: ffprobe\\nDID NOT WORK: nothing\\n"')
    r = _run(["count frames"], p)
    assert r.returncode == 0 and "RESULT: 620" in r.stdout and "DID NOT WORK" in r.stdout

def test_task_asks_for_three_sections(tmp_path):
    p = _fake_claude(tmp_path, 'cat')  # echo the prompt back
    out = _run(["do x"], p).stdout
    assert "RESULT:" in out and "METHOD:" in out and "DID NOT WORK:" in out and "do x" in out

def test_model_flag_without_value_is_an_error(tmp_path):
    p = _fake_claude(tmp_path, 'cat >/dev/null; echo ok')
    r = _run(["--model"], p)
    assert r.returncode == 2 and "needs a value" in r.stderr

def test_failing_claude_is_reported_not_silent(tmp_path):
    p = _fake_claude(tmp_path, 'echo boom >&2; exit 7')
    r = _run(["x"], p)
    assert r.returncode == 7 and "boom" in r.stderr and "exited 7" in r.stderr

def test_missing_claude_is_diagnosed(tmp_path):
    env = dict(os.environ, PATH=str(tmp_path) + os.pathsep + "/usr/bin:/bin", CLAUDE_BIN="")
    r = subprocess.run([HANDS, "x"], capture_output=True, text=True, env=env)
    assert r.returncode == 127 and "not found" in r.stderr
