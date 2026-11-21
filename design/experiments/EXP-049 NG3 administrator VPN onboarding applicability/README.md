# EXP-049 — administrator VPN endpoint onboarding applicability

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R3.C2]** *Для выполнения требования изоляции управляемой сетевой среды NG3 использует отдельный изолированный network domain, а не host network namespace как рабочее пространство маршрутизации.* | Поддерживаемый внешний VPN-канал может использоваться VPN-GATE только если его data-plane endpoint может быть представлен внутри изолированной управляемой сетевой среды; VPN-адаптер, остающийся только в обычном сетевом пространстве хоста, не считается полноценным управляемым VPN-путем NG3. [`closed`]
- **[VPNG0001-R1.R2.R4.R6.R4]** *Чтобы client-side VPN transport/control traffic поддерживаемого Device мог работать внутри managed network domain с default-deny local policy без широких или неявных локальных разрешений.* | Device должен позволять пользователю явно описать bounded client-side transport/control flows, необходимые поддерживаемой VPN integration; такие flow intents должны ограничиваться transport/control traffic этого Device и не должны сами по себе создавать payload forwarding permission, разрешать произвольную local connectivity или требовать blanket local allow. [`closed`]
- **[VPNG0004-R4.R6.R1.R5.R1]** *Чтобы пользовательский Device firewall ограничивал VPN payload, не заставляя пользователя одновременно администрировать внутренний control/probe plane VPN-GATE.* | Пользовательские Device firewall rules должны влиять только на managed payload forwarding, а необходимые локальные `INPUT/OUTPUT` исключения для поддерживаемых VPN-GATE control, probe, publication или integration функций должен формировать и владеть сам VPN-GATE; такие исключения не должны становиться разрешением произвольного payload forwarding или изменением firewall обычного host network namespace. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

**Status:** PASSED — OpenVPN 2.6.14 via systemd NetworkNamespacePath, bounded local transport admission, two clean cycles

## Requirement traceability

- `VPNG0001-R1.R3.C1` — Release 1 leaves VPN-channel provisioning/configuration to the administrator.
- `VPNG0001-R1.R3.C1.R1` — supported integrations must provide an administrator-facing onboarding contract.
- `VPNG0001-R1.R3.C1.R1.R1` — that contract must have reproducible end-to-end applicability evidence.
- `VPNG0001-R1.R3.C1.R1.R2` — the supported onboarding contract must keep VPN-specific configuration policy-neutral relative to VPN-GATE-owned state.
- `VPNG0001-R1.R3.R2` — for this integration, the managed data-plane endpoint must exist inside the isolated managed network domain.
- `VPNG0001-R1.R3.R2` — for this integration, a logical path must have one unambiguous current concrete endpoint before use.
- `VPNG0001-R1.R3.R6.R2` — Device policy supplies bounded client-side VPN transport/control facts.
- `VPNG0004-R4.R6` — those facts may materialize only as explicit owned local/system exceptions under default-deny managed-domain policy.

The endpoint-placement, binding and forwarding checks below are therefore the **composed
acceptance scenario for this concrete integration**, not lower mechanisms prescribed by
`VPNG0001-R1.R3.C1.R1.R1` itself.

## Question

Can an administrator, using only a documented supported integration procedure and normal
external VPN tooling, place or create a real VPN data-plane endpoint inside the NG3 managed
network domain such that VPN-GATE can freshly observe it, bind it unambiguously to the expected
logical path, and use that path through the already accepted forwarding contract?

This is a product-applicability gate. Passing lower namespace/veth, route, nft or binding unit
tests separately is not sufficient.

## First hypothesis

For at least one VPN implementation intended for Release 1 support, a clean Debian 13 target
can be taken from:

```text
managed domain present
VPN endpoint absent
```

to:

```text
administrator follows published procedure
    ->
real external VPN session/data-plane endpoint exists in managed domain
    ->
fresh NG3 endpoint inventory observes it
    ->
binding projection selects exactly one expected logical path
    ->
a controlled payload packet traverses the admitted path
```

without:

- patching VPN-GATE code;
- manually injecting internal route/RPDB/nft state that VPN-GATE itself owns;
- relying on an endpoint that existed before the procedure;
- moving the endpoint back to the host namespace for forwarding.

