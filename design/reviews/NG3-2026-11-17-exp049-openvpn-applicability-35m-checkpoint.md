# VPN-GATE NG3 — EXP-049 OpenVPN applicability CD checkpoint

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-exp049-openvpn-applicability-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `db481a00481f3c939901817d0fdc2d535bb41dcf`  
**T0:** 2026-11-17T07:21:29Z

## Cycle boundary

The EXP-049 logical unit completed before the nominal interval.

Last pre-checkpoint logical commit:

`362fd8eb3a82ec3d62a1208e0d5f4c3e5c87e71c` at
`2026-11-17T07:27:19Z`.

Elapsed logical-development interval before checkpoint: approximately **5m50s**.

The unit ends on an accepted negative applicability result. It is not extended with an ad-hoc
policy fix because EXP-049 explicitly forbids changing VPN-GATE internals merely to convert a
failed run into PASS.

## Experiment

`EXP-049 — administrator VPN endpoint onboarding applicability`

Candidate:

```text
OpenVPN 2.6.14
client process started inside NG3 managed network namespace
client creates vpn0 TUN directly inside that namespace
```

No WireGuard-specific namespace behavior and no interface move from another namespace is used.

## Evidence

Substantive evidence commit:

`efbb7db0ce18ec2d9afe6fd0bf127afd4767b49f`

GitHub Actions run:

`44038446087`

Environment inside the privileged experiment container:

```text
Debian GNU/Linux 13.7 (trixie) userspace
OpenVPN 2.6.14
Python 3.13
privileged Linux namespace/TUN/nft execution
```

The container runs on the GitHub Actions host kernel; therefore a future positive target claim
must still satisfy any separately required target-kernel confirmation. The observed negative
finding is an explicit current NG3 nft policy effect and does not depend on claiming a Debian
kernel version.

All ordinary NG3 jobs on the run passed. Only `linux-exp049-openvpn` failed.

## Two clean cycles

Both cycles proved:

```text
VPN endpoint initially absent                         PASS
managed underlay reaches OpenVPN server               PASS
real OpenVPN tunnel inside managed domain             PASS
fresh production observation                          PASS
exact LogicalPathId -> vpn0 binding                   PASS
production startup/binding/activation                 PASS
controlled payload through admitted VPN path          FAIL
local VPN underlay after activation                   BLOCKED
external client stop removes vpn0                     PASS
NG3 controller/domain cleanup                         PASS
```

Production activation left:

```text
stack_output:
    policy drop
    no supported-integration local/system allow rule
```

The real OpenVPN process therefore loses the locally generated/received UDP underlay required
to carry encrypted tunnel traffic.

## Finding

**Supported-integration local/system policy gap.**

The experiment disproves neither:

- real userspace VPN placement inside managed netns;
- current interface discovery;
- exact logical-path binding.

It rejects the current complete onboarding closure because a bound/admitted path is unusable
after NG3 activates its own fail-closed local policy.

No ad-hoc nft exception was added.

## Requirement disposition

`VPNG-U001-R1.R3.C1.R1.R1`:

```text
[closed] -> [rejected_closure]
```

Reason: its required real applicability acceptance evidence failed.

The Requirement remains desired and appears reachable.

### `unreal`

none

### `broken`

none

### `decomp`

Six accumulated links remain resolved.

Pending: none.

### `[rejected_closure]`

- `VPNG-U001-R1.R3.C1.R1.R1` — EXP-049 current OpenVPN candidate cannot carry payload after
  production activation because concrete integration local/system permission is absent.

## Architecture disposition

The existing generic `LocalSystemAllowIntent(owner_function=integration(...))` boundary was
not weakened.

Architecture now records the evidence:

```text
real in-stack OpenVPN
    -> placement/binding works
    -> terminal local DROP blocks transport
    -> exact integration selector contract still required
```

The next closure unit must derive the minimum safe source-owned integration local/system intent
and its observable/mutable Linux realization.

## EXP-050

**BLOCKED.**

Its explicit prerequisite remains EXP-049 PASS.

## Review

`design/reviews/NG3-2026-11-17-exp049-openvpn-applicability-review.md`

Verdict:

**EXP-049 FAIL — finding accepted.**

## Next intended logical unit

Requirement/architecture closure for a concrete supported-VPN local/system control contract.

Questions to answer from the evidence, not from generic framework assumptions:

- which underlay/control facts the onboarding contract must expose;
- minimum safe `stack_output` selectors;
- minimum safe reverse `stack_input` selectors;
- stale contribution identity/removal;
- how those facts enter current desired-state activation without ambient socket inference.

Then implement/evidence that bounded contribution and rerun the unchanged EXP-049 scenario.

Do not begin EXP-050 or bounded-VPN lifecycle ownership work before EXP-049 PASS.

## Checkpoint verdict

**COMPLETE NEGATIVE GATE — EXP-049 FAIL ACCEPTED AND REQUIREMENT CLOSURE REJECTED.**
