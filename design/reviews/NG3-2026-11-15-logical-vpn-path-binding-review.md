# VPN-GATE NG3 — Logical VPN Path Binding Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** logical VPN path identity, current endpoint binding, and runtime verification.

## Review questions

1. Can VPN-GATE distinguish a product-level VPN path from the transient runtime endpoint that currently realizes it?
2. Can the architecture verify that a concrete endpoint is the current endpoint for the intended logical path without defining the final user configuration syntax?
3. Does endpoint replacement invalidate the old runtime object cleanly?
4. Does this unblock managed-domain endpoint verification and administrator onboarding without inventing a configuration schema?

## Requirement result

The product semantics are now:

- `VPNG-R1.R3.R1` — a VPN path has stable logical identity for its configuration lifecycle;
- `VPNG-R1.R3.R2` — use requires one unambiguous current binding from logical path to concrete endpoint;
- `VPNG-R1.R3.R3` — replacement creates a new current binding and supersedes the old endpoint.

These requirements do not prescribe YAML fields, interface names or discovery mechanisms.

## Architecture result

The architecture introduces one narrow `VPNPathAdapter` Machinery boundary.

It accepts:

```text
logical_path_id
+
normalized_binding_intent
```

and observes whether exactly one concrete endpoint currently matches the binding inside the managed network domain.

Possible semantic outcomes include:

- matched current endpoint;
- absent;
- ambiguous;
- wrong managed domain;
- structurally unusable.

The Adapter does not provision VPN, choose routing policy, decide availability health or define the user-facing config schema.

## Closure decisions

### VPNG-R1.R3.R1

**Verdict:** ACCEPT CLOSURE.

The architecture distinguishes stable logical path identity from transient runtime endpoint identity. No further architecture decision is required at this level.

### VPNG-R1.R3.R2

**Verdict:** ACCEPT CLOSURE.

The `VPNPathAdapter` contract provides the required single current binding and explicitly rejects absent/ambiguous/mismatched bindings.

### VPNG-R1.R3.R3

**Verdict:** ACCEPT CLOSURE.

The binding contract treats endpoint replacement as a change of current concrete endpoint under the same logical path identity and does not return superseded endpoints as current.

### VPNG-R4.R6.R1.R4

**Verdict:** ACCEPT CLOSURE.

The previously unresolved "expected identity" part is now answered by `VPNG-R1.R3.R2`: the endpoint must match the normalized binding intent for the logical path.

The architecture can therefore verify both:

- placement in the correct managed domain;
- identity/binding before use.

Its decomposition link correctly records the resolved dependency:

```text
[decomp: VPNG-R1.R3 -> VPNG-R1.R3.R2]
```

### VPNG-R1.R3.C1.R1

**Verdict:** STILL OPEN.

Two earlier blockers are resolved:

```text
[decomp: VPNG-R4.R6 -> VPNG-R4.R6.R1]
[decomp: VPNG-R1.R3 -> VPNG-R1.R3.R2]
```

The remaining blocker is now exactly the declarative-operation requirement:

```text
[decomp: VPNG-R1.R2 -> pending]
```

The product knows what must be represented internally, but administrator instructions still cannot say how to express the binding until the declarative configuration boundary is decomposed.

## Simplification review

The `VPNPathAdapter` is justified as a separate Adapter because it crosses a different semantic boundary from `NetworkPolicyAdapter`:

- `VPNPathAdapter`: externally provisioned endpoint -> verified logical VPN path binding;
- `NetworkPolicyAdapter`: desired payload/network policy -> lower network-policy domain.

Merging them would couple external channel identity to route/policy materialization without a requirement.

No Manager/Agent is introduced because binding observation does not yet require an autonomous lifecycle or event loop.

No registry, discovery service, persistent binding database or generic plugin framework is justified.

## Closure/evidence semantics

This review itself is sufficient acceptance evidence for the architectural separation and contracts above. No kernel claim is being accepted here beyond the already-selected managed-domain placement.

Future implementation evidence will still be required to prove the Adapter behaves according to the accepted contract.

## Verdict

**PASS.**

Accept architecture closure for:

- `VPNG-R1.R3.R1`;
- `VPNG-R1.R3.R2`;
- `VPNG-R1.R3.R3`;
- `VPNG-R4.R6.R1.R4`.

Keep `VPNG-R1.R3.C1.R1` open and blocked on `VPNG-R1.R2`.

The next requirement-first unit should decompose only the declarative configuration boundary necessary to express the normalized binding intent and other already-accepted product policy, without designing a universal configuration framework.