## Integration selection

The concrete VPN implementation for the first run is intentionally not fixed by this planning
artifact. Select the cheapest already-intended Release-1 integration whose real client/server
or tunnel endpoint can be established in disposable CI/target infrastructure.

The result must identify the exact implementation/version and whether onboarding works by:

- starting the VPN process inside the managed network namespace;
- moving an externally created interface into it;
- creating the endpoint directly in the namespace;
- or another explicitly documented supported mechanism.

A PASS applies only to the tested mechanism unless a later review proves equivalence.

## Required procedure

1. Start from a clean disposable target and create/verify the NG3 managed network domain with
   forwarding protectively closed.
2. Confirm the expected VPN endpoint is absent.
3. Follow the candidate administrator instruction exactly, using only documented external VPN
   commands/configuration.
4. Establish the real VPN channel or equivalent real data-plane endpoint.
5. Prove from inside the managed domain that the endpoint exists with current kernel identity.
6. Run the production/current NG3 observation and binding path against that endpoint.
7. Prove exactly one expected `LogicalPathId` binds to exactly one current
   `InterfaceIdentity`.
8. Materialize/activate the already accepted forwarding policy for a minimal controlled
   destination.
9. Send a controlled payload flow and prove it traverses the VPN endpoint.
10. Tear down the VPN channel and managed domain using the documented cleanup procedure.
11. Repeat the onboarding from clean state at least once to reject accidental dependence on
    stale host state.

## PASS criteria

All of the following are required:

- the administrator procedure is complete enough to reproduce without undocumented internal
  VPN-GATE actions;
- the VPN data-plane endpoint is physically inside the managed network domain;
- NG3 observes the current endpoint from fresh authoritative state;
- binding is exact and unambiguous;
- the path reaches the existing forwarding contract and carries the controlled payload;
- teardown removes the externally provisioned VPN endpoint and leaves no hidden prerequisite
  for the second clean run;
- both clean runs pass.

## FAIL / finding classes

A run is not converted to PASS by adding ad-hoc product internals. Findings are classified as:

- **instruction gap** — the external procedure is incomplete or ambiguous;
- **integration limitation** — the selected VPN implementation cannot provide the required
  endpoint placement/visibility shape;
- **binding gap** — the endpoint exists but current NG3 discovery/binding cannot identify it
  under accepted semantics;
- **integration-policy gap** — placement/binding work, but VPN-GATE-owned local/system or other
  managed-domain policy required by the supported integration is not yet materially defined or
  implemented, so the channel cannot remain usable through the accepted forwarding contract;
- **architecture contradiction** — the managed-domain boundary and the real integration cannot
  coexist without changing accepted R/C semantics;
- **environmental failure** — the disposable target cannot execute an otherwise valid step;
  rerun only after the environmental cause is isolated.

An architecture contradiction reopens the affected requirement/constraint closure; it must
not be hidden as a documentation defect.

## Artifacts to retain

- exact administrator instruction used for the run;
- exact external VPN implementation/version;
- external configuration with secrets removed;
- namespace/interface inventory before and after onboarding;
- NG3 observation/binding output;
- forwarding-policy activation evidence;
- controlled payload packet evidence;
- cleanup evidence;
- second clean-run evidence;
- final result document with workflow/target reference and source commit.

## Current disposition

**PASSED on 2026-11-17.**

The original failed result remains retained in `EXP-049-result-20261117.md`: it exposed the
missing supported-integration local/system policy.

The repaired systemd onboarding mechanism passed on Debian 13 / OpenVPN 2.6.14 in two clean
cycles:

- distinct stack-specific systemd VPN service;
- `BindsTo` + `After` managed-domain lifecycle anchor;
- `NetworkNamespacePath` into the managed netns;
- policy-neutral OpenVPN configuration with `route-noexec`;
- explicit administrator-supplied integration transport facts;
- bounded production local INPUT/OUTPUT admission;
- fresh exact binding and controlled payload traversal;
- normal `systemctl stop` and clean managed-domain teardown.

See `EXP-049-result-20261117-systemd-pass.md`.

This PASS unblocks EXP-050 only for the same OpenVPN/systemd onboarding mechanism.
