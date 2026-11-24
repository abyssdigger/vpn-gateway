# NG3 2026-11-19 — probe policy projection review

## Verdict

**PASS for the pure normalized probe-policy projection and authoritative RPDB observation
correction.**

## Trigger

Release-1 architecture already selected path-specific ICMP availability and preserved the
historical EXP-021/022/024 mechanism evidence. The previous cycle also removed EXP-026
conntrack cleanup as a prerequisite.

During implementation this cycle found two stale lower-layer artifacts:

1. one Executor paragraph still claimed probe local/system materialization remained blocked by
   the historical deferral;
2. the structural RPDB observer treated an EXP-029 `fwmark/fwmask` inventory-test rule as
   the canonical probe-owner rule even though EXP-022 selected
   `uidrange + ipproto + exact target` for probe routing.

Neither finding changes product semantics or requires a new user decision.

## Gate consistency correction

The stale Executor claim was removed. The active Release-1 boundary is now consistently:

- ordinary ICMP probe materialization may proceed;
- probe routing/local state remains isolated from payload ownership;
- a dedicated probe conntrack mark is used only for reverse local admission;
- generic `ct mark -> packet mark` restoration for probe state is prohibited;
- namespace-wide conntrack cleanup remains prohibited;
- EXP-026 is optional future hardening, not a Release-1 gate.

## EXP-065 evidence

EXP-065 was added to pin the current Linux/iproute2 representation of the already selected
probe RPDB discriminator.

GitHub Actions run `44459119767`, job `135341347352`, reported **PASS**.

Current numeric JSON for:

```text
uidrange 4242-4242
ipproto icmp
to 198.51.100.7/32
priority 8192
lookup 3221225472
```

is:

```json
{"dst":"198.51.100.7","ipproto":"ipproto-1","priority":8192,"src":"all","table":"3221225472","uid_end":4242,"uid_start":4242}
```

A matching UID/ICMP lookup selected the dedicated probe table/path. UID 4243 did not.

Disposition: **selected** as current lower evidence for the Release-1 mechanism already
supported by EXP-022.

EXP-029 remains valid evidence for hexadecimal `fwmark/fwmask` JSON representation, but
that marked rule is now explicitly classified as an inventory-shape surrogate rather than
the canonical probe-routing selector.

## Pure desired-state projection

New `probe_policy.py` starts only after availability target normalization.

Input:

```text
AvailabilityProbeIntent:
    owner = (profile_id, logical_path_id)
    mechanism = ICMP
    target = concrete IPv4

+ current logical-path route realization
+ ProbePolicyAllocation
+ lower dedicated probe process UID
+ lower dedicated probe conntrack mark
```

Output:

```text
ProbeNetworkPolicyDesiredState:
    routes[]
    rules[]
    local_rules[]
```

For each current probe owner the projection creates:

- target `/32` route through the exact current logical-path realization;
- terminal blackhole default in that dedicated probe table;
- exact UID + ICMP + target RPDB rule into the dedicated table;
- narrow OUTPUT admission for dedicated UID + exact current endpoint + target + ICMP, with
  probe conntrack-mark assignment;
- narrow reverse INPUT admission for exact endpoint + remote source + ICMP + probe conntrack
  mark, without relying on receiving-socket UID.

Route metrics/protocol roles reuse the accepted shared lower route contract and
`ManagedRouteSpec`; the first implementation draft's duplicate `ProbeRouteSpec` /
`ProbeRouteType` types were removed during simplification review.

The process UID is required to be a dedicated non-root UID. UID 0 would not distinguish the
probe worker from arbitrary root/controller traffic and therefore would not satisfy the
selected process-isolation mechanism.

The UID and conntrack mark remain injected lower platform values. This unit deliberately does
not select a deployment UID or mark allocation; their eventual concrete allocation must
preserve the existing disjoint-owner invariants.

## Authoritative observer correction

`structural_routing_inventory.py` now recognizes reserved probe RPDB state using the
EXP-065 shape:

- exact host destination;
- `uid_start`;
- `uid_end`;
- normalized numeric `ipproto`;
- reserved probe priority;
- reserved probe table.

Current `"ipproto-1"` normalizes to protocol 1.

A reserved probe rule using the former EXP-029 `fwmark/fwmask` surrogate is an explicit
unsupported-owner conflict rather than silently accepted current state.

Payload observation/comparison remains disjoint:

- payload rules continue to require ingress + destination;
- probe UID/protocol selectors cannot confirm a payload rule;
- the payload delete Driver rejects probe selectors.

## Verification

Current code-bearing GitHub Actions run:

```text
run:  44459706845
head: 277451a19398a3820327c80bbeabd9baee0dfa2f
unit: PASS — 727 tests
linux-structural-inventory-shape: PASS
    EXP-029: PASS
    EXP-048: PASS
    EXP-065: PASS
```

The workflow still contains the previously known unrelated privileged failures in EXP-057,
EXP-060 and EXP-063. They are unchanged by this slice and do not exercise probe-policy
projection or structural probe observation.

## Requirement / architecture integrity

No normative R/C was changed.

Mechanical state after this unit:

```text
normative R/C nodes:             172
closed:                          172
pending_closure:                   0
rejected_closure:                  0
open:                              0
requirements with architecture: 172
architecture requirement IDs:   172
missing / extra refs:              0 / 0
```

## Requirement-state inventory

No active:

- `decomp`;
- `unreal`;
- `broken`;
- `[rejected_closure]`.

Historical resolved decomposition links remain unchanged.

## Remaining boundary

This unit does **not** yet:

- select the concrete deployment probe UID/conntrack-mark allocation;
- compare all probe desired route/RPDB state against observation as a probe-owned domain;
- render/mutate probe RPDB rules;
- observe/render/mutate probe local nft admission;
- schedule or execute ICMP;
- derive omitted targets for integration-specific bare `availability_check = "icmp"`;
- wire probe evidence into confirmation/active-route runtime orchestration.

The next autonomous unit is the pure probe actual-vs-desired route/RPDB comparison. It can be
implemented from the now unambiguous desired and observed contracts without any product
decision.

## Conclusion

The probe plane now has a coherent lower semantic boundary from normalized availability
intent to exact desired routing/local-policy state, and its authoritative RPDB observation
matches the selected mechanism rather than an old inventory-test surrogate.

No per-flow payload state and no probe conntrack cleanup machinery were introduced.
