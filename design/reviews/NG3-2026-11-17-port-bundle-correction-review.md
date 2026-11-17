# NG3 review — Release-1 port-bundle correction

**Date:** 2026-11-17  
**Cycle:** `ng3-beta-cycle-20261117-port-bundles-35m`  
**Baseline:** main snapshot 73, `6877dcba7f1fc3115e749e9edd9eb26ebb27b4ae`  
**Primary CI evidence:** NG3 Python run `44136005710`, source `7616d1c7624cc1928325d0649f1ae86aa32d1b94`, PASS

## Correction being reviewed

Snapshot 73 incorrectly recorded Release-1 Device firewall ports as single integers only and
described range support as an accidental inheritance from historical prototypes.

That conclusion was not an accepted product decision. It was a review omission: the short
configuration discussion had not re-enumerated the previously useful range capability, and
the review incorrectly converted silence into removal.

The owner clarification accepted in this cycle is:

```text
port-bundle := item ("," item)*
item        := N | A-B
```

with no whitespace inside the bundle.

This corrective unit restores the intended capability and extends it naturally to
comma-separated exact/range items.

## Canonical semantics

### Common PortBundle value

For firewall and server publication:

- each port is an integer in `1..65535`;
- a range is inclusive `A-B` with `A <= B`;
- comma-separated items contain no spaces;
- empty items are invalid;
- duplicate exact ports are invalid;
- an exact port covered by a range is invalid;
- intersecting ranges are invalid;
- declared item order is preserved.

Examples:

```text
443
8000-8007
53,123,443
53,1000-1003,8080,9000-9002
```

### Device firewall

Canonical examples:

```toml
firewall = [
    "out allow tcp to 10.20.0.0/16:80,443,8000-8099",
    "in allow udp from 10.30.0.0/16:53,5353 to 10.0.0.0/24:1024-65535",
]
```

A source bundle and destination bundle are independent packet set-membership selectors.
There is **no positional mapping** between them.

The bundle remains part of one ordered firewall rule and therefore has one terminal verdict.
The implementation does not expand a range into one policy rule per physical port.

### VPN server publication

Identity mapping:

```toml
publish_vpn_server = "udp/eth0:53,123,5000-5003"
```

means:

```text
53   -> 53
123  -> 123
5000 -> 5000
5001 -> 5001
5002 -> 5002
5003 -> 5003
```

Explicit translation:

```toml
publish_vpn_server =
    "tcp/eth0:443,8000-8002,9000>8443,18000-18002,19000"
```

Both sides are expanded in declared item order. Equal cardinality is mandatory and mapping is
positional 1:1:

```text
443  -> 8443
8000 -> 18000
8001 -> 18001
8002 -> 18002
9000 -> 19000
```

Unequal cardinality is invalid.

### VPN client transport allow

`allow_vpn_client` deliberately remains exact-port:

```text
tcp|udp[:local-port]>remote-IPv4:remote-port
```

This capability opens a narrowly bounded local/system exception for the VPN implementation's
own control/underlay flow. Extending it to ranges would broaden a safety-sensitive exception
without an accepted need and is not implied by the payload/publication PortBundle capability.

## Requirement trace

The correction refines already closed requirements rather than introducing a new independent
feature root:

- `VPNG0001-R1.R2.R4.R6.R2.R1` — Device firewall one-line grammar now uses
  `port-bundle` on source/destination selectors;
- `VPNG0001-R1.R2.R4.R6.R3` — server publication now uses host/internal port bundles and
  defines identity/positional mapping;
- `VPNG0001-R1.R2.R5.R2` — strict validation continues to reject duplicate, overlapping,
  reversed and otherwise ambiguous ranges.

The correction does not change Profile permissions, Device direction semantics, NAT
semantics, endpoint provenance, or local-system transport admission.

## Implementation review

One small normalized value object is introduced:

```text
PortSpan(first, last)
PortBundle(spans[])
```

`PortBundle` owns only common bundle invariants and declared order. It is used by the
configuration boundary and normalized Device firewall intent; it does not become a generic
network-policy subsystem.

Firewall compilation maps:

```text
single exact     -> nft scalar
single range     -> nft range
multiple items   -> nft set of exact/range operands
```

This maintains one user rule / one lower rule rather than producing potentially thousands of
rules from a large range.

The Linux Device-firewall backend independently validates the lower scalar/range/set operand
before rendering nft syntax. It does not trust desired JSON merely because it came from the
upper compiler.

Publication configuration preserves both ordered bundles as typed data and verifies equal
expanded cardinality when translation is explicit. Full host-side publication materialization
remains the separately known runtime gap; the alpha continues to reject
`publish_vpn_server` rather than silently ignoring it.

## Findings during this corrective cycle

### F1 — EXP-042 harness braces were initially wrong

The first privileged EXP-042 extension placed nft set braces directly inside a Python
f-string. Python interpreted the braces as an f-string expression, so nft received malformed
input.

Disposition: harness braces were escaped. The next run confirmed the real target nft syntax.

This was not a kernel or product-semantics failure.

### F2 — lower Linux firewall renderer still allowed only an exact integer

After EXP-042 proved nft range/set JSON, the live guarded mutation test failed with:

```text
invalid lower Device firewall port
```

The semantic compiler was correct, but `linux_device_firewall.py` still enforced the older
single-integer lower contract.

Disposition:

- lower validator/renderer now accepts only the three evidenced shapes: scalar, range, set;
- bounds, range ordering and set overlap are validated again at that lower boundary;
- live guarded mutation with a mixed port bundle now passes.

This was the material implementation defect the corrective CD needed to expose.

## Evidence

NG3 Python run `44136005710`:

```text
Ran 563 tests
OK

EXP042_PORT_BUNDLE=1
EXP-042 Device firewall predicate JSON: PASS

NG3 live bounded guarded Device firewall mutation: PASS
```

All workflow jobs passed, including:

- route/RPDB and nft structural jobs;
- payload NAT;
- payload forward / Device firewall;
- endpoint provenance;
- installed alpha smoke;
- EXP-049/050 OpenVPN/systemd applicability/lifecycle.

The dedicated lower evidence record is:

`design/experiments/EXP-042 NG3 Device firewall predicate JSON/EXP-042-result-20261117-port-bundle-pass.md`.

## Simplification review

The correction deliberately does **not** introduce:

- a generic expression language for ports;
- named reusable port groups;
- service-name lookup;
- whitespace-tolerant canonicalization;
- arbitrary set algebra;
- per-port expansion of ranges;
- port bundles in `allow_vpn_client`;
- a new component/Manager/Engine;
- publication mapping semantics beyond ordered equal-cardinality 1:1 translation.

The shared `PortBundle` value object is the minimum common semantic type required by the
accepted firewall/publication grammar.

## Historical review disposition

The snapshot-73 review and checkpoint are retained as historical artifacts but now carry
explicit corrective notes. Their single-port-only conclusion is marked **superseded**, not
silently rewritten as if the mistake had never happened.

## Verdict

**ACCEPT.**

Release-1 firewall and server-publication grammar includes strict compact ordered port
bundles. Firewall lower materialization is proven end-to-end through nft range/set
representation. Server-publication bundle parsing and positional mapping are normalized and
validated; its already-known full publication runtime materialization remains a separate beta
implementation unit.

`allow_vpn_client` remains exact-port.
