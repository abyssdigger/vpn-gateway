# EXP-070 — routed stack endpoint: IPvlan L3S and L3 device candidates

## Status

PASS — selected for the routed-veth/Proxy-ARP managed-L3 endpoint and Debian-12/Linux-6.1
portability evidence.

## Historical requirement context

### Requirement ID migration

The requirement IDs below are historical references from this record's original baseline.
Their current NG3 IDs are:

- `VPNG-U007-R7.R3.R5` -> `VPNG-D001-R1.R1.R3.R5`

The original IDs in the historical body are intentionally preserved.

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG-U004-R4.R6.R1]** *Чтобы изоляция была не декларацией, а проверяемой границей владения сетевым состоянием.* | VPN-GATE должен иметь отдельный управляемый сетевой домен, в котором локализованы принадлежащие продукту routing/policy/data-plane состояния; взаимодействие этого домена с внешней сетью и хостом должно происходить только через явно определенные граничные точки, а используемые VPN data-plane endpoints должны быть представлены внутри этого домена. [`closed`]
- **[VPNG-U004-R4.R6.R1.R1]** *Чтобы внутренние изменения VPN-GATE не требовали знания или изменения несвязанных сетевых объектов хоста.* | Сетевые объекты и mutable state, необходимые для внутренней маршрутизации и policy VPN-GATE, должны принадлежать управляемому сетевому домену либо явно объявленной boundary-области; произвольные host routes/rules/firewall state не должны использоваться как скрытая часть внутренней модели VPN-GATE. [`closed`]
- **[VPNG-U004-R4.R6.R1.R2]** *Чтобы весь обмен между управляемой сетью VPN-GATE и внешней средой был видим, проверяем и управляем.* | Вход и выход управляемого трафика из сетевого домена должны происходить через явно определенные boundary endpoints с известной ролью и направлением; наличие обычной host connectivity само по себе не должно создавать неявную границу передачи. [`closed`]
- **[VPNG-U001-R1.R2.R4.R4.R4]** *Чтобы Profile мог явно задавать требуемое представление source address для уже разрешённого VPN→ordinary traffic, не заставляя пользователя воспроизводить внутреннюю NAT-механику VPN-GATE вручную.* | VPN-GATE должен позволять пользователю для Profile явно запросить source NAT уже разрешённого VPN→ordinary payload перед его выходом из managed network domain: без такого запроса payload должен выходить из managed domain с исходным remote source address, а при запросе — с выбранной для Profile IPv4 SNAT identity. Эта функция определяет source identity на managed boundary и сама по себе не обещает последующую host-side маршрутизируемость, firewall policy или внешний NAT. [`closed`]
**[VPNG-U002-R2.R3.R1.R1]** *Чтобы разрешенный ordinary-to-VPN flow действительно попадал в изолированный routing domain без ручного дублирования внутренней VPN-GATE policy администратором.* | Для каждого enabled Profile, разрешающего ordinary-side initiation (`outbound` или `bidirectional`), VPN-GATE должен создавать и удалять только необходимые ему явные host-boundary routing contributions, направляющие Profile destinations в managed network domain; эти contributions являются эксплуатационно управляемым состоянием VPN-GATE, а администратор обязан не удалять и не подменять их конфликтующей host routing policy во время работы сервиса. [closed]
**[VPNG-U002-R2.R3.R1.R1.R1]** *Чтобы host bootstrap не завернул обратно в managed stack уже вышедший из него VPN transport, server reply или иной stack-origin traffic.* | Host-boundary bootstrap должен применять managed-destination capture только к ordinary/local initiation и сохранять ordinary host routing для пакетов, уже пришедших на host через explicit managed-domain boundary; если lower realization не может доказанно различить эти случаи, до активации bootstrap должны быть созданы эквивалентные явные исключения. [closed]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

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

- `VPNG-U004-R4.R6` — managed network-domain interaction with host/external networking
  occurs through explicit boundary points;
- `VPNG-U004-R4.R6` — mutable state required at that boundary remains explicitly owned
  rather than becoming hidden ambient host state;
- `VPNG-U004-R4.R6` — traffic crosses the managed domain only through explicit boundary
  endpoints with known roles;
- `VPNG-U007-R7.R3.R5` — the common managed-L3 contract must not be coupled to one accidental
  lower Linux mechanism when multiple mechanisms can realize the same semantics;
- `VPNG-U001-R3` / `VPNG-U001-R4.R4.R4.R4` — the experiment also retains lower evidence that
  Profile source translation can execute inside the managed domain.

The former host-bootstrap requirements are preserved verbatim in `Historical requirement context` above. They were removed from the current tree on 2026-11-20 and are no longer part of EXP-070's selected evidence role.

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
