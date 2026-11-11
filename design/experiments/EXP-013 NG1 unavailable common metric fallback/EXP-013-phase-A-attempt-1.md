# EXP-013 Phase A — first live attempt

Date: **2026-11-11**

Status: **HARNESS FALSE NEGATIVE — rerun required**

User-reported output:

```text
A1 direct-dev multipath: PASS
ERROR: A2 blackhole did not become terminal winner
```

No `a3-after-*` artifacts were created because the harness terminated at the final A2
assertion before reaching A3.

## Interpretation

The first two A2 observations had already passed:

1. normal route won while normal + unavailable + blackhole existed;
2. unavailable direct-dev multipath won after removal of the normal route.

The failure occurred only after removal of the unavailable route.

The original harness incorrectly expected ordinary:

```text
ip route get <target>
```

to print the word `blackhole`.

For a Linux blackhole route, a local sender receives `EINVAL`; therefore resolved
`ip route get` may fail instead of rendering a normal resolved route line. This makes the
old grep assertion invalid.

## Correction

Phase A now records both:

```text
ip route get <target>
ip route get fibmatch <target>
```

plus return codes and route-table inventory.

Terminal blackhole assertions use the full FIB match when available, with the owned table
inventory as structural confirmation.

The same correction is applied to the `/0` terminal-blackhole check.

## Evidence status

This attempt establishes only:

- A1 direct-dev multipath: **PASS**;
- A2 normal > unavailable portion: **PASS up to terminal assertion**;
- terminal-blackhole assertion: **INVALID HARNESS CHECK**;
- A3/A4/A5: **NOT RUN**.

No architecture conclusion is drawn from the false-negative terminal assertion.

A clean Phase A rerun is required.
