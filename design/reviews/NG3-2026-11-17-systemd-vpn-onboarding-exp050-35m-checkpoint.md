# VPN-GATE NG3 — systemd VPN onboarding + EXP-050 35m checkpoint

**Date:** 2026-11-17  
**Cycle:** `ng3-design-cycle-20261117-systemd-vpn-onboarding-exp050-35m`  
**CYCLE_INTERVAL:** 35m  
**CYCLE_START_COMMIT:** `dd103966eda993cc68fa4cc0f9b7c552e9c33f71`  
**T0:** 2026-11-17T10:43:04Z

## Cycle boundary

Last reviewed logical commit before checkpoint:

`762e0ec60c3fc999b4a419230cf7fca4596450ac` at
`2026-11-17T11:26:57Z`.

Elapsed logical-development interval: approximately **43m53s**.

The cycle exceeded the nominal interval because the same requirements-driven block had to
complete the EXP-049 repair and then execute the explicitly dependent EXP-050 lifecycle gate.
No unrelated work was added.

## Closed logical block

This cycle converts the first real VPN applicability failure into a bounded Release-1
integration/lifecycle contract:

```text
administrator prepares stack-specific VPN systemd unit + VPN-specific config
    ->
systemd starts VPN directly inside managed netns
    ->
VPN-GATE admits only bounded integration transport
    ->
fresh endpoint binding + managed network policy
    ->
normal systemctl stop/start/restart remains available
    ->
systemd stops bound VPN cgroup before domain teardown
```

Release 1 deliberately does not auto-discover/adopt/patch arbitrary VPN units.

## Requirements closed

New/repaired closures:

- `VPNG0001-R1.R3.C1.R1.R1`;
- `VPNG0001-R1.R3.C1.C1`;
- `VPNG0001-R1.R3.C1.C1.R1`;
- `VPNG0001-R1.R3.C1.C1.R2`;
- `VPNG0001-R1.R3.C1.C1.R3`;
- `VPNG0005-R5.C1`;
- `VPNG0005-R5.C1.R1`.

The prior EXP-049 `[rejected_closure]` is repaired and no rejected closure remains.

## Implementation

Added bounded supported-integration transport owner:

- normalized integration transport config;
- exact current host-boundary identity;
- exact managed local IPv4;
- exact remote IPv4/protocol/port;
- optional exact local port;
- strict nft observation/classification;
- stale/missing atomic reconciliation;
- composite structural-policy integration.

Owner marker:

`vpn-gate:ng3:local-integration-v1`

No blanket local allow or ambient socket inference was introduced.

## EXP-049

Final mechanism:

- Debian 13.7 userspace;
- OpenVPN 2.6.14;
- real systemd as PID1;
- distinct stack-specific OpenVPN service;
- `BindsTo` + `After`;
- `NetworkNamespacePath`;
- `route-noexec`;
- fixed client UDP port 11941;
- server UDP port 11940;
- explicit integration transport facts.

Result:

`EXP049_RESULT=PASS`

The historical earlier FAIL remains retained as evidence for why the integration-local owner
exists.

## EXP-050

Final privileged/systemd evidence:

- commit `12942efbb8de40b0381f1de454aecf23c8a1a5fb`;
- GitHub Actions run `44072821011`;
- all NG3 jobs PASS.

Two complete clean cycles proved:

- initial start;
- same-config service restart with fresh PID/interface generation;
- changed-config restart with `tun-mtu 1400`;
- fresh binding/reconciliation after generation changes;
- controlled payload after restart;
- aggressive OpenVPN route/hook attempts do not mutate owned managed-domain policy under the
  supported contract;
- unsupported external hook fails visibly because `script-security 2` is not enabled;
- forwarding closes before bounded stop;
- `BindsTo` stops the stack VPN unit/cgroup;
- PID/cgroup/endpoint absence before managed-domain destruction;
- final namespace + host-boundary absence.

Result:

`EXP050_RESULT=PASS`

## Accepted responsibility split

```text
administrator
    VPN-specific config
    stack-specific systemd unit/instance/drop-in

systemd
    bounded VPN process/cgroup supervision
    start/stop/restart
    dependency ordering

VPN-GATE
    managed network domain
    routing/RPDB/nft policy
    bounded local transport admission
    fresh endpoint binding/reconciliation
```

Direct root/admin modification of owned namespace/lifecycle artifacts is external intervention.
VPN-GATE remains fail-closed/diagnostic but Release 1 does not promise forensic adoption of
arbitrary surviving processes or namespace references.

## Documentation

Added:

`design/NG3/vpn-onboarding-release1.md`

It documents:

- common systemd namespace/dependency boundary;
- separate stack-specific service identity;
- OpenVPN template-instance guidance + policy-neutral restrictions;
- wg-quick template-instance guidance + `Table = off`;
- OpenConnect administrator wrapper/template model;
- transport-fact contract;
- out-of-band intervention boundary;
- future automatic unit capture explicitly deferred.

## Review

`design/reviews/NG3-2026-11-17-systemd-vpn-onboarding-exp050-review.md`

Verdict: **PASS**.

## Requirement-state inventory

### `decomp`

Six accumulated links remain resolved.

Pending: **none**.

### `unreal`

**none**

### `broken`

**none**

### `[rejected_closure]`

**none**

## Mechanical check

```text
normative R/C nodes:                    154
closed:                                 154
pending_closure:                          0
rejected_closure:                         0
open/malformed:                           0
closed without architecture reference:    0
decomp links:                              6, all resolved
active unreal:                             0
active broken:                             0
```

## Next intended logical unit

Move from lifecycle design/evidence toward the first functioning alpha.

The next unit should assemble the already accepted pieces into a concrete deployable runtime
surface rather than reopen VPN lifecycle design. Likely scope:

- concrete VPN-GATE systemd/deployment unit and stable managed-netns path;
- real configuration loading including integration transport facts;
- executable startup/reconciliation path using the existing controller;
- one documented OpenVPN stack-specific instance against that deployment;
- minimal end-to-end alpha smoke scenario.

Do not add automatic vendor-unit capture unless a new requirement explicitly requires it.

## Checkpoint verdict

**PASS — Release-1 systemd VPN onboarding and bounded lifecycle closed; EXP-049 + EXP-050 PASS.**
