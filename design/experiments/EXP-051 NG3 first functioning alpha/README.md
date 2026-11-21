# EXP-051 — first functioning NG3 alpha deployment smoke

## Status

Technical result and disposition are unchanged by this traceability annotation.

## Historical requirement context

### Requirement ID migration

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U005-R5.R1` -> `VPNG-M001-R1.R1.R1`
- `VPNG-U005-R5.R2` -> `VPNG-M001-R1.R1.R2`
- `VPNG-U005-R5.R3` -> `VPNG-M001-R1.R1.R3`
- `VPNG-U005-R5.R6.R2` -> `VPNG-M001-R1.R1.R6.R2`
- `VPNG-U005-R5.R6.R3` -> `VPNG-M001-R1.R1.R6.R3`
- `VPNG-U007-R7.R7` -> `VPNG-D001-R1.R1.R7`

The original IDs in the historical body are intentionally preserved.

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG-U001-R1.R2]** *Чтобы эксплуатация продукта не зависела от ручного воспроизведения его внутренней сетевой механики оператором.* | Пользователь должен задавать требуемое поведение через продуктовую конфигурацию и управляющие операции VPN-GATE; внутренние сетевые действия должны выполняться продуктом. [`closed`]
- **[VPNG-U001-R1.R2.R4.R6.R4]** *Чтобы client-side VPN transport/control traffic поддерживаемого Device мог работать внутри managed network domain с default-deny local policy без широких или неявных локальных разрешений.* | Device должен позволять пользователю явно описать bounded client-side transport/control flows, необходимые поддерживаемой VPN integration; такие flow intents должны ограничиваться transport/control traffic этого Device и не должны сами по себе создавать payload forwarding permission, разрешать произвольную local connectivity или требовать blanket local allow. [`closed`]
- **[VPNG-U001-R1.R2.R4.R6.R3]** *Чтобы server-side VPN transports могли быть доступны извне без смешивания host-facing listener details с Profile routing policy.* | Transport publication, если требуется Device, принадлежит Device/transport boundary и в Release 1 задаётся `publish_vpn_server = "tcp|udp[/<host-IPv4|host-interface>]:<host-port-bundle>[><internal-port-bundle>]"` либо массивом таких строк. Port bundle использует ту же strict compact grammar `N[,N|A-B...]` без пробелов, duplicate/overlap ports запрещены. Отсутствие `>...` означает identity mapping каждого host port на тот же internal port; при явном internal bundle обе стороны разворачиваются в declared order в последовательности отдельных портов, должны иметь одинаковую cardinality и мапятся позиционно 1:1. Отсутствие host selector означает публикацию на допустимых host addresses. Потеря требуемой publication не должна оставаться незаметной. [`closed`]
- **[VPNG-U004-R4.R6.R1.R5.R1]** *Чтобы пользовательский Device firewall ограничивал VPN payload, не заставляя пользователя одновременно администрировать внутренний control/probe plane VPN-GATE.* | Пользовательские Device firewall rules должны влиять только на managed payload forwarding, а необходимые локальные `INPUT/OUTPUT` исключения для поддерживаемых VPN-GATE control, probe, publication или integration функций должен формировать и владеть сам VPN-GATE; такие исключения не должны становиться разрешением произвольного payload forwarding или изменением firewall обычного host network namespace. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

**Status:** PASSED — first installed NG3 alpha controller + OpenVPN systemd stack  
**Date:** 2026-11-17

## Requirement trace

This experiment does not add product semantics. It verifies the first deployment assembly of
already accepted requirements and constraints:

- `VPNG-U001-R1.R1` / `VPNG-U001-R4` — controlled payload from accepted config;
- `VPNG-U001-R1.R3.C3.R1` — externally supervised VPN runtime lifecycle integrated with VPN-GATE;
- `VPNG-U001-R1.R3.R6.R2` — bounded Device client-side VPN transport/control facts;
- `VPNG-U004-R4.R4` / `VPNG-U004-R4.R5` — fail-closed verified network policy;
- `VPNG-M001-R1.R1.R1` / `VPNG-M001-R1.R1.R2` / `VPNG-M001-R1.R1.R3` — startup and local
  reconciliation from fresh authoritative state;
- `VPNG-M001-R1.R1.R6.R2` / `VPNG-M001-R1.R1.R6.R3` — bounded stop/restart postconditions;
- `VPNG-U001-R1.R3.R6.R1` — Device-owned server publication;
- `VPNG-U004-R4.R6` — bounded managed local publication admission;
- `VPNG-D001-R1.R1.R7` — implementation/evidence is requirements-driven.
- `VPNG-M001-R2.R2` — installed alpha publishes the required compact human current-state report from the same authoritative runtime snapshot.

## Current alpha boundary under test

The canonical Release-1 Device NAT/firewall/publication grammar is accepted. This extension
keeps the payload topology NAT-free but additionally requests a real
`publish_vpn_server = "tcp/alpha-srv-host:14443>24443"`.

The ordinary host forwarding prerequisite is enabled by the disposable harness before
controller startup. The runtime observes that prerequisite; it does not own or set the
host-global forwarding sysctl.

## Test topology

```text
host
  lo             198.19.255.1/32   (test-only ordinary host-local endpoint)
  route          198.19.255.2/32 dev vnga-host0
  vnga-host0     unnumbered routed veth
      ||
      || managed L3 boundary / Proxy ARP
      ||
  /run/netns/vpn-gate-alpha
      vnga-inner0 198.19.255.2/32
      default dev vnga-inner0
      vpn0        10.253.0.2 <-> 10.253.0.1
      OpenVPN client under systemd
      |
      | UDP 198.19.255.2:11941 -> 198.19.254.2:11940
      |
