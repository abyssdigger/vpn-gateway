# VPN-GATE NG3 — Managed Domain Contract Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** decomposition and architecture closure of `VPNG-R4.R6`, plus consequences for VPN-channel onboarding.

## Review questions

1. Does the decomposition remain about properties of the managed network domain rather than Linux commands?
2. Does the selected Linux architecture satisfy those properties with minimal machinery?
3. Which requirement nodes are now architecture-closed?
4. Which nodes remain open because another requirement branch is still insufficiently decomposed?

## Requirement result

The managed-domain requirement is decomposed into:

- `VPNG-R4.R6.R1` — separate managed network domain with explicit external boundaries and internal VPN endpoints;
- `VPNG-R4.R6.R1.R1` — internal mutable routing/policy state belongs to the managed/boundary domain;
- `VPNG-R4.R6.R1.R2` — traffic crosses the managed-domain boundary only through explicit boundary endpoints;
- `VPNG-R4.R6.R1.R3` — managed VPN data-plane endpoints are internal to the managed domain;
- `VPNG-R4.R6.R1.R4` — external endpoints must be verified before use.

This decomposition does not require a Linux namespace or veth by name.

## Architecture result

For Linux, the current architecture selects:

- one dedicated network namespace as the managed network domain;
- dedicated boundary links instead of ambient host networking;
- a veth-style host/domain link as the minimal default boundary mechanism;
- VPN data-plane endpoints used for managed forwarding inside the managed namespace;
- observation of endpoint presence/domain placement before the endpoint is accepted for use.

The architecture does not yet select the configuration/identity rule that binds a logical VPN path to a concrete endpoint.

## Closure decisions

### VPNG-R4.R6.R1.R2

**Verdict:** ACCEPT CLOSURE.

The explicit-boundary requirement is fully answered at architecture level by a dedicated managed namespace plus dedicated boundary link(s). The exact interface names/addresses are implementation/configuration details and are not required to close this architectural question.

### VPNG-R1.R3.C2.R1

**Verdict:** ACCEPT CLOSURE.

The compensating administrator-facing isolation requirement now has a sufficient architectural result:

> onboarding must leave the VPN data-plane endpoint inside the managed domain, behind the explicit domain boundary.

The concrete administrator document/commands are still implementation/documentation work, but no further architecture decision is needed for the placement result itself.

### VPNG-R4.R6.R1.R4

**Verdict:** NOT CLOSED; no rejection.

The architecture already knows that endpoint placement must be observed before use, but the requirement also says the endpoint must correspond unambiguously to the expected role/identity.

That identity cannot be derived from isolation. It depends on the still-insufficiently decomposed `VPNG-R1.R3` path identity/configuration semantics.

The node therefore correctly carries:

```text
[decomp: VPNG-R1.R3 -> pending]
```

This is not `rejected_closure`: no closure candidate failed acceptance. The architecture is simply partial.

### VPNG-R1.R3.C1.R1

**Verdict:** NOT CLOSED; no rejection.

The previous isolation blocker is resolved:

```text
[decomp: VPNG-R4.R6 -> VPNG-R4.R6.R1]
```

but the administrator instructions cannot be fully specified until the product defines how a configured logical VPN path identifies the externally provisioned channel:

```text
[decomp: VPNG-R1.R3 -> pending]
```

Again, this is an ordinary open decomposition dependency, not a rejected closure.

## Simplification review

No additional Engine is required by this unit.

In particular, this review does not justify:

- a VPN provisioning Manager;
- an onboarding Agent;
- an identity registry;
- a generic resource-discovery subsystem;
- a network-domain lifecycle Manager;
- a universal interface abstraction.

The managed namespace and explicit boundary are architectural environment choices. Existing Managers/Machinery may later use them through contracts once concrete responsibilities are derived.

## Closure-state semantics exercised by this review

This unit demonstrates all of the intended distinctions except rejection:

- architecture may reference an unlabeled/open requirement;
- an architecture reference does not auto-close the requirement;
- closure is accepted only by review;
- a resolved decomposition blocker may be followed immediately by a new lower-level blocker;
- documentation/architectural approach can be sufficient closure even before code exists.

No `rejected_closure` is produced because no proposed closure was tested and found inadequate.

## Verdict

**PASS.**

Accept architecture closure for:

- `VPNG-R4.R6.R1.R2`;
- `VPNG-R1.R3.C2.R1`.

Keep open:

- `VPNG-R4.R6.R1.R4`;
- `VPNG-R1.R3.C1.R1`;

both because path identity/configuration remains insufficiently decomposed under `VPNG-R1.R3`.

The next requirement-first unit should decompose logical VPN-path identity only as far as required to remove that blocker, without inventing a complete configuration schema.
