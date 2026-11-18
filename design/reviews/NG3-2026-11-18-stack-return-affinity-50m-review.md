# NG3 2026-11-18 — stack established-flow return affinity — 50m cycle review

## Verdict

**PASS for the bounded cycle scope.**

This cycle proves the missing continuity property inside the managed stack and implements the
Release-1 pure/lower contract for it. It deliberately does **not** claim end-to-end controller
activation integration yet: guarded observation/comparison/convergence of the new owner is the
next implementation gate.

## Why this cycle existed

The preceding host-return work proved only:

```text
ordinary host/LAN reply
    -> host connection association
    -> managed stack
```

That is insufficient when multiple managed VPN networks overlap. After the reply re-enters the
stack, ordinary destination classification can select a different channel from the one that
accepted the original inbound flow.

Differentiating example:

```text
channel A: 10.0.0.0/16
channel B: 10.0.0.0/24

10.0.0.2 enters through A
reply returns to stack
ordinary longest-prefix lookup -> B
required established-flow return -> A
```

This is the concrete scenario required by:

- `VPNG0002-R2.R6`;
- `VPNG0007-R7.R3.R4`;
- `VPNG0007-R7.R3.R4.R1`.

Release-1 implementation remains constrained by `VPNG0002-R2.R3.C1`: an inbound or
bidirectional Profile has at most one eligible logical path.

## Requirement correction before implementation

The first draft of `VPNG0002-R2.R6` incorrectly used internal vocabulary such as Profile,
path and NEW/ESTABLISHED classification in a second-level user requirement.

It was corrected to the user-level contract:

> For managed traffic accepted from the VPN side through an allowed channel, related reply
> traffic must be sent back through the channel that accepted the original traffic; the
> existence of other allowed channels for the sender address must not by itself change the
> reply channel.

Purpose:

> so that a reply to incoming traffic from a VPN channel can be correctly processed by its
> sender.

The requirements methodology already contained the invariant that a derived `Purpose` may
not introduce scope/vocabulary absent from its ancestors. `CONTINUOUS-DEVELOPMENT.md` was
strengthened so every new/changed Requirement explicitly checks that rule.

The new general development requirement is:

- `VPNG0007-R7.R3.R4`: cross-boundary semantic continuity;
- `VPNG0007-R7.R3.R4.R1`: differentiating automated evidence through all material boundaries.

Its Purpose was also corrected to stay within the ancestor implementation/contract vocabulary.

## EXP-061 — PASS

Experiment:

`design/experiments/EXP-061 NG3 stack established-flow return affinity/`

Privileged evidence:

- workflow run: `44254212993`;
- job: `134632848156`;
- environment: Ubuntu 26.04, iproute2 6.19, nftables 1.1.6, conntrack-tools 1.4.9.

Observed markers:

```text
EXP061_MORE_SPECIFIC_BASELINE=PASS
EXP061_HOST_NO_REMOTE_ROUTE=PASS
EXP061_WITHOUT_STACK_AFFINITY_FAILS=PASS
EXP061_STACK_AFFINITY_RETURN=PASS
EXP061_AFFINITY_REMOVAL_RESTORES_FAILURE=PASS
EXP061_RESULT=PASS
```

A later current-head CI run also completed `linux-stack-return-affinity` successfully.

The experiment proves all of the intended differentiating facts:

1. ordinary stack routing selects the more-specific wrong channel B;
2. without stack-side affinity the end-to-end flow fails;
3. the host has no accidental main-table remote route;
4. stack ctmark -> fwmark -> dedicated RPDB steering returns the reply through channel A;
5. removing the affinity owner restores the failure.

This satisfies the differentiating-evidence requirement of
`VPNG0007-R7.R3.R4.R1`.

## Selected Release-1 mechanism

The selected Release-1 lower semantics are:

```text
VPN-originated NEW flow
    -> classify only among Profiles allowed on the actual ingress path
    -> save original Profile routing-domain association in stack conntrack mark

reply re-enters through verified host boundary
    -> restore reserved connection mark to packet mark

affinity RPDB rule (higher precedence than ordinary payload dispatch)
    -> original Profile routing table
    -> current single eligible inbound path
```

Important boundary:

- the mark identifies the original **Profile routing domain**;
- it does not claim concrete-path pinning among several simultaneously eligible paths;
- this is sufficient only under the Release-1 one-inbound-path constraint;
- Release-2 multi-path inbound/bidirectional remains EXP-014 or equivalent evidence.

## Implementation produced

### Pure affinity projection

New `stack_return_affinity.py` provides:

- `StackReturnAffinityPlatformSpace`;
- deterministic mark/RPDB-priority allocation;
- `StackReturnClassifierSpec`;
- `StackReturnRuleSpec`;
- `StackReturnAffinityDesired`;
- exact validation that Release-1 inbound/bidirectional Profiles do not expose more than one
  current path;
- ingress-path-first source-prefix partitioning;
- mapping of the established association back to the already allocated Profile routing table.

The current Linux platform reserves:

```text
stack affinity marks:          0x10000000 .. 0x10001fff
stack affinity rule priority:  0x1800 .. 0x1fff
probe RPDB priority:           0x2000 ..
payload dispatch priority:     0x4000 ..
```

Thus established-flow affinity executes before ordinary payload destination dispatch.

### Linux lower primitives

New `linux_stack_return_affinity.py` provides a separate owner:

```text
table ip vpn_gate_return_affinity
    PREROUTING:
        accepted VPN ingress NEW -> ct mark
        host-boundary reply with reserved ct mark -> packet fwmark

exact fwmark RPDB rule
    -> original Profile table
```

