# Production implementation review 16 — Draft 5 instance configuration

Role: external expert review focused on bootstrap representability, path/address safety,
deployment semantics and Rust migration.

## Scope

Reviewed `instance_config.py`, normalized `InstanceConfig`, schema-v1 tests and Draft 5
instance invariants.

## Findings

### F1 — namespace length limit was arbitrary

The normalized lifecycle initially limited namespace names to 63 characters even though
that number was not derived from a kernel/network-namespace representability boundary.
This conflicted with the project rule against invented small limits.

Severity: low/medium, representability consistency.

Recommendation: retain the restricted safe character grammar but remove the arbitrary
length cap. Actual filesystem/kernel failure remains a bootstrap error if an extreme name
is not representable on the target.

Disposition: fixed.

### F2 — publication bind address classes

The parser accepts any syntactically valid IPv4 address, including wildcard 0.0.0.0.
Rejecting multicast/broadcast pre-emptively would add policy beyond the stated contract;
actual socket bind semantics are already validated atomically by PublicationSupervisor.
No change recommended for schema v1.

## Whole-scope review

- schema_version=1 is mandatory;
- inner role is fixed host0 through normalized InstanceConfig;
- link addresses are explicit and /31-capable;
- publication bind is explicit;
- router/state paths are absolute and distinct;
- instance ID uses safe opaque grammar and is not duplicated in the file;
- TOML representation is immediately normalized to typed addresses/paths.

## Rust-alignment review

The file parser is a thin TOML boundary over a normalized InstanceConfig/value object.
Path and address validation map directly to Rust PathBuf/Ipv4Addr/Ipv4Net-style types.

## Verdict

Approved after F1 correction. No remaining recommendation in instance-config scope.
