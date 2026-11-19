# EXP-070 — routed stack endpoint: IPvlan L3S and L3 device candidates

## Status

PREPARED — awaiting privileged CI evidence.

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

Техническое evidence относится к уже принятым обязанностям:

- `VPNG0002-R2.R3.R1.R1` — host-boundary routing contributions для ordinary initiation;
- `VPNG0002-R2.R3.R1.R1.R1` — не заворачивать stack-origin traffic обратно bootstrap-ом;
- `VPNG0001-R1.R2.R4.R4.R4` / `.R1` — Profile ordinary-side gateway NAT;
- `VPNG0004-R4.R6.R1.R6` / `.R1` — bounded host-boundary ownership.

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

## Result interpretation

`EXP070_RESULT=PASS` означает, что experiment harness получил различающее evidence.
Каждый sub-result фиксируется отдельно; отрицательный механизм не делает весь experiment FAIL.

Post-result архитектурное решение остается отдельным review/disposition.
