# VPN-GATE NG3 — host bootstrap and return-steering review

**Date:** 2026-11-18  
**Cycle branch:** `ng3-design-cycle-20261118-host-return-steering-35m`  
**Draft PR:** #22

## Scope

This cycle started from the host-routing responsibility gap created by the managed network
isolation boundary:

- ordinary-side initiated traffic still needs host bootstrap routing into VPN-GATE;
- remote-initiated traffic should not require duplicate host routes solely for its return leg
  if Linux can preserve the managed-boundary flow association;
- host route ownership should remain conventional VPN-style narrow ownership, not a general
  host routing supervisor;
- if stateful return steering is accepted, the Profile must have an explicit route-based
  opt-out rather than an implicit global dependency.

The cycle first gated the Linux mechanism with EXP-053 and only then changed requirements,
grammar, architecture and executable reference code.

## Verdict

**PASS for the bounded cycle scope.**

EXP-053 proves both forwarded and host-local return steering through the managed boundary
without a remote-prefix route in the host main table.

The resulting accepted split is:

```text
outbound
    -> bootstrap host route required

inbound
    -> stateful host return steering by default
    -> no remote-prefix host route required only for the return leg

bidirectional
    -> bootstrap route required for ordinary-side initiation
    -> remote-initiated return uses stateful steering by default

inbound|bidirectional +route-return
    -> opt out of stateful host return steering
    -> ordinary host routing supplies return reachability
```

This does not restore RC-style ownership of host routing. Host-side objects remain explicit,
narrow boundary-policy contributions.

## EXP-053 — PASS

Experiment:

`design/experiments/EXP-053 NG3 host return steering/`

Primary evidence:

- workflow `44196901273`;
- job `134440616017`;
- result file `EXP-053-result-20261118.md`.

Observed markers:

```text
EXP053_NO_REMOTE_MAIN_ROUTE=PASS
EXP053_ROUTE_PRECONDITION=PASS
EXP053_FORWARDED_REPLY=PASS
EXP053_HOST_LOCAL_REPLY=PASS
EXP053_NO_REMOTE_MAIN_ROUTE=PASS
EXP053_RESULT=PASS
```

The experiment deliberately made the ordinary unmarked route to the remote address use the
LAN default. Only the marked RPDB lookup used the managed-stack boundary. Therefore successful
return traffic cannot be explained by an accidental main-table route.

Proven mechanism:

```text
remote NEW enters host from managed boundary
    -> PREROUTING stores connection mark

forwarded reply
    -> PREROUTING restores packet mark

host-local reply
    -> nft type-route OUTPUT restores packet mark

packet mark
    -> dedicated RPDB table
    -> managed boundary
```

EXP-053 does not prove multi-path selection inside the managed namespace and does not replace
historical EXP-014.

## Requirement changes

Added:

- `VPNG0002-R2.R3.R1.R1` — VPN-GATE owns the narrow host bootstrap route contribution for
  Profiles permitting ordinary-side initiation;
- `VPNG0002-R2.R3.R1.R1.R1` — bootstrap must preserve ordinary reachability to any required
  external VPN transport endpoint before a managed route can capture that endpoint;
- `VPNG0002-R2.R3.R3.R1` — default stateful host-boundary return steering for
  remote-initiated flows;
- `VPNG0002-R2.R3.R3.R1.R1` — canonical Profile opt-out `+route-return`.

The administrator responsibility boundary is intentionally conventional:

- VPN-GATE creates/verifies/removes its own bootstrap contributions;
- VPN-GATE does not become an arbiter of arbitrary host route policy;
- deletion or conflicting replacement of a live VPN-GATE bootstrap route by a privileged
  administrator violates the operating contract and may produce a diagnosed failure.

## Configuration grammar

Canonical new forms:

```text
inbound+route-return
inbound+snat+route-return
bidirectional+route-return
bidirectional+snat+route-return
```

Canonical combined suffix order is:

```text
+snat+route-return
```

Reverse ordering is rejected.

`outbound+route-return` is rejected because outbound-only Profile has no remote-initiated
flow whose return mode could be changed.

The modifier name deliberately avoids `noconntrack`: route-return does not mean Linux
`NOTRACK`, does not disable conntrack globally, and does not alter the existing stateful
firewall semantics.

The current alpha recognizes the grammar but fails fast on `+route-return` until physical
host-boundary actuation is assembled end-to-end.

## Executable reference development

Added pure semantic planner:

`host_boundary_policy.py`

It computes:

