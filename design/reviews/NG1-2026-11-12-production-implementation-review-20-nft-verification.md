# Production implementation review 20 — generation-safe nft verification

Date: 2026-11-12

Role: external expert review focused on nftables generation identity, observation integrity,
failure modes and Rust migration.

## Scope

Reviewed:

- EXP-017 numeric iif/oif evidence;
- nft JSON output after same-name/new-ifindex replacement;
- `nft_policy.py` desired state, textual canonicalization and JSON ifindex verification;
- rootless regression tests.

## Evidence

EXP-017 proved:

- numeric iif/oif matches the original generation;
- a fresh same-name/new-ifindex interface does not inherit those rules;
- `nft -j list table` preserves the stale rule's iface_index numerically even after the
  name has been reused by a new interface generation.

The JSON example contained meta iif/oif right-hand values for the old index, independent of
the current interface name.

## Findings

### F1 — generation identity must not rely on textual name normalization

Accepted and fixed before this review. Production verification now compares the exact
multiset of numeric iif/oif references parsed from nft JSON in addition to complete textual
policy canonicalization.

A textual false-positive caused by live-name resolution therefore cannot make a stale
generation verify as the desired generation.

### F2 — nft live reads should be one explicit observation boundary

The first implementation called text and JSON helpers directly from the verifier. That
invites future Planner/transition code to reimplement partial observation differently.

Severity: low/medium, maintenance consistency.

Disposition: fixed with immutable `NftObservedState` and `observe_nft_state()`.

The runtime serializes its own table mutations. A foreign concurrent writer can always make
any post-verification observation stale; the normal periodic audit/structural-drift model
handles that. The important safety property here is that one concrete stale interface
generation cannot be normalized into another.

### F3 — verification diagnostics should always expose both policy and generation refs

Severity: low.

Disposition: fixed. Actual and expected diagnostics now both include the numeric interface
reference multiset.

## Rust-alignment review

The desired/observed/verification split maps directly to Rust structs and a backend trait.
Numeric generation identity is represented as typed pairs rather than reconstructed from
human-facing interface names.

## Verdict

Approved. The generation-safe nft verification boundary has no remaining recommendation.

This removes the verification gate for migrating PlannerEngine to nftables.
