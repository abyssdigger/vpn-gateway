# NG3 2026-11-19 — probe route/RPDB mutation review

## Verdict

**PASS for the bounded Linux probe route/RPDB mutation Driver.**

## Scope

This unit materializes only the already reviewed probe routing desired state:

- dedicated probe-table target route;
- terminal probe-table blackhole guard;
- exact EXP-065 probe RPDB rule.

Probe local nft admission remains a separate physical owner and is not implemented by this
Driver.

## Implementation

New `linux_probe_routing.py` provides `LinuxProbeRoutingBackend`.

The Driver deliberately does **not** duplicate the shared route renderer. Probe route
add/delete first validate reserved probe ownership and expected route role, then delegate to
the existing `LinuxStructuralRoutingBackend`.

Probe-owned validation requires:

- table inside `platform.probe_tables`;
- path route protocol = platform path-route role;
- path route metric = first preference metric;
- blackhole guard protocol = platform guard role;
- blackhole guard metric = terminal guard metric.

Probe RPDB mutation is the only probe-specific renderer:

```text
add:
    priority <probe-priority>
    uidrange <dedicated-uid>-<dedicated-uid>
    ipproto icmp
    to <target>/32
    lookup <probe-table>

delete observed:
    same exact selector
    ipproto 1
```

Delete accepts only the current recognized Release-1 probe-owner shape. A payload rule,
marked RPDB rule, UID range, root UID, non-ICMP selector or object outside probe reserved
resources is rejected before mutation.

## Authoritative-owner hardening

The shared structural observer was tightened in this unit so a recognized current probe rule
must use:

- one exact UID, not a UID range;
- non-root UID in `1..2^32-2`;
- ICMP protocol exactly;
- exact IPv4 host target;
- reserved probe priority/table.

Objects inside reserved probe resources that do not satisfy that current owner shape become
explicit conflicts rather than cleanup candidates. This preserves the project's
reserved-namespace rule: classification enables ownership checks, not blind deletion.

## EXP-065 exact-delete evidence

The EXP-065 harness was extended to verify exact deletion of the selected probe RPDB rule.

GitHub Actions run `44460548666`, job `135346035819`, reported:

```text
EXP065_EXACT_DELETE=PASS
EXP065_UNRELATED_PRESERVED=PASS
EXP065_RESULT=PASS
```

The selected rule was deleted with full priority/UID/protocol/target/table selectors while a
neighboring unrelated rule remained present.

This directly backs the Driver's exact observed-rule deletion command.

## Tests

Current run:

```text
run:  44460548666
head: e60b73391c46929fd827cd80785284b96f122b83
unit: PASS
linux-structural-inventory-shape: PASS
```

Unit coverage includes:

- shared exact probe route rendering;
- exact observed guard deletion;
- EXP-065 RPDB add shape;
- EXP-065 exact-delete shape;
- rejection of payload table/rule ownership;
- rejection of non-probe observed selector shape;
- rejection of probe route role mismatch before mutation.

Known EXP-057/060/063 privileged failures remain unrelated.

## Simplification review

No new route mutation engine or duplicate route command builder was introduced.

The physical split is:

```text
common ManagedRouteSpec
    -> existing LinuxStructuralRoutingBackend route renderer

probe RPDB semantic rule
    -> thin LinuxProbeRoutingBackend owner-specific renderer
```

The wrapper exists only to enforce probe reserved ownership before reusing the common lower
route machinery.

## Requirement-state inventory

No normative R/C changed. No active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

## Remaining boundary

Probe routing now has desired state, authoritative observation, comparison and exact physical
mutation.

The remaining lower physical prerequisite before an ICMP attempt can honestly execute is the
probe-owned local nft policy:

```text
OUTPUT:
    dedicated probe UID
    + exact current endpoint
    + exact target
    + ICMP
        -> set dedicated probe conntrack mark
        -> accept

INPUT:
    exact current endpoint
    + exact target as source
    + ICMP
    + probe conntrack mark
        -> accept
```

That local owner needs its own observation/comparison/mutation contract and must remain
disjoint from payload/integration/publication policy.

## Conclusion

The Release-1 probe route/RPDB plane can now be materialized with exact owner checks and exact
cleanup using the selected EXP-065 selector, without importing fwmark as a routing
discriminator and without duplicating the generic route renderer.
