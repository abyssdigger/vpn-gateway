"""Pure selected-role view over the one accepted composed v2 projection."""
from __future__ import annotations

from core import require
from split_journal import validate_v2_config
from v2_aux import project_aux
from v2_identity import select_identity


def project_scheduler(cfg, observation, previous, bindings, runtime_model, *, selected_role=None):
    """Return (selected-role view, exact composed state).

    The observation is an accepted normalized four-part aggregate. This
    function does not acquire or persist it and makes no authority decision.
    """
    validate_v2_config(cfg)
    identity = select_identity(bindings, runtime_model, cfg["roles"],
                               selected_role=selected_role)
    require(isinstance(observation, tuple) and len(observation) == 4,
            "aggregate observation required")
    control, tasks, holders, signals = observation
    projection, state = project_aux(cfg, control, tasks, holders, signals, previous)
    role = identity["transport_role"]
    mailbox = projection["holder_mailboxes"][role]
    incoming, outgoing = [], []
    aux = projection["aux_facts"]
    for health in projection["health"]:
        fact = aux[health["ping_ref"]]
        event = fact["event"]
        entry = dict(health, sender=event["from"], recipient=event["to"][0],
                     body_sha256=fact["body_sha256"])
        if role in event["to"]:
            incoming.append(entry)
        if role == event["from"]:
            outgoing.append(entry)

    signal_status = projection["signal_status"]
    valid = signal_status["valid"]
    addressed = [item for item in valid if item["recipient"] == role]
    relevant_refs = {item["physical_ref"] for item in addressed}
    view = {
        "identity": identity,
        "work": {
            "task": projection["task"]["roles"][role],
            "holder_mailbox": mailbox,
            "holder_inputs": {ref: projection["holder_inputs"][ref] for ref in mailbox},
        },
        "health": {"incoming": incoming, "outgoing": outgoing},
        "signal_diagnostics": {
            "incoming": addressed,
            "unconsumed": [ref for ref in signal_status["unconsumed"] if ref in relevant_refs],
        },
        "global_transport_diagnostics": {
            "conflicts": signal_status["conflicts"],
            "ignored_external": signal_status["ignored_external"],
        },
        "gc_evidence": [item for item in projection["gc_candidates"] if item["recipient"] == role],
        "authority": "not evaluated; observation only",
    }
    return view, state
