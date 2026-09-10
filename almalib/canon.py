"""Canonical JSON serialization and hashing.

The whole integrity story rests on one invariant: for any object we persist,
there is exactly ONE byte string that represents it. We call that the canonical
form. Files are written as their canonical form and never any other way; the
verifier re-derives the canonical form from the parsed object and requires it to
equal the bytes on disk. That single check turns "flip any byte" into "produce a
non-canonical file", which is always detectable -- structural bytes and
insignificant whitespace included.
"""

import hashlib
import json


def canon(obj):
    """Return the canonical JSON *string* for ``obj``.

    Deterministic: keys sorted, no insignificant whitespace, all non-ASCII
    escaped. json.loads(canon(x)) round-trips back to an object whose canon() is
    byte-identical, so re-serialization is a fixed point.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canon_bytes(obj):
    """Canonical form as UTF-8 bytes (what we write to disk)."""
    return canon(obj).encode("utf-8")


def sha256_hex(data):
    """SHA-256 hex digest of a str (utf-8) or bytes."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    """SHA-256 hex digest of a file's raw bytes."""
    with open(path, "rb") as f:
        return sha256_hex(f.read())
