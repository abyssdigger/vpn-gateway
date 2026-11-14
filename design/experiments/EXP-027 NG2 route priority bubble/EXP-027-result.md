# EXP-027 — result

Date: 2026-11-14

Result: **PASS**

Environment:

- GitHub privileged Linux runner;
- disposable network namespace;
- four veth path interfaces;
- one table for `198.51.100.0/24`;
- one table for `default`;
- owned unicast protocol 202;
- terminal blackhole protocol 201, metric 65536.

Initial projection in each table:

```text
A metric 10
B metric 20
C metric 30
D metric 40
blackhole metric 65536
```

Applied sequence:

```text
replace metric 10 with B
replace metric 20 with C
replace metric 30 with A
```

Observed after each step:

```text
A B C D
B B C D
B C C D
B C A D
```

The old copy of the promoted interface survived at its lower metric until that slot was
replaced. No userspace delete-then-add sequence was needed for the promoted slot.

The same behavior passed for an ordinary prefix and for `default`.

Attempt 1 failed before route setup because the runner did not support the chosen dummy-link
fixture. It produced no routing evidence and is retained in the README. Attempt 2 reused
the already CI-proven veth mechanism and reached the intended hypothesis.

Architectural consequence:

- path-priority-only changes may use fixed metric slots;
- bubble materialization can use top-down `ip route replace`;
- temporary duplicate paths are valid implementation state;
- a displaced non-confirmed path need not keep a route at every intermediate step;
- staging tables are unnecessary for ordinary availability-driven path permutations;
- the existing structural fail-closed rebuild remains the fallback for any broader change
  or failed fast-path verification.
