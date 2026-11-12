# Production implementation review 18 — Draft 5 firewall envelope and NAT materialization

Role: external expert review focused on cumulative firewall policy, existing-flow
restriction, NAT scope, iptables representability and Rust migration.

## Scope

Reviewed Draft 5 envelope/NAT contract, `firewall_state.py`, `nat_state.py`, unit tests
and privileged firewall integration harness.

## Findings

### F1 — runtime assert in envelope chain materialization

A chain lookup used `assert envelope is not None`. The invariant is structural, but
assertions disappear under optimized Python and are an inconsistent production error
boundary.

Severity: low, robustness.

Disposition: fixed with explicit ValueError.

## Firewall review

- envelope jumps occur before ESTABLISHED/RELATED and Profile NEW verdicts;
- envelope allow is RETURN, never ACCEPT;
- envelope drop is DROP;
- first-match rule order is preserved;
- terminal default exists independently for from/to chains;
- only bound interfaces jump through Device chains;
- TCP/UDP port lists expand to ordinary contiguous rules rather than relying on multiport
  entry limits;
- specific Profile deny ordering remains intact after envelope traversal.

Thus Device envelope can narrow both existing and NEW traffic without widening Profile
direction.

## NAT review

- production NAT is derived only from explicit Device.nat;
- none produces no translation rule;
- masquerade expands only to current bound interfaces;
- each rule is additionally restricted to remote prefixes of enabled Profiles referencing
  that Device;
- disabled/unreferenced Devices and over-quota interfaces receive no NAT state;
- historical all-egress MASQUERADE provider remains clearly named experimental and is not
  used as production config semantics.

## Kernel evidence

The existing privileged filter round-trip harness now contains a real user envelope chain
and TCP dport match. NAT uses the same iptables restore/save transaction boundary; a
dedicated NAT integration extension should remain in the kernel-integration job before
final release.

## Rust-alignment review

Envelope/NAT compilation is a pure typed-policy -> desired-state transformation. Backend
execution remains separate. The chain RETURN/DROP model maps directly to nftables/verdict
abstractions if the Rust implementation later changes backend.

## Verdict

Approved after F1 correction. Source semantics have no remaining recommendation. Final
kernel-integration evidence must include the config-derived NAT table.
