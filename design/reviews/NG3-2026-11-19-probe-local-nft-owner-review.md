# NG3 2026-11-19 — probe-local nft owner review

## Verdict

**PASS — EXP-066-backed probe-local nft owner is integrated into the existing composite
`vpn_gate` convergence contract.**

## Scope

This unit closes the physical local-admission half of the Release-1 ICMP probe policy that was
left at an evidence-only boundary in snapshot 102.

It does not execute or schedule probes. It materializes only the already accepted local
preconditions for a later ICMP attempt.

## Desired semantics

The existing `ProbeLocalRuleSpec` remains the semantic input.

OUTPUT:

```text
dedicated non-root probe UID
+ exact current endpoint
+ exact target
+ ICMP
    -> set dedicated probe conntrack mark
    -> accept
```

INPUT:

```text
exact current endpoint
+ exact remote source
+ ICMP
+ dedicated probe conntrack mark
    -> accept
```

INPUT does not use receiving-socket UID.

## Authoritative observation

New `probe_local_observation.py` decodes only rules carrying:

```text
vpn-gate:ng3:probe-local-v1
```

inside the existing `ip vpn_gate` owner.

The decoder requires the exact EXP-066 expression shape and validates:

- chain/hook;
- dedicated UID on OUTPUT;
- exact interface selector;
- exact IPv4 target/source;
- IPv4 protocol 1;
- conntrack-mark assignment on OUTPUT;
- conntrack-mark match on INPUT;
- terminal plain ACCEPT.

The whole nft snapshot remains the existing link-bracketed composite observation. No second
nft observer or table is introduced.

## Interface-generation safety

EXP-066 showed that an nft rule created against `path0` at ifindex 2 survives deletion and
same-name recreation at ifindex 3 with its old selector exposed as raw string `"2"`.

The decoder therefore resolves:

```text
current interface name -> current InterfaceIdentity
raw numeric old ifindex -> stale physical generation
```

and cannot silently rebind an old probe allow to a same-name replacement interface.

## Semantic owner vs physical nft identity

`ProbeLocalRuleSpec` carries `(Profile,path)` for semantic traceability, but nft does not
encode that owner identity and does not need to.

Two Profiles may legitimately project to the same physical local admission. The comparator
therefore treats desired probe-local policy as a **set-union of physical keys**:

```text
hook
current endpoint identity
target/source address
conntrack mark
process UID on OUTPUT only
```

Identical physical rules from different semantic owners are materialized once. No artificial
owner tag, per-Profile chain or duplicate ACCEPT is introduced.

## Comparison and mutation

`ProbeLocalComparison` reports:

- confirmed physical rules;
- missing physical rules;
- stale observed rules;
- conflicts.

New `probe_local_mutation.py` produces one full-diff transaction:

```text
delete every stale probe-local handle
add every missing unique physical rule
```

New `linux_probe_local.py` renders that transaction as one nft batch using the existing
`stack_input` / `stack_output` chains.

Deletion is exact chain + handle. Addition uses the EXP-066 shape.

## Composite integration

`CompositeNftDesiredState` now accepts the probe-local contribution and
`compare_composite_nft_policy` classifies its owner comment rather than treating it as an
unclassified local/system rule.

The existing planner preserves the fail-closed ordering:

```text
stale local accepts
    -> removed before payload cleanup

payload restrictive cleanup/addition
existing local additions
probe-local missing additions
```

The relative order between independent local-owner repair classes carries no new product
semantics; all stale positive local admission remains before payload cleanup and all missing
probe admission remains after the protected payload structural work.

`converge_composite_nft_step_once` includes probe-local missing/stale state in its strict
progress distance and delegates the physical batch through the existing
`LinuxCompositeNftBackend`.

No new Manager, nft table, generic local-firewall framework, rollback journal or retry state
was added.

## Verification

Current code-bearing run:

```text
GitHub Actions run: 44463957983
head: 471800c71ebd03b4a142dd33653c931df76c052f

unit: PASS — 752 tests
linux-structural-inventory-shape: PASS
```

New rootless coverage includes:

- exact EXP-066 OUTPUT/INPUT pair confirmation;
- same-name/new-ifindex stale classification;
- physical set-union across two semantic owners;
- malformed OUTPUT conntrack-mark shape conflict;
- duplicate physical rule conflict;
- atomic stale-delete + missing-add planning;
- exact Linux OUTPUT/INPUT rendering;
- composite owner classification;
- stale probe-local cleanup before payload cleanup;
- missing probe-local addition after payload additions;
- Linux composite backend delegation.

The workflow's previously known unrelated privileged failures remain outside this unit.

## Requirement / architecture integrity

No normative Requirement or Constraint changed.

Mechanical state remains:

```text
normative R/C nodes:             172
closed:                          172
pending_closure:                   0
rejected_closure:                  0
open:                              0

architecture requirement IDs:   172
missing exact refs:                0
extra refs:                        0
```

## Requirement-state inventory

Active:

- `decomp`: none pending;
- `unreal`: none;
- `broken`: none;
- `[rejected_closure]`: none.

Historical resolved decomposition links are unchanged.

## Preliminary runtime-transparency expectation

This cycle also records, in `design/NG3/declarations.md`, the requested preliminary
non-normative expectation that VPN-GATE should eventually expose a config-shaped current-state
snapshot organized by Device and Profile.

That declaration deliberately does not modify the 172-node normative tree in this unit.
Unresolved user-visible semantics are deferred for explicit requirement discussion and are
listed in the cycle handoff rather than guessed in implementation.

## Remaining probe boundary

The lower network-policy preconditions for a normalized concrete probe subject are now
materializable:

```text
probe route/RPDB owner
    -> desired / observe / compare / mutate

probe-local nft owner
    -> desired / observe / compare / mutate
```

Still absent:

- target derivation for bare `availability_check = "icmp"` cases that require derived
  targets;
- actual ICMP attempt execution;
- observation-context generation handling around attempts;
- confirmation/hysteresis orchestration;
- feeding confirmed availability into the already implemented effective route-order runtime.

## Conclusion

The probe-local nft plane is no longer an evidence-only gate. It is a bounded classified owner
inside the existing composite nft transaction and preserves the exact EXP-024/066 isolation
mechanism without widening local traffic admission or inventing new lifecycle machinery.
