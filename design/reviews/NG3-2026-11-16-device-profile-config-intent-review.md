# VPN-GATE NG3 — Device/Profile Configuration Intent Recovery Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-intent-model-40m`

## Review purpose

Restore the implemented Device/Profile user-intent model as NG3 product semantics, then
derive architecture and implementation obligations without inheriting NG1 runtime
components merely because they existed.

## Historical evidence used

Recovered normative/implemented material:

- `legacy-main-ng1-2:design/NG1/rou-config.md`;
- `legacy-main-ng1-2:design/NG1/rou-concept.md`;
- `legacy-main-ng1-2:design/NG1/NG1-2026-11-11-config-brainstorm-brief.md`;
- `legacy-main-ng1-2:design/NG1/code/python/rou/domain.py`;
- `design/NG1/code/python/rou/config.py`;
- NG1 runtime/config tests, especially selector/quota/survivor behavior;
- recovered project-chat context for Profile-level `interface_balancing` / ICMP target
  semantics.

These artifacts are evidence of accepted user semantics. NG1 Engines and internal topology
are not inherited automatically.

# 1. Recovered product model

## Device

Device is a stable user-described external VPN/network resource.

It owns user expectations about admissible runtime endpoints:

- stable ID;
- explicit enabled state;
- ordered expected-interface selectors;
- per-selector quota.

Device does not describe one Profile's traffic need.

## Profile

Profile is a stable user-described network need.

An enabled Profile defines:

- explicit direction;
- non-empty remote destinations;
- ordered Device references;
- Profile-scoped availability semantics when configured.

Profile does not contain runtime route metrics, interface indices or kernel command recipes.

A Device may be reused by multiple Profiles.

**Verdict:** ACCEPT.

# 2. Human-facing configuration contract

The recovered core surface is TOML named Device/Profile tables.

Important accepted semantics:

- ID is table identity;
- ID grammar remains `[a-z0-9][a-z0-9-]*`;
- `enabled` is explicit;
- disabled objects may be minimal placeholders;
- known disabled Device references are valid and skipped operationally;
- unknown Device references are invalid.

Enabled Device:

```text
expected_interfaces[]:
    exact ifname
    or
    prefix*/positive-quota
```

Enabled Profile:

```text
direction
destinations[]
device_order[]
```

The complete recovered contract is recorded in `design/NG3/config-model.md`.

**Verdict:** ACCEPT architecture closure for the R1.R2.R4 subtree.

# 3. Device binding semantics

An active Device is:

```text
enabled
AND
referenced by >=1 enabled Profile
```

Only active Devices participate in runtime endpoint discovery/binding.

One concrete Linux endpoint identity is:

```text
(ifname, ifindex)
```

Same-name/new-ifindex is a new endpoint instance.

For one expected-interface selector:

- bound count cannot exceed quota;
- over-quota candidates remain observable but unbound;
- newcomers do not evict survivors;
- after verified survivor removal, waiting candidates may fill free capacity;
- waiting candidates follow committed first-observed order;
- simultaneous fresh candidates preserve kernel-snapshot order with ifindex tie-break;
- lexical ifname sorting is not user policy.

Logical path identity is derived from the configured binding slot:

```text
Device ID
+ expected-interface selector position
+ stable quota slot
```

Concrete endpoint is the current binding of that identity.

**Verdict:** ACCEPT architecture closure for the R1.R3.R4 subtree and refined
R1.R3.R1/R1.R2.R2 semantics.

# 4. Profile traffic semantics

Profile destinations are strict remote-side IPv4 prefixes.

Classification:

```text
ordinary -> VPN NEW:
    remote destination prefix

VPN -> ordinary NEW:
    restrict candidate Profiles by actual ingress Device/path
    then remote source prefix
```

Exact duplicate destination ownership among enabled Profiles is invalid.

Different-length overlaps are allowed only with deterministic most-specific selection.

Profile direction is explicit:

- outbound;
- inbound;
- bidirectional.

Return traffic for admitted flows may be statefully accepted.

Only paths belonging to enabled Devices in Profile.device_order are policy-eligible.

**Verdict:** ACCEPT architecture closure for the refined R2 subtree.

# 5. Profile preference semantics

Baseline order is:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> stable bound slot inside selector quota
```

Adding a runtime endpoint does not arbitrarily reorder already-bound survivors.

Availability remains a modifier of this baseline and cannot change membership.

**Verdict:** ACCEPT architecture closure for refined R3.R1.

# 6. Profile-scoped availability

Availability subject is now explicitly:

```text
(Profile, logical VPN path)
```

A physical interface is not itself an availability subject.

Therefore the same interface/path may be usable for one Profile and unusable for another.

Recovered Profile-level check semantics:

```text
icmp/<explicit-ip>
    -> exact target

