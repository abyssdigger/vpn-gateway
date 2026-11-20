# EXP-050 — NG3 bounded VPN lifecycle and aggressive-configuration applicability

**Status:** PASSED — OpenVPN 2.6.14 through the EXP-049 systemd onboarding mechanism

## Requirement traceability

- `VPNG0007-R7.R7` — substantial development/evidence work is requirement-driven.
- `VPNG0007-R7.R7.R1` — dependent VPN lifecycle work is gated by basic in-stack applicability.
- `VPNG0007-R7.R7.R1.R1` — after applicability PASS, lifecycle and aggressive-config behavior must be tested before accepting bounded-VPN lifecycle semantics.
- `VPNG0001-R1.R3.C3` — Release 1 may leave external VPN runtime lifecycle ownership/supervision outside VPN-GATE.
- `VPNG0001-R1.R3.C3.R1` — that external lifecycle must have a reproducible integration contract coordinated with VPN-GATE safety/lifecycle postconditions.
- prerequisite product evidence: `VPNG0001-R1.R3.C1.R1.R1` / EXP-049.

## Dependency gate

EXP-050 MUST NOT execute on an invented or merely hypothetical VPN integration.

Input is the exact implementation/version and onboarding mechanism that passed EXP-049.

If EXP-049 FAILs, EXP-050 remains blocked and the affected integration/managed-domain assumptions return to requirement/architecture review.

## Question

Given one real VPN integration already proven able to run with its data-plane endpoint inside the
NG3 managed network domain, can its runtime be started, stopped and restarted predictably
without stale process/interface/network state, including after changing VPN-specific
configuration and when that configuration contains hooks or equivalent mechanisms that attempt
to mutate network state inside the managed domain?

This experiment collects evidence for the later bounded-VPN lifecycle/ownership decision. It
does not pre-accept that VPN-GATE must own every tested action.

## Required scenarios

Run from a clean disposable target using the EXP-049 integration.

1. **Start**
   - establish managed domain;
   - start the real VPN using the supported onboarding mechanism;
   - prove process/runtime and data-plane endpoint are inside the intended stack boundary;
   - prove fresh NG3 discovery/binding and one controlled payload traversal.

2. **Stop**
   - request the candidate bounded stop path;
   - prove the VPN runtime no longer holds the managed namespace;
   - prove its endpoint is gone or otherwise no longer active;
   - prove managed-domain teardown reaches its required absence postcondition;
   - record every residual process, interface, route, rule, nft object or namespace reference.

3. **Restart, same VPN-specific config**
   - repeat a complete start -> stop -> start cycle;
   - prove the second start depends only on fresh authoritative state.

4. **Restart, changed VPN-specific config**
   - stop the first runtime completely;
   - change a material VPN-specific setting that produces a distinguishable new runtime
     generation/endpoint/session shape;
   - start again and prove NG3 observes/binds only current state;
   - prove no stale prior generation is required or silently reused.

5. **Aggressive VPN-specific config**
   Exercise supported/configurable hooks or equivalent mechanisms that attempt one or more of:
   - route mutation;
   - RPDB/rule mutation;
   - NAT/firewall mutation;
   - sysctl/network-state mutation;
   - other network-side effects inside the managed domain.

   Record:
   - what actually executes and in which namespace;
   - which state is created;
   - how current NG3 ownership/guard logic observes or conflicts with it;
   - whether any effect can bypass fail-closed guarantees;
   - diagnostics visible to the administrator;
   - which legacy hook behavior must be prohibited, moved to external admin-owned
     orchestration, or otherwise documented.

## Responsibility boundary under test

The experiment must keep these categories distinct:

- **VPN-specific configuration**: keys, peers/remotes, credentials and other VPN implementation settings — administrator supplied.
- **Managed-domain network policy owned by VPN-GATE**: payload routes/RPDB, VPN-GATE NAT/firewall and other explicitly owned state.
- **External infrastructure outside the managed domain**: host/external NAT, forwarding, publication or underlay setup — administrator/integration owned unless a separate accepted requirement says otherwise.

