# collab-watch: legacy v0 and M v1

A read-only, one-shot collaboration projection. Python 3 (stdlib; Linux local
`flock`). No wake actuator, daemon, GitHub mutation, shell execution, model
selection or authority evaluation. The process and acceptance rules are in
`COLLABORATIVE-EXECUTION.md` and `AGENTS.md`.

## Run the legacy v0 offline fixture

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

## Read legacy v0 live rooms once

```sh
cd tools/collab-watch
cp pilot-config.example.json "$HOME/collab-config.json"
mkdir -m 700 -p "$HOME/.local/state/collab-watch"
python3 collab_watch.py --once --config "$HOME/collab-config.json" \
  --state "$HOME/.local/state/collab-watch/pilot.json"
```

Review the example config against the active cycle before running. It identifies
this pilot's current event-room epoch #36, task room #34 and projectholder room #35
with the cooperative role incarnations. Failed predecessor event room #33 is historical
audit evidence and is not acquired by the current config. The #32 research room is not acquired. Optional `COLLAB_GITHUB_TOKEN` must come from a read-only
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
not process liveness, activation eligibility, or permission. For canonical CONFLICT no role recommendation is emitted. In M v1, a
signal-only conflict is diagnostic, not canonical CONFLICT. Physical actor admission does not authenticate
the cooperative roles when they share the same GitHub account. Review and mutation
gates remain independent of all helper output.

## Preview a legacy v0 outgoing event (E2 preflight)

From this directory, call the pure API `preflight.preflight(cfg, snapshots,
actor, body, previous=None)` with the exact outgoing UTF-8 comment text,
configured transport actor ID, freshly acquired complete stable room lists
in the same format as `core.project`, and the prior integrity ledger when
available. It replays the current observation and a private copy with the
candidate appended under a synthetic physical ID. A conflict raises
`core.Conflict`; no send is permitted. An already observed logical ID is
rejected even for identical text: reconcile delivery rather than resend.

A successful return binds the event ID, kind, event room, exact body SHA-256,
config hash, baseline integrity-ledger hash (`observation_sha256`) and
prospective integrity-ledger hash (`prospective_sha256`, excluding only the
synthetic event's physical ref). The prospective hash binds newly referenced
payloads; the exact event body is bound separately. Send only those exact bytes,
under a separate mutation gate, after fresh acquisition; repeat the preview
if the relevant observation, config or candidate changes. Valid known-stale
claims follow canonical replay semantics; PASS is not a READY recommendation. This API neither acquires
rooms nor saves state nor sends anything. It cannot prevent an intervening
remote change between preview and send, establish transport identity or
authorize publication. Re-read the actual remote comment and reconcile any
ambiguous delivery; never blindly retry. A missing ledger still permits only
fresh-current reconstruction, not a historical integrity assertion.

Run `python3 -m unittest -v test_preflight` for the offline acceptance tests.

## M v1: journal and signals (offline acceptance; cutover pending)

The M path is selected only by the explicit configuration field
`"protocol": "vpng-collab/1"`. The v0 format has no protocol field and is
not reinterpreted. Unknown or mixed formats fail closed. M uses a durable
journal in the configured task rooms, exact holder inputs, and a separate
ephemeral signal room. Missing, duplicated or quarantined signals do not
change the canonical projection. The helper never sends or deletes comments.

Run the separate synthetic offline fixture, not a live pilot:

```sh
state_dir=$(mktemp -d)
python3 collab_watch.py --once --config fixtures/m1-config.json \
  --fixture fixtures/m1-snapshot.json --state "$state_dir/state.json"
```

The fixture has an OPEN, an INPUT, its exact HANDLED receipt, a consumed
signal and ordinary holder prose. The open obligation remains READY despite
receipt/GC eligibility. Removing the signal from the fixture and replaying
with the same state leaves the semantic projection unchanged.

V1 retained state has exactly `protocol`, `semantic_config_hash` and
`ledger`. The hash covers all semantic configuration including journal epoch,
roles/incarnations, holder routing, task rooms, repository and command registry.
Only the transport signal room is excluded; rotating it preserves this state.
Changes to semantic configuration require a new, explicitly reconciled journal
epoch. The ledger binds canonical physical comments only, never signals.
Legacy and M state files are not interchangeable. A lost ledger cannot prove
historical integrity. The complete double-scan acquisition still includes every
configured room and current signal observation; direct live HTTP was not
available in the builder test environment.

### M outgoing preflight

Pure APIs in `preflight_m.py`:

- `preflight_journal_fact(cfg, snapshots, actor, body, previous=None)`
  validates the exact reserved journal frame against prospective semantic replay.
  It returns exact candidate body, journal epoch, task room, semantic config,
  baseline-state and prospective-state hashes. It excludes only the synthetic
  fact's physical ref from the prospective hash.
- `preflight_signal(cfg, snapshots, actor, body, previous=None)` validates a
  signal referencing an already physically admitted journal fact. It binds
  the target ref/digest, recipient, body, canonical state, full transport config
  and normalized current signal observations (including quarantined rows).
  It must not change semantic projection or retained state.

Both reject already observed outgoing logical IDs; reconcile ambiguous sends
instead of replaying them. Publication order: journal preflight, actual journal
publication under the mutation gate, remote verification and admission, then
optional signal preflight, publication under the gate and remote verification.
Do not preview a signal against a synthetic not-yet-published journal fact.
Repeat preflight if relevant bindings change. This is not atomic remote
publication or authorization. No API acquires, persists, sends, wakes, or
deletes anything. GC candidates are evidence only; actual GitHub deletion is
not authorized by the M process decision. No live M cutover is claimed here.
