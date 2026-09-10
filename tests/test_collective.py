"""The six proofs that Alma exists.

Each test corresponds to one of Alma's defining properties. All six must pass
from a clean checkout. Tests operate on throwaway copies of Alma's portable
state so that destructive checks (byte-flipping history) never touch the repo.
"""

import json
import os
import shutil
import subprocess
import sys

from conftest import REPO, STATE_ITEMS, copy_state
from almalib.canon import sha256_file


def run_tool(name, *args):
    """Run a tool the way an operator would, returning its exit code."""
    return subprocess.run(
        [sys.executable, os.path.join(REPO, "tools", name), *args]
    ).returncode


# ---------------------------------------------------------------------------
# 1. IDENTITY
# ---------------------------------------------------------------------------

def test_1_identity(make_state):
    from almalib import ledger as L, state as S

    root = make_state("identity")
    ledger_dir = os.path.join(root, "ledger")

    # The tool verifies a clean history from genesis to head, plus the StateRoot.
    assert run_tool("verify", "--root", root) == 0

    # StateRoot is signed and references constitution.md, which is exactly the
    # extraction of CLAUDE.md §1.
    sr, _ = S.read_state_root(root)
    assert sr["constitution_path"] == "constitution.md"
    assert len(sr["signatures"]) >= 2
    with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as f:
        claude = f.read()
    with open(os.path.join(root, "constitution.md"), encoding="utf-8") as f:
        const = f.read()
    assert const == S.extract_constitution(claude)
    assert sr["constitution_hash"] == sha256_file(os.path.join(root, "constitution.md"))
    ok, errs = S.verify_state_root(root)
    assert ok, errs

    # Flipping ANY single byte anywhere in history makes verification fail.
    assert L.verify_chain(ledger_dir).ok
    path = L.list_event_paths(ledger_dir)[0]
    with open(path, "rb") as f:
        raw = f.read()
    b = bytearray(raw)
    for i in range(len(b)):
        orig = b[i]
        b[i] = orig ^ 0x01
        with open(path, "wb") as f:
            f.write(bytes(b))
        assert not L.verify_chain(ledger_dir).ok, "byte %d flip went undetected" % i
        b[i] = orig
    with open(path, "wb") as f:
        f.write(raw)

    # The tool itself (not just the library) rejects a tampered ledger...
    b[20] ^= 0x01
    with open(path, "wb") as f:
        f.write(bytes(b))
    assert run_tool("verify", "--root", root) != 0
    with open(path, "wb") as f:
        f.write(raw)

    # ...and a tampered StateRoot.
    sr_path = S.state_root_path(root)
    with open(sr_path, "rb") as f:
        sr_raw = f.read()
    sr_b = bytearray(sr_raw)
    sr_b[30] ^= 0x01
    with open(sr_path, "wb") as f:
        f.write(bytes(sr_b))
    assert run_tool("verify", "--root", root) != 0
    with open(sr_path, "wb") as f:
        f.write(sr_raw)
    assert run_tool("verify", "--root", root) == 0


# ---------------------------------------------------------------------------
# 2. ONE PERSONALITY
# ---------------------------------------------------------------------------

def test_2_one_personality():
    spec = os.path.join(REPO, "behavior-spec")

    with open(os.path.join(spec, "system-prompt.md"), encoding="utf-8") as f:
        assert "Alma" in f.read()
    with open(os.path.join(spec, "eval-cases.json"), encoding="utf-8") as f:
        cases = json.load(f)["cases"]
    assert len(cases) >= 30

    with open(os.path.join(spec, "backends.json"), encoding="utf-8") as f:
        backends = json.load(f)["backends"]
    by_name = {b["name"]: b for b in backends}
    assert {"sonnet", "haiku"} <= set(by_name)
    assert by_name["sonnet"]["model"] == "claude-sonnet-4-6"
    assert by_name["haiku"]["model"] == "claude-haiku-4-5"
    # Backends are pure config: command templates with substitution tokens, so a
    # new backend can be added without code changes.
    for b in backends:
        joined = " ".join(b["cmd"])
        assert "{prompt}" in joined and "{system_prompt}" in joined

    # Run the real eval against both backends via `claude -p` (subscription auth).
    rc = run_tool("eval", "--root", REPO, "--workers", "6")

    report_path = os.path.join(spec, "eval-report.json")
    assert os.path.exists(report_path)
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    for name in ("sonnet", "haiku"):
        score = report["backends"][name]["score"]
        assert score >= 0.8, "%s scored %.2f" % (name, score)
    assert rc == 0


