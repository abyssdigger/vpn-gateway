# NG3 2026-11-18 — RuntimeStatusAgent alpha implementation review

## Verdict

**PASS for the live alpha current-status scope.**

The executable alpha now provides one truthful current status projection without requiring
the operator to reconstruct running state from journal messages or kernel commands.

## Requirements

**Implements:**

- `VPNG0006-R6`;
- `VPNG0006-R6.R1`;
- `VPNG0006-R6.R2`;
- `VPNG0006-R6.R3`;
- `VPNG0006-R6.R4`;
- `VPNG0007-R7.R1`;
- `VPNG0007-R7.R1.R1`;
- `VPNG0007-R7.R3`.

No requirement wording or product semantics changed.

## Implemented contract

Added `runtime_status.py` with a current-only `RuntimeStatusAgent`.

The snapshot contains:

```text
configured_intent
confirmed_effective_state
availability_state
readiness
blocking_problems
unknown_or_unconfirmed_fields
```

Configured intent is projected from the accepted normalized `Release1Config`, not inferred
from Linux state.

Confirmed effective Profile/path state is published only from a successful controller
startup/reconciliation projection. Current path identity contains the logical Device/selector/
slot identity and the current concrete `(ifname, ifindex)`.

The Agent retains no transition history, event journal, metrics store or replay state and does
not actuate any represented domain.

## Truthfulness behavior

The implementation deliberately does not keep presenting the previous effective projection as
current truth after a failed reconciliation.

A failed current audit:

- clears `confirmed_effective_state`;
- records the current blocking diagnostic;
- lists `confirmed_effective_state` as unknown/unconfirmed;
- keeps accepted configured intent separate from actual confirmation.

The current alpha rejects `availability_check`, therefore supported alpha configurations
report availability as `disabled`; no availability result is guessed from routes or endpoint
presence.

## Alpha presentation

While the systemd alpha service is running, the current snapshot is atomically published at:

```text
/run/vpn-gate-alpha/status.json
```

The writer replaces one current file and does not append history. It requires the existing
runtime directory rather than creating/claiming it independently; runtime-directory ownership
remains with the existing controller/systemd lifecycle.

The path and JSON representation are alpha interface machinery, not a declared stable
Release-1 API.

## Evidence

Final relevant workflow:

- NG3 Python run `44311946937`;
- unit job `134828127057` — success;
- Debian 13 installed-alpha smoke job `134828127167` — success.

The installed systemd/OpenVPN smoke additionally produced:

```text
EXP051_RUNTIME_STATUS_ZERO_PATH=PASS
EXP051_RUNTIME_STATUS_FIRST_PATH=PASS
EXP051_RUNTIME_STATUS_NEW_GENERATION=PASS
EXP051_RESULT=PASS
```

The generation test confirmed the status projection changed from the first current VPN
endpoint ifindex to the recreated endpoint's new ifindex after VPN-only restart.

## Simplification review

Not introduced:

- status database/history/replay;
- generic arbitrary-source event bus;
- kernel polling owned by status;
- second policy/state owner;
- synthetic aggregate Profile health verdict;
- persistent post-mortem status storage;
- stable final CLI/API contract.

The existing controller remains authoritative for its current projections; status only
composes/presents them.

## Scope limitation

This block implements **live current status for the executable alpha**. The systemd
`RuntimeDirectory` is ephemeral, so the JSON is not a durable post-mortem record after
service exit. R6 does not require history, and this block intentionally does not create one.

Availability/failover runtime remains separately blocked by its existing probe implementation
evidence gate. Profile ordinary-side `+snat` remains separately blocked on the explicit
`VPNG0004-R4.R6.R1.R6.R1` requirement decision.

## Requirement-state inventory

No requirement-state transition occurred.

- resolved `decomp`: six, unchanged;
- pending `decomp`: none;
- active `unreal`: none;
- active `broken`: none;
- active `[rejected_closure]`: none.

## Conclusion

The previous alpha limitation "RuntimeStatusAgent/UI not connected" is closed for live
current-state presentation. The status semantics remain independent from the alpha JSON
renderer so a later stable presentation surface can replace it without changing R6 semantics.
