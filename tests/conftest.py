import os
import shutil
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