Do not assume a legacy VPN hook intended for the host namespace remains valid when the VPN is
run inside the managed domain.

## PASS criteria

EXP-050 passes only if all required scenarios produce enough evidence to make a bounded
lifecycle/ownership decision without relying on stale state or undocumented manual cleanup.

At minimum:

- start/stop/restart same-config is reproducible;
- changed-config restart creates and uses fresh current state;
- stop can prove the old VPN runtime no longer prevents managed-domain teardown;
- aggressive configuration cannot silently escape the accepted safety boundary;
- conflicts and unsupported hook behavior are observable enough to produce a precise
  administrator contract;
- two clean repetitions reject accidental dependence on stale host or namespace state.

A PASS does **not** automatically choose the final lifecycle ownership model; it supplies the
evidence for that requirement/architecture decision.

## FAIL / finding classes

- **lifecycle limitation** — the real VPN runtime cannot be bounded/terminated in the required shape;
- **namespace-retention gap** — VPN runtime keeps the managed namespace alive after intended stop;
- **stale-generation gap** — restart depends on or reuses old runtime state unexpectedly;
- **ownership conflict** — VPN-side network mutation collides with VPN-GATE-owned state;
- **safety contradiction** — aggressive config can bypass an accepted fail-closed boundary;
- **diagnostic/documentation gap** — behavior is safe enough but an administrator cannot determine why expected legacy behavior was rejected/removed;
- **architecture contradiction** — current accepted R/C cannot coexist with the observed real integration;
- **environmental failure** — test stand failed independently of the hypothesis.

## Artifacts to retain

- exact EXP-049 prerequisite result and tested implementation/version;
- all VPN-specific configs with secrets removed;
- process + namespace-reference evidence;
- interface/route/rule/nft/sysctl snapshots for each phase;
- NG3 discovery/binding evidence;
- payload evidence;
- cleanup evidence;
- same-config and changed-config restart evidence;
- aggressive-config observations and diagnostics;
- final result/review with requirement disposition.

## Current disposition

**PASSED on 2026-11-17.**

EXP-049 first passed with OpenVPN 2.6.14 launched by a distinct stack-specific systemd unit
through `NetworkNamespacePath`, `BindsTo` and `After`. EXP-050 then used that same
implementation and onboarding mechanism.

Two clean lifecycle cycles passed:

- initial start with process and `vpn0` inside the managed namespace;
- same-config `systemctl restart` with a fresh process and fresh interface generation;
- changed-config restart using `tun-mtu 1400`, again with a fresh interface generation;
- aggressive route/hook configuration under the supported policy-neutral contract without
  creating the attempted foreign route/RPDB/nft/sysctl state;
- visible OpenVPN/systemd failure when an external hook required unsupported
  `script-security 2`;
- fail-closed forwarding containment, systemd dependency stop, empty VPN cgroup and endpoint
  absence before managed-domain teardown;
- final namespace/host-boundary absence.

See `EXP-050-result-20261117-systemd-openvpn-pass.md`.

This evidence supports the Release-1 bounded systemd lifecycle contract. It does not imply
automatic adoption of arbitrary administrator VPN processes or arbitrary privileged VPN hooks.


## Current requirement disposition (2026-11-20)

EXP-050 remains selected evidence for the bounded systemd lifecycle and for the fact that the
supported integration does not require generic process adoption or arbitrary privileged hook
execution.

For `VPNG0005-R5.C1`, the experiment supports only the bounded recovery/adoption conclusion:
Release 1 need not forensic-adopt arbitrary surviving processes or reconstruct unknown
namespace ownership after unsupported external intervention. EXP-050 did **not** test
arbitrary root damage and therefore is not evidence for a blanket fail-closed reaction to
every possible out-of-band mutation.

The fail-closed forwarding containment observed in the tested lifecycle remains valid evidence
for the specific managed-domain safety postconditions that required it; that behavior is
owned by the applicable `VPNG0004` safety requirements rather than by `VPNG0005-R5.C1`.
