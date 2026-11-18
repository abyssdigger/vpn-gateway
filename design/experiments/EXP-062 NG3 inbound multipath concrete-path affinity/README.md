# EXP-062 — NG3 inbound multipath concrete-path affinity

## Status

PREPARED — evidence pending.

## Historical predecessor

This experiment supersedes the unexecuted historical **EXP-014 — remote-initiated multi-path
flow pinning** as the current evidence vehicle.

EXP-014 correctly identified the problem class, but mixed several questions before NG3 had
separately proved host-boundary return steering and Profile-level stack affinity. EXP-053 and
EXP-061 now let this experiment start at a narrower boundary:

```text
precondition:
    reply has already returned to the managed stack

question:
    when one Profile has multiple simultaneously eligible inbound paths,
    can an established flow remain pinned to the concrete ingress path?
```

The ordinary host is therefore intentionally absent from this topology.

## Technical question

On the target Linux data plane, can one remotely initiated TCP flow:

1. enter a multi-path Profile through its currently secondary concrete path;
2. retain that exact path for replies after ordinary Profile preference changes to another path;
3. fail closed rather than silently migrate to another eligible path if the pinned path becomes
   unusable?

This experiment resolves technical feasibility only. It does **not** decide whether VPN-GATE
should adopt the mechanism. On completion its registry disposition remains
`pending_decision` until the result is discussed.

## Topology

```text
sink-A1 ns
  172.16.1.2/30
       |
       | path A1
       |
stack ns
  A1 172.16.1.1/30
  A2 172.16.2.1/30
  ordinary 192.0.2.1/30
       |                 \
       | path A2          \ ordinary-side test peer
       |                   \
remote-A2 ns               ordinary ns
  172.16.2.2/30             192.0.2.2/30
  10.0.0.2/32
```

Both A1 and A2 are simultaneously present and eligible in one Profile-equivalent routing
table. A1 is a sink: if an established reply is reclassified by current preference and sent
through A1, the TCP exchange fails.

No host-boundary routing/conntrack mechanism participates.

## Phases

### Control

1. Profile table initially prefers A2.
2. Establish a remote-A2 -> ordinary TCP flow and complete one request/reply.
3. Change Profile preference so A1 is preferred.
4. Send another request on the **same TCP connection**.
5. Expected control result: reply follows A1 and the exchange fails.

### Concrete-path affinity

1. Restore A2 as initial Profile preference.
2. On NEW ingress through A2, save a concrete-path connection mark.
3. On return ingress from ordinary side, restore that mark to packet fwmark.
4. A higher-precedence RPDB rule selects an A2-specific guarded return table.
5. Establish a fresh TCP flow and complete one request/reply.
6. Change ordinary Profile preference to A1.
7. Send another request on the same connection.
8. Expected: exchange still succeeds through A2.

### Pinned-path loss

1. Keep the established affinity-marked flow.
2. Make A2 unusable while A1 remains eligible.
3. Send another request on the same connection.
4. Expected: the marked reply does not silently migrate to A1. It fails closed in the
   path-specific guarded lookup.

This last phase tests technical fail-closed capability only. It does not choose product
recovery/failover semantics.

## PASS criteria

All markers must pass:

```text
EXP062_INITIAL_A2_FLOW=PASS
EXP062_CONTROL_PREFERENCE_SWITCH_BREAKS_FLOW=PASS
EXP062_AFFINITY_SURVIVES_PREFERENCE_SWITCH=PASS
EXP062_MARKED_LOOKUP_SELECTS_A2=PASS
EXP062_PINNED_PATH_LOSS_FAILS_CLOSED=PASS
EXP062_RESULT=PASS
```

A PASS means concrete-path affinity is technically feasible on Linux for the tested
multi-path topology. Adoption remains a separate project decision recorded in the registry.
