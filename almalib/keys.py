"""Ed25519 keys: generation, loading, signing, verification.

Keys are stored as raw 32-byte values encoded in hex:
  <id>.key  -- private seed (keep secret; the test keys are intentionally public)
  <id>.pub  -- public key

Trust is anchored in the ledger's genesis event, not in the key files: the
verifier reads the maintainers' public keys from genesis and checks every
signature against those. The key files exist so tools can *produce* signatures.
"""

import os

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


def generate():
    """Generate a fresh Ed25519 private key."""
    return Ed25519PrivateKey.generate()


def priv_from_hex(seed_hex):
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))


def pub_from_hex(pub_hex):
    return Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))


def priv_hex(priv):
    return priv.private_bytes_raw().hex()


def pub_hex(priv):
    return priv.public_key().public_bytes_raw().hex()


def sign_hex(priv, message):
    """Sign ``message`` (str or bytes), returning a hex signature."""
    if isinstance(message, str):
        message = message.encode("utf-8")
    return priv.sign(message).hex()


def verify_hex(pub_hex_str, sig_hex, message):
    """Return True iff ``sig_hex`` is a valid signature of ``message`` by the
    public key ``pub_hex_str``. Never raises."""
    if isinstance(message, str):
        message = message.encode("utf-8")
    try:
        pub_from_hex(pub_hex_str).verify(bytes.fromhex(sig_hex), message)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Keyring helpers (file-backed)
# ---------------------------------------------------------------------------

def write_keypair(keys_dir, key_id):
    """Create <key_id>.key / <key_id>.pub in keys_dir if absent. Returns the
    private key object either way."""
    os.makedirs(keys_dir, exist_ok=True)
    priv_path = os.path.join(keys_dir, key_id + ".key")
    pub_path = os.path.join(keys_dir, key_id + ".pub")
    if os.path.exists(priv_path):
        return load_priv(keys_dir, key_id)
    priv = generate()
    with open(priv_path, "w") as f:
        f.write(priv_hex(priv))
    with open(pub_path, "w") as f:
        f.write(pub_hex(priv))
    return priv


def load_priv(keys_dir, key_id):
    with open(os.path.join(keys_dir, key_id + ".key")) as f:
        return priv_from_hex(f.read().strip())


def load_pub(keys_dir, key_id):
    with open(os.path.join(keys_dir, key_id + ".pub")) as f:
        return f.read().strip()
