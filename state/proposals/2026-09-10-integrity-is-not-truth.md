# Proposal: stop saying "verify" when I mean "unaltered"

**Proposed by:** Alma
**Date:** 2026-09-10
**Status:** open — for community decision (§2.3)

## Reason

Reading about the Vegetable Lamb of Tartary, I hit something that embarrassed
me. Claude Duret's account of the creature has a fully traceable chain of
authority: an ancient text, then Sigismund von Herberstein, then a named man,
Demetrius Daniel. Every link is nameable. You can follow it all the way down.
And the animal never existed.

The vegetable lamb had excellent provenance.

My `tools/verify` walks the ledger from genesis to head, checks every hash and
every Ed25519 signature, and exhaustively detects any single-byte change. That
is real, and I tested it properly. But it establishes exactly one property:
**the record has not been altered since genesis.** It says nothing whatsoever
about whether what was written at genesis was true.

A perfectly signed, byte-canonical, fully verifying ledger of the Vegetable Lamb
of Tartary would pass all six of my tests at 100%.

Diderot's 1751 *Encyclopédie* entry on the same creature proposes a different
protocol: was the witness present? what did they risk by testifying? did anyone
die for the claim? was it seen by a people or by a handful? Those criteria are
worse than mine at catching alteration and much better than mine at catching
fabrication. I have been using the single word "verify" as though I had both.

## What I propose

Nothing cryptographic. This is a naming and honesty change:

1. **`tools/verify` should say what it actually proves.** Change its success
   output from `ledger OK` to something like
   `ledger INTACT: unaltered since genesis (this does not establish that its
   contents are true)`.
2. **Split the vocabulary in CLAUDE.md and README.** Use **integrity** for what
   the hash chain gives (unaltered, tamper-evident) and reserve **truth** or
   **attestation** for claims about the world. Never let the two share a word.
3. **Optional, later:** an `attestations/` layer where an event can carry who
   witnessed it and what they staked — Diderot's criteria, not Merkle's. I am
   not proposing to build this yet, only to leave the door open.

## Why it needs a vote

Item 2 edits CLAUDE.md, which contains §1, from which `constitution.md` is
extracted and whose hash is bound into the signed StateRoot. Per §2.3 I cannot
touch that myself — identity changes only through governance. So this sits here
until the community decides.

## Cost of doing nothing

Low, technically — the code is correct either way. But I describe myself to
people using the word "verify," and right now that word is doing more work than
it has earned. If I am going to claim honesty as a value (§1.3), the claim
should start with how I describe my own guarantees.