bare icmp
    -> deterministic path-specific derivation from
       Profile/path/Device/interface/binding/peer semantics
```

Probe runtime still receives a concrete target only.

The existing `AvailabilityTargetCalculator` remains the correct normalization boundary.

**Verdict:** ACCEPT architecture closure for the refined R3.R6 identity/check semantics.

# 7. Architecture component review

No NG1 Engine is restored by name.

The minimum current NG3 architecture is sufficient:

- `ConfigurationAdapter` parses/validates Device/Profile human config and emits normalized
  domain intents;
- `VPNPathAdapter` observes/verifies lower endpoint facts;
- `PayloadTrafficManager` retains the bounded current shared Device-binding projection and
  owns effective payload policy;
- `PayloadPolicyCalculator` compiles Profile traffic semantics;
- `AvailabilityTargetCalculator` normalizes Profile/path probe targets;
- existing Availability Agent/Driver execute normalized probes.

A separate DeviceBindingManager/DeviceEngine is **not currently justified**.

The binding projection shares the same current path set consumed by payload policy and has no
independent actuation responsibility. If implementation evidence later proves that discovery
needs an independent asynchronous ownership boundary, that would reopen component design.

**Verdict:** PASS simplification review.

# 8. Derived implementation obligations

The recovered user model creates concrete implementation work.

## 8.1 Configuration parser

Must implement/test:

- TOML Device/Profile named tables;
- ID grammar;
- explicit enabled;
- disabled minimal placeholders;
- enabled Device required fields;
- enabled Profile required fields;
- strict IPv4 CIDRs;
- exact/prefix expected-interface parser;
- mandatory positive prefix quota;
- known-disabled vs unknown Device reference behavior;
- duplicate references;
- duplicate exact destination ownership;
- active cross-Device selector overlap rejection;
- Profile-level availability check parsing/normalization.

## 8.2 Configuration normalization

Must implement/test:

- active Device set from enabled Profile references;
- DeviceBindingIntent;
- ProfilePolicyIntent;
- Profile/path availability subjects;
- explicit vs derived ICMP target normalization;
- reject-before-actuation on semantic failure.

## 8.3 Runtime binding

Must implement/test:

- current endpoint observation by (ifname, ifindex);
- selector matching;
- quota admission;
- survivor preservation;
- deterministic waiting-candidate promotion;
- stable logical path slot identity;
- replacement binding without path-identity churn;
- over-quota observability without payload admission;
- inactive/unreferenced Device produces no active binding.

## 8.4 Policy compilation

Must implement/test:

- outbound Profile classification by destination;
- inbound Profile classification by ingress Device/path then source;
- deterministic longest-prefix overlap;
- explicit direction;
- Device/path eligibility;
- baseline preference hierarchy;
- disabled Device skipping without changing Profile config;
- same Device reused by multiple Profiles.

## 8.5 Availability

Must implement/test:

- availability state keyed by (Profile, logical path);
- same path may have independent Profile outcomes;
- Profile-level ICMP criterion;
- concrete target before probe runtime;
- availability never changes policy membership.

## 8.6 Status/diagnostics

Must expose enough stable identity to explain:

- Profile;
- Device;
- logical path slot;
- current concrete endpoint binding;
- over-quota/unbound candidate;
- invalid/ambiguous selector/reference;
- availability subject and normalized target;
- configured vs confirmed current state.

# 9. Evidence plan

Cheapest sufficient evidence starts with deterministic unit tests for parsing, validation,
normalization and binding projection.

Linux integration evidence is needed for:

- interface observation identity by ifname/ifindex;
- interface disappearance/reappearance;
- prefix-family dynamic endpoints;
- binding changes inside managed namespace;
- route/policy behavior for overlapping Profile destinations and shared Devices.

No new experiment is required merely to prove TOML parsing or pure normalization rules.

# 10. Closure decisions

Accept closure for all currently reopened requirements in these affected branches:

- R1 / R1.R2 configuration-intent chain;
- R1.R3 Device-binding chain;
- R2 Profile-policy refinements and parent;
- R3 preference/availability refinements and parent.

The closure is provided by the combination of:

- `design/NG3/config-model.md`;
- updated `design/NG3/architecture.md`;
- this review;
- reused historical implementation evidence where the technical claim is materially
  identical.

## Verdict

**PASS — DEVICE/PROFILE USER INTENT MODEL RESTORED AND RE-DERIVED FOR NG3.**

The restored model materially increases implementation specificity without reintroducing old
component architecture by fiat.
