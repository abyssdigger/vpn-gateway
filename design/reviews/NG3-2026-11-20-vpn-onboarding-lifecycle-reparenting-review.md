# VPN-GATE NG3 — VPN onboarding/lifecycle requirement reparenting review

**Date:** 2026-11-20  
**Branch:** `ng3-onboarding-evidence-requirement-cleanup`  
**Reviewed head:** `a09df747c237cd0ba972c4c11b67c02ae87a7bd9`

## Verdict

**PASS.**

The former systemd-specific subtree under
`VPNG0001-R1.R3.C1.C1` has been removed from the current requirement tree and its surviving
semantics have been reparented to requirements whose immediate ancestry actually justifies
them.

No runtime behavior or selected Release-1 systemd architecture was removed.

## Requirement-tree result

### External VPN runtime lifecycle ownership

Historical:

```text
VPNG0001-R1.R3.C1
└── C1
    └── R1
```

mixed administrator provisioning with external VPN process/service lifecycle ownership.

Current:

```text
VPNG0001-R1.R3
├── C1  administrator-owned VPN provisioning/configuration
├── C2  isolated managed-domain endpoint constraint
└── C3  external VPN runtime lifecycle may remain externally owned
    └── R1  reproducible external lifecycle integration contract
```

`VPNG0001-R1.R3.C3` contains no service-manager mechanism. It limits first-release ownership:
VPN-GATE need not discover/adopt/create/supervise external VPN runtime processes/services when
an external lifecycle manager and the supported integration contract can satisfy the required
coordination.

`VPNG0001-R1.R3.C3.R1` compensates for that external ownership by requiring a reproducible
lifecycle integration contract for supported start/stop/restart behavior and coordination with
applicable VPN-GATE lifecycle/safety postconditions.

### Policy-neutral administrator configuration

Historical `VPNG0001-R1.R3.C1.C1.R2` did not depend on process supervision.

Its current owner is:

`VPNG0001-R1.R3.C1.R1.R2`

under the administrator onboarding contract. It requires supported integration documentation
to separate VPN-specific configuration/state from VPN-GATE-owned network policy/state and to
make conflicting hooks/network mutations explicitly unsupported, externalized or separately
authorized.

### Client-side VPN transport/control intent

Historical `VPNG0001-R1.R3.C1.C1.R3` also did not depend on lifecycle ownership.

Its user-facing need now belongs to Device transport policy:

`VPNG0001-R1.R2.R4.R6.R4`

The Requirement asks only for bounded client-side VPN transport/control flow intent. It no
longer embeds the Release-1 field spelling or lower nft realization.

The existing grammar constraint
`VPNG0001-R1.R2.R4.R6.C1` continues to select `allow_vpn_client` as the canonical
Release-1 spelling.

The existing safety requirement
`VPNG0004-R4.R6.R1.R5.R1` continues to own the rule that required integration-local
INPUT/OUTPUT exceptions are explicit VPN-GATE-owned contributions under default-deny local
policy.

## Architecture preservation

The systemd realization remains explicitly present in `design/NG3/architecture.md` and
`design/NG3/vpn-onboarding-release1.md`.

Preserved selected mechanism includes:

- distinct stack-specific VPN unit/instance;
- `NetworkNamespacePath=`;
- `After=`;
- `BindsTo=`;
- administrator-visible normal systemd start/stop/restart behavior;
- systemd process/cgroup supervision;
- policy-neutral OpenVPN/wg-quick integration restrictions.

The architecture now states explicitly that these are the selected Release-1 Linux/systemd
realization of generic requirements, not the generic requirement semantics themselves.

## Evidence/reference remap

Current live references were remapped:

- EXP-049 now separately traces:
  - administrator onboarding evidence;
  - policy-neutral VPN-specific configuration;
  - isolated endpoint/binding requirements;
  - bounded Device client transport/control intent;
  - default-deny owned local/system exception safety.
- EXP-050 now traces the external lifecycle ownership constraint and lifecycle integration
  compensation requirement.
- EXP-051 traces `VPNG0001-R1.R3.C3.R1` for external lifecycle integration and
  `VPNG0001-R1.R2.R4.R6.R4` for client-side transport/control facts.
- `config-model.md` and the user-facing grammar deferral now trace
  `VPNG0001-R1.R2.R4.R6.R4` rather than the historical systemd child.

Historical reviews retain their original IDs and reasoning but carry an explicit current
mapping:

```text
historical C1.C1     -> current R1.R3.C3
historical C1.C1.R1  -> current R1.R3.C3.R1
historical C1.C1.R2  -> current R1.R3.C1.R1.R2
historical C1.C1.R3  -> current R1.R2.R4.R6.R4
```

This preserves temporal evidence without leaving historical IDs looking like live normative
links.

## Static verification

Current normative/operator/evidence documents contain no live occurrence of the historical
`VPNG0001-R1.R3.C1.C1*` IDs.

Each new current requirement ID exists exactly once as a requirement-tree heading.

`architecture.md` and `vpn-onboarding-release1.md` still contain the selected systemd
mechanism, including `NetworkNamespacePath`, `BindsTo` and `After=`.

No production/runtime code changed; this review unit is requirement/architecture/evidence
trace cleanup only.
