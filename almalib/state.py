"""StateRoot, constitution extraction, and signed knowledge objects."""

import json
import os

from .canon import canon, canon_bytes, sha256_hex, sha256_file
from . import keys as K
from . import ledger as L


# ---------------------------------------------------------------------------
# Constitution: the canonical text of CLAUDE.md section 1.
# ---------------------------------------------------------------------------

def extract_constitution(claude_md_text):
    """Extract the section 1 block from CLAUDE.md.

    Section boundaries are the top-level markers ``## S1`` ... up to the next
    ``## S2`` marker (written with the section sign in the file). The returned
    text is the block including its heading, stripped of surrounding blank lines
    and normalized to end with a single newline.
    """
    lines = claude_md_text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if start is None and stripped.startswith("## §1"):
            start = i
            continue
        if start is not None and stripped.startswith("## §2"):
            end = i
            break
    if start is None:
        raise ValueError("CLAUDE.md: could not find section 1 (## §1 ...)")
    block = "\n".join(lines[start:end]).strip("\n")
    return block + "\n"


# ---------------------------------------------------------------------------
# StateRoot: a signed snapshot binding the identity together.
# ---------------------------------------------------------------------------

def _sr_content(root):
    return {k: v for k, v in root.items() if k not in ("hash", "signatures")}


def build_state_root(root_dir, ledger_head_hash, timestamp):
    """Build (unsigned) a StateRoot referencing the constitution, the system
    prompt, and the current ledger head."""
    const_path = "constitution.md"
    sp_path = os.path.join("behavior-spec", "system-prompt.md")
    root = {
        "type": "state_root",
        "collective": "Alma",
        "timestamp": timestamp,
        "constitution_path": const_path,
        "constitution_hash": sha256_file(os.path.join(root_dir, const_path)),
        "system_prompt_path": sp_path,
        "system_prompt_hash": sha256_file(os.path.join(root_dir, sp_path)),
        "ledger_head_hash": ledger_head_hash,
    }
    root["hash"] = sha256_hex(canon_bytes(_sr_content(root)))
    root["signatures"] = []
    return root


def sign_state_root(root, signers):
    for key_id, priv in signers:
        root["signatures"].append({"key_id": key_id, "sig": K.sign_hex(priv, root["hash"])})
    root["signatures"].sort(key=lambda s: s["key_id"])
    return root


def state_root_path(root_dir):
    return os.path.join(root_dir, "state", "StateRoot.json")


def write_state_root(root_dir, root):
    path = state_root_path(root_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(canon_bytes(root))
    return path


def read_state_root(root_dir):
    with open(state_root_path(root_dir), "rb") as f:
        raw = f.read()
    return json.loads(raw), raw


def verify_state_root(root_dir, ledger_dir=None):
    """Verify the StateRoot: canonical bytes, hash, constitution binding, ledger
    head binding, and 2-of-3 maintainer signatures. Returns (ok, errors)."""
    errors = []
    try:
        root, raw = read_state_root(root_dir)
    except FileNotFoundError:
        return False, ["StateRoot.json not found"]

    if canon_bytes(root) != raw:
        return False, ["StateRoot is not in canonical form (tampered)"]

    if sha256_hex(canon_bytes(_sr_content(root))) != root.get("hash"):
        errors.append("StateRoot hash does not match content")

    const_path = os.path.join(root_dir, root.get("constitution_path", ""))
    if not os.path.exists(const_path):
        errors.append("StateRoot references a missing constitution")
    elif sha256_file(const_path) != root.get("constitution_hash"):
        errors.append("constitution hash does not match constitution.md")

    if ledger_dir is None:
        ledger_dir = os.path.join(root_dir, "ledger")
    lv = L.verify_chain(ledger_dir)
    if not lv.ok:
        errors.append("ledger does not verify: %s" % (lv.errors[0] if lv.errors else "?"))
    elif root.get("ledger_head_hash") != lv.head_hash:
        errors.append("StateRoot ledger_head_hash does not match verified head")

    maintainers = L.maintainer_pubkeys(ledger_dir)
    valid = set()
    for s in root.get("signatures", []):
        kid = s.get("key_id")
        pub = maintainers.get(kid)
        if pub and kid not in valid and K.verify_hex(pub, s.get("sig", ""), root["hash"]):
            valid.add(kid)
    if len(valid) < 2:
        errors.append("StateRoot has fewer than 2 valid maintainer signatures")

    return (len(errors) == 0), errors


# ---------------------------------------------------------------------------
# Knowledge objects: enter state/knowledge/ only with the owner's signature.
# ---------------------------------------------------------------------------

def knowledge_signing_bytes(obj):
    """The exact bytes an owner signs to admit a knowledge object: the canonical
    form of the object's content (everything except owner_pub/owner_sig)."""
    content = {k: v for k, v in obj.items() if k not in ("owner_pub", "owner_sig")}
    return canon(content)


def verify_knowledge(obj):
    """A knowledge object is admissible iff it carries the owner's public key and
    a valid signature by that key over its content."""
    pub = obj.get("owner_pub")
    sig = obj.get("owner_sig")
    if not pub or not sig:
        return False
    return K.verify_hex(pub, sig, knowledge_signing_bytes(obj))


def sign_knowledge(obj, owner_priv):
    """Attach owner_pub + owner_sig to a knowledge object and return it."""
    obj = dict(obj)
    obj.pop("owner_pub", None)
    obj.pop("owner_sig", None)
    obj["owner_pub"] = K.pub_hex(owner_priv)
    obj["owner_sig"] = K.sign_hex(owner_priv, knowledge_signing_bytes(obj))
    return obj


def admit_knowledge(root_dir, obj):
    """Write a knowledge object into state/knowledge/ ONLY if its owner signature
    verifies. The object must already carry an ``id`` (part of the signed
    content). Returns the path written, or None if rejected."""
    if not verify_knowledge(obj):
        return None
    kid = obj.get("id")
    if not kid:
        return None
    kdir = os.path.join(root_dir, "state", "knowledge")
    os.makedirs(kdir, exist_ok=True)
    path = os.path.join(kdir, "%s.json" % kid)
    with open(path, "wb") as f:
        f.write(canon_bytes(obj))
    return path
