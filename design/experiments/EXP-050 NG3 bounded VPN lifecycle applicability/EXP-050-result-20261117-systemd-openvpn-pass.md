# EXP-050 result — systemd-bounded OpenVPN lifecycle PASS

**Date:** 2026-11-17  
**Verdict:** **PASS**  
**Evidence commit:** `12942efbb8de40b0381f1de454aecf23c8a1a5fb`  
**GitHub Actions run:** `44072821011`  
**Target userspace:** Debian GNU/Linux 13.7  
**VPN:** OpenVPN 2.6.14

## Prerequisite

The same run first reproduced `EXP049_RESULT=PASS` using the Release-1 systemd onboarding
mechanism:

```text
distinct stack-specific VPN systemd service
    + BindsTo / After managed-domain lifecycle anchor
    + NetworkNamespacePath = managed netns
    + policy-neutral OpenVPN configuration
    + explicit bounded integration transport facts
```

EXP-050 used the same OpenVPN implementation/version and the same onboarding mechanism.

## Scenario 1 — start

Both clean cycles proved:

- systemd OpenVPN MainPID runs in the managed network namespace;
- OpenVPN creates `vpn0` there;
- the session reaches OpenVPN initialization completion;
- NG3 freshly observes and binds the current `vpn0`;
- current structural policy converges;
- controlled host payload traverses the admitted VPN path.

Cycle 1 started with:

`pid=4872, vpn0 ifindex=2`

Cycle 2 started with:

`pid=5665, vpn0 ifindex=2`

## Scenario 2 — bounded stop

The tested stop sequence is:

```text
ForwardingGate = DISABLED
    ->
stop managed-domain systemd lifecycle anchor
    ->
BindsTo / reverse After ordering stops stack VPN unit
    ->
confirm VPN service inactive
    ->
confirm old MainPID absent
    ->
confirm VPN service cgroup empty
    ->
confirm vpn0 absent
    ->
run controller owned-domain cleanup
    ->
confirm managed namespace + host boundary absent
```

Both cycles passed.

Cycle 1 final VPN PID: `5426`  
Cycle 2 final VPN PID: `6216`

No custom PID registry or process-tree walker was required. systemd remained the process/cgroup
supervisor.

## Scenario 3 — same-config restart

A normal administrator `systemctl restart` of the VPN service left the managed domain alive,
started a new OpenVPN process inside the same managed namespace and created a fresh interface
generation.

Cycle 1:

```text
old pid 4872 / vpn0 ifindex 2
    ->
new pid 5048 / vpn0 ifindex 3
```

Cycle 2:

```text
old pid 5665 / vpn0 ifindex 2
    ->
new pid 5840 / vpn0 ifindex 3
```

Fresh NG3 observation/reconciliation used only the current endpoint and controlled payload
continued to pass.

## Scenario 4 — changed VPN-specific config

The VPN-specific configuration was materially changed to set:

```text
tun-mtu 1400
```

After complete stop/start, both cycles produced a new process and a new `vpn0` generation
whose observed MTU was 1400.

Cycle 1: `pid=5221, vpn0 ifindex=4, mtu=1400`  
Cycle 2: `pid=6015, vpn0 ifindex=4, mtu=1400`

Fresh NG3 observation/reconciliation bound the new endpoint and controlled payload passed.
The previous generation was neither retained nor required.

## Scenario 5 — aggressive VPN-specific configuration

The aggressive OpenVPN configuration attempted:

- a route directive;
- an external `up` hook which, if executed, would create:
  - an RPDB rule;
  - an nft rule in VPN-GATE's owned table;
  - a sysctl mutation;
  - an external marker proving execution.

The supported OpenVPN integration retained:

```text
route-noexec
no script-security 2 elevation
```

Observed in both cycles:

- no aggressive route appeared;
- no aggressive `lookup main` RPDB rule appeared;
- no aggressive nft marker appeared;
- no hook marker appeared;
- OpenVPN explicitly diagnosed that user-defined scripts require `--script-security 2`;
- the VPN service failed visibly rather than silently executing the hook.

The unrelated priority-16384 rule observed during the test was the legitimate current
VPN-GATE payload rule to its allocated table, not the aggressive `lookup main` rule.

This supports an administrator contract in which arbitrary elevated VPN hooks that mutate
VPN-GATE-owned managed-domain state are outside the supported Release-1 integration.

## Responsibility finding

The evidence supports this Release-1 split:

```text
administrator
    -> VPN-specific configuration
    -> distinct stack-specific VPN systemd unit/instance/drop-in

systemd
    -> VPN process/cgroup supervision
    -> start/stop/restart
    -> dependency/ordering propagation

VPN-GATE
    -> managed network domain
    -> fail-closed forwarding boundary
    -> owned routes/RPDB/nft state
    -> bounded integration-local transport allowance
    -> fresh endpoint observation/binding/reconciliation
```

VPN-GATE does not need to become a generic VPN process supervisor.

## Out-of-band intervention

The experiment tests the supported systemd lifecycle, not arbitrary root damage.

Direct administrator mutation/deletion of VPN-GATE-owned namespace/lifecycle artifacts or
explicit elevation of arbitrary root-capable VPN hooks is outside the supported first-release
lifecycle contract. Observable invariant loss must remain fail-closed/diagnosable; automatic
forensic adoption of arbitrary surviving processes is not required.

## Scope

PASS applies to the tested OpenVPN/systemd integration and the lifecycle mechanism it proves.

It is evidence for the generic Release-1 systemd supervision boundary, but does not silently
prove every vendor helper's VPN-specific configuration safe. WireGuard/wg-quick, OpenConnect
and other integrations retain their own documented policy-neutral onboarding restrictions.

## Final result

```text
EXP050_RESULT=PASS
```


## Current requirement mapping (2026-11-20)

The result above is unchanged. The experiment explicitly did not test arbitrary root damage.

Its current `VPNG0005-R5.C1` value is the negative recovery fact: the first release need not
forensic-adopt arbitrary surviving processes or reconstruct untrustworthy namespace ownership
after unsupported external intervention.

The historical sentence that observable invariant loss "must remain fail-closed/diagnosable"
must not be read as a blanket rule sourced from `VPNG0005-R5.C1`. Where the tested runtime
closed forwarding, that containment is justified by the concrete safety/readiness invariant
that was lost and by the corresponding `VPNG0004` / lifecycle requirements.
