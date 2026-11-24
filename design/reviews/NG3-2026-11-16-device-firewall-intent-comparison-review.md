# VPN-GATE NG3 — normalized Device firewall intent and lower comparison review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-device-firewall-cont2-35m`

## Scope

Close the bounded logical unit between the already accepted ordered Device-firewall
semantics and the later nft predicate compiler:

1. normalized internal Device firewall policy intent;
2. exact lower desired child-chain/jump/rule representation;
3. pure actual-vs-desired comparison over the existing structural observer.

External configuration grammar, semantic-to-nft predicate compilation, physical mutation and
final protocol-appropriate REJECT realization are outside this unit.

## Requirement trace

**Implements/refines lower realization for:**

- `VPNG-U001-R1.R2.R4.R6.R2`;
- `VPNG-U001-R1.R2.R4.R6.R2.R1`;
- `VPNG-U001-R1.R2.R4.R6.R2.R2`;
- `VPNG-U001-R1.R2.R4.R6.R2.R3`;
- `VPNG-U001-R1.R2.R4.R6.R2.R4`;
- `VPNG-U004-R4.R1`;
- `VPNG-U004-R4.R2`.

**Constrained by:**

- `VPNG-U001-R1.R2.R4.R6.C1` — exact human-facing grammar remains postponed;
- `VPNG-U001-R1.R2.R4.R6.R2.R5.C1` — endpoint-scoped firewall remains outside Release 1.

## Findings

### F1 — omitted policy must not collapse into explicit empty policy

Accepted semantics distinguish:

```text
omitted Device firewall
    -> no Device-layer restriction

explicit non-empty Device firewall
    -> ordered first-match policy
    -> no match => DROP
```

Representing both as an empty list would lose that semantic distinction.

**Disposition:** fixed. `DeviceFirewallPolicyIntent.rules` is `None` for omission and a
non-empty ordered tuple for explicit policy.

### F2 — normalized intent must not freeze external grammar

The semantic requirement already defines direction/action and optional L3/L4 fields, but the
external spelling and final accepted protocol vocabulary are explicitly deferred.

**Disposition:** the internal model types the accepted fields without parsing or canonicalizing
external tokens. Protocol remains an internal non-empty token at this layer. No TOML spelling,
protocol-name whitelist or parser behavior was selected.

### F3 — lower desired state must preserve order exactly

The Device firewall is first-match and user order is semantic. A set comparison would accept
a physically reordered rule list.

**Disposition:** `DeviceFirewallChainSpec.rules` is an ordered tuple and
`compare_device_firewall` compares the sequence position-by-position. Tests prove that the
same rules in a different physical order fail desired-state confirmation.

### F4 — semantic intent and physical desired data are different layers

Directly storing nft JSON in the normalized Device intent would leak Linux realization into
the product semantic model. Conversely, pretending the current unit can compile every
accepted semantic field would cross the still-open protocol/port evidence gate.

**Disposition:** two explicit layers:

```text
DeviceFirewallPolicyIntent
    semantic internal policy

future semantic compiler
    -> exact lower expressions/actions

DeviceFirewallDesiredState
    exact physical desired data
```

The exact lower desired layer accepts canonical predicate/action JSON but does not generate
it.

### F5 — production child-chain naming remains unselected

EXP-041 intentionally proved an experimental child chain, not a production naming scheme.

**Disposition:** lower desired state accepts an opaque non-empty `child_chain_name` supplied
by its caller. This unit does not derive or standardize production names.

### F6 — extra recognized owned objects are stale desired-state, not success

An exact desired chain can be present while an additional owned Device child chain/jump
remains from old state.

**Disposition:** comparison reports extra recognized owned chains and jumps as stale and does
not report `desired_confirmed`.

### F7 — non-current desired interfaces are invalid input

A desired lower firewall state bound to an interface generation outside the fresh current
inventory must not be compared as if it were current policy.

**Disposition:** comparison rejects desired ingress/egress identities absent from the supplied
current inventory. Observed stale numeric generations remain separately classified by the
structural observer.

## Component-model review

- `DeviceFirewallPolicyIntent` is semantic data, not an Engine.
- `DeviceFirewallDesiredState` is lower desired data.
- `compare_device_firewall` is a pure Direct Calculator.
- existing structural observation remains read-only lower Machinery.

No new Manager, Agent, event stream, persistent state or mutation path is introduced.

## Simplification review

Not introduced:

- firewall AST framework;
- external grammar parser;
- protocol registry;
- production chain-name allocator;
- persistent handle map;
- userspace packet evaluator;
- mutation/retry loop;
- endpoint-scoped Release-1 policy.

## Tests / CI

Behavior-bearing workflow:

`43927867199` — **PASS**.

Covered explicitly:

- omission vs explicit non-empty policy;
- literal rule-order preservation;
- field/range validation for already accepted internal semantics;
- protocol vocabulary intentionally not selected;
- exact lower rule/action canonicalization;
- terminal fallthrough placement;
- exact ordered comparison;
- same-rule-set/wrong-order mismatch;
- stale extra owned chain;
- non-current desired interface rejection.

Earlier prerequisite workflows for EXP-041 and the structural observer remain green.

## Accumulated requirement-state inventory

### `decomp`

All six current links are **resolved**:

1. `VPNG-U001-R1.R2`: `VPNG-U005-R5 -> VPNG-U005-R5.R6`.
2. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
3. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.
4. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.
5. `VPNG-U001-R1.R3.C2.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
6. `VPNG-U004-R4.R6.R1.R6.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Next logical unit

Semantic Device-firewall compiler:

```text
DeviceFirewallPolicyIntent
    + current host/path InterfaceIdentity
    + deterministic lower child identifier
        -> DeviceFirewallDesiredState
```

Before accepting protocol/port expression generation, establish the minimum Linux/nft JSON
evidence required for exact IPv4 source/destination, L4 protocol and source/destination-port
predicates. Final REJECT mapping remains separately gated and must not be guessed from the
single EXP-041 evidence rendering.

## Verdict

**PASS.** The normalized-intent and exact lower comparison unit is complete and can be
snapshotted independently of the current CD window.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
