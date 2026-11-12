# Production implementation review 09 — NAT policy gate

Role: external expert review focused on preventing prototype behavior from silently
becoming production policy.

## Scope

Reviewed the Draft 4 NAT wording, v0 MASQUERADE behavior, NAT blocker document,
`nat_state.py`, `nat_kernel.py` and tests.

## Findings

No corrective finding remains.

The architecture does not define production NAT scope or configuration. The implementation
correctly refuses to infer it:

- `UnresolvedNatProvider` is the production default gate;
- `ExplicitNoNatProvider` supports explicitly routed/integration environments;
- `ExperimentalMasqueradeAllBoundProvider` preserves v0-compatible plumbing for tests
  without claiming normative production semantics;
- kernel apply/verify is generic over normalized NatDesiredState.

The experimental provider name and docstring are sufficiently explicit to prevent accidental
promotion to normative config semantics.

## Rust-alignment review

NatProvider is trait-shaped and decouples normalized policy from iptables realization.
Future TOML design can populate a Rust enum/provider without changing Planner ownership.

## Verdict

Approved. Production NAT remains an explicit design blocker, isolated so all other
implementation can continue.
