# VPN-GATE NG3 — combined Profile / Device / NAT nft convergence review

**Date:** 2026-11-16  
**Cycle branch:** `ng3-design-cycle-20261116-composite-policy-35m`

## Scope

Review the first whole-table nft convergence unit that combines all currently materialized
payload owner classes:

- invariant four-chain scaffold;
- Profile `payload_forward` NEW/RETURN admission;
- ordered Device firewall child chains/jumps/rules;
- payload postrouting NAT.

`stack_input` / `stack_output` local-system allow contributions are intentionally outside this
unit because their exact lower owner shapes are not yet evidence-backed.

## Main result

**PASS.** The previously separate bounded slices can now coexist under one read/compare/plan/
mutate/re-observe Executor without one owner class treating another accepted class as foreign.

## Evidence

### Composite read-only coexistence

Rootless tests prove one observation containing Profile forward + Device firewall + NAT can
simultaneously satisfy one `CompositeNftDesiredState`. Unknown local/system rules and foreign
child chains remain whole-scope conflicts.

### EXP-045 — missing Profile write primitive

Workflow `43933507340`: **PASS**.

With Device and NAT objects already present:

- Profile `add rule` appended after the existing Device jump;
- exact-handle deletion removed only the selected Profile rule;
- Device child/jump and NAT objects were preserved;
- real forwarded traffic passed with Profile admission and failed after its exact deletion.

Accepted lower primitives:

```text
missing Profile rule -> add rule
stale Profile rule   -> delete exact observed handle
```

### Combined privileged integration

Workflow `43934154036`: **PASS**.

Starting from scaffold-only state, the combined Executor converged in this addition order:

```text
NAT
Device chain/jump
Device chain/jump
Profile admission
Profile admission
```

Both Device jumps were physically before Profile accepts.

Convergence back to scaffold-only state used:

```text
Profile rule
Profile rule
Device jump
Device jump
Device chain
Device chain
NAT
```

The ForwardingGate remained disabled throughout. An unclassified `stack_input` rule caused
`CONFLICT` before mutation.

## Findings

### F1 — owner-specific green is not whole-table ownership

Running Profile, Device and NAT comparisons independently is insufficient because an object
unknown to all of them could remain in the reserved table.

**Disposition:** `compare_composite_nft_policy` performs the owner-specific comparisons and
then classifies every remaining table object. Unknown objects are whole-scope conflicts.

### F2 — bounded executors must not reject each other's valid state

The earlier NAT-only and Device-only mutation slices deliberately refused other owner classes.
That behavior was safe as bounded evidence but cannot serve final coexistence.

**Disposition:** combined desired/compare/backend now recognizes Profile + Device + NAT
together from one fresh snapshot.

### F3 — new positive Profile permission must be last among additions

Creating Profile acceptance before required NAT or Device restriction could expose an
incomplete policy if the barrier were lost.

**Disposition:** pure planner orders additions `NAT -> Device -> Profile`.

### F4 — stale positive admission should be removed first

Old Profile ACCEPT is the widest positive object among current classes.

**Disposition:** cleanup starts with stale Profile rules, then removes Device references/
chains and NAT. Device jump removal remains before child deletion due nft reference rules.

### F5 — mutation commands are not committed truth

**Disposition:** every step requires one pre-write link-bracketed composite snapshot, a closed
ForwardingGate, one planned write, a fresh post-write composite snapshot, unchanged interface
inventory, strict distance reduction and a final closed-gate check.

### F6 — local/system rules must not be guessed into the combined scope

The architecture already accepts VPN-GATE-owned local exceptions, but exact rule shapes for
probe/publication/integration functions are not all proven.

**Disposition:** current combined Executor rejects unclassified `stack_input`/`stack_output`
rules. This is an implementation/evidence boundary, not a product Constraint. The next nft
owner extension must define those exact contributions first.

## Component-model review

- `CompositeNftDesiredState`: immutable composed lower desired data.
- `compare_composite_nft_policy`: pure Direct Calculator.
- `select_composite_nft_step`: pure Direct Calculator.
- `converge_composite_nft_step_once`: Executor.
- `LinuxCompositeNftBackend`: Driver over existing nft mechanism.

No Manager, Agent, persistent handle registry, event stream or rollback journal was introduced.

## Simplification review

Not introduced:

- whole-table blind rebuild;
- generic firewall AST;
- a second semantic policy model;
- duplicated Device/NAT lower Drivers;
- persistent nft handle database;
- automatic adoption of unknown local/system rules;
- forwarding activation inside the structural Executor.

## Accumulated requirement-state inventory

### `decomp`

All six current links remain **resolved**:

1. `VPNG-U001-R1.R2`: `VPNG-U005-R5 -> VPNG-U005-R5.R6`.
2. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
3. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.
4. `VPNG-U001-R1.R3.C1.R1`: `VPNG-U001-R1.R2 -> VPNG-U001-R1.R2.R2`.
5. `VPNG-U001-R1.R3.C2.R1`: `VPNG-U004-R4.R6 -> VPNG-U004-R4.R6.R1`.
6. `VPNG-U004-R4.R6.R1.R6.R1`: `VPNG-U001-R1.R3 -> VPNG-U001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Human decisions required

**none**

## Next logical unit

Extend whole-table ownership to exact VPN-GATE local/system INPUT/OUTPUT contributions only
where a supported function has a proven lower packet shape. Do not add blanket conntrack/
loopback/probe/publication exceptions by convention. Probe remains constrained by the existing
EXP-024/025/026 evidence boundary.

## Verdict

**PASS.** Combined nft structural convergence is closed for Profile forward + Device firewall
+ payload NAT.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5` -> `VPNG-M001-R1.R1`
- `VPNG-U005-R5.R6` -> `VPNG-M001-R1.R1.R6`

The original IDs in the historical body are intentionally preserved.
