# Production implementation review 03 — kernel desired state and verifier

Role: external expert review focused on Linux route/RPDB semantics, false drift detection,
fail-closed ownership and Rust-oriented modeling.

## Scope

Reviewed:

- `kernel_state.py`
- `test_kernel_state.py`
- `environment.py` parser types consumed by verification
- Draft 4 route/fallback/RPDB invariants
- iproute2 JSON serialization behavior for route table/protocol fields.

## Findings

### F1 — iproute2 numeric table/protocol fields are string-rendered

The desired state uses numeric table IDs and numeric route protocol tags. Current
iproute2 route JSON prints those fields through name/string conversion; unknown numeric
values can therefore arrive as strings such as `"313"` and `"202"`.

Without normalization:

- numeric custom table IDs could be rejected by the parser;
- route protocol `"202"` would not compare equal to desired integer `202`;
- verifier would report false drift on correct kernel state.

Severity: high for verification correctness.

Disposition: fixed in `environment.py` by normalizing decimal strings to integers for
table and protocol fields. Regression test now uses string-form numeric table/protocol.

## Whole-scope review

- Profile tables are verified as exclusive complete owned state.
- RPDB rules are verified exactly in the owned priority window.
- main/local/default state outside the owned window is intentionally tolerated.
- UNAVAILABLE single-member fallback becomes one direct route at 65535.
- multi-member fallback becomes one equal-cost direct-device route.
- terminal blackhole remains in every Profile table.
- terminal host0 RPDB action is explicit `unreachable`, allowed by Draft 4's
  blackhole/unreachable requirement.

No additional architectural inconsistency or unnecessary abstraction was found.

## Rust-alignment review

Desired/observed types are structural value objects and verification is a pure set
comparison over normalized semantic keys. This is a good Rust migration shape and avoids
string-command comparison as a source of truth.

## Verdict

Approved after F1 correction. No recommendation remains in this scope.
