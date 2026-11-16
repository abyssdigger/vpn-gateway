# VPN-GATE NG3 — Managed Network Isolation Review

**Cycle:** `ng3-design-cycle-20261115-isolation-40m`  
**Scope:** isolation requirement, managed-network boundary, VPN-channel onboarding consequence, requirement-management links.

## Review questions

1. Does the requirement describe required product isolation rather than prescribe Linux machinery?
2. Is the "стакан" an architecture choice derived from that requirement?
3. Are consequences for administrator-provisioned VPN channels represented as constraints plus compensating requirements?
4. Are unresolved onboarding details blocked explicitly rather than guessed?
5. Are requirement-maintenance rules sufficient without introducing a separate semantic change journal?

## Findings

### F1 — Isolation requirement is product-facing enough

**Disposition:** accepted.

`VPNG-R4.R6` requires VPN-GATE-owned network state to be isolated from unrelated host network state and to cross the host boundary only through explicit interfaces.

It does not require Linux network namespaces by name.

Therefore the requirement states the security/manageability property, while architecture remains free to choose the minimal mechanism that realizes it.

### F2 — Dedicated network namespace remains architecture

**Disposition:** accepted.

The architecture currently selects a dedicated Linux network namespace as the minimal realization of `VPNG-R4.R6`.

The namespace is not protected by the requirement itself. A later architecture may replace it if another mechanism satisfies the same isolation, ownership and explicit-boundary properties with lower complexity.

This avoids converting current Linux implementation knowledge into product semantics.

### F3 — Isolation creates a real VPN-channel constraint

**Disposition:** accepted.

Once the router data plane is isolated, an administrator-provisioned VPN channel cannot be a fully managed NG3 path merely by existing only in the ordinary host network namespace.

This consequence is represented by:

- `VPNG-R1.R3.C2` — the external channel's data-plane endpoint must be present in the isolated managed network domain;
- `VPNG-R1.R3.C2.R1` — VPN-GATE must provide an onboarding contract that tells the administrator what result must be achieved.

This is an appropriate architecture-derived constraint rather than an invented L1 product capability.

### F4 — Externalized work creates a product obligation

**Disposition:** accepted and generalized.

Both `VPNG-R1.R3.C1` and `VPNG-R1.R3.C2` move work to the administrator.

The requirements model now explicitly requires constraint review to ask:

1. who must compensate for the limitation;
2. what the product must provide so that participant can perform the adaptation correctly and reproducibly.

The compensating requirement may be an instruction, API, configuration contract, validation rule, diagnostic surface or another minimal integration mechanism.

### F5 — Onboarding decomposition is correctly blocked

**Disposition:** accepted.

Current links:

```text
VPNG-R1.R3.C1.R1
  [decomp: VPNG-R4.R6 -> pending]

VPNG-R1.R3.C2.R1
  [decomp: VPNG-R4.R6 -> pending]
```

The current architectural choice of a network namespace is not sufficient to replace `pending`.

The deblocker must be an accepted requirement/constraint in the `VPNG-R4.R6` branch that states enough of the managed-network contract to derive onboarding requirements without guessing Linux commands or deployment shape.

### F6 — Single blocker-state link is sufficient

**Disposition:** accepted.

The decomposition dependency representation:

```text
[decomp: <blocker> -> <pending|deblocker>]
```

is sufficient for the current project stage.

It preserves the original cause of the block while allowing the state to become resolved by a concrete descendant. A later child may still introduce a deeper block.

No separate decomposition event log or dependency state machine is justified.

### F7 — Requirement change journal is deliberately deferred

**Disposition:** accepted.

Stable IDs, Git history, current-tree links and architecture revalidation are sufficient for the current design phase.

A separate semantic requirements change journal would add machinery before there is a demonstrated need to query semantic transitions independently from Git history.

The requirements model now records this explicitly.

## Evidence

Mechanical checks on current branch:

```text
requirement/constraint IDs: 58
active decomposition links: 2
broken architecture references: 0
```

Both active decomposition links point to existing `VPNG-R4.R6` and remain `pending`.

## Verdict

**PASS.**

The managed-network isolation property is separated correctly from its current Linux realization.

The next design unit should decompose `VPNG-R4.R6` only far enough to define the required properties of the managed network domain and its external boundary. It should not specify onboarding commands or VPN-process placement until those properties require them.

A successful descendant of `VPNG-R4.R6` may become the deblocker for one or both current onboarding links.
