# NG1 production configuration resolution — external review

Role: external expert review focused on policy ownership, firewall composability, transport
publication safety, configuration evolution and Rust migration.

## Scope

Reviewed the proposal resolving Draft 4 deferred surfaces:

- router schema version;
- Device NAT policy;
- publication grammar;
- traffic-envelope grammar/materialization;
- instance/bootstrap grammar.

## Findings

### F1 — internal publication endpoint ownership must be unambiguous across Devices

The first proposal rejected external socket overlap but did not reject two active Devices
mapping to the same internal protocol/port on the common host0 address. That would make
Device ownership of one listener ambiguous and would normally imply conflicting server
binds.

Severity: medium, ownership/config correctness.

Recommendation: reject internal target range overlap for the same protocol across
different active Devices. Allow multiple external aliases to the same internal endpoint
inside one Device.

Disposition: fixed in the proposal.

### F2 — instance ID grammar must be explicit

The instance ID is not stored inside the file, but it is used in paths/systemd template
arguments. Leaving its grammar unspecified would recreate the escaping ambiguity already
avoided for Device/Profile IDs.

Severity: low/medium, deployment correctness.

Recommendation: use the existing opaque ID grammar
`[a-z0-9][a-z0-9-]*`.

Disposition: fixed.

## Policy ownership review

### NAT

Device scope is the least surprising first-production model:

- Profile does not model trusted local source prefixes;
- host source admission remains BOU-owned;
- the tunnel/remote domain is the resource that determines whether translated source
  addressing is required;
- shared Profiles cannot disagree about one concrete egress tunnel.

Requiring explicit `none|masquerade` prevents prototype MASQUERADE from becoming a
silent default. Restricting MASQUERADE rules to remote prefixes of enabled Profiles using
the Device is narrower than v0's egress-wide rule and is preferable.

### Traffic envelope

The proposed chain semantics are correct and preserve Draft 4 cumulative policy:

- envelope DROP -> DROP;
- envelope allow -> RETURN, never ACCEPT;
- terminal allow -> RETURN;
- terminal drop -> DROP;
- envelope traversal occurs before ESTABLISHED/RELATED and generated NEW verdicts.

This allows an operational Device restriction to terminate existing flows without ever
widening Profile.direction.

### Publications

The adopted ext/protocol->internal grammar is already present conceptually in the
architecture and is suitable as the schema-v1 human form. Explicit instance-level bind
address avoids a hidden wildcard choice.

### Versioning

Mandatory schema_version=1 is preferable to heuristically accepting legacy production
files. The project has no deployed production NG1 config requiring compatibility.

## Rust-alignment review

All proposed surfaces map to enums/value structs rather than free-form strings after parse:
NatMode, TransportProtocol, PublicationRange, EnvelopeRule/PortRange and InstanceConfig.
The parser can stay strict and discard TOML-specific representation immediately.

## Verdict

Approved after F1/F2 corrections. This proposal is suitable to promote to NG1 Draft 5 and
implement. No remaining recommendation in the reviewed configuration scope.
