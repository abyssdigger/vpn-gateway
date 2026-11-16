# VPN-GATE NG3 — Device/Profile Config Intent 40m Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261116-config-intent-model-40m`  
**CYCLE_INTERVAL:** 40m  
**Base:** `19940667ec2d88688995c80ecd56ac93e818168f`

## Cycle clock

```text
first content commit:
4eb42004dc6123878b2317b5f88b8989c7259f12
2026-11-16T00:00:33Z
NG3: restore Device and Profile user intent model

closure-restored head:
e029036e2756df57bfbc5697239c69bca892dd50
2026-11-16T00:06:11Z
NG3: restore complete closure after config recovery

elapsed:
5m 38s
```

The cycle completes early because the recovered implemented configuration model supplied the
missing user semantics directly; no unrelated design unit is started merely to consume the
interval.

## Recovered user model

```text
Device
    = expected external VPN/network resource

Profile
    = desired user network behavior using ordered Devices
```

A Device may be reused by multiple Profiles.

Profile configuration intentionally does not contain runtime route metrics, interface indices
or kernel command recipes.

## Human-facing core contract

Recorded in:

`design/NG3/config-model.md`

Recovered core TOML semantics include:

- named `[device.<id>]` / `[profile.<id>]` tables;
- stable IDs using `[a-z0-9][a-z0-9-]*`;
- explicit `enabled`;
- minimal disabled placeholders;
- Device `expected_interfaces`;
- exact and `prefix*/quota` selectors;
- Profile `direction`;
- Profile strict IPv4 `destinations`;
- ordered Profile `device_order`;
- Profile-scoped availability-check semantics.

## Device binding consequences

An active Device is enabled and referenced by at least one enabled Profile.

Logical paths are derived from configured Device binding slots:

```text
logical_path_id :=
    Device ID
    + expected-interface selector position
    + stable slot within selector quota
```

Concrete endpoint binding is separate from logical identity.

Linux concrete endpoint identity:

```text
(ifname, ifindex)
```

Same-name/new-ifindex is a fresh endpoint.

Quota admission preserves survivors and uses the recovered deterministic waiting-candidate
order; lexical ifname sorting is not policy.

## Profile policy consequences

Profile traffic semantics are now explicit:

- destinations describe remote-side IPv4 prefixes;
- outbound NEW classification uses remote destination;
- inbound NEW classification first filters by actual ingress Device/path and then remote
  source;
- exact duplicate prefix ownership across enabled Profiles is invalid;
- different-length overlaps require deterministic most-specific classification;
- direction is explicit `outbound|inbound|bidirectional`;
- only enabled referenced Devices/paths are eligible.

Baseline preference:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> stable runtime slot
```

## Availability consequence

Availability identity is explicitly:

```text
(Profile, logical VPN path)
```

not physical interface identity.

Recovered Profile-level ICMP semantics remain:

```text
icmp/<explicit-ip> -> exact target
bare icmp          -> deterministic Profile/path-specific derivation
```

Probe runtime always receives a concrete IPv4 target.

## Architecture result

No NG1 Engine was inherited.

Current minimal mapping:

- `ConfigurationAdapter` -> Device/Profile parsing/validation/normalization;
- `VPNPathAdapter` -> lower endpoint observation/verification;
- `PayloadTrafficManager` -> bounded current shared Device-binding + payload-policy
  projection;
- `PayloadPolicyCalculator` -> Profile classification/eligibility;
- `AvailabilityTargetCalculator` -> Profile/path target normalization;
- existing Availability Agent/Driver -> normalized probe execution.

A separate DeviceBindingManager/DeviceEngine is not currently justified.

## Implementation obligations derived

The recovered model now requires implementation/test work for:

- Device/Profile TOML parsing;
- ID and enabled validation;
- disabled placeholders;
- expected-interface selector/quota parsing;
- selector overlap validation;
- active-Device derivation;
- endpoint observation by ifname/ifindex;
- quota/survivor binding;
- stable logical path slot identities;
- Profile direction/destination/device reference validation;
- inbound/outbound Profile classification;
- overlap resolution;
- preference compilation;
- Profile/path availability subjects;
- target normalization;
- stable-identity status/diagnostics.

Detailed review/evidence plan:

`design/reviews/NG3-2026-11-16-device-profile-config-intent-review.md`

## Requirement state

The recovery added/refined 21+ product/interface nodes and caused affected ancestry to be
re-reviewed.

Current tree:

```text
R/C nodes:          104
closed:             104
pending_closure:      0
rejected_closure:     0
open:                 0
```

Integrity:

```text
unique architecture requirement refs: 104
closure errors:                        0
active decomposition blocks:            0
broken decomposition links:             0
stale config-gap architecture claims:   0
```

## Verdict

**PASS — DEVICE/PROFILE USER INTENT MODEL RESTORED AND FULL NG3 ARCHITECTURE CLOSURE RESTORED.**

The next bounded implementation/evidence cycle should treat
`design/NG3/config-model.md` as the concrete user-intent source for configuration work,
rather than starting from the older abstract `PayloadPolicyIntent` view alone.
