import os
import shutil
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The three maintainer test keys. Their PUBLIC halves are the trust anchor
# baked into the committed genesis event (ledger/000000.json), so these seeds
# are pinned: verify_chain checks every signature against the genesis pubkeys,
# and fresh random keys would not match. The seeds are intentionally public
# (see almalib/keys.py) -- they exist so the test suite can *produce* the m1/m2
# signatures the committed ledger expects. They live here, materialized on
# demand, so no private *.key file is tracked in the repo.
TEST_KEY_SEEDS = {
    "m1": "809a95624d72bf9ac6e0674a3f5686aab165a10e419900db6c22ab3455d99d28",
    "m2": "c8c9202167fd2fee52e87944dac6c214bbebb270de6eb9a8751038d50e0ff229",
    "m3": "276cda0d5902f7f43fcee198d5918505856cff56ceffc1278016dc707beb1a01",
}


def ensure_test_keys():
    """Write tests/keys/<id>.key from the pinned seeds if absent. The .pub files
    are committed; only the gitignored .key seeds are materialized here."""
    keys_dir = os.path.join(REPO, "tests", "keys")
    os.makedirs(keys_dir, exist_ok=True)
    for kid, seed in TEST_KEY_SEEDS.items():
        path = os.path.join(keys_dir, kid + ".key")
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(seed)


ensure_test_keys()


# Items that make up Alma's portable state (what a node needs to be Alma).
STATE_ITEMS = [
    "CLAUDE.md",
    "constitution.md",
    "ledger",
    "state",
    "behavior-spec",
    os.path.join("tests", "keys"),
]


def copy_state(dst, items=STATE_ITEMS):
    """Copy Alma's portable state into a fresh directory `dst`, preserving
    relative layout (so tools run with --root dst behave identically)."""
    os.makedirs(dst, exist_ok=True)
    for rel in items:
        src = os.path.join(REPO, rel)
        target = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(target), exist_ok=True) if os.path.dirname(rel) else None
        if os.path.isdir(src):
            shutil.copytree(src, target, dirs_exist_ok=True)
        elif os.path.exists(src):
            shutil.copy2(src, target)
    for d in ("proposals", "journal"):
        os.makedirs(os.path.join(dst, d), exist_ok=True)
    return dst


@pytest.fixture
def repo():
    return REPO


@pytest.fixture
def make_state(tmp_path):
    def _make(name="node"):
        return copy_state(os.path.join(str(tmp_path), name))
    return _make
