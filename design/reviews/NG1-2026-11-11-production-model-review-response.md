# NG1 — response to production-model architecture review

Date: **2026-11-11**

Review: `design/reviews/NG1-2026-11-11-production-model-review.md`

All six findings are accepted.

## A1 — disabled Device and metric allocation

**Accepted.**

Architecture now defines an active Device as an enabled Device referenced by at least one
enabled Profile.

Only active Devices consume current Profile-local metric ranges. A known disabled Device
may remain in `device_order` without a complete `expected_interfaces` body and consumes
no current metric space.

Enabling it later is a configuration transition that may re-project metric ranges.

## A2 — /0 and terminal blackhole ordering

**Accepted.**

The normative ordering is now:

```text
normal metric < UNAVAILABLE_METRIC < BLACKHOLE_METRIC
```

Metric-space validation reserves both tail values. The terminal blackhole is explicitly:

```text
blackhole default metric BLACKHOLE_METRIC
```

This removes ambiguity when a Profile destination itself is `0.0.0.0/0`.

## A3 — UNKNOWN availability

**Accepted.**

UNKNOWN and AVAILABLE both remain in the normal routing tier. UNKNOWN means only “no
positive availability determination”; it is not a health assertion.

Only positive UNAVAILABLE classification demotes a path to the fallback tier.

## A4 — Profile identity

**Accepted.**

The internal Profile model now includes stable `name`, derived from the named TOML
`[profile.<id>]` table exactly as Device identity is derived from
`[device.<id>]`.

## A5 — publication notation

**Accepted.**

The old `5678/udp>7890` forms are now labelled conceptual mapping notation only.
`rou-config.md` remains authoritative that human-facing publication TOML syntax is
unresolved.

## A6 — duplicate rou down operation

**Accepted.**

The duplicate supervised-runtime stop step was removed.

## Additional consistency updates

- `rou-concept.md` now reflects UNKNOWN/AVAILABLE normal-tier semantics and the strict
  metric tail ordering.
- `rou-config.md` now states explicitly that disabled Device references consume no
  current metric range.

## Status

All findings from the first review are incorporated into the normative documents.

A second independent consistency pass is required before implementation starts.
