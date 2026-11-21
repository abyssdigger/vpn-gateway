# VPN-GATE NG3 — publication-local owner and composite convergence review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-local-publication-cont-35m`

## Scope

Review the first materialized `stack_input` / `stack_output` local/system owner class:
Device transport publication, and its integration into the existing whole-table nft
convergence boundary.

The reviewed scope is deliberately narrow:

- normalized internal publication endpoint facts;
- exact publication-local INPUT/OUTPUT desired rules;
- strict owner observation/comparison;
- atomic full-diff mutation;
- coexistence with Profile forward, Device firewall and payload NAT.

Probe, loopback and integration-specific local/system permissions remain outside this unit.

## Verdict

**PASS.**

The publication-local owner class is exact, bounded by EXP-046/047 evidence, and integrated
into whole-table convergence without promoting the payload ForwardingGate into a false
local-plane safety mechanism.

## Evidence

### EXP-046 — exact publication-local packet shape

Workflow `43934873628`: **PASS**.

With terminal-DROP `stack_input` and `stack_output`, real TCP and UDP publication traffic
worked only with the exact rules:

```text
INPUT:
    current host-boundary iif
    exact local publication IPv4 destination
    tcp|udp exact destination port
    accept

OUTPUT:
    current host-boundary oif
    exact local publication IPv4 source
    tcp|udp exact source port
    accept
```

Negative controls proved:

- wrong port remained blocked;
- Device-side ingress to the same address/port remained blocked;
- no blanket `ct state established,related` local exception was required.

Accepted owner marker:

`vpn-gate:ng3:local-publication-v1`.

### EXP-047 — atomic full-diff mutation

Canonical workflow evidence is included in the fully green NG3 run
`43937617335`: **PASS**.

The canonical EXP-047 proves:

- failed add batch rolls back the earlier valid command;
- valid TCP+UDP INPUT/OUTPUT add batch is complete;
- failed replacement rolls back all stale deletions;
- valid replacement atomically changes the publication-local desired state;
- unrelated payload-forward/NAT state remains unchanged.

The previously duplicated second EXP-047 harness was removed. One canonical EXP-047 now
represents this evidence unit.

### Whole-table privileged convergence

Workflow `43937617335`: **all jobs SUCCESS**.

The live composite integration proves:

```text
scaffold-only
    -> NAT
    -> Device direction chains/jumps
    -> Profile NEW/RETURN
    -> atomic publication-local admission
```

and cleanup:

```text
stale publication-local admission
    -> Profile positive admission
    -> Device jumps
    -> Device chains
    -> NAT
    -> scaffold-only
```

A publication endpoint replacement is one `APPLY_LOCAL_PUBLICATION` composite step; the
fresh postcondition contains the new exact pair and no old port contribution.

Unknown local/system rules remain whole-scope `CONFLICT` and cause no mutation.

## Findings

### F1 — ForwardingGate cannot protect local INPUT/OUTPUT mutation

`ip_forward=0` prevents managed forwarding but does not block locally delivered traffic.
Using the existing ForwardingGate as the safety proof for publication-local mutation would
therefore be incorrect.

**Disposition:** local publication uses its own EXP-047-backed atomic nft transaction.
ForwardingGate remains closed during combined convergence for payload safety only.

### F2 — publication desired state is pair-complete

A normalized publication endpoint requires both receive and reply traffic through the local
terminal-DROP chains.

**Disposition:** `LocalPublicationDesiredState` rejects a desired endpoint that lacks either
INPUT or OUTPUT. A physically partial pair is drift, never a valid desired state.

### F3 — observer ownership is exact and current-generation scoped

The observer accepts only the publication owner marker with the exact chain, interface
operand, local IPv4 selector, TCP/UDP port selector and plain `accept`.

Current interface identity is resolved through the same nft JSON + fresh
`InterfaceIdentity` contract already accepted for Profile/NAT/Device observers.
Same-name/old-ifindex rules are stale. Malformed, duplicated or wrong-scope owned rules are
conflicts.

No publication permission is inferred from Device firewall ALLOW, Profile permission or
historical config examples.

### F4 — replacement must be one atomic full diff

An endpoint-scoped two-stage "delete, observe, add" repair could expose a transient state and
would unnecessarily infer old-to-new endpoint pairing.

**Disposition:** the pure local planner computes one owner-class full diff:

```text
all stale exact (hook, handle) refs
    + all missing exact desired rules
        -> one nft transaction
```

Delete handles are ephemeral current-observation facts. No persistent nft handle registry is
introduced.

### F5 — composite ordering distinguishes local positive permission from payload state

Local publication admission is an independent positive permission and is not protected by the
payload ForwardingGate.

**Disposition:**

- stale local publication admission is removed before payload cleanup;
- missing NAT and Device restrictions are established before Profile admission;
- missing publication-local admission is added last.

This is a convergence safety ordering, not user-visible firewall ordering.

### F6 — publication is not a generic local/system exception framework

The architecture allows local/system contributions only from explicit supported functions,
but exact lower selectors must be proven per function.

**Disposition:** this block materializes only Device transport publication. Probe remains
behind EXP-024/025/026. Loopback and integration-specific contributions remain
unmaterialized until separate evidence/implementation units exist.

### F7 — duplicated EXP-047 evidence was repository noise

Two harness directories with the same experiment number appeared during the interrupted CD
work. Both exercised the same lower transaction property; keeping both would make evidence
ownership ambiguous.

**Disposition:** retained the stronger canonical
`EXP-047 NG3 atomic local publication mutation`, recorded its canonical result, removed the
duplicate directory and duplicate CI entry.

## Component-model review

- `PublicationLocalEndpointIntent`: normalized internal semantic input, not external grammar.
- `build_local_publication_desired`: pure Calculator.
- `compare_local_publication`: pure read-only Calculator.
- `select_local_publication_step`: pure full-diff Calculator.
- `LinuxLocalPublicationBackend`: narrow Driver for the accepted nft rule shapes and atomic
  transaction.
- `converge_composite_nft_step_once`: existing Executor extended with the new owner step.

No new Manager, Agent, persistent state store, retry queue or generic firewall AST is
introduced.

## Simplification review

Not introduced:

- blanket INPUT/OUTPUT accept;
- blanket conntrack-established local accept;
- generic local firewall DSL;
- copying Device firewall rules into local hooks;
- per-Device duplicate physical publication rules when selectors are identical;
- persistent handle database;
- command replay;
- a second whole-table Executor;
- publication config grammar inferred from lower nft syntax.

## Requirement-state inventory

### `decomp`

All six accumulated links remain **resolved**:

1. `VPNG0001-R1.R2`: `VPNG0005-R5 -> VPNG0005-R5.R6`.
2. `VPNG0001-R1.R3.C1.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
3. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.
4. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.
5. `VPNG0001-R1.R3.C2.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
6. `VPNG0004-R4.R6.R1.R6.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Remaining local/system gates

- probe: EXP-024/025/026 generation/conntrack evidence remains authoritative;
- loopback: no exact lower contribution accepted in this unit;
- integration-specific control traffic: no exact lower contribution accepted in this unit;
- user-facing publication grammar remains deferred and is not selected by these lower rules.

## Conclusion

**PASS.** Device transport publication is now the first fully materialized local/system owner
class. Its desired state, strict observation, atomic mutation and coexistence with
Profile/Device/NAT are closed as one logical block.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