The owner is deliberately separate from `ip vpn_gate/payload_forward`:

- `payload_forward` owns permission;
- return affinity owns routing continuity;
- an address-based RETURN allow rule is not treated as routing affinity.

Current lower API is bounded create/delete/rendering only. It does not blind-adopt an existing
table and is not yet wired into activation.

## Inherited regression found and fixed

The previous host-boundary cycle had left `controller_startup.py` with an optional
`boundary_contribution` referenced before initialization in stop/error paths.

This cycle corrected:

- initialization of the optional boundary owner before checkpoints;
- no artificial stop checkpoint when no boundary phase exists;
- lifetime-lock retention when boundary convergence/cleanup cannot safely remove owned host
  state;
- regression coverage for convergence+cleanup failure.

This finding is inherited from the previous cycle, not caused by EXP-061.

## Why activation integration is not claimed

`activate_network_policy(...)` eventually enables the managed ForwardingGate inside the
structural transaction.

Therefore stack affinity must be fully and freshly confirmed **before** that activation point.
The current lower driver does not yet have:

- authoritative nft owner observation;
- authoritative RPDB owner observation;
- exact actual-vs-desired comparison;
- guarded create/update/delete convergence;
- cleanup/drift handling;
- composition into the same containment transaction.

Wiring a blind create after or around activation would violate the existing ownership and
fail-closed model. This is the next implementation gate.

## Suspicious reverse-engineered requirements for human discussion

Per current project guidance, these are **not automatically rewritten in this cycle**.

### A. Semantic suspects

These look materially shaped by existing code/model rather than being obviously forced by the
user-level ancestor promise.

1. **`VPNG0002-R2.R1.R2`** — the exact symmetric rule
   “ordinary NEW selects Profile by remote destination; VPN NEW selects Profile by remote
   source restricted by ingress Device/path”.
   - The inbound ingress restriction is useful and currently prevents one VPN from shadowing
     another.
   - However the exact Profile/source-prefix classification contract may be an implementation
     model reconstructed from code.
   - Discussion needed: what is the simplest user-level obligation from which this exact
     classification follows?

2. **`VPNG0002-R2.R2.R2`** — “Profile intent is Device-level; concrete paths arise only from
   bindings”.
   - The safety property “do not guess a path” is strong.
   - The specific Profile/Device/binding formulation looks architectural.
   - Discussion needed: retain as product requirement, move/lift into implementation-quality
     requirements, or leave the user-level requirement only as “runtime discovery may not
     expand the allowed channel set”.

### B. Placement/Purpose suspects

Their semantics may be valid or explicitly accepted, but their current `Purpose` uses
vocabulary not introduced by ancestor Statements and therefore fails the strengthened
requirement-gate test.

1. **`VPNG0002-R2.R1.R1`** — Purpose first introduces `Profile`.
2. **`VPNG0002-R2.R1.R2`** — Purpose relies on “Profile destination semantics” introduced by
   a sibling, not an ancestor.
3. **`VPNG0002-R2.R2.R1`** — Purpose first introduces Profile/user-described VPN resources.
4. **`VPNG0002-R2.R2.R2`** — Purpose first introduces Profile/Device/binding.
5. **`VPNG0002-R2.R3.R3`** — Purpose first introduces Profile under the generic direction
   branch.
6. **`VPNG0002-R2.R3.R3.R1`** — Purpose introduces host routing, Linux capability and the
   managed boundary under a user-direction branch.
7. **`VPNG0002-R2.R3.R1.R1`** — Purpose introduces the isolated routing domain/host-boundary
   mechanism below the user-level ordinary-to-VPN direction requirement.
8. **`VPNG0002-R2.R5.R1`** — Purpose first introduces Profiles under the generic
   deterministic-overlap requirement.

Notes:

- the **semantics** of host bootstrap, host stateful return, `+route-return`, the Release-1
  multi-path inbound constraint and most-specific routing have been explicitly discussed with
  the project holder; their appearance here does not mean those decisions are being revoked;
- the finding is that some current tree positions/Purposes may reflect reverse-engineered
  implementation structure rather than clean causal ancestry;
- `VPNG0002-R2.R6` is not in this suspect list: its user-level wording was explicitly
  corrected and accepted in this cycle.

## Requirement-state inventory

Current normative tree contains six `decomp` link occurrences, all resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` (two occurrences);
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` (two occurrences);
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Current active state:

- pending `decomp`: **none**;
- active `unreal`: **none**;
- active `[rejected_closure]`: **none**.

## Remaining gate / next development unit

The next bounded unit should implement the affinity owner as an authoritative managed-stack
resource:

1. observe the reserved affinity nft table and exact RPDB priority/mark/table keys;
2. classify absent / exact / stale / conflicting state;
3. converge only under confirmed ForwardingGate=DISABLED;
4. verify exact postconditions;
5. compose convergence before structural forwarding activation;
6. clean the owner during stop/restart and retain fail-closed ownership on cleanup failure;
7. add a production-shaped privileged scenario that runs the actual lower backend rather than
   the hand-written EXP-061 commands.

Only after that unit should alpha/runtime claim `VPNG0002-R2.R6` end-to-end materialization.

## Cycle conclusion

The original concern was valid: host-side return steering can be perfectly correct and still
lose the selected VPN channel when the reply re-enters the managed stack.

EXP-061 demonstrates the failure and the Linux mechanism that fixes it. The resulting Release-1
design preserves the original inbound routing domain without weakening most-specific NEW-flow
classification.

No Release-2 multi-path claim was made.
