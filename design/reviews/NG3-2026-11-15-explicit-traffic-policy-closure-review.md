# VPN-GATE NG3 — Explicit Traffic Policy Closure Review

**Cycle:** `ng3-design-cycle-20261115-managed-domain-contract-40m`  
**Scope:** `VPNG-R2` explicit traffic policy semantics and normalized architecture contract.

## Requirement result

The policy tree requires independently:

- managed traffic membership;
- explicit eligible VPN path set;
- explicit direction permissions;
- no implicit admission from runtime/availability state;
- deterministic resolution or rejection of ambiguity.

Direction semantics are refined into:

- ordinary network -> VPN;
- VPN -> ordinary network;

with independent permission.

## Architecture result

The configuration boundary produces:

```text
PayloadPolicyIntent:
    traffic_selector
    direction_permissions
    allowed_path_ids
    configured_preference
```

`PayloadPolicyCalculator` is pure and derives structural payload policy from that normalized
intent.

Availability is applied only after structural membership/eligibility has been established and
may alter effective ordering only.

## Closure decisions

### VPNG-R2.R1 — traffic membership

**Verdict:** ACCEPT CLOSURE.

`traffic_selector` is the sole normalized source of traffic membership. The exact external
selector syntax is an interface implementation detail.

### VPNG-R2.R2 — path eligibility

**Verdict:** ACCEPT CLOSURE.

`allowed_path_ids` explicitly defines the eligible logical VPN paths. Availability and
configured preference cannot add membership.

### VPNG-R2.R3 / R1 / R2 — direction

**Verdict:** ACCEPT CLOSURE.

`direction_permissions` independently represents both product directions. Permission in one
direction does not imply the other.

### VPNG-R2.R4 — no implicit VPN admission

**Verdict:** ACCEPT CLOSURE.

The architecture applies availability only as a priority modifier after structural policy.
A working/recovered VPN path does not create permission or traffic membership.

### VPNG-R2.R5 — deterministic resolution

**Verdict:** ACCEPT CLOSURE.

The configuration boundary rejects declarations that cannot produce one deterministic
semantic result, and the pure policy Calculator cannot use hidden runtime history to resolve
ambiguity.

### VPNG-R2 parent

**Verdict:** ACCEPT CLOSURE.

The normalized intent plus policy Calculator fully answer how a user-visible policy is
represented architecturally without choosing the final textual/API syntax.

## Simplification review

No policy Engine separate from `PayloadTrafficManager` is required.

No availability-aware structural policy object is introduced.

No universal rule language or generic ACL framework is justified by the accepted
requirements.

## Important separation

```text
PayloadPolicyIntent
    -> structural membership / direction / allowed paths / preference

availability state
    -> effective ordering among already allowed paths
```

The two are intentionally separate contracts.

## Verdict

**PASS.**

Accept closure for the complete current `VPNG-R2` subtree.
