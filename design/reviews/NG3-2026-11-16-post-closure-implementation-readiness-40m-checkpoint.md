# VPN-GATE NG3 — Post-closure implementation-readiness CD checkpoint

**Cycle:** `ng3-design-cycle-20261116-post-closure-implementation-readiness-40m`  
**Date:** 2026-11-16

## Cycle clock

```text
CYCLE_START_COMMIT:
2173dd1a1d96f22f49364ba7c4fd4a54f27606de
2026-11-16T01:27:49Z

pre-checkpoint validated head:
5da4dbf8cbee6b335be123544c39059debbd8edd
2026-11-16T02:10:13Z

elapsed:
42m24s
```

The 40-minute trigger was crossed while finishing the already-started executable
traceability/document-integrity review unit. No new review unit was started after the trigger.

## 1. Accepted executable review units

### Structural Device/Profile configuration

Implemented:

- bounded structural TOML parser;
- stable IDs and explicit enabled;
- exact/prefix expected-interface selectors and quotas;
- strict IPv4 destinations;
- Device references / active Device derivation;
- selector/destination ambiguity validation;
- Release 1 inbound/bidirectional configured-capacity validation.

Review:

`design/reviews/NG3-2026-11-16-structural-config-code-review.md`

### Stable-slot Device binding projection

Implemented:

- concrete current interface identity `(ifname, ifindex)`;
- logical path identity Device/selector/stable-slot;
- survivor preservation;
- bounded waiting-candidate order;
- delayed promotion only after a disappearance projection can be committed;
- same-name/new-ifindex fresh endpoint semantics.

Review:

`design/reviews/NG3-2026-11-16-device-binding-projection-code-review.md`

### PayloadProfileRequest projection

Implemented:

- Profile-local structural path membership;
- configured Device/selector/slot baseline ordering;
- zero-path Profile preservation;
- concrete endpoint generation independence.

Review:

`design/reviews/NG3-2026-11-16-payload-profile-request-code-review.md`

### Authoritative interface inventory

Implemented:

- strict ordered `ip -j link show` parser;
- valid empty inventory vs observation failure distinction;
- strict ifname/ifindex identity validation.

Review:

`design/reviews/NG3-2026-11-16-interface-inventory-code-review.md`

### Profile NEW-flow classification

Implemented:

- outbound remote-destination classification;
- inbound actual-ingress restriction then remote-source classification;
- matching-prefix longest-prefix semantics;
- fail-closed defensive ambiguity behavior.

Review:

`design/reviews/NG3-2026-11-16-profile-classification-code-review.md`

### Pure route-priority move planner

Implemented:

- same-membership priority-only planner;
- add-at-free / delete-old move primitives;
- deterministic scratch-metric cycle breaking;
- no semantic/configured hole object;
- rejection of structural membership change.

Review:

`design/reviews/NG3-2026-11-16-route-priority-planner-code-review.md`

### Bounded availability confirmation state

Implemented:

- positive / negative / no_evidence transition semantics;
- bounded degradation/recovery progress;
- threshold transition/reset semantics;
- no evidence history/window/replay.

Review:

`design/reviews/NG3-2026-11-16-availability-confirmation-code-review.md`

### Availability priority transformation

Implemented:

- stable negative-priority partition of configured allowed paths;
- exact membership preservation;
- automatic restoration of configured position after problem removal.

Review:

`design/reviews/NG3-2026-11-16-availability-priority-code-review.md`

### Pure structural pipeline integration evidence

Added cross-contract scenarios:

```text
config
-> authoritative interface inventory
-> stable binding
-> PayloadProfileRequest
-> Profile classification
-> availability priority
```

including zero-binding fail-closed policy-domain preservation and Release 1 inbound
single-path ingress restriction.

Review:

`design/reviews/NG3-2026-11-16-pure-structural-pipeline-integration-review.md`

### Executable-reference traceability

