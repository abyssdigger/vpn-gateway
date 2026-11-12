# Production implementation review 23 — RPDB JSON prefix parsing

Date: 2026-11-12

Role: external expert review focused on iproute2/netlink representation, exact RPDB
verification, fail-closed parsing and Rust migration.

## Scope

Reviewed:

- live production-cycle failure in RPDB verification;
- current iproute2 `iprule.c` JSON rendering contract;
- `environment.py::_parse_rule_network()`;
- RPDB parser regression tests.

## Finding

### F1 — iproute2 rule JSON separates address and prefix length

Severity: HIGH / kernel-boundary correctness.

The original parser treated a bare JSON `dst`/ `src` address as a host prefix. Current
iproute2 emits non-host rule prefixes as separate fields, for example:

    "dst": "198.51.100.0"
    "dstlen": 24

and equivalently `src` + `srclen`.

The full disposable production-cycle exposed the defect exactly: desired /24 was observed
as /32 and final verification correctly failed closed.

Disposition: fixed.

## Corrected contract

- `all` / absent source or destination means no selector;
- bare address + explicit len field becomes that exact prefix;
- bare address without len is host /32;
- explicitly prefixed alternate rendering is accepted;
- if an explicit prefix and separate len are both present, they must agree;
- malformed/non-strict IPv4 prefixes fail parsing rather than being normalized loosely.

## Test coverage

Rootless tests now cover:

- source /24 via `src` + `srclen`;
- destination /24 via `dst` + `dstlen`;
- host destination with omitted len -> /32;
- conflict between embedded prefix and separate length -> parse error.

## Rust-alignment review

The parser now mirrors the actual wire/renderer representation explicitly rather than
depending on IPv4Network's host-prefix default. A Rust port can map the pair
(address, prefix_len) directly to a checked Ipv4Net value.

## Verdict

Approved after F1 correction. No remaining recommendation in RPDB parsing scope.
