# VPN-GATE NG3 — Device firewall compiler and guarded mutation review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-device-firewall-cont2-35m`

## Scope

Review the completed bounded lower-realization block for ordinary Release-1 Device firewall:

- semantic compiler from normalized Device policy to exact nft desired data;
- Linux evidence for L3/L4 predicates and active REJECT;
- required Device-jump ordering ahead of Profile acceptance;
- compositional Profile/Device observation inside `payload_forward`;
- guarded one-step Device-firewall mutation under the closed forwarding barrier;
- real Linux integration for initial materialization and replacement.

External human-facing grammar, endpoint-scoped rules and whole-policy convergence with NAT/local-system owner classes are outside this block.

## Evidence

### EXP-042 — predicate JSON

Final green workflow: `43928686439`.

Confirmed canonical lower facts:

- IPv4 source/destination selectors;
- protocol-only TCP/UDP/ICMP via `meta l4proto`;
- TCP/UDP source/destination ports;
- redundant `l4proto` removal when protocol-specific ports already constrain the rule.

An initial red run was retained because it exposed exactly that nft canonicalization rather than a product defect.

### EXP-043 — active REJECT

Final green workflow: `43929887044`.

Confirmed real forwarded behavior:

- TCP REJECT -> TCP reset -> immediate `ECONNREFUSED`;
- UDP REJECT -> ICMP port-unreachable -> active refusal;
- ICMP REJECT -> active unreachable;
- protocol-unspecified IPv4 REJECT -> active ICMP unreachable.

### EXP-044 — jump ordering

Green workflow: `43929778491`.

`add rule` after existing Profile accepts was demonstrated unsafe: matching traffic bypassed the later Device jump. `insert rule` placed the Device jump first and restored the accepted Device-before-Profile composition.

## Findings and dispositions

### F1 — compiler must target canonical observed nft, not textual source

EXP-042 proved that nft removes redundant protocol expressions. The first compiler form would therefore have produced desired JSON that could never compare equal after round-trip.

**Disposition:** fixed. The compiler emits exact observed canonical shapes.

### F2 — protocol-only TCP REJECT has another canonicalization rule

The first privileged guarded-mutation run created `meta l4proto tcp reject with tcp reset`, but fresh nft observation omitted the explicit `l4proto` because TCP reset itself constrains the protocol. The new chain was consequently classified stale and the Executor correctly refused success.

**Disposition:** fixed in the compiler, not weakened in the observer. Protocol-only TCP REJECT now expects no redundant match. Workflow `43931436544` then passed.

### F3 — Device jump must precede Profile acceptance

Appending a new Device jump is semantically unsafe.

**Disposition:** Linux mutation backend uses only the EXP-044-proven `insert rule` primitive for new Device jumps.

### F4 — Profile observer must coexist with Device owner class

The original strict Profile observer classified every `payload_forward` rule not matching NEW/RETURN shape as conflict. Once Device jumps became a legitimate co-owned class, this would reject valid combined state.

**Disposition:** marked Device jumps are delegated to the Device structural observer. The Profile observer remains strict for its own owner class; malformed Device jumps are still rejected by combined classification.

### F5 — replacement order must remove references before child chains

A changed child chain cannot be safely deleted while a base-chain jump still targets it.

**Disposition:** bounded Executor convergence order is `stale jump -> stale child chain -> missing desired chain`. Every step starts and ends with fresh observation.

### F6 — command success is not postcondition proof

The mutation path must remain safe under wrapper errors, partial application and interface drift.

**Disposition:** every step runs under confirmed `ip_forward=0`, re-observes links+nft afterwards, rechecks the barrier and accepts success only on independently observed strict progress/exact state.

### F7 — bounded mutation is not whole Release-1 nft convergence

The reference slice currently accepts only invariant scaffold, Profile NEW/RETURN owner rules and Device firewall owner objects. Valid NAT/local-system contributions are deliberately refused.

**Disposition:** retain this as an explicit implementation boundary, not a product Constraint. The next logical lower-policy block is a combined structural Executor that classifies/preserves all accepted owner classes together.

## Semantic compiler result

For one current Device/path, exact realization is two direction-specific child chains:

```text
OUT: host boundary -> Device path
IN:  Device path -> host boundary
```

Each chain receives the ordered subsequence for its direction and explicit policy ends with terminal DROP. Omitted policy creates no Device chain/jump.

Actions:

```text
ALLOW  -> return
DENY   -> drop
REJECT TCP -> tcp reset
REJECT otherwise current IPv4 subset -> ICMP port-unreachable
```

Ports require normalized TCP/UDP. Unsupported protocol tokens fail closed at compilation rather than being guessed.

## Guarded mutation result

The bounded state machine supports:

1. no-op exact confirmation;
2. exact-handle stale jump deletion;
3. flush+delete stale unreferenced owned child chain;
4. create ordered child rules and insert its jump;
5. fresh postcondition and barrier verification after every step.

Rootless state-machine/backend tests passed. Privileged integration initially caught F2, then final workflow `43931436544` passed all jobs including the live guarded Device-firewall mutation integration.

## Simplification review

Not introduced:

- whole-table blind rebuild;
- persistent nft handle registry;
- userspace per-packet evaluator;
- generic ACL framework;
- endpoint-scoped Release-1 rules;
- external grammar decisions;
- automatic adoption/deletion of NAT or local/system rules by this bounded Executor.

## Accumulated requirement-state inventory

### `decomp`

All six current links are **resolved**:

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

## Remaining logical work

The Device-firewall bounded lower realization is complete. The next independent logical block is whole-policy structural convergence: combine scaffold, Profile forward, Device firewall, NAT and local/system owner classes behind one guarded Executor without weakening any existing strict owner classifier.

## Verdict

**PASS.** No unresolved finding remains in this bounded Device-firewall lower-realization unit.
