"""Bounded remote-read/local-checkpoint runtime composition; no execution policy."""
from __future__ import annotations

from core import require
from split_journal import validate_v2_config
from v2_acquisition import acquire_aggregate_v2
from v2_runtime_state import RuntimeStateStore
from v2_scheduler import project_scheduler


def run_once(cfg, bindings, runtime_model, store, *, history_mode, selected_role=None,
             read_token=None, read_opener=None):
    """Commit the exact accepted replay before returning its selected-role view.

    No fallback, reset, remote mutation, clock, command or authority evaluation.
    The trusted caller pins the already-open store identity externally.
    """
    validate_v2_config(cfg)
    require(type(store) is RuntimeStateStore
            and store._repository == cfg["repository"].lower()
            and store._epoch == cfg["journal_epoch"], "runtime checkpoint scope mismatch")
    require(type(history_mode) is str and history_mode in ("retained", "fresh-current"),
            "explicit runtime history mode required")
    checkpoint = store.load()
    if history_mode == "retained":
        require(checkpoint is not None, "retained runtime requires checkpoint")
        previous, generation = checkpoint["state"], checkpoint["generation"]
        label = "retained"
    else:
        require(checkpoint is None, "fresh-current requires empty checkpoint")
        previous, generation = None, 0
        label = "fresh-current-only"

    observation = acquire_aggregate_v2(cfg, token=read_token, opener=read_opener)
    view, state = project_scheduler(cfg, observation, previous, bindings, runtime_model,
                                    selected_role=selected_role)
    # No DB transaction is held across the remote reads. CAS makes a competing
    # checkpoint commit fail; never return a view for a failed/uncertain save.
    committed = store.save(state, generation)
    return {"history": label, "view": view,
            "checkpoint": {"generation": committed["generation"],
                           "state_sha256": committed["state_sha256"]}}
