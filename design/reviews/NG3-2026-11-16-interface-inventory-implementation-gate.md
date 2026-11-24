# VPN-GATE NG3 — Authoritative interface inventory implementation gate

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Review unit:** Linux link-inventory observation boundary for Device binding

## 1. Scope

Implement the minimal Linux-facing observation parser required by the accepted Device binding
projection:

```text
full `ip -j link show` output
    ->
ordered tuple[InterfaceIdentity]
```

This unit does not observe addresses, routes, rules, peers or availability.

## 2. Requirements / constraints

Primary:

- `VPNG-R1.R3.R2`;
- `VPNG-R1.R3.R3`;
- `VPNG-R5.R2`;
- `VPNG-R5.R2.R1`;
- `VPNG-R4.R1`;
- `VPNG-R6.R4`;
- `VPNG-R7.R3.R2`.

Historical evidence:

- EXP-002/002A: interface existence must not be inferred from IPv4-address inventory;
- NG1/RC3: events are wakeups, decisions use fresh authoritative snapshot;
- runtime binding evidence: concrete current identity is `(ifname, ifindex)`.

## 3. Source of truth

For interface presence/identity, the Linux boundary uses the full ordered output of:

```text
ip -j link show
```

It must not use `ip -j -4 addr show` as the interface inventory because an existing
interface may have no IPv4 address and be omitted from that view.

Netlink events are outside this unit and may only trigger a fresh collection.

## 4. Parse contract

Accepted item requires:

- JSON root is an array;
- each item is an object;
- `ifname` is a non-empty string;
- encoded ifname length does not exceed Linux IFNAMSIZ-1 (15 bytes);
- `ifindex` is a positive integer; boolean is not accepted as integer;
- one snapshot contains no duplicate ifname;
- one snapshot contains no duplicate ifindex.

Output preserves authoritative snapshot order exactly.

## 5. Failure semantics

Malformed/untrustworthy inventory raises an observation error.

It must never be normalized to:

```text
interfaces = ()
```

because valid absence and inability to observe are different states.

The caller therefore cannot accidentally turn inventory failure into mass endpoint
disappearance.

## 6. Component boundary

This parser is lower technical machinery inside current `VPNPathAdapter` observation
responsibility.

No new Engine is introduced.

Actual process execution/injected command runner can be added independently; this unit proves
the semantic parse boundary first.

## 7. Simplification review

Not included:

- address/peer/topology facts;
- Netlink subscription;
- polling scheduler;
- retry policy;
- binding state;
- Linux mutation;
- global EnvironmentSnapshot object.

Those need separate requirements/consumers before implementation.

## 8. Evidence plan

Rootless tests:

- preserves input JSON order;
- empty authoritative array is valid empty inventory;
- duplicate ifname rejected;
- duplicate ifindex rejected;
- bool/zero/negative ifindex rejected;
- missing/empty/oversized ifname rejected;
- malformed JSON / non-array root / non-object item rejected;
- same ifname with new ifindex is valid in a **later** separate snapshot, not duplicated within
  one snapshot.

## Verdict

**PASS — minimal authoritative link-inventory parser may be implemented.**
