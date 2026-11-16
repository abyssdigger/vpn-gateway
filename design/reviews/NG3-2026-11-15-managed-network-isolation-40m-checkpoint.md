# VPN-GATE NG3 — Managed Network Isolation Cycle Checkpoint

**Cycle:** `ng3-design-cycle-20261115-isolation-40m`  
**CYCLE_INTERVAL:** 40m  
**Transition reason:** current review unit completed; user explicitly authorized entry into the next cycle before interval expiry.

## Cycle clock

```text
CYCLE_START_COMMIT:
1319cc7704d0677b9660e9468306aef40726fc57
2026-11-15T20:32:33Z
NG3: define managed network isolation requirement

last content head before checkpoint:
0bb2ca76d98ba974be800aa66fe2b594821858eb
2026-11-15T20:49:36Z
NG3: review managed network isolation boundary

elapsed to last content head:
17m 03s
```

## Completed

- added `VPNG-R4.R6` managed-network isolation requirement without prescribing Linux netns;
- selected a dedicated Linux network namespace as current NG3 architecture for that requirement;
- added VPN-channel constraints `VPNG-R1.R3.C2` / `VPNG-R1.R3.C2.R1`;
- generalized the rule that accepted constraints which move work outward create a compensating product obligation;
- introduced compact decomposition dependency links:
  `[decomp: <blocker> -> <pending|deblocker>]`;
- linked both VPN onboarding requirement branches to `VPNG-R4.R6 -> pending`;
- added requirement-maintenance rules: stable IDs, in-place updates, Git history as current editorial record, semantic change journal deferred;
- completed managed-network isolation review with PASS verdict.

## Evidence

```text
requirement/constraint IDs: 58
active decomposition links: 2
broken architecture references: 0
```

## Open decomposition gate

```text
VPNG-R1.R3.C1.R1
  [decomp: VPNG-R4.R6 -> pending]

VPNG-R1.R3.C2.R1
  [decomp: VPNG-R4.R6 -> pending]
```

The next cycle must decompose `VPNG-R4.R6` only far enough to define the required properties of the isolated managed network domain and its external boundary. It must not guess Linux onboarding commands or VPN-process placement.
