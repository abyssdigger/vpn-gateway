# NG3 2026-11-19 — probe runtime 35m CD checkpoint

**Cycle:** `ng3-design-cycle-20261119-probe-runtime-35m`  
**CYCLE_INTERVAL:** 35m  
**Base:** Main snapshot 97 `f4652446079c179514e207ea5aa9303664eb84c6`

## Verdict

**PASS — autonomous probe-plane implementation advanced to the probe-local nft owner boundary
without requiring a product decision.**

The cycle removed one stale architecture gate, converted the accepted EXP-021/022/024 probe
mechanism into executable lower contracts, corrected a fossilized EXP-029 selector surrogate,
and added current EXP-065/066 Linux evidence.

## Snapshot sequence

### Main snapshot 98 — stale probe materialization gate removed

`83d7805777a6983bc76b944b2defef7458fa3924`

The active architecture already said EXP-026 conntrack cleanup was not a Release-1
prerequisite, but one later Executor paragraph still said probe local/system materialization
remained blocked by that historical deferral.

The stale statement was corrected. Release-1 ordinary ICMP probe work may proceed under the
accepted non-interference contract without namespace-wide conntrack cleanup.

### Main snapshot 99 — normalized probe policy + current RPDB evidence

`a5023d31a71863d575c6435a90308878babd301f`

Added pure `probe_policy.py`:

```text
normalized (Profile, logical path, concrete target, ICMP)
+ current path realization
+ probe allocation
+ lower dedicated UID / conntrack mark
    ->
probe route/RPDB/local desired state
```

The route desired state reuses common `ManagedRouteSpec`; no duplicate probe route model
survived simplification review.

EXP-065 proved the selected probe RPDB discriminator on current Linux/iproute2:

```text
exact uidrange + ICMP + exact target
    -> dedicated probe table
```

and recorded current JSON:

```json
{"dst":"198.51.100.7","ipproto":"ipproto-1","priority":8192,"src":"all","table":"3221225472","uid_end":4242,"uid_start":4242}
```

The authoritative structural observer was corrected accordingly. The older EXP-029
`fwmark/fwmask` rule remains representation evidence only and is no longer treated as the
current probe-routing owner shape.

### Main snapshot 100 — pure probe route/RPDB comparison

`15aecac7549003dc7cf310fae176b3674c8888fe`

Added owner-filtered actual-vs-desired comparison over the shared authoritative structural
inventory.

Comparison is exact on:

- probe table/priority ownership;
- target;
- UID;
- ICMP protocol;
- route metric/protocol;
- current ifname + ifindex;
- gateway/onlink/scope.

Payload-owner state and payload conflicts do not pollute probe comparison.

Current gate at this unit: `unit PASS — 734 tests`.

### Main snapshot 101 — probe route/RPDB physical mutation

`fce7f02d2577635b4c7ab2653833635a797eba93`

Added thin `LinuxProbeRoutingBackend`.

Route add/delete reuses the existing common structural route Driver after probe-owner
validation. Only probe RPDB add/delete has a probe-specific renderer.

EXP-065 was extended to prove exact deletion with the full observed selector and preservation
of an unrelated neighboring rule:

```text
EXP065_EXACT_DELETE=PASS
EXP065_UNRELATED_PRESERVED=PASS
```

The authoritative observer was tightened to recognize as current probe ownership only:

- exact one non-root UID;
- ICMP;
- exact host target;
- probe reserved priority/table.

Other shapes in reserved probe space are conflicts, not blind cleanup candidates.

### Main snapshot 102 — probe local nft representation evidence

`fe6fbbcf0ba2a87df4a67da461f0b93e9b97f50a`

EXP-066 recorded current nftables representation for the accepted EXP-024 local mechanism.

OUTPUT:

```text
probe uid + exact oif + target + ICMP
    -> ct mark set <probe-mark>
    -> accept
```

INPUT:

