# NG1 production final whole-project review — pass 2

Date: 2026-11-12

Role: final internal expert review under CONTINUOUS-DEVELOPMENT.md.

Reviewed baseline: commit 86d10b2e5c983290af1ceba772af9ed28484ba61 plus
documentation-only review recording.

## Scope

Re-reviewed the complete current production implementation after all findings from final
review pass 1 were fixed:

- schema/domain invariants;
- Device/Traffic engines and durable state;
- routing/RPDB allocation, verification and incremental/structural transitions;
- nft filter/NAT ownership, generation markers and verification;
- Planner/run loop/event source;
- namespace lifecycle/publications/runtime composition;
- status/CLI/systemd/deployment;
- disposable privileged integration evidence;
- deferred/future experiment boundaries.

## Verification of pass-1 corrections

Confirmed:

- status and Planner now share exclusive nft ruleset ownership semantics;
- rou up returns success only after verified appliance/state/policy and ip_forward=1;
- already-active rou up verifies non-disruptively;
- failed-up rollback destroys the namespace only after service inactivity is proven;
- uncertain/active rollback is contained and refuses teardown;
- EXP-018 documentation names the nft production backend.

## Evidence

GitHub validation on the corrected baseline:

- RC3 Python validation: SUCCESS;
- NG1 rootless test job: SUCCESS;
- NG1 privileged kernel-integration job: SUCCESS.

Privileged evidence includes:

- EXP-017 numeric iif/oif same-name/new-ifindex isolation: PASS;
- production nft policy round-trip: PASS;
- disposable production cycle:
  - PASS A initial production reconcile;
  - PASS B same-name/new-ifindex incremental replacement;
  - PASS C verified metric-slot release/promotion;
  - PASS D ordinary member disappearance incremental repair;
  - PASS E foreign nft structural barrier repair;
  - PASS F durable runtime state matches final verified state;
  - NG1_PRODUCTION_CYCLE=PASS.

## Whole-project consistency

No conflicting production backend remains: nftables owns production filter/NAT semantics;
legacy iptables remains regression/historical evidence only.

Remote-initiated schema-v1 safety remains bounded by:

- active capacity exactly 1;
- restrictive Device envelope default=drop.

Persistent shadow fallback is implemented and verified while its positive UNAVAILABLE
trigger remains deliberately absent until future DeviceManager/availability work.

Structural/unknown drift remains barriered; proven binding-lifecycle and route-additive
transitions remain incremental.

Status, CLI and systemd semantics are consistent with the architecture's definition of a
successful and safe ROU appliance.

## Rust-alignment assessment

No new recommendation.

The current Python code retains suitable Rust migration boundaries:

- typed immutable domain/value objects;
- pure projection separated from mutation;
- explicit desired/observed/verification types;
- backend-neutral transition evidence;
- RAII-shaped runtime/lifecycle ownership;
- fail-closed errors rather than implicit adoption;
- no shell-string policy execution path.

## Remaining work classification

No unblocked required production-code function remains in the current core scope.

Outstanding items are evidence/future work:

- EXP-018: real Debian 13 systemd/PID1 deployment smoke — requires target host;
- EXP-015: real VPN TCP MTU/MSS signoff — requires real OpenConnect/WireGuard payload
  topology;
- EXP-016: ECMP hash-policy prerequisite — future availability work and feasible in a
  disposable namespace;
- DeviceManager/positive UNAVAILABLE trigger — future scope after EXP-016;
- EXP-014 multi-interface remote-initiated flow pinning — explicitly postponed until after
  the first working production release.

## Verdict

**CLEAN.**

No unresolved finding of minor severity or higher remains in the implemented production
code scope.

The NG1 Python production implementation therefore satisfies the current code-completion
criterion. Further work should proceed through the remaining evidence gates/future scope
rather than by adding more core implementation without a new requirement.
