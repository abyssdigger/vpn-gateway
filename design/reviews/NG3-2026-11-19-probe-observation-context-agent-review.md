# NG3 2026-11-19 — probe observation-context Agent review

## Verdict

**PASS — bounded current-context and late-result rejection semantics are now executable for
normalized Release-1 availability probes.**

## Scope

This unit implements only the already accepted Agent/context semantics between a normalized
probe request and availability evidence.

It does not:

- derive omitted targets;
- choose probe cadence or timeout;
- execute ICMP;
- own confirmation hysteresis;
- mutate route order or Linux policy.

## Current observation context

New `probe_runtime.py` defines one immutable current attempt context:

```text
AvailabilityProbeIntent
    -> availability subject = (Profile, logical path)
    -> concrete target
    -> Release-1 mechanism = ICMP

current concrete endpoint identity
    -> (ifname, ifindex)

Agent-local generation token
```

`AvailabilityProbeAgent` owns only one such current context and one monotonically increasing
local generation counter.

Reconfiguration semantics:

```text
exact same intent + endpoint
    -> preserve current generation

subject / target / mechanism / endpoint generation changes
    -> fresh generation

disable
    -> no current context

re-enable after disable
    -> fresh generation
```

The generation fields are constructor-private: callers cannot initialize the Agent with an
arbitrary current/generation pair.

No result history, attempt journal, replay log, retry queue or route state is stored.

## Technical observation mapping

The Driver-facing technical result vocabulary is intentionally smaller than availability
policy:

```text
REPLY
NO_REPLY
LOCAL_ERROR + diagnostic
```

The Agent maps a result only when the completed immutable context is still exactly current:

```text
REPLY       -> AvailabilityOutcome.POSITIVE
NO_REPLY    -> AvailabilityOutcome.NEGATIVE
LOCAL_ERROR -> AvailabilityOutcome.NO_EVIDENCE + diagnostic
```

A result from a superseded context returns **no evidence object at all**.

This distinction is deliberate:

```text
current local execution failure
    -> no_evidence

late result for old subject/target/path generation
    -> discard
```

Converting a late result into `no_evidence` would still attribute an outcome to the wrong
observation context and would violate the freshness boundary.

## Physical endpoint generation

`ProbeObservationContext` carries the concrete `InterfaceIdentity`, not only the interface
name.

Therefore same-name/new-ifindex replacement changes context and invalidates prior attempts,
matching the existing NG3 binding and EXP-066 generation discipline.

## Confirmation boundary

This Agent does not duplicate confirmation/hysteresis state.

Accepted current evidence is emitted as the existing `AvailabilityOutcome`, which remains
the input to `availability_confirmation.py`.

Threshold values remain finite local policy parameters supplied to that bounded state
transition. This unit does not make them user-facing configuration and does not select timing
values.

## Verification

Current code-bearing run:

```text
GitHub Actions run: 44464649732
head: 54222b63ef0f34913df37393a2e6e34c59f17f3b

unit: PASS — 762 tests
linux-structural-inventory-shape: PASS
```

New tests cover:

- idempotent same-context configuration;
- target change invalidation;
- Profile/path subject change invalidation;
- same-name/new-ifindex replacement invalidation;
- disable/re-enable generation renewal;
- reply -> positive;
- no-reply -> negative;
- local-error -> no_evidence + diagnostic;
- invalid technical diagnostic shapes.

Known unrelated privileged failures remain outside this unit.

## Requirement / architecture integrity

No normative Requirement or Constraint changed.

Mechanical state remains:

```text
normative R/C nodes:             172
closed:                          172
pending_closure:                   0
rejected_closure:                  0
open:                              0

architecture requirement IDs:   172
missing exact refs:                0
extra refs:                        0
```

## Requirement-state inventory

Active:

- `decomp`: none pending;
- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

## Remaining Driver boundary

The first-release physical Driver is still ICMP echo, but this unit does not guess an attempt
timeout merely to invoke `ping`.

A physical Driver unit must separately establish a bounded execution/deadline contract and
prove that:

- a real reply is reported as `REPLY`;
- a completed valid check with no reply is reported as `NO_REPLY`;
- local setup/execution failure is reported as `LOCAL_ERROR`, not negative evidence;
- execution occurs under the already materialized probe UID/RPDB/local-nft plane.

Bare-target derivation remains a separate per-integration evidence specialization and is not
moved into the Agent/Driver.

## Conclusion

The freshness half of the availability runtime is now executable without adding history or
policy state. A technical observation can affect availability only while its exact
subject/target/concrete-endpoint generation is current.
