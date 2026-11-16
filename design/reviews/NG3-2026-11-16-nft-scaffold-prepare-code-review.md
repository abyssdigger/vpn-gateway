# VPN-GATE NG3 — Guarded nft Scaffold Preparation Code Review

**Date:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-structural-barrier-40m`  
**Reviewed commit:** `f8c17bc7d0aff5dc54c7f90fd37533eef4e22bf2`

## Scope

This unit is the first structural nft mutation in NG3.

It is intentionally restricted to the invariant payload scaffold and cannot materialize any
Profile allow rule, traffic-envelope rule or NAT rule.

## Root barrier coupling

PASS.

`prepare_payload_nft_scaffold_once()` first converges the managed-netns ForwardingGate to
DISABLED.

No nft observation or mutation begins unless that gate is independently confirmed.

Immediately before a required nft mutation the gate is reread again.

After the final nft observation the gate is reread once more and success is impossible if
the gate is no longer disabled.

The function never re-enables forwarding.

## Allowed mutation surface

The backend can perform only two operations:

```text
ABSENT namespace:
    create marked table + both invariant chains

OWNED, fully classified partial scaffold:
    add only the proved-missing invariant chain(s)
```

There is no delete/replace/general-rule API in this backend.

Generated scripts contain only fixed reviewed constants; no user ID or arbitrary nft
statement is interpolated.

## Refusal conditions

PASS.

Mutation is refused when any of the following is present:

- table marker conflict;
- invariant-chain metadata conflict;
- any `unclassified_object`;
- root barrier lost/unreadable immediately before mutation.

This means the bootstrap helper cannot become a cleanup mechanism for a partially understood
future/full nft table.

## Failure/re-observation semantics

PASS.

A lower nft apply exception is followed by fresh full-ruleset observation.

If the exact fully classified scaffold is independently present afterward, the attempt may
return SUCCESS while preserving the apply error as diagnostic evidence.

Otherwise the result is unconfirmed.

No retry loop is hidden.

## No-op semantics

PASS.

An already exact scaffold is still freshly re-observed and the root barrier is rechecked
before success.

## Linux backend

PASS.

The physical backend uses nft batch stdin with fixed scripts.

A missing invariant chain is added without replacing the marked table or the surviving
invariant chain.

## Live evidence

GitHub Actions run:

```text
run:      43839920067
commit:   f8c17bc7d0aff5dc54c7f90fd37533eef4e22bf2
unit:     256 tests, OK
EXP-032 payload nft scaffold: PASS
scaffold comparison integration: PASS
scaffold prepare integration: PASS
EXP-031 owner marker: PASS
EXP-030 root barrier: PASS
EXP-028/029 + route-priority: PASS
overall:  success
```

The live preparation integration proves:

1. starting with forwarding enabled, the Executor closes the gate and creates the scaffold;
2. deleting one invariant chain is repaired while the gate remains disabled;
3. after adding an unclassified nft rule and deleting a chain, scaffold-only repair refuses
   mutation and leaves the missing chain missing.

## Residual boundary

The invariant nft substrate is now executable.

The next question is semantic rather than mechanical:

```text
normalized DevicePolicyIntent
+ PayloadProfileRequest / binding state
    ->
complete payload nft desired rules
```

This may proceed only to the extent that the internal normalized policy semantics are already
accepted. It must not invent unresolved human-facing TOML grammar.

## Final verdict

**PASS.**
