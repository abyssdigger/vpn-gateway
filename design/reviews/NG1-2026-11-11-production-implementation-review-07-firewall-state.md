# Production implementation review 07 — generated Profile-direction filter state

Role: external expert review focused on stateful firewall semantics, overlapping prefixes,
shared Devices, unbound-interface isolation and Rust migration.

## Scope

Reviewed `firewall_state.py`, `firewall_intent.py`, filter-state tests and Draft 4
§5.4/invariants 32–34/61.

## Findings

No corrective finding remains.

## Whole-scope observations

- FORWARD policy is DROP.
- INVALID is rejected first.
- The future Device-envelope restriction block has an explicit reserved location before
  generated ACCEPT rules.
- ESTABLISHED/RELATED is not globally accepted: it is scoped to host0 <-> currently bound
  interfaces, preserving over-quota/unbound isolation.
- NEW policy expands Device-scoped intents only to bound interfaces.
- Explicit DROP is materialized for the non-allowing Profile direction.
- Longest-prefix order survives Device->interface expansion, so the Draft 4 overlap
  counterexample remains fail-closed.
- With zero bound interfaces no ACCEPT rule exists.

The current stateful model allows an already-established conntrack flow to continue while
its concrete interface remains bound. That is consistent with Draft 4 wording
"ESTABLISHED,RELATED traffic belonging to an admitted flow"; restrictive future Device
envelope rules remain positioned ahead of this acceptance and can terminate such traffic.

## Rust-alignment review

Firewall generation is a deterministic pure transformation to a complete owned-table
representation. It does not embed subprocess execution or parse shell text. This is a
good boundary for later replacement by nftables or a Rust netfilter backend if desired.

## Verdict

Approved. No recommendation remains in this scope.
