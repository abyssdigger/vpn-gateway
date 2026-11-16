# VPN-GATE NG3 — ordered Device firewall and managed-stack default-policy closure review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-endpoint-provenance-35m`

## Review unit

Close the product semantics and component architecture for:

- ordered user-authored Device firewall policy;
- `IN/OUT` semantics relative to a VPN Device/path;
- literal payload L3/L4 match fields;
- omission/default behavior;
- the boundary between Device firewall and Profile permission;
- managed-domain `INPUT/FORWARD/OUTPUT = DROP/DROP/DROP`;
- future endpoint-scoped firewall dependency on transport provenance.

Exact human-facing compact syntax and physical nft mutation are outside this unit.

## Requirement validation

### VPNG0001-R1.R2.R4.R6.R2

**Purpose / Зачем:** allow transport-level restrictions to protect tunnel traffic without
turning Device policy into a bypass around Profile policy.

**Actor / Кто:** VPN-GATE.

**Action / Что:** maintain an ordered Device firewall layer whose `ALLOW` can only continue
traffic already eligible under Profile semantics and whose negative verdicts can narrow it.

**When / scope:** for managed payload traversing concrete paths of that Device.

### R6.R2.R1 — ordered first-match rules

VPN-GATE preserves user order. Every normalized rule carries:

```text
direction = IN | OUT
action    = ALLOW | DENY | REJECT
protocol?
source_port?
destination_port?
source_ipv4_cidr?
destination_ipv4_cidr?
comment?
```

The first applicable terminal Device verdict wins. A broad early rule is not repaired or
reordered around a later specific rule.

Exact external encoding and exact accepted protocol/port combinations remain under
`VPNG0001-R1.R2.R4.R6.C1`. The lower normalized contract must receive a coherent predicate;
the parser/compiler must not invent semantics for an external combination that has not been
accepted by the configuration-format review.

### R6.R2.R2 — IN/OUT and packet fields

VPN-GATE interprets:

```text
OUT = ordinary/host boundary -> current Device path
IN  = current Device path -> ordinary/host boundary
```

Both are Linux forwarding traffic. User-facing `IN/OUT` are not Linux
`INPUT/OUTPUT`.

Source/destination IP and port mean literal payload packet fields at this forwarding point.
They are not outer VPN transport addresses.

The accepted outbound Device MASQUERADE runs later in postrouting, so the Device firewall can
still inspect the original local source before VPN-GATE's own outbound source NAT.

### R6.R2.R3 — omission and fallthrough

```text
no Device firewall configured
    -> Device layer is permissive in IN and OUT

explicit non-empty Device firewall
    -> preserve exactly the explicit ordered policy
    -> no matched terminal verdict => DROP
```

This keeps omission equivalent to "no additional Device restriction" while making an
explicit firewall fail closed.

### R6.R2.R4 — scope boundary

User Device firewall applies only to VPN-GATE managed payload between the explicit host
boundary and current VPN paths. It does not become a generic host firewall and does not own
arbitrary host-local/host-to-host traffic.

### R6.R2.R5 + R6.R2.R5.C1 — endpoint-scoped future policy

The accepted future capability allows a Device firewall rule to be scoped to a logical
transport endpoint without long-lived dependence on `tun17`-style runtime names.

Its implementation is intentionally outside Release 1 until:

1. the corresponding integration supplies confirmed transport-endpoint provenance under
   `VPNG0001-R1.R3.R5`;
2. the named-endpoint configuration format is accepted.

Ordinary Device firewall rules do not depend on this future selector.

### R4.R6.R1.R5 + R5.R1 — DROP/DROP/DROP appliance boundary

Before payload forwarding can be reported ready, VPN-GATE's managed network domain has
default filter policies:

```text
INPUT   DROP
FORWARD DROP
OUTPUT  DROP
```

User Device rules apply only to payload `FORWARD`.

VPN-GATE itself owns the explicit local exceptions required by supported control, probe,
publication and integration functions. Those exceptions neither open arbitrary payload
forwarding nor grant ownership over the ordinary host namespace firewall.

## Architecture composition

### Device firewall before Profile terminal acceptance

The simplest composition satisfying all accepted semantics is:

```text
exact managed host/path pair
        |
        v
ordered Device chain
        |
        +-- DENY   -> drop
        +-- REJECT -> reject
        +-- ALLOW  -> return
        |
        v
Profile hard gate
        |
        +-- permitted NEW/RETURN -> accept
        +-- otherwise            -> payload_forward policy drop
```

