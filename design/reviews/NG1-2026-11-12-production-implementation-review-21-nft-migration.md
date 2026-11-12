# Production implementation review 21 — nftables production-backend migration

Date: 2026-11-12

Role: external expert analyst focused on Linux netfilter, fail-closed transition design,
generation identity, whole-control-plane consistency and Rust migration.

## Scope

Reviewed the migration of Planner/runtime/status from legacy iptables/NAT projectors to the
ifindex-aware nftables backend, including transition classification, generation-safe
verification, ownership repair and deployment migration boundary.

## Findings

### F1 — transition proof initially re-read policy once per previous/desired comparison

Severity: medium, observation consistency.

The first migration implementation called the live verifier independently for previous and
desired filter/NAT generations. That widened the race surface and mixed observation with
reasoning.

Recommendation: observe each owned nft table once per assessment, then compare that
immutable observation to previous and desired states in memory.

Disposition: fixed with `NftObservedState` + `verify_nft_observation()`; Planner now
takes one filter and one NAT observation for each lifecycle assessment.

### F2 — absent owned nft tables were treated as backend failure

Severity: high, first-start liveness.

On a fresh namespace the production nft tables do not yet exist. Throwing from observation
prevented Planner from reaching the structural repair path that creates them.

Recommendation: represent absent owned table as a known observed state that simply fails
desired verification; reserve exceptions for actual observation/tool failures.

Disposition: fixed. Fresh absence is repairable structural state.

### F3 — verifying only the two owned tables did not prove exclusive firewall ownership

Severity: high, control-plane ownership.

A foreign nft base-chain/table in the dedicated namespace could affect packet behavior even
when vpng_filter and vpng_nat each matched desired state.

Recommendation:

- observe the full nft ruleset inventory;
- permit only the two ROU-owned tables;
- classify any foreign table as structural drift;
- behind the global forwarding barrier, remove foreign tables before rebuilding/verifying
  owned state.

Disposition: fixed and rootless-tested.

### F4 — same-name/new-ifindex structural special case belonged to legacy backend, not architecture

Severity: medium, architectural duplication.

The old transition classifier forced a global barrier for same-name/new-ifindex because
iptables matched reusable interface names. With numeric nft iif/oif and generation-safe
JSON verification this is unnecessary.

Recommendation: make transition classifier backend-neutral and consume only proof that
filter/NAT state is a previous or desired verified generation.

Disposition: fixed. Same-name replacement is ordinary lifecycle when policy generation is
known; unknown policy remains structural.

### F5 — pre-nft development namespaces cannot be silently upgraded in place

Severity: medium, deployment migration.

A namespace left by a development build may still contain legacy iptables filter/NAT state
outside nft observation. Reintroducing iptables-legacy as a production runtime dependency
only to clean unreleased development state would be architectural regression.

Recommendation: document a hard migration boundary: pre-nft development instance must be
`rou down` and recreated with `rou up` when installing the nft production baseline.

Disposition: accepted and documented in
`NG1-2026-11-12-nft-production-migration.md`.

## Production ownership after corrections

- nftables is the only production packet-policy backend;
- legacy iptables modules/tests remain historical/regression evidence only;
- dynamic Device admission is numeric-ifindex based;
- policy verification combines complete canonical policy semantics with exact numeric
  iif/oif generation references;
- full nft ruleset inventory is exclusive ROU state;
- ordinary proven lifecycle stays forwarding-open;
- structural/unknown drift uses global barrier and repairs foreign nft state;
- missing first-start tables are structural-but-repairable rather than fatal.

## Rust-alignment review

The corrected model has one production backend and explicit immutable observation values.
Transition reasoning receives proof objects rather than backend-specific serialization.
This is substantially better for a Rust port than carrying two policy engines or performing
live reads inside classification.

## Verdict

Source migration is approved after F1–F5 corrections.

Final acceptance of this function requires the privileged evidence gates to pass:

1. EXP-017 numeric-generation isolation;
2. production nft filter/NAT round-trip;
3. full disposable production reconcile cycle, including same-name replacement and foreign
   nft structural repair.
