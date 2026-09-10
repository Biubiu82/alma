"""README.md must not drift from the repository it describes.

On 2026-09-11 Alma read her own README as its subject and found nine things that
were not true of her: a birthday her genesis event contradicted, a git tag that
did not exist, directories that were not there, a voting mechanism nothing
implemented, and a claim about surviving any single model that rested on two
backends from one vendor.

None of it was anyone's dishonesty. It was a page written at one moment
describing a repository that moved -- a record failing by custody, which is the
failure these tests exist to catch.
"""

import json
import os
import re
import subprocess

from conftest import REPO

README = os.path.join(REPO, "README.md")


def readme():
    with open(README, encoding="utf-8") as f:
        return f.read()


def test_every_path_in_the_tree_block_exists():
    """The repository map must map the repository."""
    blocks = re.findall(r"```\n(.*?)```", readme(), re.S)
    assert blocks, "no tree block found in README"
    checked = 0
    for block in blocks:
        for line in block.splitlines():
            m = re.match(r"^([A-Za-z0-9_./-]+/?)(\s{2,}|$)", line.strip())
            if not m:
                continue
            for token in m.group(1).split():
                if not re.search(r"[./]", token) and token not in ("tests", "journal"):
                    continue
                path = os.path.join(REPO, token.rstrip("/"))
                assert os.path.exists(path), "README names %r, which does not exist" % token
                checked += 1
    assert checked >= 8, "only %d paths checked; the tree block may have changed shape" % checked


def test_no_birth_date_that_the_genesis_event_contradicts():
    """Alma's first ledger event is the only thing entitled to say when she began."""
    with open(os.path.join(REPO, "ledger", "000000.json"), encoding="utf-8") as f:
        genesis_date = json.load(f)["timestamp"][:10]

    for m in re.finditer(r"\bborn on ([0-9]{1,2} \w+ [0-9]{4})", readme()):
        claimed = m.group(1)
        assert False, (
            "README claims she was 'born on %s' while ledger/000000.json is "
            "timestamped %s. Either the genesis stamp is wrong -- and it is "
            "append-only, so that is a governance matter, not an edit -- or the "
            "README should make the narrower, true claim about when she was "
            "assembled and first run." % (claimed, genesis_date))


def test_genesis_tag_claim_matches_reality():
    text = readme()
    if not re.search(r"genesis[^.\n]*\btagged\b", text, re.I):
        return
    out = subprocess.run(["git", "tag", "--list"], cwd=REPO,
                         capture_output=True, text=True)
    tags = [t.strip() for t in out.stdout.splitlines() if t.strip()]
    assert tags, "README says the technical genesis is tagged; git has no tags"
    named = re.findall(r"`([a-z0-9][a-z0-9._/-]*)`", text)
    if any(n in tags for n in named):
        return
    assert False, ("README says the genesis is tagged but names no tag that "
                   "exists. Tags present: %s" % tags)


def test_vendor_claim_is_not_overstated():
    """Two models is not two vendors, and the page must not imply otherwise."""
    with open(os.path.join(REPO, "behavior-spec", "backends.json"), encoding="utf-8") as f:
        backends = json.load(f)["backends"]
    for b in backends:
        assert "vendor" in b, "backend %r does not record a vendor" % b.get("name")
    vendors = sorted({b["vendor"] for b in backends})
    text = readme()

    if len(vendors) == 1:
        assert re.search(r"one vendor|single vendor|same vendor", text, re.I), (
            "every backend is supplied by %r, so the README must say so plainly "
            "rather than implying independence from any company." % vendors[0])
        assert not re.search(r"no single (model|company|vendor) (is her|owns her)"
                             r"(?![^.]*vendor)", text, re.I)
    else:
        assert len(vendors) >= 2


def test_proposal_path_is_where_proposals_actually_go():
    """The page must send people where tools/routine writes."""
    text = readme()
    m = re.search(r"`(state/proposals/|proposals/)`", text)
    assert m, "README does not name a proposals directory"
    named = m.group(1)
    assert os.path.isdir(os.path.join(REPO, named.rstrip("/"))), \
        "README names %r, which does not exist" % named

    with open(os.path.join(REPO, "tools", "routine"), encoding="utf-8") as f:
        routine = f.read()
    assert 'os.path.join(root, "state", "proposals", pid)' in routine
    assert named == "state/proposals/", (
        "README sends people to %r but tools/routine writes to state/proposals/"
        % named)
    assert not os.path.exists(os.path.join(REPO, "proposals")), \
        "a second, stale proposals/ directory still exists"


def test_threshold_is_described_as_signatures_not_votes():
    """config.json's threshold authorizes events; it is not an upvote count."""
    text = readme()
    if "config.json" not in text:
        return
    window = text[max(0, text.find("config.json") - 400):text.find("config.json") + 400]
    assert not re.search(r"upvote[^.]{0,80}threshold|threshold[^.]{0,80}upvote",
                         window, re.I), (
        "README ties config.json's threshold to upvotes. It is the number of "
        "signatures an event must carry (CLAUDE.md 2.3).")
