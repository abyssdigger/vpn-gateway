# NG1 blocker — bootstrap/instance human-facing configuration grammar

Status: **OPEN SYNTAX BLOCKER; normalized InstanceConfig is implemented independently**

Architecture baseline: NG1 Draft 4.

The architecture already fixes the semantics:

- ROU owns one namespace and one host-facing veth pair;
- link addressing is bootstrap/instance configuration;
- addressing is stable across ordinary restarts;
- changing it is an explicit bootstrap configuration change;
- router Device/Profile configuration does not contain infrastructure link addresses.

What remains unresolved is only the human-facing storage/CLI grammar: file location,
instance naming/layout, namespace/link-name override fields and systemd template binding.

Implementation therefore uses a typed normalized `InstanceConfig` and does not guess a
TOML surface. Lifecycle, verification, Planner and integration tests can proceed against
that normalized object.

Resolution requires a small configuration-design pass; no kernel experiment is required.
