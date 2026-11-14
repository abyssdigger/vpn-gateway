# NG2 — 40-minute autonomous cycle checkpoint

**Date:** 2026-11-14  
**Branch:** `code-cycle-20261114-runtime-bootstrap-40m`  
**CYCLE_INTERVAL:** 40 minutes  
**CYCLE_START_COMMIT:** `4b2509447fcc007e9d542b0c7edf6fef919c1406`  
**CYCLE_START_TIMESTAMP:** `2026-11-14T08:43:55Z`

This checkpoint is the recovery anchor for the cycle. It records the operational state
needed to resume without reconstructing intent from individual commits.

## Completed review units

### Runtime lower assembly

- protective runtime bootstrap before Adapter publication — PASS;
- production execution inside a pre-existing ROU network namespace — PASS;
- recovered IPv4-only namespace prerequisites:
  `rp_filter=0`, IPv6 forwarding containment and IPv6 disablement — PASS;
- dual-stack protective startup/failure barrier — PASS;
- Linux namespace/veth instance infrastructure lifecycle — PASS;
- exact reciprocal veth peer verification from kernel ifindex/link_index — PASS;
- full absent/present instance -> fail-closed infrastructure -> Adapter publication
  composition — PASS;
- runtime lower assembly whole-code audit — PASS.

The instance lifecycle owns only namespace/veth/address/main-route infrastructure.
NetworkRulesAdapter remains the sole physical owner of payload/probe network policy.

## ProbeRules semantic boundary

- a separate physical ProbeRulesAdapter was rejected because it would conflict with the
  structural NetworkRulesAdapter's exclusive physical-policy reconciliation;
- `LOCAL_PROCESS` was added as common semantic NetworkRules endpoint without exposing Linux
  uid/gid/mark;
- local-process dispatch requires exact target, protocol and concrete bound output path;
- exact ICMP echo-request/echo-reply selectors were added to common TrafficSelector;
- pure ICMP `ProbeRulesCalculator` is implemented and reviewed;
- logical probe ids are correlation identities, while physical NetworkRules are
  deduplicated by `(mechanism, InterfaceIdentity, target)`;
- same target through different concrete interface generations remains distinct;
- ProbeRules semantic whole-code audit — PASS;
- concrete Linux backend intentionally still rejects `LOCAL_PROCESS` dispatch.

## EXP-024 selective shared-namespace probe isolation

Privileged CI experiments produced three useful stages:

1. packaged `ping` could not execute after an empty capability bounding set because of its
   file-capability packaging; the harness now uses a capability-free executable copy;
2. direct nft INPUT `meta skuid` was experimentally rejected: OUTPUT matched the probe uid,
   the reply reached the exact INPUT candidate, but receiving-socket uid was not available
   there;
3. carrying the admitted OUTPUT identity through a conntrack mark passed:
   - unrelated local traffic remained on the ordinary alternate path;
   - capability-free bound probe succeeded through the intended path;
   - unbound probe could not escape through the alternate path;
   - wrong target remained blocked;
   - unrelated local traffic remained unaffected.

Result: **preliminary mechanism PASS on privileged GitHub Linux CI**.

The exact Debian 13 confirmation command is recorded in the EXP-024 README.

## Evidence baseline

Relevant green gates on this branch include:

- NG2 rootless unit suite — PASS;
- NG2 privileged structural Linux Adapter integration — PASS;
- NG2 privileged live payload dataplane/NAT integration — PASS;
- NG2 Linux instance lifecycle integration — PASS;
- dual-stack restart containment — PASS;
- namespace prerequisite mutation/repair — PASS;
- exact live veth peer verification — PASS;
- production nft exact/negated ICMP selector syntax through kernel `nft -c` — PASS;
- EXP-024 conntrack-mark selective probe isolation P1..P5 — PASS;
- NG1 Python regression validation — PASS.

The latest implementation code baseline before documentation-only closure is
`96cb9d8ccf976655bb72a629f8543be4e7d0ba3c`, with NG2 and NG1 gates green.

## Intentionally unfinished / blocked

1. Run EXP-024 unchanged on the Debian 13 target and retain complete output.
2. Only after target PASS, implement Linux `LOCAL_PROCESS` physical materialization as one
   reviewed unit:
   - process-identity/output-interface/protocol/target RPDB selector;
   - owner routing table and fail-closed terminal path;
   - selective nft OUTPUT admission;
   - lower-domain conntrack flow mark;
   - selective reverse INPUT admission;
   - exact observation and verification.
3. After real physical apply/renew observation exists, implement
   `ProbeRulesStateCalculator`.
4. Then perform the mandatory `PayloadRulesState` vs `ProbeRulesState` comparison and
   introduce a common rules-state type only if their semantics are genuinely identical.

## Human agreement

No product-policy or architecture choice currently requires human agreement.

The only gate before the next physical implementation unit is target evidence for the
already selected EXP-024 mechanism.
