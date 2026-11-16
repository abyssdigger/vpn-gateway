# Production implementation review 15 — Draft 5 router config/domain

Role: external expert review focused on strict config boundaries, normalized domain
invariants, security-sensitive defaults, representability and Rust migration.

## Scope

Reviewed Draft 5 configuration proposal, `domain.py`, `config.py` and config tests.

## Findings

### F1 — normalized Device still had an implicit NatMode.NONE constructor default

Although TOML parsing required `nat`, direct/internal construction of an enabled Device
could silently inherit no-NAT. That contradicted the Draft 5 rule that enabled Device NAT
is explicit.

Severity: medium, cross-boundary semantic consistency.

Recommendation: normalized enabled Device must reject missing NatMode. Disabled
placeholders may retain `None`.

Disposition: fixed. Manual test fixtures are being converted to explicit
`NatMode.NONE`.

### F2 — envelope port disjointness lived only in the TOML parser

The parser rejected overlapping source/destination port ranges, but a directly constructed
TrafficEnvelopeRule could violate that normalized invariant.

Severity: low/medium, domain integrity/Rust migration.

Recommendation: enforce disjoint ranges in the value object as well; retain parser checks
for precise source-location errors.

Disposition: fixed.

## Whole-scope review

- schema_version=1 is mandatory and boolean/other versions are rejected;
- enabled Devices require expected interfaces and explicit NAT;
- publications normalize to protocol plus inclusive PortRange pairs with equal cardinality;
- active external publication collisions are rejected;
- internal target collisions across active Devices are rejected while same-Device aliases
  remain possible;
- traffic envelope is typed immediately into direction/action/protocol/CIDR/port-range
  values;
- ports require TCP/UDP;
- disabled placeholders preserve shallow-validation semantics;
- exact duplicate Profile destinations and active selector overlap rules remain intact.

## Rust-alignment review

The normalized objects are enum/value-struct shaped and no TOML syntax survives beyond the
parser. Value-level invariants now cover the meaningful port/NAT constraints rather than
depending solely on parser call paths.

## Verdict

Approved after F1/F2 corrections. No remaining recommendation in router config/domain
scope.