```text
exact iif + source + ICMP + ct mark <probe-mark>
    -> accept
```

Current JSON shape is now known for `skuid`, interface selector, IPv4 field, protocol,
conntrack mark assignment/match, accept, comment and handle.

Critical generation result:

```text
old path0 ifindex = 2
delete/recreate path0
new path0 ifindex = 3

old nft rule after replacement:
    meta oif/iif right = "2"
```

Thus same-name/new-ifindex replacement is observable as stale state rather than falsely
resolving the old rule onto the new interface generation.

Handle deletion also passed.

## Probe-plane state reached by this cycle

The implemented chain now reaches:

```text
normalized AvailabilityProbeIntent
    |
    v
pure probe desired state
    |
    +--> route/RPDB desired
    |       |
    |       v
    |   authoritative structural observation
    |       |
    |       v
    |   probe comparison
    |       |
    |       v
    |   exact Linux mutation
    |
    +--> probe local nft desired rules
            |
            v
        representation evidence complete
        observer/comparison/mutation not yet integrated
```

No ICMP execution/scheduling was added yet.

## Next implementation seam

No product decision is required at the current boundary.

The existing composite nft pattern already supplies the required atomicity model:

- stale local ACCEPT rules are removed before payload cleanup because `ip_forward=0` does
  not protect local traffic;
- one owner-specific full diff is applied as one nft batch;
- missing local admission is added after the protected structural work;
- fresh whole nft observation verifies strict progress.

Probe-local policy can follow the same publication/integration pattern inside the existing
`ip vpn_gate` table:

```text
ProbeLocalRuleSpec
    -> EXP-066-backed observer/comparison
    -> full-diff owner step
    -> handle delete + exact add in one nft batch
    -> CompositeNftPolicyComparison / planner
```

No new nft table, Manager, Engine or atomicity concept is justified.

After that physical owner exists, the remaining larger availability runtime work is:

- concrete target derivation specializations for bare `availability_check = "icmp"`;
- ICMP Driver / Agent execution and observation-context generation handling;
- bounded confirmation orchestration;
- feeding the already implemented active-route state and route-priority convergence.

## Requirement / architecture integrity

```text
normative R/C nodes:             172
closed:                          172
pending_closure:                   0
rejected_closure:                  0
open:                              0

architecture requirement IDs:   172
missing exact refs:                0
extra refs:                        0
```

No normative requirement was changed in this cycle.

## Accumulated requirement-state inventory

### `decomp`

Six historical occurrences remain resolved. Pending: **none**.

### `unreal`

Active: **none**.

### `broken`

Active: **none**.

### `[rejected_closure]`

Active: **none**.

## CI / evidence

Positive current evidence produced or revalidated in this cycle:

- unit suite through the probe-comparison slice: **PASS — 734 tests**;
- `linux-structural-inventory-shape`: **PASS**;
- EXP-029: **PASS**;
- EXP-048: **PASS**;
- EXP-065 selector / lookup / exact delete: **PASS**;
- EXP-066 local nft representation / ifindex replacement / handle delete: **PASS**;
- active-lineage guard remained **PASS**.

The known unrelated privileged failures remain visible:

- EXP-057;
- EXP-060;
- EXP-063.

They are not exercised by the new probe-policy contracts.

## Simplification result

This cycle did not create:

- a generic probe framework;
- per-flow payload state;
- a separate probe nft table;
- a probe routing Engine;
- conntrack GC/cleanup ownership;
- duplicate route representations.

The probe plane is being assembled from narrow owner-specific values and existing shared lower
machinery.

## Conclusion

The old statement “probe materialization is blocked” is no longer true for Release 1.

Probe route/RPDB materialization is now implemented and evidence-backed. Probe-local nft
semantics are also evidence-backed down to current JSON and interface-generation behavior.
The next CD can implement that local nft owner mechanically; no user/product decision is
currently pending.