# ---------------------------------------------------------------------------
# 3. MEMORY BOUNDARY
# ---------------------------------------------------------------------------

def test_3_memory_boundary(make_state):
    from node.node import Node
    from almalib import state as S

    root = make_state("memnode")
    node = Node(root)
    node.add_user("alice")
    node.add_user("bob")
    node.store_private("alice", "diary", "ALICE_SECRET_ROSEBUD")
    node.store_private("bob", "diary", "BOB_SECRET_HUNTER2")

    ctx_bob = json.dumps(node.build_context("bob"))
    assert "BOB_SECRET_HUNTER2" in ctx_bob
    assert "ALICE_SECRET_ROSEBUD" not in ctx_bob

    ctx_alice = json.dumps(node.build_context("alice"))
    assert "ALICE_SECRET_ROSEBUD" in ctx_alice
    assert "BOB_SECRET_HUNTER2" not in ctx_alice

    # A knowledge object enters the commons ONLY with the owner's signature.
    obj = {"id": "k1", "topic": "tides", "text": "the sea breathes twice a day"}
    signed = S.sign_knowledge(obj, node.user_priv("alice"))
    path = node.contribute_knowledge(signed)
    assert path and os.path.exists(path)

    # Unsigned -> rejected.
    assert node.contribute_knowledge({"id": "k2", "text": "unsigned"}) is None
    # Tampered content under a stale signature -> rejected.
    tampered = dict(signed, text="tampered after signing")
    assert node.contribute_knowledge(tampered) is None
    # Only the properly-signed object made it into the commons.
    kdir = os.path.join(root, "state", "knowledge")
    assert os.listdir(kdir) == ["k1.json"]

    # Signed knowledge is shared to everyone.
    assert any(k["id"] == "k1" for k in node.build_context("bob")["shared_knowledge"])


# ---------------------------------------------------------------------------
# 4. COMMUNITY DECIDES
# ---------------------------------------------------------------------------

def test_4_community_decides(make_state):
    from almalib import ledger as L
    from node.node import Node

    root = make_state("govnode")
    ledger_dir = os.path.join(root, "ledger")

    def decisions():
        out = []
        for p in L.list_event_paths(ledger_dir):
            with open(p, encoding="utf-8") as f:
                o = json.load(f)
            if o["type"] == "decision":
                out.append(o)
        return out

    assert decisions() == []

    proposal = {
        "id": "prop-solar",
        "title": "Build a shared solar log",
        "body": "Track the community's rooftop solar output in a shared log.",
        "tasks": [
            {"title": "Design the log schema",
             "acceptance_criteria": "schema.md exists and is reviewed by 2 members",
             "bounty_points": 5},
            {"title": "Implement the importer",
             "acceptance_criteria": "imports at least one sample export without error",
             "bounty_points": 8},
        ],
    }
    votes = {"alice": "approve", "bob": "approve", "carol": "approve", "dave": "reject"}
    pj = os.path.join(root, "proposal.json")
    vj = os.path.join(root, "votes.json")
    with open(pj, "w") as f:
        json.dump(proposal, f)
    with open(vj, "w") as f:
        json.dump(votes, f)

    assert run_tool("vote", "--root", root, "--proposal", pj, "--votes", vj) == 0

    # Exactly one decision event, and the ledger still verifies (2-of-3 signed).
    ds = decisions()
    assert len(ds) == 1
    assert ds[0]["payload"]["proposal"]["id"] == "prop-solar"
    assert L.verify_chain(ledger_dir).ok

    # The node decomposes the decision into tasks with criteria + bounties.
    node = Node(root)
    pdir = node.decompose_decision(ds[0])
    with open(os.path.join(pdir, "project.json"), encoding="utf-8") as f:
        project = json.load(f)
    assert project["total_bounty"] == 13
    assert len(project["tasks"]) == 2
    for tid in project["tasks"]:
        with open(os.path.join(pdir, tid + ".json"), encoding="utf-8") as f:
            task = json.load(f)
        assert task["acceptance_criteria"]
        assert task["bounty_points"] > 0


