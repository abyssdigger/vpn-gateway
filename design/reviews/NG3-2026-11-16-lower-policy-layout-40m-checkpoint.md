# VPN-GATE NG3 — Lower Policy Layout / Structural Observation Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261116-lower-policy-layout-40m`  
**CYCLE_INTERVAL:** 40m  
**Cycle type:** continuous design/development  
**Checkpoint reason:** configured interval exceeded while finishing the bounded payload
actual-vs-desired comparison review unit.

## Cycle clock

```text
CYCLE_START_COMMIT:
e2a751f461366c723c1b921b2fef210df6062448
2026-11-16T07:31:00Z
NG3: define shared lower network-policy ownership layout

last content/review head before checkpoint:
c248ce6aea45862a27932ae8eebf33b52dc5d5f0
2026-11-16T08:13:44Z
NG3: review structural routing comparison and record cycle progress

elapsed:
42m 44s
```

The interval was crossed while the final comparator unit still required CI/fix/review.
No new review unit was started after checkpoint became pending.

## Completed — shared lower ownership/allocation

- defined semantic payload/probe owner scopes below NetworkPolicyAdapter;
- defined disjoint internal table and RPDB resource pools, route role markers, metric
  ownership and dedicated nft namespace rules;
- retained zero-path Profiles as allocated fail-closed routing domains;
- required reserved-space conflicts to fail closed rather than authorize blind cleanup;
- implemented deterministic pure allocation over an injected platform resource contract;
- preserved stale-allocation classifiability without a durable allocation journal.

## Completed — accepted Linux platform space

EXP-028 accepted and the code now exposes `NG3_LINUX_POLICY_PLATFORM`:

```text
payload tables:        [0x80000000, 0xC0000000)
probe tables:          [0xC0000000, 0x100000000)
probe RPDB:            [0x2000, 0x4000)
payload RPDB:          [0x4000, 0x6000)
ambient main:          32766
path route protocol:   202
guard route protocol:  201
first path metric:     1
terminal guard metric: 0xffffffff
nft namespace:         table ip vpn_gate
```

Privileged evidence covered first/last IDs of the table/RPDB pools and real route lookup.

## Completed — semantic-to-physical route realization

- kept PathBinding separate from route gateway/onlink realization;
- made direct-device routing an explicit opt-in integration capability rather than a
  universal interface assumption;
- added a direct-device realizer for integrations whose onboarding/evidence proves it;
- added exact Profile/allocation/path realization assembly into per-destination
  RoutePriorityDomainRealization objects;
- stale allocation cardinality and destination-set mismatches are rejected before entering
  the pure-priority path.

## Completed — complete payload routing desired state

The pure lower desired projection now contains:

```text
per Profile:
    allocated routing table
    terminal BLACKHOLE default guard
    desired ordinary path routes for every destination/path

per destination:
    host-boundary RPDB dispatch rule
```

Zero-path Profiles retain table + guard + dispatch and contain no ordinary path routes.

The projection validates exact current path-route membership, endpoint uniqueness, canonical
dispatch ordering and unique/increasing RPDB priorities.

## Completed — guarded structural activation boundary

Physical RPDB activation is explicitly **not** a standalone route operation.

Accepted structural ordering is:

```text
fresh observation
 -> establish/verify restrictive barrier
 -> prepare/verify guarded routing tables
 -> prepare/verify nft filtering/NAT
 -> switch/verify RPDB dispatch
 -> verify complete route+nft desired state
 -> release barrier
 -> fresh final verification
 -> cleanup stale state
```

This preserves the old/new policy safety invariant during mixed structural state.

## Completed — authoritative structural observation

EXP-029 accepted the current iproute2 6.19 numeric JSON forms for:

- `ip -j -N -4 route show table all`;
- `ip -j -N -4 rule show`.

Important evidence includes:

- numeric-string high table/protocol values;
- blackhole route type `"6"` under `-N`;
- bare IPv4 representation for `/32` route destinations;
- RPDB `dst + dstlen` representation;
- explicit `src=all`;
- hexadecimal `fwmark/fwmask`.

The strict observer inventories the entire reserved table/priority namespaces and returns
typed recognized objects plus explicit owner-scoped conflicts for unsupported reserved
shapes. It retains current InterfaceIdentity and observed route scope.

## Completed — pure actual-vs-desired comparison

Payload comparison now classifies:

```text
confirmed desired routes/rules
missing desired routes/rules
stale recognized payload routes/rules
payload-owner reserved conflicts
```

Probe-owner state is kept independent even though the physical observer is shared.

Same-name/new-ifindex replacement and route scope mismatch do not confirm desired state.

## Evidence

Latest complete code-bearing workflow evidence:

```text
workflow: NG3 Python
run:      43829159828
commit:   1fcf8f2f395f49ec4aa8f4dba10632ad3ad3b62d
unit:     217 tests, OK
linux-route-priority: PASS
linux-policy-platform / EXP-028: PASS
linux-structural-inventory-shape / EXP-029: PASS
overall:  success
```

The later `c248ce6` commit contains review/trace/CHANGELOG only and does not change code.

## Mechanical integrity at checkpoint

```text
normative requirement nodes:        128
unique normative IDs:               128
primary roots:                        7
Constraints:                           6
requirements absent from architecture: 0
unknown architecture requirement IDs:  0
unknown config-model requirement IDs:   0
legacy VPNG-R... IDs:                  0
```

`PROJECT-CONVENTIONS.md` still requires immediate GitHub publication of every commit, and
every commit in this cycle was published before the next unit continued.

## Findings fixed during cycle

- allocator negative precedence test initially exercised overlap instead of precedence;
- VPN-GATE RPDB pools now explicitly exclude Linux local priority 0;
- allocator direct-construction Profile IDs are hardened;
- EXP-028 normalized current numeric-string `RTN_BLACKHOLE` representation;
- EXP-028 payload lookup harness was corrected to use a representable ingress source;
- EXP-028/029 changes were added to symmetric push/PR CI path triggers;
- route-domain builder now rejects stale allocation cardinality;
- complete desired projection rejects stale extra path realizations and malformed dispatch;
- structural observation retains scope and conflicts on unknown reserved route fields;
- reserved conflicts now preserve payload/probe owner scope;
- missing `Enum` import in the first comparison commit was fixed before acceptance.

## Exact next boundary

Do **not** implement independent RPDB activation next.

The next review unit is the shared restrictive structural transaction, beginning with the
nft barrier/owner contract needed to make mixed structural state safe.

It must establish how affected traffic is blocked/restricted while:

- new guarded route tables are prepared;
- final payload/probe nft policy is prepared;
- RPDB dispatch is switched;
- complete route+nft postconditions are verified.

Only after that barrier contract is accepted may physical structural route/RPDB mutation be
implemented.

Existing unresolved user-facing NAT / traffic-envelope / publication grammar remains a
separate gate. If the next nft desired-policy unit cannot be derived without resolving that
grammar, autonomous refinement must stop there and escalate the exact requirement chain.

## Human decisions

None required by the work completed in this cycle.

## Checkpoint verdict

**PASS — CURRENT REVIEW UNIT COMPLETE.**

Autonomous development stops after this checkpoint commit and resumes only after the next
user turn with a reset cycle clock.