host forwarding
      |
  alpha-srv-host 198.19.254.1/30
      |
  alpha-srv netns
      alpha-srv0  198.19.254.2/30
      tun-srv     10.253.0.1 <-> 10.253.0.2
      OpenVPN test server
```

The remote test namespace receives an explicit return route for host source
`198.19.255.1/32` through `tun-srv`, so no payload masquerade is needed.

## PASS criteria

1. Install the actual alpha package/service files.
2. Start `vpn-gate-alpha.service`; systemd start completes only after `READY=1`.
3. Confirm `/run/netns/vpn-gate-alpha` and the managed boundary exist.
4. Confirm the host boundary is unnumbered, the stack endpoint owns only
   `198.19.255.2/32`, and both host service route and stack default are device-only.
5. Confirm zero-path startup is fail-closed but contains the exact OpenVPN transport allow.
6. Before VPN start, confirm host publication owner + managed local publication admission and
   pass real external TCP through 14443 -> 24443.
7. Start the actual stack-specific OpenVPN systemd unit.
8. Confirm its MainPID is inside the managed netns and `vpn0` appears.
9. Without restarting VPN-GATE, wait for local reconciliation to observe/bind `vpn0`.
10. Confirm host payload to `10.253.0.1` succeeds through the current path.
11. Restart only the OpenVPN unit and confirm:
   - new PID;
   - fresh `vpn0` generation;
   - payload recovers through ordinary periodic reconciliation.
12. Stop `vpn-gate-alpha.service` and confirm:
    - bound OpenVPN unit inactive;
    - old VPN PID absent;
    - managed netns absent;
    - host boundary absent.
13. Repeat only as needed to distinguish harness defects from runtime defects; do not hide
    product failures with test-only repair.

## Evidence

**PASS on 2026-11-17.** Original first-alpha evidence is retained; the server-publication
extension also passed on run `44167358884`, job `134336862209`.

Final runtime evidence:

- runtime commit `5a1a9f53c8d861e9a616cf18bfa7107764f4a38d`;
- GitHub Actions run `44082595411`;
- alpha smoke job `134036710197`;
- `EXP051_RESULT=PASS`;
- two production reconciliation markers: first endpoint appearance and VPN-only restart.

See `EXP-051-result-20261117-pass.md`.

Managed-L3 lifecycle migration evidence on 2026-11-19:

- workflow run `44604743687`, job `linux-alpha-smoke` (`135845485684`);
- `EXP051_ROUTED_MANAGED_L3_BOUNDARY=PASS`;
- `EXP051_SELECTED_HOST_BOOTSTRAP_DEVICE_ONLY=PASS`;
- publication E2E, first payload, host-local `+route-return`, VPN-only restart/reconcile and
  clean stop all remained PASS;
- `EXP051_RESULT=PASS`.

The harness is `exp051_alpha_smoke.py` and runs in the dedicated
`linux-alpha-smoke` GitHub Actions job.
