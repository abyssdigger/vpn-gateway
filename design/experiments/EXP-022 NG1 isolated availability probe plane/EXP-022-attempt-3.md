# EXP-022 attempt 3 — neighbour-cache assertion bug

Date: 2026-11-13

Result: **HARNESS ASSERTION INVALID; Stage-3 hypothesis itself passed**

Observed:

```text
STAGE 3: prove bound probe has no usable vpn0 route before control plane
FAIL: routed target unexpectedly became a direct vpn0 neighbor
```

The preceding assertion was:

```sh
if probe; then
    fail "bound probe unexpectedly reached routed target before probe plane existed"
fi
```

and it did **not** fail. Therefore the bound probe was correctly unable to reach the target
before the control plane existed.

The later harness check treated any neighbour-cache entry for the target as evidence that
the target had become directly reachable. That is incorrect: the failed bound probe itself
may create an `INCOMPLETE` or `FAILED` ARP neighbour entry. Such an entry records an
unsuccessful resolution attempt, not positive L2 reachability.

Correction:

- keep probe failure as the authoritative negative control;
- print the neighbour table for diagnostics;
- do not classify cache-entry presence as failure.

A fresh run is required only to continue the remaining EXP-022 stages.
