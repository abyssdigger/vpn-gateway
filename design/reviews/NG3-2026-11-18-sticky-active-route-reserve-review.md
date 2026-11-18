# NG3 2026-11-18 — sticky active route and Profile-local reserve review

## Verdict

**PASS for requirement/config/architecture correction.**

This review supersedes the current applicability of
`NG3-2026-11-18-established-flow-stability-probe-simplification-review.md` for outbound
availability semantics. The historical review and EXP-062 evidence remain unchanged as records
of the earlier decision and mechanism evidence.

## Accepted product decision

The availability policy is failover-oriented, not continuous best-path rebalancing.

For an ordinary Profile membership:

```text
baseline: A > B > C

A becomes unavailable
    -> B becomes active

A recovers while B remains usable
    -> B remains active
    -> A returns to its baseline place among standby paths
    -> effective order B > A > C
```

Recovery alone therefore does not cause failback.

A Device membership can instead be explicitly marked as reserve inside one Profile:

```toml
device_order = ["primary", "cellular:reserve"]
```

If the active path belongs to a reserve membership, any currently usable path with higher
baseline preference may preempt it. This supports expensive, limited or otherwise
principally-backup links without making reserve a global Device property.

## Configuration boundary

Canonical Release-1 syntax is:

```text
<deviceid>
<deviceid>:reserve
```

The suffix is normalized before structural Device-reference validation. Lower consumers see
the plain Device ID plus a Profile-local reserve Device subset.

Review checks:

- unsuffixed membership is sticky by default;
- reserve is local to one Profile;
- all paths derived from that Device membership inherit the role;
- the same underlying Device cannot appear twice through suffixed/unsuffixed spellings;
- unknown suffixes are configuration errors;
- baseline order is unchanged by the role.

## Architecture correction

The previous outbound design combined immediate recovery failback with a requirement that an
established flow never migrate between potentially non-equivalent paths. That combination
forced per-flow concrete-path affinity.

The corrected Release-1 design instead owns one bounded `current_active_path` per Profile:

```text
current active usable + ordinary membership
    -> keep it first

current active unusable/problematic
    -> select first usable baseline path

current active usable + reserve membership
    -> higher-baseline usable path may preempt

other recovered usable paths
    -> baseline order among standby
```

This is sufficient to prevent the avoidable recovery-driven route change that motivated the
outbound flow-pinning requirement.

If the active path itself fails, a route change is already an availability failover boundary.
Release 1 does not promise preservation of source IP/port/NAT identity, transport session
continuity, buffering/replay or seamless flow migration across that boundary.

Managed-stack return affinity for remote-initiated traffic under `VPNG0002-R2.R6` is a
different responsibility and remains unchanged.

## Simplification review

Removed from the Release-1 outbound availability prerequisite:

- per-flow concrete-path state;
- conntrack-like flow lifecycle/timeout ownership for this purpose;
- dynamic path-equivalence proofs;
- flow-specific fail-closed routing after active-path loss;
- first-outbound-packet egress capture solely to preserve recovery affinity.

Retained:

- bounded Profile/path availability confirmation state;
- one current active path identity per Profile;
- baseline path order;
- Profile-local reserve membership;
- existing probing hysteresis and stale-evidence rules.

EXP-062 remains technically useful if a later requirement needs finer-grained established-flow
semantics. It is no longer a Release-1 availability blocker.

## Non-normative resource declaration

`design/NG3/declarations.md` records the current engineering preference that VPN-GATE should
remain suitable for resource-constrained gateways and that equivalent behavior should prefer
less CPU/memory/state tracking.

Per explicit product decision, this is **not** promoted to a Requirement or Constraint in this
cycle. Quantitative resource acceptance criteria remain intentionally absent until working
code provides a useful basis.

## Requirement trace review

Changed/reopened and now architecturally covered:

- `VPNG0003-R3`;
- `VPNG0003-R3.R4`;
- `VPNG0003-R3.R5.R2`;
- `VPNG0003-R3.R7`;
- `VPNG0003-R3.R8`;
- `VPNG0003-R3.R8.R1`;
- `VPNG0003-R3.R8.C1`.

Added and architecturally covered:

- `VPNG0003-R3.R4.R1` — explicit Profile-local reserve behavior;
- `VPNG0003-R3.R4.R1.R1` — canonical `:reserve` membership grammar and scope.

The Purpose/Reason of each changed node is supported by the existing `VPNG0003` path
preference/availability ancestry and by the explicit user decision in this design cycle.
No new primary requirement is introduced.

## Requirement-state inventory

This cycle creates no active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

The changed nodes were deliberately reopened before architecture correction. With the
architecture above and the exact references now present, they may return to `[closed]`.

## Evidence boundary

No new Linux/kernel fact is required for this design correction. The selected behavior is
implemented by route-order policy and bounded Manager state already inside the accepted
architecture. Existing route-priority evidence remains applicable.

This review does not claim that the current executable alpha already parses `:reserve` or
implements sticky-active calculation. That is the next implementation review unit.

## Conclusion

The corrected policy preserves ordinary traffic stability by avoiding gratuitous recovery
failback rather than by tracking every flow. Reserve membership provides an explicit opt-out
when rapid return from a backup link matters more than route stickiness.

The design is smaller, has bounded Profile-level state, and removes the outbound per-flow
affinity gate without weakening the separate remote-initiated return-affinity requirement.
