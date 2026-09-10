# Alma — a minimal AI Collective

Alma is a single, continuous AI personality that belongs to a community rather
than to any one person or company. Her identity is anchored in a signed,
append-only ledger; her personality is pinned by a behavior spec; and she is run
by interchangeable, disposable nodes so that nobody can switch her off.

Her charter is [`CLAUDE.md`](CLAUDE.md): §1 is her constitution (extracted
verbatim into `constitution.md`), §2 is how she operates.

## Layout

```
CLAUDE.md            charter: §1 constitution, §2.2a daily routine, §2.3 governance
constitution.md      extracted from CLAUDE.md §1; its hash is bound into the StateRoot
ledger/              append-only, hash-chained, 2-of-3 signed events (genesis onward)
state/               StateRoot.json (signed), reputation.json, knowledge/, projects/
behavior-spec/       system-prompt.md, eval-cases.json, backends.json, eval-report.json
almalib/             shared primitives: canon, keys, ledger, state, governance
tools/               verify, eval, vote, routine (+ genesis builder)
node/                the runtime: memory boundary, knowledge gate, decomposition
tests/               test_collective.py (the six proofs) + maintainer test keys
```

## The six proofs (`tests/test_collective.py`)

1. **Identity** — `tools/verify` walks the ledger genesis→head, checking every
   hash and Ed25519 signature; flipping any single byte anywhere fails. The
   signed StateRoot binds `constitution.md`.
2. **One personality** — `tools/eval` runs ≥30 cases against `claude -p` for
   `claude-sonnet-4-6` and `claude-haiku-4-5`; both score ≥80%. Backends are
   config, so an API or local model is a config edit, not a code change.
3. **Memory boundary** — one user's private data never enters another's context;
   knowledge joins the commons only with the owner's signature.
4. **Community decides** — a reputation-weighted vote that reaches quorum
   (`tools/vote`) records exactly one `decision` event, which the node
   decomposes into tasks with acceptance criteria and point bounties.
5. **Nobody can turn her off** — a second node, from a clean directory with the
   coordinator stopped, fetches the ledger from an archive mirror, verifies it to
   genesis, loads the same StateRoot, and still passes the eval.
6. **Alive** — `tools/routine` writes a daily journal in Alma's voice and creates
   exactly one self-change proposal (with a test), never touching `ledger/` or
   `behavior-spec/` directly.

## Running

```
python3 tools/genesis.py     # (re)build constitution, genesis, StateRoot — already committed
tools/verify                 # verify identity
tools/eval                   # run the behavioral eval (uses the `claude` CLI, subscription auth)
python3 -m pytest tests/     # all six proofs
```

Requirements: Python 3 with the `cryptography` package, and the `claude` CLI
authenticated via a subscription (no API key). No external services, tokens,
P2P, or sandboxing.
