# NG3 2026-11-18 — continuation gap-truth / VPNPathAdapter 35m review

> **Historical requirement trace note (2026-11-20):** this review records the requirement
> tree that was current when the review was performed. `VPNG0002-R2.R3.R1.R1`
> was later removed from the current requirement tree when the old direction-derived host-routing
> ownership decomposition was rejected. References below to that ID are historical facts about
> what this review evaluated, not current requirement links; the review conclusions are not rewritten retroactively.

## Cycle identity

- `CYCLE_INTERVAL`: 35 minutes.
- `CYCLE_START_COMMIT`: `c8732deed77ab708f2eac177356b49cdbdfae9e1`.
- `T0`: 2026-11-18 16:11:49Z.
- Active branch: `ng3-design-cycle-20261118-continuation-gap-truth-35m`.
- Base at cycle start: main snapshot 87, `16445398512dad1d405ea3d78ecf21c95ee0fa45`.

Before this continuation window began, the interrupted preceding CD was recovered to its last
completed logical boundary and the already-reviewed selected host-boundary alpha integration
was published as **main snapshot 87**.

## Verdict

**PASS for the two autonomous review units completed in this continuation cycle.**

The cycle ends early by the CD continuation rule because every next current executable gap is
behind an already-known human/evidence/interface decision boundary. Starting another block
would require guessing semantics or selecting an unaccepted mechanism.

## Mainline snapshots

### Snapshot 88 — current executable gap truthfulness

Main:

`c3ecac7a9785030a0d36d8a5dd0f3dc55e4dfe13`

The normative architecture had one stale statement: it still listed user-visible status
presentation as an unresolved executable gap after RuntimeStatusAgent had already been wired
into the alpha and snapshotted.

The correction distinguishes:

```text
implemented:
    live current-only RuntimeStatusAgent presentation through alpha JSON

still open:
    stable production packaging/version lifecycle
    stable external Release-1 status API
```

Historical reviews/results were deliberately not rewritten.

Review:
`design/reviews/NG3-2026-11-18-current-gap-truthfulness-review.md`.

### Snapshot 89 — executable Linux VPNPathAdapter runtime collection

Main:

`3d98b299671a2cec0c5a796e0a3ac827af3531d7`

Added a stateless `LinuxVpnPathAdapter` fresh-observation boundary and routed both controller
startup and alpha periodic reconcile through it.

The runtime contract is:

```text
wakeup
    -> fresh complete managed-netns interface snapshot
    -> strict InterfaceIdentity(ifname, ifindex) inventory
    -> exact verified host-boundary generation check
    -> existing bounded Device binding projection
```

No interface cache, Netlink history, process registry, retry queue or second binding owner was
introduced.

The architecture gap list now correctly stops treating "full VPNPathAdapter runtime
collection" as missing. The alpha's timer is only a wakeup cadence; authoritative decisions
still use a fresh full snapshot.

Review:
`design/reviews/NG3-2026-11-18-linux-vpn-path-adapter-runtime-review.md`.

## Evidence

Primary implementation workflow:

- NG3 Python run `44345359341`;
- unit job `134946162925` — **SUCCESS**;
- installed Debian 13 alpha smoke job `134946163432` — **SUCCESS**.

Relevant alpha evidence remained green through the new Adapter boundary:

```text
EXP051_RUNTIME_STATUS_ZERO_PATH=PASS
EXP051_FIRST_PAYLOAD=PASS
EXP051_RUNTIME_STATUS_FIRST_PATH=PASS
EXP051_ROUTE_RETURN_HOST_LOCAL_REPLY=PASS
EXP051_RUNTIME_STATUS_NEW_GENERATION=PASS
EXP051_VPN_ONLY_RESTART_RECONCILED=PASS: old_ifindex=2 -> new_ifindex=3
EXP051_STACK_STOP_CLEAN=PASS
EXP051_RESULT=PASS
```

The overall workflow is expected to remain red because
`linux-nft-marked-host-bootstrap` executes EXP-057, the intentionally failed/rejected
shared-mark bootstrap alternative. That job is not a regression in either review unit.

