# Production implementation review 01 — EnvironmentSnapshot collector

Role: external expert review focused on Linux networking correctness, Rust-oriented Python
structure, fail-closed behavior and consistency with NG1 Draft 4.

## Scope

Reviewed:

- `environment.py`
- `test_environment_live.py`
- existing DeviceEngine/environment interfaces
- Draft 4 invariants relevant to fresh observation, ifindex identity, rp_filter and IPv6.

## Findings

### F1 — sequential observation could mix two interface generations

The first implementation collected link/address/route/rule/sysctl state sequentially and
returned it without checking whether interface identity changed during the collection.
That could combine addresses/routes from one `(ifname, ifindex)` generation with another.

Severity: medium, correctness.

Recommendation: bracket collection with ordered `ip -j link show` snapshots and reject
the observation if the interface identity/order differs.

Disposition: fixed.

### F2 — address observation verified ifname but not ifindex

`ip -j addr` output was associated with the link snapshot by interface name only. A
same-name/new-ifindex replacement during collection could therefore be accepted as the
old identity.

Severity: medium, correctness.

Recommendation: when `ifindex` is present in address JSON, require exact agreement with
the link snapshot.

Disposition: fixed.

### F3 — namespace prerequisite observation was incomplete

Only global forwarding sysctls were observed. Draft 4 also makes per-interface
`rp_filter` and IPv6 disable state part of the safety boundary.

Severity: medium, verification completeness.

Recommendation: observe per-interface `rp_filter` and `disable_ipv6` for every
currently observed interface.

Disposition: fixed using direct `/proc/sys` reads inside the namespace so interface
names containing dots are not ambiguous in sysctl dotted syntax.

## Rust-alignment review

The code uses immutable dataclasses as value objects, explicit parser errors, injected
command execution and no hidden global mutation. This maps cleanly to future Rust structs,
Results and trait-injected command backends.

The collector returns either one complete snapshot or an error; no partial-success object
escapes. This is the correct fail-closed boundary.

## Verdict

No remaining recommendation in this scope. EnvironmentSnapshot collection is approved as
the production observation foundation.
