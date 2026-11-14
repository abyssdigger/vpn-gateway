# NG2 — AvailabilityProbeManager observation-generation review

Date: 2026-11-14
Status: PASS

## Question

Does AvailabilityProbeManager require a physical generation token from NetworkRulesAdapter,
or can evidence validity be represented entirely inside the Manager?

## Decision

Use one Manager-local owner-wide rules-readiness epoch.

The epoch identifies one continuous interval in which the Manager has authoritative
probe rules state:

    KNOWN + MATCHED + READY

No epoch exists before READY has been freshly established.

The current epoch ends when:

- rules observation becomes UNKNOWN;
- rules become DIVERGED/INVALID;
- the accepted desired probe set changes semantically;
- concrete InterfaceIdentity in current desired intent changes.

A later fresh return to READY starts a new epoch.

All availability evidence collected in an ended epoch is stale.

## Why no Adapter generation token is required

NetworkRulesAdapter exposes semantic current state rather than its internal transaction
history. Availability evidence needs to be invalidated when the Manager can no longer
prove that its measurement plane is READY, not merely because some lower-domain command
sequence happened.

An identical physical rebuild caused by another owner may leave this owner's semantic
rules continuously READY. Completed historical availability evidence does not become false
merely because the backend re-materialized equivalent policy.

Future attempts still require the lower domain to prevent stale-flow escape. That is the
separate EXP-025/026 conntrack-generation problem and must not be solved by overloading the
upper observation epoch.

## Scope

The first ProbeRulesState is owner-wide. Therefore the readiness epoch is owner-wide too.
If any physical probe plane makes the aggregate rules state non-READY, evidence for all
logical probes in the current epoch becomes stale.

This is conservative but matches the already accepted ProbeRulesState scope. Per-plane
epochs would require a per-plane rules-state model and are not introduced preemptively.

## Representation

Expose an opaque semantic value type `ProbeObservationGeneration` rather than a bare Linux
or Adapter identifier.

Its first implementation may use a Manager-local monotonically increasing sequence.
The sequence has no meaning outside ordering/equality within one Manager runtime epoch and
must not be persisted as kernel identity.

## Result

PASS.

No new NetworkRulesAdapter API, uid/mark encoding, routing allocation field, or nft marker
is required for AvailabilityProbeManager observation generation.