## Findings resolved in this cycle

### F1 — current architecture understated implemented status capability

**Disposition:** fixed in current normative architecture; historical reviews remain untouched.

### F2 — accepted VPNPathAdapter boundary existed only as lower parser + inline runtime usage

Startup and reconcile both issued raw interface observation themselves.

**Disposition:** fixed with one explicit stateless Linux Adapter used by both paths.

### F3 — same-name host-boundary replacement must not inherit old authority

**Disposition:** Adapter observation can require the exact already-verified
`InterfaceIdentity(ifname, ifindex)`; same-name/new-ifindex fails the current observation.

### F4 — event/poll mechanism must not become semantic state

**Disposition:** periodic alpha polling remains a wakeup only. No Netlink/event state/history
was added or made authoritative.

## Why the cycle stops here

The remaining current executable gaps are not autonomous next blocks.

### Profile ordinary-side `+snat`

Blocked by the explicit human requirement decision around
`VPNG0004-R4.R6.R1.R6.R1`.

EXP-064 technically proves the four fixed host-boundary behavior lanes, but adoption remains
`pending_decision` while the requirement literally says full Profile identity must cross the
boundary.

### Availability probe execution/runtime assembly

Blocked behind the existing Linux probe-plane materialization/evidence gate. EXP-026 is a
candidate remediation for generation-safe probe cleanup but lacks the required target-platform
acceptance/selection. Production code must not assume that candidate merely because it exists.

### Stable production packaging/version lifecycle and stable external status API

The alpha has a working deployment and current JSON status surface, but the stable external
interface/version lifecycle is not yet an accepted product contract. Selecting it autonomously
would create new user-facing semantics.

## Requirement-state inventory

### `decomp`

Six links exist and all are resolved:

1. `VPNG0005-R5 -> VPNG0005-R5.R6`
2. `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
3. `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`
4. `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`
5. `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`
6. `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`

Pending `decomp`: **none**.

### `unreal`

Active: **none**.

### `broken`

Active: **none**.

### `[rejected_closure]`

Active: **none**.

## Accumulated suspicious requirement wording/placement

No new suspect requirement was introduced in this cycle. The previously surfaced unresolved
review list remains:

Semantic suspicion:

- `VPNG0002-R2.R1.R2` — exact symmetric classifier wording may be code-derived;
- `VPNG0002-R2.R2.R2` — Profile intent expressed through Device/concrete binding vocabulary
  may be below the appropriate abstraction level.

Placement/Purpose suspicion:

- `VPNG0002-R2.R1.R1`;
- `VPNG0002-R2.R1.R2`;
- `VPNG0002-R2.R2.R1`;
- `VPNG0002-R2.R2.R2`;
- `VPNG0002-R2.R3.R3`;
- `VPNG0002-R2.R3.R3.R1`;
- `VPNG0002-R2.R3.R1.R1`;
- `VPNG0002-R2.R5.R1`.

This inventory is review debt only; it does not revoke the separately accepted semantics of
host bootstrap, stateful return, `+route-return`, most-specific routing or the current
Release-1 single-path inbound constraint.

## Human decisions / explicit re-entry gates

1. Decide whether `VPNG0004-R4.R6.R1.R6.R1` truly requires full Profile identity across the
   host boundary or whether preserving the already-selected Profile-derived host behavior is
   sufficient. This decides whether EXP-064 can be selected and `+snat` materialization can
   continue.
2. Before production availability probe materialization, select/confirm the Linux probe-plane
   isolation/cleanup mechanism on the target platform rather than treating EXP-026 as already
   accepted.
3. Stable production packaging/status API requires a separately accepted external-interface
   contract if/when that becomes the next product block.

## Conclusion

The interrupted development stream is back on a clean linear mainline through snapshot 89.
Two further autonomous inconsistencies/gaps were closed in the continuation window. No
unblocked executable Release-1 block remains that can be started without crossing an explicit
decision/evidence boundary.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
