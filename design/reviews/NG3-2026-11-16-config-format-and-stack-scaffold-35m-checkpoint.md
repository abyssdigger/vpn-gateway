# NG3 CD checkpoint — unreal label, grammar deferral and four-chain managed scaffold

**Cycle branch:** `ng3-design-cycle-20261116-config-format-35m`  
**CYCLE_START_COMMIT:** `2b36a270c8c0441ec14da3ff6289718a15efe6e4`  
**T0:** `2026-11-16T16:26:35Z`  
**CYCLE_INTERVAL:** 35 minutes  
**Nominal deadline:** `2026-11-16T17:01:35Z`

## Completed unit 1 — requirements-method label and residual-state reporting

The requirement-unrealizability causal link now uses the canonical compact syntax:

```text
[unreal: <R/C-ID>, <R/C-ID>, ...]
```

`unreal` means **unrealizable**. Its semantics are unchanged from the previously accepted
verbose link: the listed normative causes jointly make the Requirement impossible to satisfy.

`CONTINUOUS-DEVELOPMENT.md` now requires every final autonomous review/checkpoint to list:

- every current `decomp` link and whether it is pending/resolved;
- every active `unreal` link;
- every `[rejected_closure]` node;

with `none` written explicitly for empty categories.

Normative method documents contain no remaining former verbose link syntax.

Review:
`design/reviews/NG3-2026-11-16-unreal-link-method-review.md`.

## Completed unit 2 — exact user-facing grammar classified as postponed interface work

The audit found stale wording that mixed already-closed product semantics with exact
human-facing spelling still awaiting a dedicated schema decision.

Created:

`design/deferrals/NG3-user-facing-policy-grammar.md`

The deferral inventories exact external spelling/encoding for:

- Device VPN-side NAT;
- ordered Device firewall;
- named endpoint declarations/selectors;
- Profile ordinary-side gateway NAT;
- Device publication;
- Profile availability-check field/string spelling and any future user-facing timing/unit
  knobs not otherwise required.

Re-entry occurs when one of these parser/config surfaces becomes the next implementation unit
or when the user explicitly requests the compact notation decision.

The deferral does not reopen semantic R/C nodes. `config-model.md`,
`transition-tips.md` and architecture coverage wording were aligned accordingly.

Review:
`design/reviews/NG3-2026-11-16-user-facing-grammar-deferral-review.md`.

## Completed unit 3 — EXP-040 managed INPUT/OUTPUT DROP scaffold

EXP-040 established the missing Linux/nft evidence for the accepted managed-stack
`DROP/DROP/DROP` baseline.

Accepted exact lower chains:

```text
chain stack_input
    type filter
    hook input
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-input-v1"

chain stack_output
    type filter
    hook output
    priority 0
    policy drop
    comment "vpn-gate:ng3:stack-output-v1"
```

GitHub Actions run `43910097781`:

- exact JSON shape PASS;
- foreign unconditional ACCEPT before/after priority 0 did not bypass INPUT DROP;
- foreign unconditional ACCEPT before/after priority 0 did not bypass OUTPUT DROP;
- explicit owned ICMP allow in both chains restored the tested local traffic.

The architecture now accepts all four invariant managed nft base chains:

```text
stack_input
payload_forward
stack_output
payload_postrouting
```

System/local allow contributions remain a separate lower-policy unit.

## Completed unit 4 — executable four-chain scaffold

The existing scaffold Calculator/backend/guarded Executor were extended through their existing
exact invariant tuple rather than by adding a second component.

Findings resolved during implementation:

1. NAT/forward tests and live fixtures still modeled the old two-chain scaffold; they
   correctly failed closed and were migrated to all four chains.
2. EXP-034 itself used the production NAT observer over the old two-chain fixture; it was
   migrated.
3. EXP-034 was executed by CI but its directory was missing from workflow path triggers; the
   trigger list now includes it.
4. protocol/test wording still said "both invariant chains"; fixed to the four-chain meaning.

Final behavior-bearing CI:

`43912610968` — **PASS, all 10 jobs**.

Evidence includes:

- rootless suite: **363 tests PASS**;
- EXP-040 PASS;
- scaffold comparison Linux integration PASS;
- guarded scaffold prepare Linux integration PASS;
- payload NAT observation PASS;
- EXP-034 PASS;
- guarded NAT-only mutation PASS;
- payload-forward Linux job PASS.

Wording-only follow-up run:

`43913075435` — **PASS**.

Intermediate red runs are retained as transition evidence: the central invariant had already
become four-chain while dependent fixtures still claimed the obsolete two-chain state. The
fix was to migrate the fixtures, not weaken the invariant.

Review:
`design/reviews/NG3-2026-11-16-four-chain-managed-nft-scaffold-code-review.md`.

## Current requirement/architecture audit

```text
Requirement/Constraint nodes: 144
closed:                     144
pending_closure:              0
rejected_closure:             0
unlabeled:                    0
closed without architecture:  0
```

All semantic nodes remain closed. Deliberately postponed user-facing spelling is represented
through explicit constraints plus the new deferral rather than hidden open semantics.

## Accumulated requirement-state inventory

### `decomp`

All six current links are **resolved**:

1. owner `VPNG0001-R1.R2`:  
   `VPNG0005-R5 -> VPNG0005-R5.R6`.
2. owner `VPNG0001-R1.R3.C1.R1`:  
   `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
3. owner `VPNG0001-R1.R3.C1.R1`:  
   `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.
4. owner `VPNG0001-R1.R3.C1.R1`:  
   `VPNG0001-R1.R2 -> VPNG0001-R1.R2.R2`.
5. owner `VPNG0001-R1.R3.C2.R1`:  
   `VPNG0004-R4.R6 -> VPNG0004-R4.R6.R1`.
6. owner `VPNG0004-R4.R6.R1.R6.R1`:  
   `VPNG0001-R1.R3 -> VPNG0001-R1.R3.R2`.

Pending `decomp`: **none**.

### `unreal`

**none**

### `[rejected_closure]`

**none**

## Exact unfinished / blocked items

No requirement-semantic blocker was introduced in this cycle.

The next lower-policy work is still separated into bounded units. In particular:

- `stack_input`/`stack_output` are now proven and materialized as invariant DROP hooks,
  but the exact VPN-GATE-owned local/system allow contributions required for loopback,
  probes, publications and supported integrations are not yet designed/materialized;
- ordered Device firewall child-chain lower realization remains separately gated;
- Profile ordinary-side gateway NAT boundary-association Linux evidence remains pending;
- per-integration transport-endpoint provenance remains future/evidence-gated;
- exact user-facing optional-policy grammar remains postponed under its explicit deferral.

## Human decisions required now

**none**

No user-visible syntax was selected and no product semantic choice was guessed.

## Next intended review unit

Define the smallest exact managed local/system allow policy required on top of
`stack_input` / `stack_output` DROP for the already-supported Release-1 control/probe/
publication/integration scenarios, with strict separation from user Device firewall policy.
