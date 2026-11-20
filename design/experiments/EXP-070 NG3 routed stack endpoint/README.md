# EXP-070 — routed stack endpoint: IPvlan L3S and L3 device candidates

## Status

PASS — selected for the routed-veth/Proxy-ARP managed-L3 endpoint and Debian-12/Linux-6.1
portability evidence.

## Purpose

Проверить более VPN-подобную модель managed stack, в которой Profile policy и optional
ordinary-side SNAT могут оставаться внутри stack, а host видит только routed endpoint /
host-integration contract.

Эксперимент отвечает на четыре вопроса:

1. может ли stack-side IPvlan L3S slave напрямую выходить через host lowerdev;
2. может ли stack выполнять SNAT/reverse-NAT до выхода через IPvlan L3S;
3. можно ли представить stack хосту как стабильный device target для routes без gateway IP;
4. если IPvlan не дает такого device target, подходит ли L3 netkit pair и сохраняет ли он
   packet metadata при явном `scrub none`.

## Requirements/evidence scope

Current selected evidence from this experiment maps to live requirements for the explicit
managed-L3 boundary and mechanism isolation:

- `VPNG0004-R4.R6.R1` — managed network-domain interaction with host/external networking
  occurs through explicit boundary points;
- `VPNG0004-R4.R6.R1.R1` — mutable state required at that boundary remains explicitly owned
  rather than becoming hidden ambient host state;
- `VPNG0004-R4.R6.R1.R2` — traffic crosses the managed domain only through explicit boundary
  endpoints with known roles;
- `VPNG0007-R7.R3.R5` — the common managed-L3 contract must not be coupled to one accidental
  lower Linux mechanism when multiple mechanisms can realize the same semantics;
- `VPNG0001-R1.R2.R4.R4.R4` / `.R1` — the experiment also retains lower evidence that
  Profile source translation can execute inside the managed domain.

The former references to `VPNG0002-R2.R3.R1.R1` and
`VPNG0002-R2.R3.R1.R1.R1` described the then-current host-bootstrap model. Those requirement
IDs were removed from the current tree on 2026-11-20 and are no longer part of EXP-070's
selected evidence role.

Эксперимент не меняет requirements и не выбирает новую архитектуру автоматически.

## Disposable stand

```text
REMOTE ---- veth ---- STACK
                     |
                     | IPvlan L3S or netkit L3
                     |
HOST master/uplink ---+---- LAN
```

Все объекты создаются в disposable network namespaces на privileged CI runner.

## Phase A — IPvlan L3S

Host `uplink` остается master. IPvlan L3S slave переносится в STACK и получает stack-owned
routed address.

Проверяется:

- LAN -> stack IPvlan address;
- REMOTE -> STACK -> IPvlan -> LAN;
- SNAT/MASQUERADE выполняется в STACK;
- reply возвращается в тот же stack conntrack и reverse NAT завершает flow.

## Phase B — host-visible IPvlan alias

На том же master создается второй IPvlan L3S slave, остающийся в HOST.

Проверяются два route shape:

```text
remote-prefix dev <host-ipvlan-alias>
```

и контрольный:

```text
remote-prefix via <stack-ipvlan-IP> dev <host-ipvlan-alias>
```

Это отделяет вопрос «можно ли маршрутизировать по стабильному device identifier» от
варианта, где все равно требуется stack next-hop IP.

## Phase C — netkit L3

Если runner поддерживает netkit:

- primary остается в HOST;
- peer переносится в STACK;
- host route задается как `remote-prefix dev <netkit-host>` без gateway address;
- затем pair пересоздается с `scrub none` и проверяется перенос `meta mark` через
  cross-netns boundary.

Это отдельный candidate, не утверждение, что netkit должен быть выбран.

## Phase D — routed veth legacy-compatible L3 facade

Проверяются четыре формы host-visible `vpng0` на обычной veth pair:

1. unnumbered `route <remote> dev vpng0` без Proxy ARP;
2. /32 peer addresses, но все еще `route <remote> dev vpng0`;
3. /32 peer addresses + explicit `via <peer-IP> dev vpng0`;
4. device-only routes с Proxy ARP на обоих концах veth, с и без /32 link-local peer addresses.

Payload идет LAN -> HOST -> STACK -> REMOTE без NAT; remote observer должен видеть исходный LAN source.
Это различает настоящий routed network path от NAT/proxy forwarding.

## Result interpretation

`EXP070_RESULT=PASS` означает, что experiment harness получил различающее evidence.
Каждый sub-result фиксируется отдельно; отрицательный механизм не делает весь experiment FAIL.

Post-result архитектурное решение остается отдельным review/disposition.