- which Profile destinations require host bootstrap routes;
- which remote prefixes use stateful return;
- explicit route-return negative classifier verdicts;
- deterministic longest-prefix classifier ordering;
- explicit full-tunnel presence.

Route requirement is exactly:

```text
ordinary-side initiation allowed
    OR
route_return requested
```

so an inbound-only default-stateful Profile creates no host destination route.

Added Linux desired-state compiler:

`linux_host_boundary_policy.py`

It compiles:

- bootstrap route desired objects;
- one stateful-return table/default;
- one fwmark RPDB rule;
- deterministic nft PREROUTING classifier;
- PREROUTING mark restore for forwarded replies;
- type-route OUTPUT mark restore for host-local replies.

Numeric mark/table/rule/protocol allocation is passed explicitly rather than inventing another
global range in this cycle.

### Mixed Profile correctness

A simple interface-wide mark would make a per-Profile opt-out incorrect.

Example:

```text
10.0.0.0/8      -> stateful return
10.20.0.0/16    -> route-return
```

The planner therefore emits longest-prefix classification with an explicit negative verdict:

```text
10.20.0.0/16 -> route return / do not mark
10.0.0.0/8   -> stateful / mark
```

The more-specific opt-out cannot fall through into the broader stateful rule.

## Full-tunnel finding

NG3 already allows `0.0.0.0/0` Profile destinations.

A naive default or split-default bootstrap route can capture the VPN transport's own external
endpoint and loop the underlay back into the managed stack.

The architecture now requires:

```text
observe ordinary host route to required VPN transport endpoint
    -> pin exact endpoint reachability through the ordinary path
    -> only then activate catch-all managed bootstrap routing
```

The reference Linux compiler currently **fails closed** on a bootstrap plan containing
`0.0.0.0/0` with `FullTunnelUnderlayPinningRequired`.

This is deliberate: the current cycle proves and models the responsibility but does not
materialize a partial unsafe full-tunnel implementation.

## Self-review finding F1 — non-string direction regression

The first parser edit used:

```python
if value in forms:
```

which would raise raw `TypeError` for an unhashable non-string TOML value instead of
`Release1ConfigError`.

**Disposition:** fixed to require `isinstance(value, str)` before dictionary membership and
added a regression test.

## Evidence

### Rootless/unit

Workflow `44197704338` after the new host-boundary planners/compiler:

```text
Ran 590 tests
OK
```

A later unit job `134444116498` including the parser robustness fix and its dedicated test:

```text
Ran 591 tests
OK
```

### Privileged Linux

- EXP-053 primary run: `44196901273` / job `134440616017` — **SUCCESS**;
- subsequent run with the new reference planners/compiler:
  `44197704338` / `linux-host-return-steering` — **SUCCESS**.

## What this cycle deliberately did not add

- general ownership of host `main`;
- host route conflict arbitration against arbitrary administrator policy;
- continuous repair of privileged administrator changes;
- Linux `NOTRACK`;
- per-flow pinning between multiple VPN paths inside the managed domain;
- automatic full-tunnel activation without underlay pinning;
- new global numeric mark/table allocation ranges;
- silent alpha acceptance of a not-yet-materialized `+route-return`.

## Remaining technical gate

One bounded gate remains before complete host bootstrap actuation:

**full-tunnel / endpoint-capturing underlay pinning**.

The next implementation unit should:

1. obtain the exact external VPN transport endpoint set for each relevant Profile/Device;
2. freshly observe each endpoint's ordinary host route before managed bootstrap mutation;
3. materialize exact endpoint exception routes with explicit ownership;
4. activate catch-all bootstrap routing only after those exceptions verify;
5. verify cleanup and administrator-conflict behavior;
6. prove the sequence on privileged Linux, preferably including the Debian 13 target.

This is mechanism/evidence work, not a pending product decision.

## Accumulated requirement-state inventory

### `decomp`

Six accumulated links remain resolved. Pending: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none.**

The previously discussed conntrack opt-out is now represented by the canonical
`+route-return` spelling; no additional decision is needed for this cycle.

## Conclusion

**PASS.**

The host-routing gap is now reduced to a conventional VPN boundary:

- VPN-GATE owns only the host bootstrap routes it needs;
- administrator tampering with those routes is outside the product's protective ownership
  promise;
- inbound return traffic can avoid duplicate host routes through proven conntrack/RPDB
  steering;
- users can explicitly select route-based return;
- unsafe full-tunnel bootstrap remains fail-closed until underlay endpoint pinning is
  implemented and evidenced.
