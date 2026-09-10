"""Reputation-weighted voting with quorum, and decision recording.

A proposal passes iff:
  * quorum is met: the reputation that participated is at least ``quorum``
    (a fraction, default 0.5) of the total reputation in the electorate, and
  * approval wins: the reputation weight of "approve" votes strictly exceeds the
    weight of "reject" votes.

A passing vote records exactly one `decision` event on the ledger (2-of-3
maintainer signatures), embedding the proposal so a node can decompose it.
"""

from . import ledger as L


def tally(proposal, votes, reputation, quorum=0.5):
    """Compute the outcome. ``votes`` maps voter_id -> 'approve'|'reject'
    (others ignored). ``reputation`` maps voter_id -> points. Returns a dict."""
    total_rep = sum(max(0, r) for r in reputation.values())
    approve = 0
    reject = 0
    for voter, choice in votes.items():
        w = max(0, reputation.get(voter, 0))
        if choice == "approve":
            approve += w
        elif choice == "reject":
            reject += w
    participating = approve + reject
    quorum_met = total_rep > 0 and (participating / total_rep) >= quorum
    approved = quorum_met and approve > reject
    return {
        "proposal_id": proposal["id"],
        "total_reputation": total_rep,
        "participating_reputation": participating,
        "approve_weight": approve,
        "reject_weight": reject,
        "quorum": quorum,
        "quorum_met": quorum_met,
        "approved": approved,
    }


def record_decision(ledger_dir, proposal, result, signers, timestamp):
    """Append exactly one `decision` event capturing the passing vote. The
    proposal (with its task breakdown) travels in the payload so the node can
    decompose it without re-reading anything."""
    payload = {
        "proposal": proposal,
        "result": result,
        "outcome": "approved",
    }
    return L.append_event(ledger_dir, "decision", payload, signers, timestamp)
