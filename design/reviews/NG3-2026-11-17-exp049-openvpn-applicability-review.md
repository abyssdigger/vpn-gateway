# VPN-GATE NG3 — EXP-049 OpenVPN applicability review

**Date:** 2026-11-17  
**Cycle branch:** `ng3-design-cycle-20261117-exp049-openvpn-applicability-35m`  
**Experiment:** EXP-049 administrator VPN endpoint onboarding applicability

## Experiment verdict

**FAIL.**

The first real candidate integration reaches in-stack OpenVPN endpoint placement, fresh
production observation and exact logical-path binding, but cannot carry controlled payload
after current NG3 policy activation.

This is a valid acceptance failure, not an environmental or harness failure.

## Evidence baseline

Substantive evidence commit:

`efbb7db0ce18ec2d9afe6fd0bf127afd4767b49f`

GitHub Actions run:

`44038446087`

Target inside privileged disposable environment:

```text
Debian GNU/Linux 13.7 (trixie)
OpenVPN 2.6.14
Python 3.13
```

All ordinary NG3 jobs on the same run passed. Only `linux-exp049-openvpn` failed.

Two earlier runs are not acceptance evidence:

- `44038136700` — initial probe lacked enough OpenVPN failure diagnostics;
- `44038297619` — isolated a harness error: named `vpn0` required explicit
  `dev-type tun`.

The harness was corrected without weakening the hypothesis and with TLS certificate role
verification enabled.

## Finding F1 — generic userspace VPN placement inside managed netns is viable

Both clean cycles proved:

```text
managed domain present
vpn0 absent
    ->
OpenVPN client process starts inside managed netns
    ->
real vpn0 TUN created inside that same netns
    ->
real tunnel payload works before NG3 activation
```

This rejects the hypothesis that a real non-WireGuard userspace VPN is inherently unable to
create its data-plane endpoint inside the NG3 managed network domain.

No interface was created outside the namespace and then moved inward.

## Finding F2 — current NG3 discovery/binding works on the real endpoint

Both clean cycles used fresh production inventory plus
`project_device_bindings(...)`.

Observed binding:

```text
LogicalPathId(device_id='ovpn', selector_index=0, slot_index=0)
    ->
InterfaceIdentity(ifname='vpn0', ifindex=2)
```

The production controller startup independently repeated fresh observation/binding through its
prepared-policy seam and reached structural activation READY.

Therefore this run exposes no binding gap.

## Finding F3 — current terminal local policy kills the VPN transport

After production activation, the managed namespace contains:

```text
chain stack_output {
    comment "vpn-gate:ng3:stack-output-v1"
    type filter hook output priority filter; policy drop;
}
```

with no supported-integration local/system exception.

Observed in both cycles:

```text
REAL_OPENVPN_TUNNEL_IN_MANAGED_DOMAIN=PASS
PRODUCTION_STARTUP_BINDING_ACTIVATION=PASS
CONTROLLED_PAYLOAD_THROUGH_ADMITTED_PATH=FAIL
LOCAL_UNDERLAY_AFTER_ACTIVATION=BLOCKED
```

The OpenVPN process needs locally generated/received UDP underlay traffic. The current
`stack_input` / `stack_output` terminal-DROP boundary blocks that traffic after activation.

This makes the apparently admitted logical path unusable for real payload.

## Finding F4 — do not fix the experiment with ad-hoc nft allow rules

EXP-049 explicitly forbids manually injecting internal route/RPDB/nft state owned by VPN-GATE.

Adding a one-off allow rule in the experiment would therefore invalidate the applicability
claim instead of repairing it.

The existing architecture already defines a source-owned
`LocalSystemAllowIntent(owner_function=integration(...))` boundary. The missing unit is the
concrete supported-integration intent and its executable realization, not permission to weaken
terminal DROP globally.

## Finding F5 — exact safe selector shape remains open

This experiment proves that local/system integration permission is necessary but does not by
itself prove its minimum safe selectors.

The next unit must not automatically choose:

- blanket local UDP allow;
- blanket `ct state established,related accept`;
- ambient socket discovery as policy;
- interface-name-only acceptance;
- another universal VPN transport exception.

The supported onboarding contract must provide enough normalized facts to derive bounded
INPUT/OUTPUT acceptance and stale-rule removal.

## Finding F6 — cleanup was reproducible under the current administrator-owned EXP-049 procedure

For both cycles:

```text
VPN_ENDPOINT_AFTER_CLIENT_STOP=ABSENT
CONTROLLER_STOP=stopped
MANAGED_DOMAIN_CLEAN=PASS
```

This only proves the explicit EXP-049 procedure in which the external OpenVPN client is stopped
before NG3 managed-domain cleanup.

It does **not** settle bounded-VPN process lifecycle ownership. That question remains downstream
of EXP-049 PASS and EXP-050.

## Requirement disposition

### `VPNG-U001-R1.R3.C1.R1.R1`

The Requirement remains desired and appears reachable.

Its existing closure candidate has failed the Requirement's own real applicability acceptance
evidence.

Disposition:

`[rejected_closure]`

This is not `unreal`: a valid implementation path still appears possible.

This is not `broken`: the Requirement itself remains correct.

## EXP-050 disposition

**BLOCKED.**

`VPNG-U007-R7.R7.R1` explicitly requires EXP-049 PASS before dependent bounded-VPN
lifecycle experimentation.

Endpoint placement/binding partial success does not satisfy that prerequisite.

## Requirement-state inventory

### `decomp`

Six accumulated links, all resolved.

Pending: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

- `VPNG-U001-R1.R3.C1.R1.R1` — EXP-049 failed because a real in-stack OpenVPN transport is
  blocked by the current terminal local policy after activation.

## Next logical unit

Requirement/architecture closure for the smallest supported-integration local/system policy
contract.

The unit should answer only what the real evidence now requires:

```text
supported in-stack VPN integration
    ->
which normalized underlay/control facts are available from its onboarding contract
    ->
minimum fail-closed LocalSystemAllowIntent
    ->
exact observable/mutable Linux realization
    ->
rerun unchanged EXP-049
```

Do not start EXP-050 or bounded-VPN lifecycle ownership work before EXP-049 PASS.

## Conclusion

**EXP-049 FAIL — finding accepted.**

The useful part of the hypothesis is now proven: a real generic userspace VPN can live inside
the managed namespace and bind correctly.

The remaining blocker is ours: current executable NG3 local/system policy does not yet admit
the VPN transport needed to keep that real path usable.


## Requirement migration note

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R7.R1` -> `VPNG-D001-R1.R1.R7.R1`

The original IDs in the historical body are intentionally preserved.
