# Production implementation review 14 — normalized ROU instance lifecycle

Role: external expert review focused on Linux namespace/veth lifecycle, structural
verification, fail-closed bootstrap, consistency with TrafficEngine and Rust migration.

## Scope

Reviewed `instance_lifecycle.py`, normalized config tests, disposable-netns integration
harness and Draft 4 bootstrap/link invariants.

## Findings

### F1 — configurable inner interface contradicted the current TrafficEngine contract

The first normalized InstanceConfig allowed an arbitrary inner veth name while routing and
firewall production code currently uses the semantic internal role `host0`. Such a
configuration could bootstrap successfully but never match Profile RPDB/filter policy.

Severity: high, cross-module consistency.

Recommendation: until an explicit interface-role refactor propagates the name through all
TrafficEngine objects, require `inner_if == "host0"`.

Disposition: fixed.

### F2 — ordinary subnet usable-address validation incorrectly rejected /31

The first validation rejected network/broadcast addresses for all prefix lengths. RFC3021
/31 links use both addresses as endpoints and are valid for this point-to-point veth
contract.

Severity: medium, representability.

Disposition: fixed; network/broadcast rejection applies only through /30. /31 is tested.

### F3 — create verification did not verify all sysctls it applied

Bootstrap set rp_filter/IPv6 prerequisite state but `verify_instance()` initially checked
only `ip_forward=0`.

Severity: medium, verification completeness.

Recommendation: reuse the production EnvironmentSnapshot and namespace-prerequisite
verifier before declaring create success.

Disposition: fixed.

### F4 — interface absence probe must distinguish missing from inspection failure

A bare nonzero return from `ip link show` was initially interpreted as "absent". That
could turn permission/tool failures into an attempted create.

Severity: medium, safety.

Disposition: fixed. Known not-found diagnostics map to absence; other inspection failures
are fatal.

## Whole-scope review

- existing namespace or host link is never adopted;
- create is fail-closed and cleans up owned resources on failure;
- host/inner interfaces are structurally verified as veth and UP;
- exact IPv4 address/prefix pairs are verified;
- underlay default route is verified;
- full namespace prerequisite state is verified;
- teardown closes forwarding before deleting namespace resources and verifies absence;
- host routing/firewall outside the owned veth is untouched.

A real disposable-netns lifecycle test is wired into the privileged CI job. Source design
is approved; that job is the kernel proof gate.

## Rust-alignment review

InstanceConfig is a typed normalized object, lifecycle execution is argv-based, and
human-facing syntax is deliberately separated. This maps well to a Rust config struct plus
privileged lifecycle backend.

## Verdict

Approved after F1–F4 corrections, subject to the disposable-netns CI gate.
