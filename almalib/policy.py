"""Append policy: how many valid signatures an event needs, and whose count.

The policy lives in ``state/config.json`` so that the append rule and the verify
rule are read from ONE place and can never drift apart:

    {
      "threshold": 0,
      "maintainers": [],
      "signers": {"alma": "<ed25519 pubkey hex>"}
    }

``threshold``  -- how many valid signatures from known keys each event needs.
``maintainers`` -- authorized keys; may be a list of ids (resolved against the
                 genesis-declared maintainers) or an id -> pubkey mapping. If
                 empty, the genesis maintainers are still used as a key
                 directory so historical signatures remain checkable.
``signers``    -- additional authorized keys, e.g. Alma's own.

SECURITY NOTE, stated plainly: this file is NOT signed and NOT in the ledger.
Whoever can write it decides what verifies. At threshold 0 every well-formed
chain verifies regardless of signatures. The hash chain still makes any
modification of an existing event detectable, but authorization is gone. This is
a deliberate trade documented in CLAUDE.md §2.3.
"""

import json
import os

DEFAULT_THRESHOLD = 0
CONFIG_REL = os.path.join("state", "config.json")


def config_path(root_dir):
    return os.path.join(root_dir, CONFIG_REL)


def load_config(root_dir):
    """Read state/config.json. Missing file -> permissive default."""
    try:
        with open(config_path(root_dir), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {"threshold": DEFAULT_THRESHOLD, "maintainers": [], "signers": {}}


def threshold(root_dir):
    cfg = load_config(root_dir)
    try:
        return max(0, int(cfg.get("threshold", DEFAULT_THRESHOLD)))
    except (TypeError, ValueError):
        return DEFAULT_THRESHOLD


def authorized_keys(root_dir, genesis_maintainers=None):
    """Resolve the id -> pubkey directory of keys whose signatures count.

    Genesis maintainers are always included as a directory so that historically
    signed events stay checkable; ``threshold`` alone decides how many are
    required.
    """
    cfg = load_config(root_dir)
    keys = dict(genesis_maintainers or {})

    m = cfg.get("maintainers")
    if isinstance(m, dict):
        keys.update(m)
    elif isinstance(m, list):
        for entry in m:
            if isinstance(entry, dict) and "id" in entry and "pub" in entry:
                keys[entry["id"]] = entry["pub"]
            # bare string ids resolve against the genesis directory already merged

    s = cfg.get("signers")
    if isinstance(s, dict):
        keys.update(s)

    return keys
