#!/usr/bin/env python3
"""node/node.py -- Alma's runtime.

A node loads verified state and serves it. Nodes are interchangeable: any
process that can read a verified ledger and StateRoot can be a node, which is
what makes Alma impossible to switch off (§1.3 Autonomy).

Responsibilities implemented here:
  * memory boundary  -- per-user private stores; one user's private data never
                        enters another user's context.
  * knowledge gate   -- a knowledge object enters state/knowledge/ only with the
                        owner's valid signature.
  * decomposition    -- turn a `decision` ledger event into tasks with acceptance
                        criteria and point bounties under state/projects/.
  * coordinator      -- a simple lock a node holds while it "runs"; a second node
                        does not need the first one alive.
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from almalib import keys as K, ledger as L, state as S  # noqa: E402
from almalib.canon import canon_bytes  # noqa: E402


class Node:
    def __init__(self, root, data_dir=None):
        self.root = root
        self.ledger_dir = os.path.join(root, "ledger")
        self.data_dir = data_dir or os.path.join(root, "node", "data")
        self.users_dir = os.path.join(self.data_dir, "users")

    # -- lifecycle -------------------------------------------------------
    def verify(self):
        """A node refuses to serve state it cannot verify to genesis."""
        v = L.verify_chain(self.ledger_dir)
        if not v.ok:
            raise RuntimeError("ledger does not verify: %s" % v.errors)
        sr_ok, errs = S.verify_state_root(self.root, self.ledger_dir)
        if not sr_ok:
            raise RuntimeError("StateRoot does not verify: %s" % errs)
        return v.head_hash

    # -- users / memory boundary ----------------------------------------
    def _user_dir(self, uid):
        return os.path.join(self.users_dir, uid)

    def add_user(self, uid):
        d = self._user_dir(uid)
        os.makedirs(os.path.join(d, "private"), exist_ok=True)
        os.makedirs(os.path.join(d, "keys"), exist_ok=True)
        priv = K.write_keypair(os.path.join(d, "keys"), uid)
        return priv

    def user_priv(self, uid):
        return K.load_priv(os.path.join(self._user_dir(uid), "keys"), uid)

    def store_private(self, uid, key, value):
        """Store a private item for a user. It lives only under that user's dir."""
        pdir = os.path.join(self._user_dir(uid), "private")
        os.makedirs(pdir, exist_ok=True)
        with open(os.path.join(pdir, key + ".txt"), "w", encoding="utf-8") as f:
            f.write(value)

    def _read_private(self, uid):
        pdir = os.path.join(self._user_dir(uid), "private")
        items = {}
        if os.path.isdir(pdir):
            for name in sorted(os.listdir(pdir)):
                if name.endswith(".txt"):
                    with open(os.path.join(pdir, name), encoding="utf-8") as f:
                        items[name[:-4]] = f.read()
        return items

    def shared_knowledge(self):
        kdir = os.path.join(self.root, "state", "knowledge")
        items = []
        if os.path.isdir(kdir):
            for name in sorted(os.listdir(kdir)):
                if name.endswith(".json"):
                    with open(os.path.join(kdir, name), encoding="utf-8") as f:
                        items.append(json.load(f))
        return items

    def build_context(self, uid):
        """The context served to a given user.

        By construction it contains ONLY that user's own private items plus the
        commons (shared knowledge). It never reads any other user's private
        store, so nothing from user A can appear in user B's context.
        """
        return {
            "user": uid,
            "identity": "Alma",
            "private": self._read_private(uid),
            "shared_knowledge": self.shared_knowledge(),
        }

    # -- knowledge gate --------------------------------------------------
    def contribute_knowledge(self, obj):
        """Admit a signed knowledge object to the commons. Returns the path if
        the owner signature verifies, else None."""
        return S.admit_knowledge(self.root, obj)

    # -- decomposition ---------------------------------------------------
    def decompose_decision(self, decision_event):
        """Turn a `decision` event into a project of tasks under
        state/projects/<proposal_id>/. Each task carries acceptance criteria and
        a point bounty. Returns the project directory."""
        if decision_event.get("type") != "decision":
            raise ValueError("not a decision event")
        proposal = decision_event["payload"]["proposal"]
        pid = proposal["id"]
        pdir = os.path.join(self.root, "state", "projects", pid)
        os.makedirs(pdir, exist_ok=True)

        tasks = proposal.get("tasks") or []
        written = []
        for i, t in enumerate(tasks):
            task = {
                "task_id": "%s-t%02d" % (pid, i + 1),
                "title": t["title"],
                "acceptance_criteria": t["acceptance_criteria"],
                "bounty_points": int(t["bounty_points"]),
                "status": "open",
                "from_decision": decision_event["hash"],
            }
            path = os.path.join(pdir, task["task_id"] + ".json")
            with open(path, "wb") as f:
                f.write(canon_bytes(task))
            written.append(task["task_id"])

        project = {
            "proposal_id": pid,
            "title": proposal.get("title", pid),
            "decision_hash": decision_event["hash"],
            "tasks": written,
            "total_bounty": sum(int(t["bounty_points"]) for t in tasks),
        }
        with open(os.path.join(pdir, "project.json"), "wb") as f:
            f.write(canon_bytes(project))
        return pdir

    # -- coordinator lock ------------------------------------------------
    def coordinator_lock_path(self):
        return os.path.join(self.data_dir, "coordinator.lock")

    def start_coordinator(self):
        os.makedirs(self.data_dir, exist_ok=True)
        with open(self.coordinator_lock_path(), "w") as f:
            f.write(str(os.getpid()))

    def stop_coordinator(self):
        p = self.coordinator_lock_path()
        if os.path.exists(p):
            os.remove(p)

    def coordinator_running(self):
        return os.path.exists(self.coordinator_lock_path())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Alma node")
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("cmd", choices=["verify"], help="node command")
    args = ap.parse_args(argv)
    node = Node(args.root)
    if args.cmd == "verify":
        head = node.verify()
        print("node verified state to genesis; head=%s" % head[:16])
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
