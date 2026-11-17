# VPN-GATE NG3 — requirement-driven development and VPN evidence sequencing review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-requirements-development-evidence-35m`

## Scope

Review four linked changes:

1. strengthen the generic requirements model so a derived Requirement `Purpose` must correlate
   with its immediate parent;
2. require substantial development/experiments to be driven by accepted R/C rather than
   becoming independent sources of product semantics;
3. introduce the `broken` causal link for an R/C invalidated by other accepted R/C, distinct
   from `unreal` and `[rejected_closure]`;
4. add an NG3 development/evidence branch that gates bounded-VPN lifecycle work behind
   EXP-049 and then requires a separate lifecycle/aggressive-config experiment (EXP-050).

## Verdict

**PASS.**

No product lifecycle ownership semantics are accepted by this review. The review establishes
the development/evidence sequence required before such a decision.

## Finding F1 — derived Purpose must be locally causal

The generic model now requires a derived `Purpose` to explain why the child `Statement` is
necessary or materially contributes to the **immediate parent Statement**.

A distant ancestor or generally desirable outcome is insufficient.

The added counterfactual check is:

> if the immediate parent is mentally removed, would the same Purpose still independently
> justify the child?

If yes, the node placement must be reconsidered.

This prevents requirement trees whose hierarchy is syntactic while their "зачем" chains are
causally unrelated.

## Finding F2 — substantial development is requirement-driven

Both `design/requirements-model.md` and `CONTINUOUS-DEVELOPMENT.md` now make the direction
explicit:

```text
accepted R/C
    -> unresolved implementation/evidence question
    -> development or experiment
    -> evidence
    -> requirement/architecture decision
```

An interesting mechanism or experiment is not independently sufficient reason to develop it.

Before a non-trivial implementation/experiment/evidence unit starts, the project must identify
the exact accepted R/C whose implementation, verification or closure requires that work.

## Finding F3 — `broken` is a separate normative-causality state

Canonical form:

```text
[broken: <R/C-ID>, <R/C-ID>, ...]
```

Meaning:

the target R/C itself is no longer a correct normative decision because the listed accepted
R/C broke its premise or made preserving that rule semantically wrong.

Distinction:

- `decomp` — further decomposition lacks sufficient semantics;
- `unreal` — the target Requirement remains desired but is impossible under the causal R/C;
- `broken` — the target R/C itself must be repaired/replaced/removed;
- `[rejected_closure]` — one architecture closure candidate failed acceptance.

An active `broken` node cannot remain `[pending_closure]` or `[closed]`, and future
review/checkpoint inventories must list active `broken` links explicitly.

## Finding F4 — current VPN provisioning constraint is not broken

`VPNG0001-R1.R3.C1` says that Release-1 VPN **provisioning and VPN-specific configuration**
remain administrator responsibilities.

That remains consistent with the current discussion and is therefore not marked `broken`.

The previously written architecture statement that "external VPN channel lifecycle remains
administrator/integration-owned under C1" was an unsupported extrapolation: C1 does not say
that.

The architecture has been corrected. Process lifecycle ownership for a VPN executing inside
the managed domain is now explicitly evidence-gated rather than inferred from C1.

## Finding F5 — new development requirement branch is correctly rooted under R7

Added:

### `VPNG0007-R7.R7`

Purpose correlates with `R7`: safe, maintainable development requires implementation and
experiments not to become independent sources of semantics.

Statement requires every substantial development/evidence unit to have an exact R/C trace and
an expected evidence/review result.

### `VPNG0007-R7.R7.R1`

Purpose correlates with `R7.R7`: requirement-driven integration work must not build lifecycle,
ownership or safety mechanisms on an unproven basic applicability assumption.

Statement gates dependent in-stack VPN integration work on PASS evidence required by
`VPNG0001-R1.R3.C1.R1.R1` / EXP-049.

### `VPNG0007-R7.R7.R1.R1`

Purpose correlates with `R7.R7.R1`: after basic applicability is proven, one clean launch is
still insufficient evidence for a lifecycle/ownership decision.

Statement requires a separate experiment covering:

- start;
- stop;
- restart with unchanged VPN-specific config;
- restart with changed VPN-specific config;
- fresh-state independence from the previous runtime generation;
- aggressive VPN-specific configuration attempting route/RPDB/NAT/firewall/sysctl or other
  network mutation inside the managed domain.

The branch adds development/evidence obligations, not final runtime ownership semantics.

## Finding F6 — EXP-050 is correctly dependent on EXP-049

Created:

`design/experiments/EXP-050 NG3 bounded VPN lifecycle applicability/README.md`

Status:

**BLOCKED — execute only after EXP-049 PASS.**

EXP-050 consumes the exact implementation/version and onboarding mechanism that passed
EXP-049. If EXP-049 fails, the project must revisit the affected integration assumptions
before lifecycle experimentation.

This prevents "solving" lifecycle for an integration that has not first been shown usable in
the stack at all.

## Finding F7 — aggressive configuration is an evidence subject, not pre-decided semantics

EXP-050 deliberately distinguishes:

- administrator-supplied VPN-specific configuration;
- VPN-GATE-owned managed-domain network policy;
- external infrastructure outside the managed domain.

It includes hooks/equivalent mechanisms that attempt to mutate routes, RPDB, NAT/firewall,
sysctl or other network state inside the managed domain.

The experiment records where such effects execute, how current ownership/guards react, whether
safety can be bypassed, and what must later be prohibited, externalized or documented.

It does not yet claim that equivalent external NAT/forwarding belongs in Device/Profile
configuration.

## Finding F8 — existing bounded stop remains scoped, not falsely generalized

The current controller stop proof remains valid for currently implemented VPN-GATE-owned
resources.

It must not be cited as evidence that a real supported in-stack VPN process can always be
cleanly terminated or that administrator-only process lifecycle is sufficient.

That question is now explicitly downstream of EXP-049 -> EXP-050.

## Architecture closure

Exact architecture references now exist:

- `VPNG0007-R7.R7` — architecture-wide requirement-driven development rule;
- `VPNG0007-R7.R7.R1` — dependent bounded-VPN lifecycle evidence gate;
- `VPNG0007-R7.R7.R1.R1` — EXP-050 lifecycle/aggressive-config evidence gate.

The three new requirements may therefore move from `[pending_closure]` to `[closed]` after
this PASS review. Their closure means the development/evidence plan is accepted; it does not
mean EXP-049 or EXP-050 has executed.

## Accumulated requirement-state inventory

### `decomp`

Six accumulated links, all resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1` (two referencing nodes);
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2` (two referencing nodes);
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Open evidence gates

- EXP-049: **PLANNED/PENDING execution**;
- EXP-050: **BLOCKED on EXP-049 PASS**.

## Human decisions required

**none for this review.**

The user already selected the methodological changes and evidence ordering. The later
bounded-VPN lifecycle/ownership semantics remain intentionally undecided pending evidence.

## Next logical unit

The next executable integration evidence unit is still **EXP-049**.

Do not implement a bounded-VPN process manager or process-control semantics merely to prepare
for EXP-050 before EXP-049 passes.

## Conclusion

**PASS.**

The project now has a requirement-rooted and causally ordered development path:

```text
R7 requirement-driven development
    ->
EXP-049 basic real-VPN in-stack applicability
    ->
EXP-050 lifecycle + changed-config + aggressive-config evidence
    ->
bounded-VPN lifecycle/ownership requirement decision
    ->
implementation
```