`ALLOW -> return` is essential. Compiling Device ALLOW directly to `accept` would let a
Device rule widen Profile permission and violate R6.R2.

The Device chain is traversed before both Profile NEW admission and the accepted
prefix-scoped ESTABLISHED/RELATED return rule. Therefore user firewall rules govern actual
packets of an existing flow too; there is no hidden established-flow bypass before the
ordered Device policy.

This follows directly from the accepted first-match packet policy: inserting an implicit
stateful acceptance before user rules would make later user DENY/REJECT rules ineffective
for existing flows.

### Profile prefix partition remains valid

The existing most-specific Profile CIDR partition is still useful and remains unordered
positive-only Profile permission.

It is not final Device firewall policy.

Its output is consumed after Device firewall ALLOW/return and remains the hard permission
gate.

### Current lower payload_forward model is a sub-contract

EXP-035..038 and the current `PayloadForwardRuleSpec` remain valid evidence for exact
Profile NEW/RETURN rule primitives.

They do **not** represent:

- per-Device jump rules;
- ordered child-chain rules;
- `return`;
- `drop` / `reject`;
- explicit-policy terminal no-match drop.

The strict current observer must therefore not be extended by assumption. Physical Device
firewall mutation remains blocked until a later lower-policy unit defines and proves the
complete owner/desired representation.

### INPUT/OUTPUT scaffold expansion

The accepted architecture adds managed-domain base chains with `policy drop` for INPUT and
OUTPUT. Existing EXP-032 predates those chains; it remains evidence for the already accepted
FORWARD/postrouting scaffold only.

Before Release-1 forwarding readiness can rely on DROP/DROP/DROP, a bounded lower scaffold
unit must prove/implement exact INPUT/OUTPUT owner shapes and required system exceptions.

## Components and responsibilities

- **ConfigurationAdapter** — later parses the separately accepted external grammar and emits
  normalized ordered Device firewall intent.
- **PayloadPolicyCalculator** — composes Profile permission with normalized Device firewall
  policy without widening Profile semantics.
- **VPNPathAdapter / binding projection** — supplies exact current path identities; later
  endpoint-scoped rules may consume confirmed provenance, but do not discover it themselves.
- **NetworkPolicyAdapter / lower nft machinery** — later materializes ordered chains and base
  policies after owner-shape evidence.
- **Linux kernel nftables** — performs packet-by-packet ordered rule evaluation.

No userspace per-packet firewall evaluator is introduced.

## Interactions

```text
user config
   -> ConfigurationAdapter
   -> normalized ordered Device firewall
                         +
                 Profile permission
                         |
                         v
              PayloadPolicyCalculator
                         |
                         v
             lower desired nft policy
                         |
                         v
                  Linux nftables
```

## External environment

The design relies on Linux forwarding/nftables inside the isolated managed network domain,
exact current interface generations, conntrack for Profile return semantics and the existing
postrouting NAT boundary.

Host firewall state outside the explicit VPN-GATE boundary is not an input to Device firewall
semantics.

## Constraint lifting

- unresolved compact user syntax remains visible under `R6.C1`;
- endpoint-scoped policy is explicitly postponed under `R6.R2.R5.C1`;
- the current lower observer/compiler is explicitly insufficient for final Device policy;
- INPUT/OUTPUT default-DROP physical readiness is explicitly not claimed from old EXP-032.

None of these constraints removes ordinary ordered Device firewall semantics from the
accepted product model.

## Simplification review

Rejected as unnecessary:

- host-level firewall ownership;
- userspace packet evaluation;
- reordering/optimizing user rules;
- a generic ACL/trie framework for Device rules;
- runtime ifname as a durable user endpoint selector;
- a second Device permission model separate from ordered rules;
- a conntrack shortcut that bypasses Device rules for established traffic.

The child-chain `ALLOW -> return -> Profile gate` composition is sufficient.

## Remaining implementation/evidence gates

These do not block requirement/architecture closure, but do block physical completion:

- exact normalized config grammar and rule encoding;
- exact supported protocol/port combinations;
- nft owner/observation model for jumps, ordered child rules, return/drop/reject;
- exact protocol-appropriate REJECT realization;
- INPUT/OUTPUT base-chain owner evidence and explicit system exceptions;
- full semantic compiler and guarded mutation.

## Verdict

**PASS.**

The affected requirement/constraint nodes have explicit Purpose/Reason, actors, scope and
architecture references. The accepted architecture preserves Profile as a hard permission
gate, preserves literal user rule order and keeps the user firewall inside managed VPN
payload scope.

The pending closure nodes may be marked `[closed]`; implementation remains gated where
listed above.
