# NG3 server-publication runtime — 35m cycle checkpoint

**Cycle interval:** 35 minutes  
**Branch:** `ng3-beta-cycle-20261117-server-publication-35m`  
**Base clean main:** `b242fd9d74ba9a62b88f07225da6a61b62d7e4ab`  
**CYCLE_START_COMMIT:** `c3d8fe3903037794a0e03dd7f7457c56401efb85`  
**T0:** 2026-11-17T19:59:36Z  
**Final technical hardening commit:** `4ba2db57587f2bd8797c70f75e46ee120aee0d8a`  
**Final review commit:** `06e177adb141acafd74377862dcc7d043aa9bbdf`

The logical work unit completed materially before the nominal 35-minute boundary; no new
review unit was started merely to consume the remaining window.

## Closed logical unit

Canonical Release-1 Device `publish_vpn_server` is now materialized through the complete
reference runtime path:

```text
canonical Release-1 config
    ->
pre-mutation publication projection validation
    ->
managed local publication admission
    ->
strict ordinary-host publication DNAT owner
    ->
fresh prerequisite/owner verification
    ->
READY / periodic reconciliation
    ->
host owner cleanup
    ->
managed-domain teardown
```

The cycle did not change product requirements or grammar.

## Evidence

Final full NG3 Python run after the last technical hardening:

- run `44168281782` — **PASS**;
- unit — PASS;
- `linux-host-publication-dnat` — PASS;
- `linux-alpha-smoke` — PASS;
- all other NG3 Linux/experiment jobs in the workflow — PASS.

Installed publication extension evidence:

- run `44167358884`;
- alpha smoke job `134336862209` — PASS;
- real external TCP crossed host DNAT + managed local admission;
- publication existed before VPN endpoint appearance;
- VPN-only restart remained functional;
- host publication owner was absent after controller stop.

## Review findings fixed in-cycle

1. Initial host DNAT match could capture same-port foreign transit.
   - Fixed with mandatory pre-DNAT `fib daddr type local`.
2. Host forwarding risked becoming implicit runtime ownership.
   - Kept as observed external prerequisite; runtime does not set host-global forwarding.
3. Explicit host selectors lacked complete readiness checks.
   - Interface must exist and be UP; exact IPv4 must be locally assigned.
4. Overlapping selector mappings could otherwise acquire rule-order semantics.
   - Conflicting overlaps are rejected.
5. Conflict detection was initially too late in startup.
   - Complete host-publication projection is now validated before any runtime mutation.
6. Lower interface-name type was weaker than canonical parser.
   - Hardened independently to safe ASCII Linux-ifname subset.
7. Omitted selector semantics were rechecked against `config-model.md`.
   - It means no additional user-selected host address/interface restriction; no hidden
     public-only whitelist was invented.
8. Cleanup semantics were bounded.
   - Owner rule absence is proven; forced destruction of pre-existing conntrack/session state
     is not claimed because no accepted requirement demands it.
9. Foreign arbitrary host NAT/firewall remains outside VPN-GATE ownership.
   - Exact owner/prerequisite postconditions are proven without adopting unrelated host state.

## Requirement state

All **159/159 actual requirement entries remain `[closed]`**.

Accumulated decomposition links, all resolved:

- `VPNG0005-R5 -> VPNG0005-R5.R6`;
- `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
- `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
- `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.

Active `unreal`: **none**.  
Active `broken`: **none**.  
`closure_rejected`: **none**.

## Review verdict

**PASS.**

No human product decision remains for this unit. The final branch tree is suitable for one
linear mainline snapshot; intermediate cycle commits remain on the cycle branch.
