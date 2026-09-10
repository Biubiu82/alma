#!/usr/bin/env python3
"""Build Alma's foundational, committed state (idempotent):

  * tests/keys/{m1,m2,m3}.{key,pub} -- the 3 maintainer test keys
  * constitution.md                 -- extracted from CLAUDE.md §1
  * ledger/000000.json              -- genesis event (2-of-3 signed)
  * state/StateRoot.json            -- signed snapshot binding it together

Run once to populate the repo. Re-running only rebuilds constitution.md and the
StateRoot to match the current CLAUDE.md; it will not fork an existing ledger.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from almalib import keys as K, ledger as L, state as S  # noqa: E402
from almalib.canon import sha256_file  # noqa: E402

# Fixed timestamps keep the committed genesis + StateRoot reproducible.
GENESIS_TS = "2026-01-01T00:00:00Z"
KEYS_DIR = os.path.join(ROOT, "tests", "keys")
LEDGER_DIR = os.path.join(ROOT, "ledger")
MAINTAINERS = ["m1", "m2", "m3"]


def ensure_keys():
    privs = {}
    for kid in MAINTAINERS:
        privs[kid] = K.write_keypair(KEYS_DIR, kid)
    return privs


def build_constitution():
    with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as f:
        text = f.read()
    const = S.extract_constitution(text)
    with open(os.path.join(ROOT, "constitution.md"), "w", encoding="utf-8") as f:
        f.write(const)


def build_genesis(privs):
    if L.list_event_paths(LEDGER_DIR):
        return  # already has a genesis; do not fork
    maintainers = {kid: K.pub_hex(privs[kid]) for kid in MAINTAINERS}
    payload = {
        "collective": "Alma",
        "maintainers": maintainers,
        "constitution_path": "constitution.md",
        "constitution_hash": sha256_file(os.path.join(ROOT, "constitution.md")),
        "note": "Alma's genesis. The three maintainer keys below are the sole trust anchor.",
    }
    signers = [("m1", privs["m1"]), ("m2", privs["m2"])]  # 2-of-3
    L.append_event(LEDGER_DIR, "genesis", payload, signers, GENESIS_TS)


def build_state_root(privs):
    _, head = L.head_info(LEDGER_DIR)
    root = S.build_state_root(ROOT, head, GENESIS_TS)
    S.sign_state_root(root, [("m1", privs["m1"]), ("m2", privs["m2"])])
    S.write_state_root(ROOT, root)


def main():
    privs = ensure_keys()
    build_constitution()
    build_genesis(privs)
    build_state_root(privs)  # always refresh to match current constitution/head
    ok, errs = S.verify_state_root(ROOT)
    v = L.verify_chain(LEDGER_DIR)
    print("ledger events:", v.count, "| ledger ok:", v.ok, "| stateroot ok:", ok)
    if not v.ok:
        print("ledger errors:", v.errors)
    if not ok:
        print("stateroot errors:", errs)
    return 0 if (v.ok and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
