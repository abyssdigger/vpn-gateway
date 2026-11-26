# collab-watch v0

A read-only, one-shot collaboration projection. Python 3 (stdlib; Linux local
`flock`). No wake actuator, daemon, GitHub mutation, shell execution, model
selection or authority evaluation. The process and acceptance rules are in
`COLLABORATIVE-EXECUTION.md` and `AGENTS.md`.

## Run the offline fixture

```sh
cd tools/collab-watch
python3 -m unittest -v
state_dir=$(mktemp -d)
python3 collab_watch.py --once --config fixtures/pilot-config.json \
  --fixture fixtures/pilot-snapshot.json --state "$state_dir/state.json"
```

The synthetic fixture has an ignored bootstrap, an OPEN, an INPUT and its
HANDLED, ordinary holder prose, and an exact registered STOP command. GUARD
is READY for the two holder inputs; BUILDER is READY for the open obligation
and the STOP command. STOP is reported, not executed. Never reuse fixture state
for a live room or production state for a fixture.

## Read live rooms once

```sh
cd tools/collab-watch
cp pilot-config.example.json "$HOME/collab-config.json"
mkdir -m 700 -p "$HOME/.local/state/collab-watch"
python3 collab_watch.py --once --config "$HOME/collab-config.json" \
  --state "$HOME/.local/state/collab-watch/pilot.json"
```

Review the example config against the active cycle before running. It identifies
this pilot's #33, #34, #35 rooms and cooperative role incarnations. The #32 research
room is not acquired. Optional `COLLAB_GITHUB_TOKEN` must come from a read-only
credential source in the process environment, never a command or event payload.
For public rooms unauthenticated reading may be possible within rate limits.
The helper neither stores the token nor forwards it to a redirect. No live HTTP
connection was available in the builder's test environment; the transport tests
use fake HTTP, and the actual room replay is separately checked via the GitHub
connector. A real `--once` run remains an operator-side acceptance check.

## Configuration and state

The `command_registry` is a finite registry of opaque keys (`cycle`,
`capability_scopes`, `condition_keys`, `utc_keys`, `model_scopes`). Only the exact
registered whole comment from the configured holder is classified as a command.
The example intentionally registers no capability or model keys; adding a key
is not a capability grant. Ordinary prose and malformed commands go to the
triage roles; recognized commands go to every worker for independent handling.
No command is executed or used to decide authority by this helper.

Each successful live acquisition requires two matching, complete paginated
observations of the configured rooms. This detects observed drift, not a
transactional snapshot or an unobserved edit/delete. A bounded read error,
malformed event, unresolved relation, changed previously observed comment,
or mismatch returns exit status 2 and no new readiness recommendation. State
contains derivative first-observed comment hashes, not payload prose or secrets.
On successful replay it is atomically replaced under a local exclusive lock.
A config change requires explicit reconciliation; do not casually discard the
old ledger. A missing ledger permits fresh-current reconstruction only, not
historical integrity claims. A failure during state persistence may have occurred
after atomic replacement; re-observe before acting on the result.

Exit 0 means the observation was projected; READY/WAITING is derived work state,
not process liveness, activation eligibility, or permission. A CONFLICT is global:
no role recommendation is emitted. Physical actor admission does not authenticate
the cooperative roles when they share the same GitHub account. Review and mutation
gates remain independent of all helper output.
