# VPN-GATE NG3 — four-chain managed nft scaffold code review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-config-format-35m`

## Scope

Review the EXP-040-backed extension of the invariant managed nft scaffold from the historical
two-chain payload baseline to the accepted four-chain managed-stack baseline:

```text
stack_input
payload_forward
stack_output
payload_postrouting
```

The unit includes comparison, guarded creation/repair, dependent observer fixtures and live
integration coverage. It does not include local/system allow-policy materialization.

## Requirements / evidence

**Implements:**

- `VPNG0004-R4.R6.R1.R5`;
- `VPNG0004-R4.R6.R1.R5.R1`;
- `VPNG0004-R4.R4`;
- `VPNG0004-R4.R2`.

**Platform evidence:** EXP-040 PASS in GitHub Actions run `43910097781`.

Accepted exact additional chain shapes:

```text
stack_input:
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

stack_output:
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

EXP-040 additionally proved that foreign unconditional ACCEPT base chains before and after
priority 0 do not bypass either DROP policy and that explicit owned ICMP allow rules can
admit the tested local traffic.

## Reviewed implementation

- `nft_payload_scaffold.py` — exact four-chain immutable scaffold tuple and comparison;
- `linux_nft_scaffold.py` — existing exact-spec-driven creation/addition backend;
- `nft_scaffold_executor.py` — existing guarded scaffold prepare path;
- scaffold unit/integration tests;
- payload NAT and payload forward observer/comparison fixtures that require confirmed scaffold;
- EXP-034 production-observer fixture;
- NG3 workflow trigger coverage.

## Findings

### F1 — accepted: one invariant tuple is sufficient

The existing scaffold Calculator and Linux backend were already parameterized by the exact
`PAYLOAD_NFT_SCAFFOLD` tuple. Adding the two EXP-040-proven chain specs extends observation,
creation and repair without a second lifecycle or executor.

No generic arbitrary base-chain builder was introduced.

**Disposition:** accepted.

### F2 — accepted and fixed: dependent fixtures still claimed the old two-chain scaffold

After the invariant tuple changed, existing NAT/forward observer tests correctly failed
closed with "table/scaffold ownership is not confirmed" because their synthetic/live
rulesets still contained only `payload_forward` and `payload_postrouting`.

This was a useful regression signal: weakening the observer would have made a partial
DROP/DROP/DROP baseline appear complete.

All fixtures that claim confirmed scaffold were updated to provide all four exact chains.
A repository search found no remaining NG3 Python test fixture containing both historical
payload chain markers while omitting `stack_input`.

**Disposition:** accepted and fixed.

### F3 — accepted and fixed: EXP-034 changes did not trigger its executing workflow

EXP-034 is executed by the `linux-payload-nat` job, but its experiment directory was
missing from the workflow path filter. After EXP-034 itself needed the four-chain fixture
update, that omission could leave the relevant change untested unless another path also
changed.

The EXP-034 directory is now included in both push and pull-request path filters.

**Disposition:** accepted and fixed.

### F4 — accepted and fixed: stale two-chain contract wording

The `PayloadNftScaffoldBackend` protocol still described scaffold creation as creating
"both invariant chains", and one unit-test method retained the same wording.

Runtime behavior was correct but the contract text was stale.

**Disposition:** accepted and fixed to "all invariant scaffold chains"/"all chains".

## Safety review

The extension preserves the existing restrictive mutation boundary:

- the root `ForwardingGate` is disabled and freshly rechecked before mutation;
- an owned table with wrong chain metadata remains a conflict;
- missing exact invariant chains are repairable only when all other owned-table objects are
  classified for this scaffold-only slice;
- unknown rules/objects still block scaffold-only repair;
- success still requires fresh exact postcondition;
- this unit grants no authority to materialize future `stack_input`/`stack_output`
  allow rules.

The existing payload NAT and forward observers now require the complete four-chain scaffold,
so they cannot silently operate on an appliance missing one of the accepted default-DROP
hooks.

## Evidence

GitHub Actions run `43912610968` on the complete behavior-bearing change set:

- all 10 jobs PASS;
- rootless unit suite: **363 tests PASS**;
- EXP-040 PASS;
- managed nft scaffold comparison Linux integration PASS;
- managed nft scaffold guarded prepare Linux integration PASS;
- payload NAT observation PASS;
- EXP-034 stale-handle NAT deletion PASS;
- guarded NAT-only mutation PASS;
- payload-forward Linux evidence/observer job PASS.

A later wording-only protocol commit was also validated by run `43913075435`: PASS.
The final subsequent change only renames one test method from "both" to "all" and does not
change executable behavior.

Intermediate red runs are retained in GitHub history and correspond to the deliberate
transition where the central invariant had already become four-chain while dependent
fixtures still modeled the old two-chain state.

## Simplification review

No new:

- Manager/Agent;
- retry state;
- system-exception policy;
- firewall grammar;
- arbitrary nft base-chain abstraction;
- additional ownership namespace.

The existing exact scaffold tuple remains the single lower invariant source.

## Remaining gate

The four-chain **fail-closed scaffold** is now executable reference behavior.

Still separate:

- exact owned local/system allow contributions required for loopback, probe, publication and
  supported integration/control traffic;
- composition of those contributions with complete structural activation;
- ordered Device firewall child-chain realization.

Those are not hidden scaffold incompleteness; they are separate accepted policy units.

## Requirement-state inventory

### `decomp`

Six current links, all **resolved**:

1. `VPNG0001-R1.R2`: `VPNG0005-R5 -> VPNG0005-R5.R6`;
2. `VPNG0001-R1.R3.C1.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
3. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`;
4. `VPNG0001-R1.R3.C1.R1`: `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`;
5. `VPNG0001-R1.R3.C2.R1`: `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`;
6. `VPNG0004-R4.R6.R1.R6.R1`: `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Final verdict

**PASS — four-chain managed nft scaffold implementation unit accepted.**

No unresolved finding remains in this review unit. The next independent lower-policy unit is
the explicit managed local/system allow policy for the accepted INPUT/OUTPUT DROP hooks,
subject to the cycle checkpoint clock.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG0005-R5` -> `VPNG9101-R1.R1`
- `VPNG0005-R5.R6` -> `VPNG9101-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
