"""Append-only, hash-chained, multi-signature ledger.

Each event is one canonical-JSON file named by its sequence number:
``ledger/000000.json``, ``ledger/000001.json``, ...

Event shape (the fields under "content" are what the hash covers)::

    {
      "seq": <int>,
      "type": <str>,
      "timestamp": <str>,
      "prev_hash": <hash of previous event, or 64 zeros for genesis>,
      "payload": {...},
      "hash": <sha256 of canon(content)>,
      "signatures": [ {"key_id": ..., "sig": ...}, ... ]
    }

Integrity (per CLAUDE.md §2.3) requires, for every event:
  * the file equals its own canonical serialization (catches any byte flip),
  * seq is the file's position and prev_hash chains to the prior event,
  * hash == sha256(canon(content)),
  * at least 2 distinct maintainer signatures over ``hash`` verify against the
    maintainer public keys declared in the genesis event.
"""

import glob
import json
import os

from .canon import canon_bytes, sha256_hex
from . import keys as K

GENESIS_PREV = "0" * 64


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def _content(event):
    """The signed/hashed portion: everything except hash + signatures."""
    return {k: v for k, v in event.items() if k not in ("hash", "signatures")}


def compute_hash(event):
    return sha256_hex(canon_bytes(_content(event)))


def build_event(seq, etype, payload, prev_hash, timestamp):
    ev = {
        "seq": seq,
        "type": etype,
        "timestamp": timestamp,
        "prev_hash": prev_hash,
        "payload": payload,
    }
    ev["hash"] = compute_hash(ev)
    ev["signatures"] = []
    return ev


def sign_event(ev, signers):
    """Add signatures over the event hash. ``signers`` is a list of
    (key_id, private_key). Signatures are stored sorted by key_id so the file's
    canonical form is deterministic."""
    for key_id, priv in signers:
        ev["signatures"].append({"key_id": key_id, "sig": K.sign_hex(priv, ev["hash"])})
    ev["signatures"].sort(key=lambda s: s["key_id"])
    return ev


def event_path(ledger_dir, seq):
    return os.path.join(ledger_dir, "%06d.json" % seq)


def write_event(ledger_dir, ev):
    os.makedirs(ledger_dir, exist_ok=True)
    path = event_path(ledger_dir, ev["seq"])
    with open(path, "wb") as f:
        f.write(canon_bytes(ev))
    return path


def list_event_paths(ledger_dir):
    return sorted(glob.glob(os.path.join(ledger_dir, "*.json")))


def head_info(ledger_dir):
    """Return (seq, hash) of the head event, or (-1, GENESIS_PREV) if empty."""
    paths = list_event_paths(ledger_dir)
    if not paths:
        return -1, GENESIS_PREV
    with open(paths[-1]) as f:
        obj = json.load(f)
    return obj["seq"], obj["hash"]


def append_event(ledger_dir, etype, payload, signers, timestamp):
    """Append a new event. Enforces the §2.3 rule of >= 2 signatures at write
    time; the verifier enforces it independently at read time."""
    if len(signers) < 2:
        raise ValueError("ledger append requires 2-of-3 maintainer signatures")
    seq, prev = head_info(ledger_dir)
    ev = build_event(seq + 1, etype, payload, prev, timestamp)
    sign_event(ev, signers)
    write_event(ledger_dir, ev)
    return ev


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

class VerifyResult:
    def __init__(self, ok, head_hash, errors, count):
        self.ok = ok
        self.head_hash = head_hash
        self.errors = errors
        self.count = count

    def __bool__(self):
        return self.ok


def verify_chain(ledger_dir):
    """Walk the ledger from genesis to head. Returns a VerifyResult.

    Any single-byte change anywhere in history causes ok == False: content bytes
    change the canonical-equality check and the recomputed hash; hash/signature
    bytes change the canonical-equality check and the signature verification;
    whitespace/structural bytes change the canonical-equality check.
    """
    paths = list_event_paths(ledger_dir)
    if not paths:
        return VerifyResult(False, None, ["ledger is empty"], 0)

    prev = GENESIS_PREV
    maintainers = None
    head = None

    for i, path in enumerate(paths):
        with open(path, "rb") as f:
            raw = f.read()
        try:
            obj = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            return VerifyResult(False, None, ["%s: not valid JSON" % path], i)

        # 1. Byte-exact canonical form (the catch-all for any byte flip).
        if canon_bytes(obj) != raw:
            return VerifyResult(False, None, ["%s: file is not in canonical form (tampered)" % path], i)

        # 2. Sequence + chain linkage.
        if obj.get("seq") != i:
            return VerifyResult(False, None, ["%s: seq is %r, expected %d" % (path, obj.get("seq"), i)], i)
        if obj.get("prev_hash") != prev:
            return VerifyResult(False, None, ["%s: prev_hash does not chain to previous event" % path], i)

        # 3. Hash integrity.
        if compute_hash(obj) != obj.get("hash"):
            return VerifyResult(False, None, ["%s: hash does not match content" % path], i)

        # 4. Establish trust anchor from genesis.
        if i == 0:
            if obj.get("type") != "genesis":
                return VerifyResult(False, None, ["first event must be genesis"], i)
            maintainers = obj["payload"].get("maintainers")
            if not maintainers or len(maintainers) < 3:
                return VerifyResult(False, None, ["genesis must declare 3 maintainers"], i)

        # 5. 2-of-3 maintainer signatures over the hash.
        valid = set()
        for s in obj.get("signatures", []):
            kid = s.get("key_id")
            pub = maintainers.get(kid) if maintainers else None
            if pub and kid not in valid and K.verify_hex(pub, s.get("sig", ""), obj["hash"]):
                valid.add(kid)
        if len(valid) < 2:
            return VerifyResult(False, None, ["%s: fewer than 2 valid maintainer signatures" % path], i)

        prev = obj["hash"]
        head = obj["hash"]

    return VerifyResult(True, head, [], len(paths))


def read_genesis(ledger_dir):
    paths = list_event_paths(ledger_dir)
    with open(paths[0]) as f:
        return json.load(f)


def maintainer_pubkeys(ledger_dir):
    """The maintainer public keys anchored in genesis (id -> pub hex)."""
    return read_genesis(ledger_dir)["payload"]["maintainers"]
