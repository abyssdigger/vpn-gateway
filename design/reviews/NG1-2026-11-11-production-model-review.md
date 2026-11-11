# NG1 — independent production-model architecture review

Date: **2026-11-11**

Scope:

- `design/NG1/vpn-gateway-architecture-ng1.md`
- `design/NG1/rou-concept.md`
- `design/NG1/rou-config.md`
- `design/NG1/NG1-2026-11-11-config-brainstorm-brief.md`

Review stance: adversarial consistency review of the committed documents as if they were
the only design input. Historical ROU v0/EXP-012 terminology is treated as evidence, not
current normative vocabulary.

## Summary

The Device/Profile split, three-Engine ownership model, expected-interface hierarchy and
TOML surface are coherent enough to implement. The review found **three blocking semantic
gaps**, two documentation/model inconsistencies and one editorial lifecycle defect.

No finding requires reversing the agreed Device/Profile or configuration model.

## A1 — BLOCKER — disabled Device reference conflicts with metric-range allocation

The configuration contract explicitly permits an enabled Profile to reference a known
`enabled=false` Device, including a minimal placeholder containing no
`expected_interfaces`.

Architecture §11 currently says every referenced Device receives a metric range sized by
derived `Device.interface_quota`.

Those statements cannot both hold because a minimal disabled Device has no quota to
derive.

Required correction:

- only **active Devices** — enabled Devices referenced by at least one enabled Profile —
  participate in current metric-range allocation;
- disabled Device references remain in `device_order` but consume no current metric
  space;
- enabling such a Device later is a CandidateConfig transition and may re-project
  Profile-local metric ranges.

## A2 — BLOCKER — terminal blackhole ordering is undefined for a /0 destination

A Profile may legally contain `0.0.0.0/0`.

The same Profile table also contains terminal `blackhole default`. Therefore for a /0
Profile the normal/unavailable default route and the terminal blackhole have identical
prefix length and compete by route priority/metric.

The current architecture defines normal metrics and an `UNAVAILABLE_METRIC`, but does not
state that the terminal blackhole is strictly worse than both.

Required invariant:

```text
normal metric < UNAVAILABLE_METRIC < BLACKHOLE_METRIC
```

for every normal metric in the Profile table.

Metric-space validation must reserve the unavailable and blackhole tail values rather than
allowing normal allocations to consume them.

Exact numeric constants may remain an implementation/platform constant if the ordering and
capacity contract are normative.

## A3 — BLOCKER — UNKNOWN availability has no production routing semantics

The first production model explicitly says Device-specific remote-availability detection
is future work, while BoundInterface already exposes:

```text
UNKNOWN | AVAILABLE | UNAVAILABLE
```

§12 says AVAILABLE uses normal priority and UNAVAILABLE is demoted, but leaves UNKNOWN
policy deferred.

Without a detector, UNKNOWN is likely the normal initial state, so the first production
implementation cannot decide whether a bound interface is routable.

Required correction:

- UNKNOWN must remain in the **normal routing tier**;
- only a positive UNAVAILABLE classification demotes a path;
- UNKNOWN must not mean proven health, only absence of a proven unavailability result.

This preserves current interface-presence behavior until a Device-specific availability
detector exists.

## A4 — MODEL CONSISTENCY — Profile identity is missing from the internal sketch

The TOML contract intentionally makes Profiles named objects:

```toml
[profile.corp]
```

Device has a stable `name`/identifier in the internal model, but the Profile sketch lists
only:

```text
enabled
direction
destinations[]
device_order[]
```

The internal Profile needs the same stable identifier concept as Device, whether the field
is named `name` or `id`.

Recommended correction: retain the already established runtime convention and add
`Profile.name` as the stable identifier derived from the TOML table key.

## A5 — DOCUMENTATION CONSISTENCY — publication notation looks normative

`rou-config.md` correctly states that the human-facing Device publication syntax remains
unresolved.

However `rou-concept.md` labels the old forms:

```text
5678/udp>7890
44443/tcp>44443
```

as “Compact configuration syntax”. Architecture §2.4 calls them “Conceptual compact
syntax”.

The concept wording can be read as an already supported TOML/config grammar and conflicts
with the explicit deferral.

Required correction: label these forms as **conceptual mapping notation only**, not the
human-facing configuration contract.

## A6 — EDITORIAL/LIFECYCLE — rou down stops the supervised runtime twice

Architecture §3.2 currently contains both:

1. step 2: stop the supervised ROU runtime ...
2. step 4: stop the supervised runtime.

This is an accidental duplicate introduced while removing the old managed-process
wording.

Required correction: keep one ordered stop operation.

## Non-blocking observations

1. Exact lexical validation for Linux interface names/prefixes is not yet specified in the
   new TOML contract. This is not a model contradiction, but the parser implementation
   should centralize it rather than spread ad-hoc checks.
2. Direct-device multipath at the unavailable fallback metric remains correctly marked as
   experimental and should not be presented as proven until its dedicated live gate.
3. Publication and traffic-envelope TOML syntax are explicitly deferred; the first parser
   must not invent them merely because the internal Device model already has those
   concepts.

## Verdict

**CHANGES REQUIRED.**

After A1-A6 are corrected, a second consistency pass should verify:

- active/disabled Device projection;
- metric tail ordering for /0;
- UNKNOWN/AVAILABLE/UNAVAILABLE routing tier semantics;
- config-to-domain identity mapping;
- no stale normative BindingSpec/capacity language outside historical prototype sections.
