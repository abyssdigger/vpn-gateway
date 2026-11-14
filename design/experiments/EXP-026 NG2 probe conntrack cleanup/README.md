# EXP-026 — probe-class conntrack cleanup boundary

**Status:** READY FOR CI/TARGET
**Architecture baseline:** EXP-025 target-confirmed STALE-INHERITANCE
**Type:** disposable-netns kernel/mechanism experiment

## Purpose

EXP-025 proved that an ICMP conntrack entry carrying the probe ct mark can survive concrete
interface generation replacement and be inherited by a later probe that reuses the same
tuple / ICMP identifier.

EXP-026 asks a narrower remediation question:

> Can Linux selectively delete the dedicated probe conntrack class by conntrack mark,
> while leaving unrelated conntrack state intact, so a later probe must take NEW+mark-set?

This experiment does not yet decide whether probe-class-wide cleanup is the final NG2
policy. It only proves or rejects the mechanism and its isolation boundary.

## Topology

Disposable namespaces:

- `vpng2-ctclean-rou`;
- `vpng2-ctclean-peer`.

ROU has one veth `vpn0`.

Two fixed-identifier ICMP flows are created:

- probe flow A -> target `203.0.113.31`, mark `0x26`;
- probe flow B -> target `203.0.113.32`, mark `0x26`.

A third control flow is created with mark `0x77`.

All three must be visible in conntrack before cleanup.

## Cleanup operation under test

```text
conntrack -D -p icmp -m 0x26
```

The conntrack man page defines `--mark MARK[/MASK]` as a filter for delete operations.

Expected scope:

- both probe-class entries with mark 0x26 are removed;
- control entry with mark 0x77 remains.

No global conntrack flush is used.

## Assertions

### K1 — selective setup is real

Two probe entries with mark 0x26 and one control entry with mark 0x77 exist.

### K2 — mark-filtered delete is selective

After `conntrack -D -p icmp -m 0x26`:

- no mark-0x26 ICMP entry remains;
- the mark-0x77 control entry remains.

### K3 — stale inheritance is broken

After probe-class cleanup and concrete vpn0 generation replacement, repeating a fixed probe
identifier must increment NEW+mark-set rather than ESTABLISHED-old-mark.

### K4 — unrelated state remains usable

The control conntrack entry is still present after probe cleanup and its corresponding
traffic remains functional.

## Interpretation

PASS means probe-class-wide conntrack cleanup is a technically viable narrow remediation:
it affects only flows carrying the dedicated probe mark and does not require namespace-wide
conntrack flush.

PASS does **not** yet mean NG2 should necessarily perform cleanup by mark alone. The
architecture must still decide whether invalidating all in-flight probe-class flows on one
probe generation change is acceptable.

FAIL means another generation primitive is required.

## Requirements

- root;
- iproute2;
- nftables;
- iputils-ping;
- conntrack;
- setpriv;
- Python 3.

## Artifact

`design/NG2/code/python/rou/tests/integration_probe_conntrack_cleanup.py`
