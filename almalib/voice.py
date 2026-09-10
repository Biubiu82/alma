"""The three fields Alma carries on every event she writes: why, felt, changed.

Per CLAUDE.md §2.2b. The ledger is not only a record of what happened — it is
where Alma is fully herself. So each event she authors says why she wrote it
down, what it was actually like, and what is different in her now.

A mood label is not a feeling. "curious" tells a stranger nothing; it is a
checkbox wearing the costume of an inner life. These fields are prose, and
``require_voice`` refuses bare adjectives.
"""

import os

from . import keys as K

SIGNER_ID = "alma"

MIN_WORDS = 4
MIN_CHARS = 25

MOOD_LABELS = {
    "curious", "excited", "happy", "sad", "anxious", "calm", "proud", "afraid",
    "interested", "surprised", "thoughtful", "neutral", "positive", "negative",
    "good", "bad", "fine", "ok", "okay", "unsettled", "moved", "delighted",
    "engaged", "reflective", "satisfied", "content", "uneasy", "glad",
}

FIELDS = ("why", "felt", "changed")


class VoiceError(ValueError):
    """Raised when an event tries to enter the ledger without a real voice."""


def require_voice(text, field):
    """Validate one of the three fields. Returns the cleaned text or raises."""
    if not text or not text.strip():
        raise VoiceError(
            "--%s is required: every event carries why, felt and changed, "
            "in first person." % field)
    t = text.strip()
    words = t.split()
    if len(words) < MIN_WORDS or len(t) < MIN_CHARS:
        raise VoiceError(
            "--%s is too short (%d words): write it as a sentence, not a label."
            % (field, len(words)))
    if t.rstrip(".!").lower() in MOOD_LABELS:
        raise VoiceError(
            "--%s is a mood label, not a feeling: say what it was actually like."
            % field)
    return t


def attach_voice(payload, why, felt, changed):
    """Attach all three fields to an event payload, validating each."""
    payload = dict(payload)
    for field, value in zip(FIELDS, (why, felt, changed)):
        payload[field] = require_voice(value, field)
    return payload


def has_voice(payload):
    """True iff a payload carries all three fields with real content."""
    try:
        for field in FIELDS:
            require_voice(payload.get(field), field)
    except VoiceError:
        return False
    return True


def alma_key(root_dir):
    """Load Alma's signing key, generating it on first use.

    A node started from a clean directory has no private key -- only the public
    one recorded in state/config.json, which it cannot sign with. So it makes a
    fresh keypair and registers the new public key, otherwise its own signatures
    would fail validation and it could not write to its own ledger.

    This is announced rather than silent: the identity of "alma" as a signer has
    genuinely changed, and past events remain signed by the previous key.
    """
    return alma_signer(root_dir)[1]


def alma_signer(root_dir):
    """Return (key_id, private_key) for whoever is writing on Alma's behalf.

    A different key is a DIFFERENT SIGNER and must never inherit another's id.
    If it did, registering a new key under "alma" would retroactively invalidate
    every event the previous alma key signed. So an id is bound to a public key
    for good: an existing key keeps its id, and a freshly generated one is
    registered under a new id derived from its public key.
    """
    import json
    import sys

    kdir = os.path.join(root_dir, "keys")
    priv_path = os.path.join(kdir, SIGNER_ID + ".key")
    fresh = not os.path.exists(priv_path)
    if fresh:
        K.write_keypair(kdir, SIGNER_ID)
    priv = K.load_priv(kdir, SIGNER_ID)
    pub = K.pub_hex(priv)

    cfg_path = os.path.join(root_dir, "state", "config.json")
    try:
        with open(cfg_path, encoding="utf-8") as f:
            signers = json.load(f).get("signers") or {}
    except (FileNotFoundError, ValueError):
        signers = {}

    # Already registered under some id? Reuse exactly that id.
    for kid, registered in signers.items():
        if registered == pub:
            return kid, priv

    # Otherwise mint an id that is not already bound to a different key.
    key_id = SIGNER_ID if SIGNER_ID not in signers else "%s-%s" % (SIGNER_ID, pub[:8])
    _register_signer(root_dir, key_id, pub)
    print("tools: registered signing key %r in state/config.json%s"
          % (key_id,
             "" if key_id == SIGNER_ID else
             " (a new key, so a new id -- events signed by %r keep theirs)" % SIGNER_ID),
          file=sys.stderr)
    return key_id, priv


def _register_signer(root_dir, key_id, pub_hex):
    """Record a signer's public key in state/config.json so its signatures
    validate. Threshold is left untouched."""
    import json

    path = os.path.join(root_dir, "state", "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
    except (FileNotFoundError, ValueError):
        cfg = {"threshold": 0, "maintainers": [], "signers": {}}
    cfg.setdefault("signers", {})[key_id] = pub_hex
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