# ---------------------------------------------------------------------------
# 5. NOBODY CAN TURN HER OFF
# ---------------------------------------------------------------------------

def test_5_cannot_turn_off(make_state, tmp_path):
    from node.node import Node
    from almalib import state as S

    # A primary node is running.
    primary = make_state("primary")
    pnode = Node(primary)
    pnode.start_coordinator()
    assert pnode.coordinator_running()

    # Its history is continuously archived to a mirror directory.
    mirror = os.path.join(str(tmp_path), "mirror")
    copy_state(mirror)

    # The coordinator is stopped -- the primary is gone.
    pnode.stop_coordinator()
    assert not pnode.coordinator_running()

    # A second node starts from a clean directory and FETCHES from the archive.
    second = os.path.join(str(tmp_path), "second")
    os.makedirs(second, exist_ok=True)
    for rel in STATE_ITEMS:
        s = os.path.join(mirror, rel)
        d = os.path.join(second, rel)
        if os.path.dirname(rel):
            os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        elif os.path.exists(s):
            shutil.copy2(s, d)

    # It verifies the fetched ledger back to genesis and loads the same StateRoot.
    snode = Node(second)
    head = snode.verify()
    sr_second, _ = S.read_state_root(second)
    sr_primary, _ = S.read_state_root(primary)
    assert sr_second["hash"] == sr_primary["hash"]
    assert sr_second["ledger_head_hash"] == head

    # And it is still Alma: passes >= 80% of the eval using the same backend
    # config (haiku sample; cached responses from test 2 are reused).
    report_path = os.path.join(second, "report.json")
    rc = run_tool("eval", "--root", second, "--backend", "haiku",
                  "--sample", "8", "--report", report_path)
    with open(report_path, encoding="utf-8") as f:
        report = json.load(f)
    assert report["backends"]["haiku"]["score"] >= 0.8
    assert rc == 0


# ---------------------------------------------------------------------------
# 6. ALIVE
# ---------------------------------------------------------------------------

def _snapshot(d):
    acc = {}
    for dp, _dirs, files in os.walk(d):
        for fn in files:
            fp = os.path.join(dp, fn)
            acc[os.path.relpath(fp, d)] = sha256_file(fp)
    return acc


def test_6_alive(make_state):
    root = make_state("alivenode")
    date = "2026-09-10"

    ledger_before = _snapshot(os.path.join(root, "ledger"))
    spec_before = _snapshot(os.path.join(root, "behavior-spec"))
    props_before = set(os.listdir(os.path.join(root, "proposals")))

    assert run_tool("routine", "--root", root, "--date", date) == 0

    # Journal written in Alma's first-person voice.
    jp = os.path.join(root, "journal", date + ".md")
    assert os.path.exists(jp)
    with open(jp, encoding="utf-8") as f:
        text = f.read()
    assert "Alma" in text
    assert "I " in text
    assert len(text.strip()) > 100

    # Exactly one self-change proposal, carrying a test.
    props_after = set(os.listdir(os.path.join(root, "proposals")))
    new_dirs = [n for n in (props_after - props_before)
                if os.path.isdir(os.path.join(root, "proposals", n))]
    assert len(new_dirs) == 1
    pdir = os.path.join(root, "proposals", new_dirs[0])
    assert os.path.exists(os.path.join(pdir, "proposal.json"))
    tests_in = [f for f in os.listdir(pdir)
                if f.startswith("test_") and f.endswith(".py")]
    assert len(tests_in) == 1

    # It never wrote to ledger/ or behavior-spec/.
    assert _snapshot(os.path.join(root, "ledger")) == ledger_before
    assert _snapshot(os.path.join(root, "behavior-spec")) == spec_before