Fixed stale architecture cycle/status and added explicit mapping:

```text
requirement
-> architecture responsibility
-> executable reference
-> code review evidence
```

Also refreshed the Python reference README.

Review:

`design/reviews/NG3-2026-11-16-executable-reference-traceability-review.md`

## 2. Material findings found and fixed during the cycle

1. Partial structural config values incorrectly reused full architecture contract names.
   Fixed to `DeviceStructuralIntent` / `ProfileStructuralIntent`.

2. Set-like Profile destinations retained authored TOML order.
   Fixed with canonical normalized ordering.

3. Binding implementation needed current NG3 stable slot identity rather than historical NG1
   candidate-order-only projection.
   Implemented explicit stable slots and delayed promotion after committed disappearance.

4. `InterfaceIdentity` direct construction admitted Python bool as ifindex.
   Fixed strict integer typing.

5. Profile collection order leaked incidental TOML table ordering.
   Fixed canonical request collection order by Profile ID.

6. Naive Profile classification could use an unrelated longer prefix from the same Profile
   when comparing specificity.
   Fixed to consider only prefixes matching the actual remote address.

7. Architecture header remained on an obsolete Profile-recovery cycle.
   Fixed and tied to current executable reference state.

8. New traceability section initially referenced typo `VPNG-R7.R6.1`.
   Corrected to normative `VPNG-R7.R6.R1` before checkpoint.

## 3. Current executable scope

Reference code:

`design/NG3/code/python/rou/`

Current rootless test inventory:

```text
test_config.py                    19
test_binding.py                    9
test_payload_profile.py            7
test_interface_inventory.py        8
test_profile_classification.py     7
test_route_priority.py             9
test_availability_confirmation.py  6
test_availability_priority.py     10
test_pure_structural_pipeline.py   3
------------------------------------
total                             78
```

The individual review artifacts record the evidence used to accept each unit.

## 4. Intentionally not implemented

The cycle did not guess or prematurely implement:

- final Device NAT user-facing spelling;
- traffic-envelope grammar;
- transport-publication grammar;
- availability timing/user grammar;
- Netlink event/poll scheduling;
- full VPNPathAdapter process collection lifecycle;
- Linux route/RPDB/nft execution and postcondition verification;
- production ICMP probe process/network isolation mechanism;
- full daemon/bootstrap/shutdown assembly;
- Release 2 multi-path inbound/bidirectional return-path handling.

## 5. Requirement / architecture integrity

```text
R/C nodes:                         121
closed:                            121
pending_closure:                     0
rejected_closure:                    0
open:                                0

closed without architecture ref:     0
extra architecture requirement refs: 0
active decomposition blocks:         0
broken decomposition links:          0
```

## 6. Current blockers

No new product-semantic blocker was found in this cycle.

The current limitations remain explicit accepted boundaries rather than hidden blockers:

- Release 1 inbound/bidirectional capacity <= 1;
- Release 2 EXP-014 evidence backlog;
- EXP-026 Debian 13 confirmation if the production probe mechanism selects that remediation;
- unresolved user grammar areas remain intentionally outside the executable parser.

## 7. Next coherent implementation candidate

A reasonable next independent review unit is the actual `VPNPathAdapter` link-inventory
collection boundary:

```text
invoke full ip -j link show in managed network domain
-> obtain fresh authoritative text
-> parse accepted InterfaceIdentity inventory
-> feed stable-slot binding projection
```

It should keep Netlink/events as wakeups only and must preserve observation failure as
unknown/error rather than empty inventory.

This is a candidate for the next cycle, not work started after the current 40-minute trigger.

## Verdict

**PASS — POST-CLOSURE IMPLEMENTATION READINESS ADVANCED WITHOUT NEW PRODUCT SEMANTICS OR UNJUSTIFIED COMPONENTS.**

Current Release 1 requirement/architecture closure remains complete at 121/121.
