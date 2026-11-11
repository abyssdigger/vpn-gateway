# VPN-GATE — журнал экспериментов

**Терминология:** [RC3 — термины и определения](RC3/terms-and-definitions.md).

Исторические экспериментальные записи сохраняют язык, на котором они были зафиксированы:
это часть доказательной базы. Новые русскоязычные пояснения и решения используют
нормативную терминологию RC3; технические идентификаторы и команды не переводятся.

Ссылки на номера разделов и инвариантов внутри исторической записи относятся к
`Architecture baseline`, указанному в самой записи. При выпуске последующих RC такие ссылки
не перенумеровываются задним числом.

## EXP-012 — NG1: ROU v0 lifecycle and integrity

**Статус:** COMPLETE — PASS  
**Architecture baseline:** NG1 Draft 1 + EXP-010/011 PASS + executable ROU v0  
**Тип:** first complete appliance lifecycle / fail-closed / drift-recovery gate  
**Design:** [EXP-012 README](experiments/EXP-012%20NG1%20ROU%20v0%20lifecycle%20integrity/README.md)  
**Result:** [EXP-012-result-20261111.md](experiments/EXP-012%20NG1%20ROU%20v0%20lifecycle%20integrity/EXP-012-result-20261111.md)  
**Implementation:** [ROU v0](NG1/code/python/rou_v0/README.md)

### Цель

Проверить на dedicated Debian/ocserv стенде первый целиком исполняемый ROU:

- создание и удаление собственного netns/veth;
- запуск реального ocserv внутри ROU;
- TCP/UDP publication с независимыми UDP peer associations;
- materialization двух `vpnsXX` bindings и profile table;
- реальный payload path;
- штатный drop/return binding;
- zero-path fail-closed;
- repair owned route/firewall drift под `ip_forward=0` barrier;
- fail-closed teardown при нарушении целостности appliance infrastructure.

### Подготовленная проверка

Live harness:

    design/NG1/code/python/rou_v0/rou_v0_live_smoke.sh

Он содержит H1-H10 и завершает успешный прогон строкой:

    OVERALL=PASS

До live run rootless-проверки реализации завершены успешно:

- `py_compile`;
- 8 unit tests;
- multi-peer UDP relay smoke;
- `bash -n` live harness.

Живой прогон на dedicated Debian 13 завершён `OVERALL=PASS`.

Подтверждены все H1-H10: создание/teardown appliance, два одновременных реальных OC
клиента с DTLS, двухпутевая materialization, реальный payload, failover без survivor
metric churn, fresh reconnect, zero-path fail-closed, repair route/firewall drift под
`ip_forward=0` barrier и fatal teardown при structural loss `host0`.

По ходу live-gate были исправлены три реальные ошибки без ослабления критериев:
bootstrap flush отсутствующей table 100, chroot-visible socket path ocserv sec-mod и
ошибка harness H8, первоначально удалявшего route не из table 100.

**Решение:** EXP-012 COMPLETE — PASS. Hard-coded ROU v0 считается live-verified
executable reference boundary; следующий этап — обобщение NG1 configuration/domain model.

---

## EXP-011 — NG1: ocserv/OpenConnect transport publication

**Статус:** COMPLETE — PASS  
**Architecture baseline:** NG1 Draft 1 + EXP-010 PASS  
**Тип:** real-protocol transport publication proof (TCP/TLS/CSTP + UDP/DTLS)  
**Result:** [EXP-011-result-20261111.md](experiments/EXP-011%20NG1%20ocserv%20transport%20publication/EXP-011-result-20261111.md)  
**Artifacts:**  
- [experiment design](experiments/EXP-011%20NG1%20ocserv%20transport%20publication/README.md)  
- [TCP+UDP relay](experiments/EXP-011%20NG1%20ocserv%20transport%20publication/vpn-gateway-exp-011-oc-relay.py)  
- [live harness](experiments/EXP-011%20NG1%20ocserv%20transport%20publication/vpn-gateway-exp-011-harness.sh)

### Результат

Штатный test ocserv на `192.168.201.107:44443` был остановлен, а тот же внешний
TCP/UDP endpoint временно занял ROU publication relay. Внутри `vg-exp011` ocserv
слушал `192.0.2.2:44443`. Конфигурация клиентов не менялась.

Подтверждено:

- оба существующих OpenConnect клиента автоматически дошли через TCP relay до временного
  ocserv;
- клиент `pri` явно установил `CSTP connected` и
  `Established DTLS connection`;
- relay зарегистрировал bidirectional TCP и UDP traffic;
- `occtl` показал `pri` как `AES-256-GCM connected`;
- `vpns00` и `vpns01` материализовались только внутри ROU netns;
- main namespace содержал только host-side `exp11h`;
- cleanup удалил namespace, veth и publication sockets;
- после возврата штатного `ocserv.service` оба клиента переподключились.

Экспериментальный UDP relay намеренно одноклиентский. При двух одновременных клиентах
`sec` показывал `(no-dtls)`, тогда как `pri` сохранил DTLS. Это соответствует
заявленной области PoC; production relay обязан иметь независимые per-peer UDP
associations.

### Решение

**EXP-011: COMPLETE — PASS.**

Реальный ocserv/OpenConnect подтверждает NG1 transport-publication boundary для обоих
транспортов без изменения внешнего client endpoint:

    client :44443
        -> ROU-owned host TCP/UDP publication
        -> relay
        -> ocserv inside private ROU netns
        -> vpnsXX inside that netns

Same-port real-protocol publication считается доказанной. Произвольная translation
external/internal port остаётся отдельным protocol-semantic вопросом.

---

## EXP-010 — NG1: ROU transport publication relay

**Статус:** COMPLETE — PASS  
**Architecture baseline:** NG1 Draft 1  
**Тип:** generic UDP transport proof; WireGuard intentionally excluded  
**Artifacts:**  
- [rootless local smoke](experiments/EXP-010%20NG1%20ROU%20transport%20publication/vpn-gateway-exp-010-local-smoke.py)  
- [Phase A result](experiments/EXP-010%20NG1%20ROU%20transport%20publication/EXP-010-phase-A-result.md)  
- [Phase B result](experiments/EXP-010%20NG1%20ROU%20transport%20publication/EXP-010-phase-B-result.md)  
- [netns probe](experiments/EXP-010%20NG1%20ROU%20transport%20publication/vpn-gateway-exp-010-rou-transport-publication.sh)

### Мотивация

NG1 вводит transport publication как ROU-owned механизм:

    host-side published TCP/UDP socket
        -> ROU relay
        -> stable internal transport listener inside ROU namespace

Это позволяет один раз настроить опорный VPN на внутреннем порту, а затем менять
host-facing publication только в ROU config, не изменяя WireGuard/ocserv/OpenConnect config.

До подключения реального VPN необходимо отдельно доказать две вещи:

1. сам socket/relay workflow;
2. тот же workflow через отдельный Linux network namespace.

### Проверяемая цепочка

Эксперимент намеренно заменяет WireGuard простым UDP listener:

    client input
        -> published UDP port
        -> relay
        -> internal listener
        -> listener records exact input
        -> listener emits PAYLOAD:<input> to independent sink
        -> sink records dependent payload

Дополнительно listener возвращает:

    ACK:<input>

через relay исходному client.

Таким образом успешный прогон доказывает не только доставку на внутренний port, но и то,
что listener действительно получил конкретный input и породил наблюдаемый output,
зависимый от него.

### Phase A — rootless local relay smoke

**Статус:** PASS  
**Среда:** доступный execution container  
**Network namespace:** не используется

Все четыре роли работают отдельными UDP sockets в одном namespace:

- client;
- published relay;
- internal listener;
- independent sink.

Наблюдено:

    CLIENT_TX: b'exp010-local-smoke'
    RELAY_RX: ('127.0.0.1', 40186) b'exp010-local-smoke'
    RELAY_FWD: ('127.0.0.1', 55129) -> ('127.0.0.1', 17890)
    INTERNAL_RX: ('127.0.0.1', 55129) b'exp010-local-smoke'
    INTERNAL_TX: b'PAYLOAD:exp010-local-smoke'
    INTERNAL_ACK: b'ACK:exp010-local-smoke'
    INTERNAL_PASS: ok
    RELAY_RETURN: ('127.0.0.1', 17890) b'ACK:exp010-local-smoke'
    RELAY_TX: ('127.0.0.1', 40186) b'ACK:exp010-local-smoke'
    RELAY_PASS: ok
    SINK_RX: ('127.0.0.1', 56150) b'PAYLOAD:exp010-local-smoke'
    SINK_PASS: ok
    CLIENT_RX: ('127.0.0.1', 15678) b'ACK:exp010-local-smoke'
    CLIENT_PASS: ok
    OVERALL=PASS

Динамические source ports являются run-local и не входят в критерий PASS.

**Вывод Phase A:** generic UDP publication/relay workflow работоспособен.
Это не является доказательством namespace topology.

### Phase B — ROU network namespace

**Статус:** PASS

Phase B сохраняет тот же application-level workflow, но переносит internal listener в
отдельный namespace и соединяет main namespace с ним через veth:

    main NS                         ROU NS

    published socket
         |
       relay
         |
      exp10h  <----------------->  host0
    192.0.2.1/30                 192.0.2.2/30
                                      |
                              internal UDP :17890

Listener отправляет dependent payload обратно на host-visible sink через тот же veth.

Prepared script создает namespace/veth только на время опыта и удаляет их через cleanup trap.

Phase B был запущен на живом Debian-стенде с доступными network namespace/veth primitives.

### Результат Phase B

Наблюдено:

    EXP-010 NG1 ROU transport publication namespace relay
    H1 published socket -> relay -> netns listener: PASS
    H2 netns listener -> dependent host-visible payload: PASS
    H3 netns listener -> relay -> original client response: PASS

    OVERALL=PASS

Подтверждено:

- host-side published UDP socket принимает входной datagram;
- relay передает его через veth в отдельный ROU netns;
- listener внутри ROU netns регистрирует исходный input;
- listener генерирует зависимый от input datagram, наблюдаемый host-side sink;
- reply listener'а возвращается через relay исходному client.

Cleanup namespace/veth обеспечивается harness trap; отдельный H4 в данном прогоне не был
выведен как самостоятельная строка результата и поэтому не используется как доказательство.

### Решение

**EXP-010: COMPLETE — PASS.**

Для NG1 подтверждена generic transport-publication topology без зависимости от конкретного
VPN protocol:

    host-side published socket
        -> ROU relay
        -> private ROU netns listener
        -> dependent output / return path

Это достаточно, чтобы считать базовую publication abstraction жизнеспособной и переходить
к следующему эксперименту с реальным WG/OC endpoint, не меняя саму boundary-модель.

---

## EXP-009 — RC3: interface-centric failover semantics

**Статус:** COMPLETE — PASS  
**Architecture baseline:** RC3 после EXP-006, до interface-centric пересмотра модели  
**Запуск:** 2026-11-10  
**Тип:** ручной live experiment без `vpn-gatewayd`  
**Target:** Debian 13 gateway; OpenConnect multi-interface + WireGuard stable-interface cases  
**Результат:** [`EXP-009-result-20261110.md`](experiments/EXP-009%20RC3%20multi-interface%20binding%20discovery/EXP-009-result-20261110.md)

### Мотивация

Эксперимент начался как проверка association configured peer с runtime-интерфейсом и
route failover. Последующие live-наблюдения показали, что transport peer является лишней
абстракцией для VPN-GATE: Linux routes выбирают concrete interface, а transport может
иметь собственную внутреннюю peer-selection semantics.

### EXP-009.1 — OpenConnect multi-interface lifecycle

**Статус:** COMPLETE — PASS

Подтверждено:

1. две одновременные OpenConnect sessions создают разные runtime-интерфейсы
   `vpns00` / `vpns01` с одним server-side local IPv4 `172.20.130.1`;
2. исчезновение `vpns00` автоматически удаляет зависимый route через этот interface;
3. оставшийся route через `vpns01` становится рабочим backup path;
4. возвращение `vpns00` само route не восстанавливает — требуется reconciliation;
5. если preferred route остается существовать, но forwarding за ним мертв, metric сам
   не обнаруживает path failure и traffic на backup не переключается;
6. direct route без transport next-hop работает:
   `172.21.201.19/32 dev vpns00 proto 202 metric 10` успешно достиг реального target.

### EXP-009.2 — WireGuard peer semantics

**Статус:** COMPLETE — PASS

На одном стабильном `wg0` одновременно работали peers `172.20.126.2` и
`172.20.126.3`.

Подтверждено:

1. Linux FIB допускает два routes к одной цели через один `wg0` с разными next-hop и
   metric, но next-hop не выбирает WireGuard peer;
2. без target prefix в WireGuard `AllowedIPs` отправка дала
   `Required key not available`;
3. target prefix `172.21.201.19/32` может принадлежать только одному peer одного
   `wg0`; назначение того же prefix второму peer переприсваивает ownership;
4. фактический traffic идет к peer, владеющему destination по `AllowedIPs`, даже если
   Linux FIB показывает другой next-hop;
5. отключение WireGuard на owning peer не меняет runtime `AllowedIPs` ownership и не
   вызывает автоматический переход на другой peer;
6. static config с одинаковым target prefix у двух peers разрешается по принципу
   «последний примененный peer получает prefix»; смена порядка peer-блоков зеркально
   меняет владельца prefix;
7. handshake/endpoint availability не участвует в таком ownership decision.

Во время подготовки WG baseline также наблюдалась transient NAT/path anomaly. Причина не
установлена; удаление старых OC MASQUERADE rules совпало с восстановлением пути, но
повторное добавление правила отказ не воспроизвело. Подробности сохранены в result artifact
как диагностическая отправная точка, но не используются как архитектурное доказательство.

### Наблюдаемый контракт EXP-009

- VPN-GATE может выводить routing/failover state непосредственно из concrete
  runtime-интерфейсов;
- transport peer не является надежным или необходимым route-next-hop abstraction;
- prefix-family transport штатно может иметь несколько одновременно active concrete
  interfaces;
- stable exact interface может скрывать собственную transport peer-selection semantics,
  которой VPN-GATE не должен пытаться управлять через Linux route next-hop;
- route metrics задают приоритет существующих interface paths, но не являются
  end-to-end health-check;
- Netlink по-прежнему только будит reconciliation; snapshot concrete interfaces решает,
  какие paths должны существовать.

**EXP-009: COMPLETE — PASS.**

Архитектурный переход от peer-centric к interface-centric модели выполняется отдельным
нормативным изменением RC3.

---
## EXP-008 — RC3 live runtime drift recovery

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC3  
**Prerequisite:** EXP-007 COMPLETE — PASS  
**Target:** dedicated Debian 13 vpn-gateway host with a READY OpenConnect binding  
**Harness:** [`design/experiments/EXP-008 RC3 live runtime drift recovery/vpn-gateway-exp-008-runtime-drift.sh`](experiments/EXP-008%20RC3%20live%20runtime%20drift%20recovery/vpn-gateway-exp-008-runtime-drift.sh)  
**Result:** [`vpn-gateway-exp-008-result-20261109.txt`](experiments/EXP-008%20RC3%20live%20runtime%20drift%20recovery/vpn-gateway-exp-008-result-20261109.txt)  
**Run:** 2026-11-09T21:04:10Z  
**Safety:** live-host fault-injection experiment; daemon owns the gateway state for the duration

### Motivation

EXP-007 proved startup, steady reconciliation and graceful cleanup. EXP-008 exercises the
runtime reconciliation paths that are materially different after the daemon is already
ACTIVE.

The experiment deliberately separates three kinds of recoverable drift:

1. deletion of an owned proto-202 route;
2. confirmed INPUT-only firewall drift;
3. transit-affecting FORWARD drift.

The last two cases must take different safety paths.

### Preconditions

The same clean ownership boundary as EXP-007 is required before startup:

- `net.ipv4.ip_forward=0`;
- no `VPNG-*` resources;
- no proto-201/proto-202 routes;
- real managed VPN interface already READY;
- managed profile has at least one peer and protected route.

### Hypotheses

#### H1 — live startup

The daemon reaches the same ACTIVE materialized state proven by EXP-007.

#### H2 — owned route drift self-heals

The harness deletes one exact daemon-owned proto-202 route. The daemon must restore the
same route through runtime reconciliation and remain ACTIVE with forwarding enabled.

This mutation produces a route Netlink event; periodic reconciliation remains the fallback.

#### H3 — INPUT-only drift uses narrow repair

The harness creates a foreign `EXP008-IN` chain and inserts its jump at INPUT position 1,
ahead of the daemon-owned INPUT prefix.

Required recovery:

- daemon-owned INPUT prefix returns to position 1;
- the foreign jump is preserved after the daemon-owned prefix;
- daemon-owned FORWARD/NAT state is not intentionally rebuilt by the test;
- `ip_forward` must remain 1 throughout the observed recovery window.

A high-frequency watcher records any observed zero value. Seeing `ip_forward=0` is a FAIL
for this hypothesis.

#### H4 — FORWARD drift uses the protective barrier

The harness creates a foreign `EXP008-FWD` chain and inserts its jump at FORWARD position
1, ahead of the daemon-owned terminal prefix.

Required recovery:

- daemon-owned FORWARD prefix returns to position 1;
- the foreign jump is preserved after `VPNG-FORWARD-DENY`;
- the daemon remains/rereturns ACTIVE;
- the observer must see `ip_forward=0` during the repair;
- after repair, `ip_forward=1`.

Because ordinary iptables rule changes do not wake the Netlink listener, this case is
expected to be detected by the next periodic reconciliation. The observer begins before
fault injection and runs until the repaired prefix is verified.

#### H5 — graceful cleanup

After the fault-injection phases, SIGTERM must still remove every daemon-owned resource and
return `ip_forward` to 0. The harness then removes its own foreign EXP008 chains.

### Artifacts

The harness writes timestamped snapshots for baseline, route recovery, INPUT repair,
FORWARD repair and post-cleanup state, plus:

- `daemon.log`;
- forwarding watcher logs;
- injected/recovered rule snapshots;
- `result.txt`;
- tarball + SHA256.

### Result

Final live run:

```text
EXP-008 RC3 live runtime drift recovery
PASS: H1 live startup
PASS: H2 proto-202 route recovery
PASS: H3 INPUT-only narrow repair
PASS: H4 FORWARD barrier repair
PASS: H5 graceful cleanup
OVERALL=PASS
archive=vpn-gateway-exp-008-20261109-210410Z.tar.gz
sha256_file=vpn-gateway-exp-008-20261109-210410Z.tar.gz.sha256
```

The run confirms on the real Debian 13 gateway that:

- deletion of an owned proto-202 route is detected and repaired at runtime;
- confirmed INPUT-only drift is repaired without dropping IPv4 forwarding;
- FORWARD drift takes the protective barrier path and is repaired before forwarding is
  restored;
- graceful cleanup still succeeds after all injected faults.

### Decision

**EXP-008 result: PASS.**

The first real-host runtime drift recovery gate is closed. Managed-interface
disappearance/reappearance and selector ambiguity remain a separate transport-lifecycle
experiment because they require controlled mutation of the VPN interface itself.

---

## EXP-007 — RC3 live daemon lifecycle smoke

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC3  
**Implementation:** RC3 Python development line, unit suite 125/125 PASS  
**Target:** dedicated Debian 13 vpn-gateway host with the real OpenConnect transport already established  
**Harness:** [`design/experiments/EXP-007 RC3 live daemon lifecycle smoke/vpn-gateway-exp-007-rc3-live-smoke.sh`](experiments/EXP-007%20RC3%20live%20daemon%20lifecycle%20smoke/vpn-gateway-exp-007-rc3-live-smoke.sh)  
**Result:** [`vpn-gateway-exp-007-result-20261109.txt`](experiments/EXP-007%20RC3%20live%20daemon%20lifecycle%20smoke/vpn-gateway-exp-007-result-20261109.txt)  
**Run:** 2026-11-09T20:53:13Z  
**Safety:** live-host experiment; run only in a maintenance window after stopping any previous vpn-gateway controller/daemon

### Motivation

EXP-003 proved the RC2.5.1 initial happy path. EXP-006 validated the target
`iptables-restore --noflush` mechanics required by RC3. The RC3 Python implementation is
now unit-clean, but the complete RC3 daemon lifecycle has not yet been executed against the
real Debian kernel boundary.

EXP-007 is deliberately narrow. It validates the first live implementation gate before
injecting runtime drift or Netlink transition scenarios.

### Scope

The harness runs the actual RC3 entry point against a supplied root-owned production-style
configuration and records three phases:

1. **PRE** — clean fail-closed host state before the daemon starts;
2. **ACTIVE** — state after startup and after at least one periodic reconciliation interval;
3. **POST** — state after graceful `SIGTERM` shutdown and universal cleanup.

It does not inject firewall drift, route drift, interface disappearance, ambiguity or
Netlink loss. Those are follow-up experiments after this lifecycle gate passes.

### Preconditions

- dedicated Debian 13 gateway/test host;
- real VPN transport interface is already present and has the configured local IPv4;
- prior vpn-gateway service/controller is stopped;
- `net.ipv4.ip_forward=0`;
- no existing `VPNG-*` chains/jumps;
- no existing route protocol 201/202 entries;
- RC3 host IPv6 prerequisites satisfy the architecture;
- configuration path and parent directory satisfy RC3 ownership/mode checks.

The harness refuses to proceed if the clean ownership boundary is not satisfied.

### Hypotheses / pass criteria

- **H1 — config boundary:** `vpn-gatewayd.py --check-config` succeeds.
- **H2 — startup materialization:** the daemon remains alive, enables
  `net.ipv4.ip_forward=1`, creates daemon-owned `VPNG-*` filter/NAT resources,
  installs at least one proto-201 blackhole and at least one proto-202 unicast route.
- **H3 — steady reconciliation:** after one configured `reconcile_interval` plus guard
  time, the daemon is still alive and the owned-state snapshot remains valid.
- **H4 — graceful cleanup:** `SIGTERM` exits cleanly, returns
  `net.ipv4.ip_forward` to 0, removes all `VPNG-*` resources and removes all
  proto-201/202 routes that were absent at PRE.

All four hypotheses must pass.

### Artifacts

The harness creates:

```text
vpn-gateway-exp-007-<UTC timestamp>/
    environment.txt
    config-check.txt
    daemon.log
    pre/
    active-initial/
    active-stable/
    post/
    result.txt
vpn-gateway-exp-007-<UTC timestamp>.tar.gz
vpn-gateway-exp-007-<UTC timestamp>.tar.gz.sha256
```

Each phase contains forwarding/sysctl state, interface inventory, route inventory,
`iptables-save` filter/NAT snapshots, and daemon-owned resource extracts.

### Run

From the experiment directory:

```bash
sudo ./vpn-gateway-exp-007-rc3-live-smoke.sh \
    --config /etc/vpn-gateway/vpn-gateway.toml
```

By default the harness resolves the RC3 Python tree at
`../../RC3/code/python`. `--python-tree` can override it.

### Result

Final live run:

```text
EXP-007 RC3 live daemon lifecycle smoke
PASS: H1 config boundary
expect_proto202=1
PASS: H2 startup materialization
PASS: H3 steady reconciliation
PASS: H4 graceful cleanup
OVERALL=PASS
archive=vpn-gateway-exp-007-20261109-205313Z.tar.gz
sha256_file=vpn-gateway-exp-007-20261109-205313Z.tar.gz.sha256
```

All four hypotheses passed on the real Debian 13 gateway.

The run confirms that the RC3 daemon:

- accepts the production-style config through the security/lint boundary;
- materializes the expected daemon-owned firewall/NAT and route state;
- enables IPv4 forwarding only after startup materialization;
- remains stable across at least one periodic reconciliation interval;
- handles graceful SIGTERM shutdown;
- removes daemon-owned firewall/NAT and proto-201/proto-202 route state and returns
  `net.ipv4.ip_forward` to 0.

### Setup findings

Two pre-final runs produced useful negative evidence.

1. The original EXP-007 harness unconditionally required a proto-202 route whenever a
   profile contained routes. That predicate was corrected to account for the configured
   peer set.
2. The live OpenConnect interface was `vpns00` while the config used the exact selector
   `interface = "vpns0"`. RC3 therefore correctly resolved the profile as not READY,
   retained the fail-closed proto-201 blackhole, omitted proto-202, and still remained
   operationally fail-closed. Changing the selector to `interface = "vpns+"` produced
   the intended READY binding and the final PASS.

The second finding is direct live evidence that exact-vs-prefix selector semantics do not
silently broaden and that a non-matching exact selector fails closed.

### Decision

**EXP-007 result: PASS.**

The RC3 live lifecycle/materialization gate is closed. The next experimental block may
exercise runtime recovery and drift handling rather than repeating startup validation.

---

## EXP-006 — замена существующих цепочек и восстановление daemon-owned префикса

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC3  
**Run:** 2026-11-09  
**Target:** Debian GNU/Linux 13 (trixie), Linux 6.12.115+deb13.1-amd64, iptables v1.8.11 (nf_tables)  
**Harness:** [`design/experiments/EXP-006 Firewall orchestration target validation/vpn-gateway-exp-006-firewall-orchestration.sh`](experiments/EXP-006%20Firewall%20orchestration%20target%20validation/vpn-gateway-exp-006-firewall-orchestration.sh)  
**Result:** [`vpn-gateway-exp-006-result-20261109.txt`](experiments/EXP-006%20Firewall%20orchestration%20target%20validation/vpn-gateway-exp-006-result-20261109.txt)  
**Implementation gate:** satisfied; RC3 firewall orchestration may be connected to the working implementation

### Motivation

RC3 использует `iptables-restore --noflush` не только для первоначального создания
daemon-owned цепочек, но и для восстановления уже существующего состояния:

- изолирующий фильтр должен заменить содержимое существующих `VPNG-*` цепочек как полное
  требуемое состояние таблицы `filter`;
- полный фильтр должен затем заменить изолирующее содержимое;
- стороннее правило, вставленное перед daemon-owned префиксом встроенной цепочки, должно
  сохраниться, но после восстановления оказаться физически после префикса;
- операции одной таблицы должны либо примениться целиком, либо завершиться ошибкой без
  частично примененного промежуточного состояния.

Документация `iptables-restore --noflush` указывает, что повторное объявление
user-defined chain очищает и перестраивает именно эту цепочку, сохраняя остальные цепочки
таблицы. Проектное правило target validation все равно требует проверить конкретный
iptables-nft backend целевой Debian для полного сценария RC3.

### Safety boundary

Все изменения выполняются только внутри одноразовых network namespaces. Host firewall не
изменяется.

### EXP-006.1 — повторное объявление существующей daemon-owned цепочки

Исходное состояние содержит существующую `VPNG-INGRESS` с отличающимися правилами и
несвязанные сторонние цепочки.

Один `iptables-restore --noflush` payload повторно объявляет:

```text
:VPNG-INGRESS - [0:0]
```

и задает новое содержимое цепочки.

Проверяется:

- старые правила `VPNG-INGRESS` удалены;
- новые правила присутствуют ровно в заданном порядке;
- несвязанные сторонние цепочки и правила сохранены;
- `iptables-save` дает ожидаемую каноническую форму.

### EXP-006.2 — full -> isolation -> full при существующих потоках

В namespace создается рабочий exact binding block и генерируется
`ESTABLISHED,RELATED`-трафик через него.

Последовательно применяются:

```text
full filter
-> isolation filter
-> full filter
```

Проверяется:

- isolation удаляет exact `ACCEPT` и блокирует весь управляемый поток, включая уже установленный `ESTABLISHED,RELATED`-трафик;
- после восстановления full filter exact block возвращается;
- каждая стадия после `COMMIT` полностью соответствует ожидаемому состоянию;
- не наблюдается смешанного набора старых и новых правил одной таблицы.

### EXP-006.3 — точечное восстановление INPUT и транзитный drift

Проверяются два независимых сценария.

#### A. INPUT-only drift при активной пересылке

Исходное состояние:

- полный daemon-owned `INPUT`-префикс находится с позиции 1;
- `FORWARD` и NAT находятся в требуемом состоянии;
- `ip_forward=1`;
- через gateway идет установленный транзитный поток.

Перед daemon-owned `INPUT`-префиксом вставляется сторонний jump, моделирующий
host-firewall/Fail2ban. Его семантика специально не анализируется.

Точечный repair должен одной транзакцией таблицы `filter`:

- восстановить daemon-owned `INPUT`-префикс с позиции 1;
- сохранить сторонний jump и его цепочку после `VPNG-INPUT-GUARD`;
- не изменять daemon-owned `FORWARD`-цепочки и переходы;
- не изменять NAT и маршруты;
- не изменять `ip_forward`.

Проверяется, что установленный транзитный поток продолжает проходить без разрыва, а
сторонний host-filter после перестановки продолжает получать обычный `INPUT`-трафик с
неуправляемого интерфейса.

Отдельно изменяется содержимое `VPNG-INPUT-GUARD` или профильной INPUT-chain. Тот же
узкий repair должен восстановить daemon-owned INPUT-часть без изменения транзитной
политики.

#### B. FORWARD/NAT drift

Перед daemon-owned `FORWARD`-префиксом вставляется стороннее правило либо нарушается
daemon-owned NAT.

Этот случай не использует узкий INPUT repair. Он должен классифицироваться как
транзитное `UNSAFE` и запускать существующий протокол с первоначальным запретом.

Проверяется, что после восстановления стороннее правило `FORWARD` сохранено физически
после `VPNG-FORWARD-DENY`, а daemon-owned префикс снова начинается с позиции 1.

### EXP-006.4 — ошибка транзакции

В payload намеренно добавляется операция, которая должна завершиться ошибкой до
`COMMIT`.

Проверяется, что таблица после ошибки совпадает с состоянием до попытки применения и не
содержит частично перестроенного daemon-owned префикса.

### Pass criteria

EXP-006 считается успешным только если все четыре подэксперимента проходят на целевом
iptables-nft backend, включая точечное восстановление `INPUT` без изменения активной
пересылки.

### Result

На целевой Debian 13 системе все четыре подэксперимента завершились `PASS`:

- EXP-006.1 подтвердил замену содержимого существующей daemon-owned chain через
  `iptables-restore --noflush` с сохранением несвязанных сторонних правил;
- EXP-006.2 подтвердил переход `full -> isolation -> full`, включая блокировку уже установленного `ESTABLISHED,RELATED`-потока на стадии isolation;
- EXP-006.3 подтвердил точечное восстановление `INPUT` при активной пересылке без
  изменения `ip_forward`, `FORWARD` и NAT и без разрыва живого транзитного потока;
- EXP-006.4 подтвердил отсутствие частично примененного состояния после ошибки
  `iptables-restore` до `COMMIT`.

Итоговый код возврата harness: `0`. Implementation gate для подключения RC3 firewall
orchestration закрыт положительно.

---


## EXP-005 — iptables interface-prefix guard contract

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC2.6.2  
**Implementation:** RC2.5.1 running on the gateway; experiment traffic isolated in network namespaces  
**Run:** 2026-11-08

### Motivation

RC2.6.2 requires a deny-only INPUT guard that exists before the runtime VPN interface name
is known. The remaining external contract was the exact target behavior of iptables
interface-prefix matching and its canonical save form.

The experiment intentionally tests only the firewall boundary. Prefix matching is not
permitted for ACCEPT, NAT or route resources.

### Environment

Same target gateway family as EXP-004:

```text
Debian 13.7
iptables: v1.8.11 (nf_tables)
iptables-save: v1.8.11 (nf_tables)
iptables-restore: v1.8.11 (nf_tables)
```

### EXP-005.1 — acceptance and canonical save form

A namespace-local filter table was loaded with:

```text
-A VPNG-INPUT-GUARD -i vpns+ -j REJECT --reject-with icmp-host-prohibited
```

Result:

```text
iptables-restore rc=0
```

`iptables-save -t filter` emitted the same canonical interface operand:

```text
-A VPNG-INPUT-GUARD -i vpns+ -j REJECT --reject-with icmp-host-prohibited
```

**Result: PASS.**

### EXP-005.2 — actual match scope

Packets were injected through interfaces renamed sequentially to:

```text
vpns0
vpns1
vpnsX
vpns
other0
```

Observed counters:

```text
vpns0    ping_rc=1 reject_packets=1
vpns1    ping_rc=1 reject_packets=1
vpnsX    ping_rc=1 reject_packets=1
vpns     ping_rc=1 reject_packets=1
other0   ping_rc=0 reject_packets=0
```

Therefore target iptables semantics are textual prefix matching:

```text
-i vpns+  -> matches vpns and every interface name beginning with vpns
```

It is not equivalent to the previously proposed numeric-only discovery convention.

**Result: PASS.**

### EXP-005.3 — exact rule before broad deny guard

The test INPUT prefix was rebuilt as:

```text
exact profile rule: -i vpns0 -j ACCEPT
then guard:         -i vpns+ -j REJECT
```

Observed:

```text
vpns0    ping_rc=0 exact=1 guard=0
vpnsX    ping_rc=1 exact=0 guard=1
```

A known concrete binding can therefore be handled by an earlier exact profile rule while
every other interface in the reserved prefix namespace remains denied by the pre-existing
guard.

**Result: PASS.**

### Architecture decision

EXP-005 removes the need for a separate vpn-gateway-only percent-sentinel selector grammar.

Architecture RC2.6.3 uses:

```text
interface = "wg0"    # exact selector
interface = "vpns+"  # prefix-family selector
```

The `+` selector deliberately follows the tested iptables interface-prefix contract.

Consequences:

- a prefix selector reserves the entire textual prefix namespace, not only numeric suffixes;
- discovery cardinality is computed over that same namespace;
- `+` is allowed only as the final selector operator;
- prefix matching is deny-only in firewall policy;
- ACCEPT, NAT and routes use only a resolved concrete exact interface name;
- an exact selector ending in literal `+` is unsupported because the iptables backend
  interprets trailing `+` as wildcard/prefix syntax rather than an exact interface operand.

This closes the pre-binding firewall-protection question: the deny-only guard can be
materialized before any concrete runtime interface exists.

---


## EXP-004 — Gateway boundary validation after first live happy path

**Status:** COMPLETE — PASS with architecture/implementation findings  
**Architecture baseline:** RC2.4.1  
**Implementation:** RC2.5.1  
**Run:** 2026-11-08

### Motivation

EXP-003 proved that RC2.5.1 can materialize a working initial OpenConnect gateway path.
EXP-004 probes the boundaries that the happy path did not exercise:

1. whether daemon ownership of global IPv4 forwarding is complete rather than limited to
   configured protected destinations;
2. whether the FIB remains fail-closed when the VPN interface disappears;
3. whether an ocserv `device` value is an exact runtime interface name or only a prefix;
4. whether the planned `iptables-restore --noflush` cleanup payload is transactionally safe
   on the target Debian backend;
5. whether cleanup can inventory only daemon marker routes without parsing unrelated,
   unsupported foreign route shapes.

The subexperiments share one lab environment but have independent hypotheses, procedures,
results and decisions.

### Environment

Captured on the Debian 13 gateway before the block:

```text
Debian 13.7
kernel: 6.12.115+deb13.1-amd64
iptables: v1.8.11 (nf_tables)
iptables-save: v1.8.11 (nf_tables)
iptables-restore: v1.8.11 (nf_tables)
iptables alternative: /usr/sbin/xtables-nft-multi
iproute2: 6.15.0
libbpf: 1.5.0
nftables: 1.1.3
ocserv: 1.3.0-2
GnuTLS: 3.8.9
```

The gateway profile under test used:

```text
VPN network:       172.20.130.0/29
server local VPN:  172.20.130.1
OpenConnect peer:  172.20.130.5
protected route:   <protected-prefix>
```

All LAN host/target addresses are intentionally redacted from this record. The
`172.20.130.0/29` transport addresses are part of the repository's documented test design.

### Setup finding — runtime directory bootstrap

After a gateway reboot, foreground startup failed before lock acquisition because
`/run/vpn-gateway` did not exist. Creating the directory manually as root with mode `0700`
allowed startup to proceed.

Decision for the implementation review:

- the daemon should safely ensure `/run/vpn-gateway` exists before opening its lock file;
- the path must be a real directory, not a symlink, mode `0700`, and owned by the
  expected daemon service identity; the current root foreground deployment therefore
  expects UID 0;
- systemd `RuntimeDirectory=` remains the preferred deployment mechanism, especially for
  a future non-root service identity, but daemon correctness should not depend on it when
  the process itself has permission to create the directory;
- a configurable alternative lock path is not required now. It may be added later only if
  a real multi-unit/shared-lock use case appears.

---

### EXP-004.1 — Complete IPv4 FORWARD ownership

#### Hypothesis

RC2.5.1 owns only managed destination paths inside its `VPNG-*` chains. Because the daemon
also enables global `net.ipv4.ip_forward`, unmatched transit traffic may return from all
daemon chains and be accepted by the host's base `FORWARD` policy.

#### Baseline

With the daemon active:

```text
net.ipv4.ip_forward = 1
-P FORWARD ACCEPT
-A FORWARD -j VPNG-INGRESS
-A FORWARD -j VPNG-RESERVED
-A FORWARD -j VPNG-OC-FORWARD
```

For a destination outside the protected prefix, VPN transport network and local LAN,
all three daemon chains return without making a terminal decision.

The unmanaged target was first verified to be reachable through the ordinary LAN router:

```text
<allowed-source-ip>
  -> <lan-router-ip>
  -> <unmanaged-target-ip>
```

A host route was then installed on the source so only that unmanaged target traversed the
vpn-gateway host.

#### Result

The trace changed to:

```text
<allowed-source-ip>
  -> <gateway-lan-ip>
  -> <unmanaged-target-ip>
```

and ICMP echo continued to succeed.

The packet therefore entered the vpn-gateway host, matched no managed destination rule,
returned to the built-in `FORWARD` chain and was accepted by its base policy.

#### Decision

**EXP-004.1 result: CONFIRMED.**

This is an architecture-level policy gap, not a lab anomaly.

Because vpn-gatewayd owns the transition of global `net.ipv4.ip_forward` to `1`, it must
also make a terminal policy decision for **all IPv4 forwarded traffic** while forwarding is
enabled. Unmatched forwarding must not depend on a pre-existing `FORWARD ACCEPT` policy or
on downstream foreign rules.

The exact fixed-firewall representation is deferred to the post-EXP architecture review,
but complete daemon ownership of the forwarding decision is now a requirement.

---

### EXP-004.2 — FIB fail-closed behavior across VPN disappearance

#### Hypothesis

With both routes present, the preferred managed unicast route is selected over the
high-metric blackhole. When the VPN interface disappears, the kernel removes the dependent
unicast route but the marker blackhole remains and prevents fallback through the ordinary
default route.

#### Procedure and result

With the VPN up and RC2.5.1 freshly applied:

```text
blackhole <protected-prefix> proto 201 metric 65536
<protected-prefix> via 172.20.130.5 dev vpns0 proto 202 metric 10 onlink
```

A live lookup returned:

```text
<protected-target-ip> via 172.20.130.5 dev vpns0 src 172.20.130.1
```

The OpenConnect client service was then stopped. The ocserv runtime interface disappeared,
the kernel removed the dependent `proto 202` route, and the route table retained:

```text
blackhole <protected-prefix> proto 201 metric 65536
```

On this kernel/iproute2 combination, `ip -4 route get <protected-target-ip>` against the
remaining blackhole returned:

```text
RTNETLINK answers: Invalid argument
```

Most importantly, no lookup result via the ordinary default gateway was produced.

After the OpenConnect client reconnected, ocserv recreated `vpns0` with the expected local
and peer addresses, but RC2.5.1 did not recreate `proto 202` while already in RUN. Only the
blackhole remained until daemon reconciliation/restart.

#### Decision

**EXP-004.2 result: PASS.**

The route design is fail-closed across VPN-interface loss:

- kernel teardown removes the interface-dependent managed unicast route;
- the independent blackhole survives;
- the protected destination does not fall back through the default route.

The reconnect observation also confirms the already-known RC2.5.1 limitation: runtime
interface recovery alone does not restore managed unicast routes because runtime
reconciliation is not implemented yet.

The observed `EINVAL` from `ip route get` is a diagnostic behavior of this tested
blackhole case and is not interpreted as absence of the blackhole route.

---

### EXP-004.3 — ocserv runtime interface identity

#### Hypothesis

The ocserv `device` setting may name an interface family rather than a stable exact
interface. A configuration that hard-codes `interface = "vpns0"` may therefore be unsafe.

#### Procedure and result

Several sequential single-client disconnect/reconnect cycles all reused:

```text
vpns0
```

This alone did not prove exact-name stability.

Next, with the OpenConnect client stopped, a temporary TUN named `vpns0` was created on the
server. On reconnect, ocserv successfully allocated:

```text
device: vpns1
local:  172.20.130.1
peer:   172.20.130.5
```

Finally, ocserv was configured with:

```ini
device = vpns0
```

and the next connection created:

```text
vpns00
```

Therefore the setting is a basename/prefix used to construct runtime device names, not an
exact permanent Linux interface name.

A side check also demonstrated that `#` is a valid character in a Linux netdev name on
this target (`test#` was created successfully), so it is unsuitable as a configuration
sentinel.

#### Decision

**EXP-004.3 result: PASS with architecture change required.**

Keep one configuration key, `interface`, with two modes:

```toml
interface = "wg0"    # exact runtime interface
interface = "vpns%"  # numeric runtime-interface family
```

The trailing `%` is a vpn-gatewayd configuration sentinel, not a general glob or regex.

Normative semantics chosen for the architecture review:

```text
"wg0"   -> exact name "wg0"
"vpns%" -> runtime names matching ^vpns[0-9]+$
```

The sentinel is permitted only once and only as the final character.

For a numeric family:

- zero matching runtime interfaces -> profile is DOWN/not ready;
- exactly one matching runtime interface -> that interface is the profile's runtime device;
- more than one match -> state is ambiguous and must fail closed.

The daemon must never select the first, lowest-numbered or newest interface from an
ambiguous family.

This convention also leaves administrators free to give separate ocserv/WireGuard
instances different prefixes.

> **Последующее архитектурное примечание (RC3):** предложенная после EXP-004.3
> грамматика `vpns%` сохранена выше как исторически принятое на тот момент решение.
> EXP-005 позднее подтвердил нативную семантику iptables `prefix+`; RC3 поэтому заменяет
> `%` на `+` и резервирует всё текстовое пространство имён соответствующего префикса.
> Фактический вывод EXP-004.3 — необходимость семейства runtime-интерфейсов — остаётся
> неизменным.

---

### EXP-004.4 — iptables cleanup transaction contract

#### Hypothesis

The cleanup form planned by RC2.5.1 can remove all daemon jumps and then flush/delete owned
chains in one `iptables-restore --noflush` transaction per table, while preserving foreign
chains/rules. If a foreign reference prevents chain deletion, the table `COMMIT` should
fail without partially applying earlier delete/flush operations.

#### Safety boundary

All tests ran inside a disposable network namespace.

#### Filter positive case

The test table contained two `FORWARD -> VPNG-TEST` jumps with a foreign jump between them,
an owned rule inside `VPNG-TEST`, and an independent `FOREIGN` chain/rule.

One restore payload performed:

```text
-D FORWARD -j VPNG-TEST
-D FORWARD -j VPNG-TEST
-F VPNG-TEST
-X VPNG-TEST
```

Observed:

```text
rc=0
```

Both owned jumps and the owned chain disappeared. The foreign jump, chain and rule remained
unchanged.

#### NAT positive case

The same pattern was repeated in `nat` with duplicate
`POSTROUTING -> VPNG-TEST-NAT` jumps and an independent foreign NAT chain.

Observed:

```text
rc=0
```

The owned NAT resources disappeared and the foreign NAT resources remained unchanged.

#### Negative external-reference case

To test table-transaction failure independently of cleanup-builder discovery, a foreign
chain was made to reference the daemon-owned chain:

```text
FORWARD     -> VPNG-TEST
FORWARD     -> FOREIGN-REF
FOREIGN-REF -> VPNG-TEST
```

The synthetic cleanup payload deliberately did **not** delete
`FOREIGN-REF -> VPNG-TEST`; it attempted to delete the daemon jump, flush `VPNG-TEST`,
and delete the owned chain in one restore transaction.

This is intentionally narrower than an end-to-end test of
`_build_firewall_cleanup_payload()`: the current builder treats ordinary jumps whose
target is `VPNG-*` as marker-owned jumps and would normally include an explicit deletion
for such a visible `-j VPNG-*` rule.

Observed:

```text
iptables-restore v1.8.11 (nf_tables):
line 4: CHAIN_DEL failed (Device or resource busy): chain VPNG-TEST
rc=4
```

A subsequent `iptables-save` showed the complete original table state: the earlier
`-D` and `-F` operations had not been partially committed.

#### Decision

**EXP-004.4 result: PASS.**

On the tested Debian 13 / iptables-nft 1.8.11 backend, the current cleanup design is
validated:

- duplicate daemon jumps can be deleted explicitly in the same payload;
- `-F` and `-X` may follow those deletes before one `COMMIT`;
- foreign rules/chains are preserved;
- if an external reference remains undeleted and makes the daemon chain undeletable,
  restore fails nonzero and leaves the table unchanged rather than partially cleaned.

The architecture's per-table transaction assumption remains valid for this backend.

---

### EXP-004.5 — Marker-selective route inventory for cleanup

#### Hypothesis

Config-independent cleanup should not need to parse the entire `main` routing table.
Explicit `proto 201` and `proto 202` selectors should return only daemon marker routes,
thereby isolating cleanup from unrelated foreign route forms that the strict reconciliation
parser intentionally rejects.

#### Safety boundary

All routes/interfaces were created inside the EXP-004 disposable network namespace.

The namespace contained:

- a daemon-like `proto 201` blackhole;
- a daemon-like `proto 202` unicast route;
- a connected kernel route;
- an unrelated foreign multipath route with a `nexthops` array.

Full inventory included all of them, including:

```json
{"dst":"198.18.0.0/16","nexthops":[{"dev":"dummy0",...},{"dev":"dummy1",...}]}
```

Selective queries were then run:

```text
ip -j -N -4 route show table main proto 201
ip -j -N -4 route show table main proto 202
```

Observed `proto 201` result:

```json
[{"type":"6","dst":"<protected-prefix>","metric":65536,"flags":[]}]
```

Observed `proto 202` result:

```json
[{"dst":"<protected-prefix>","gateway":"172.20.130.5","dev":"dummy0","metric":10,"flags":["onlink"]}]
```

The foreign multipath route was absent from both results.

The protocol field itself is omitted by iproute2 when the protocol is already specified as
a selector. Cleanup therefore knows the protocol from the query contract rather than
requiring a `protocol` field in each returned JSON object.

#### Decision

**EXP-004.5 result: PASS.**

Introduce a cleanup-specific owned-route inventory based on two selective queries:

```text
proto 201
proto 202
```

The cleanup parser may assign the known marker protocol from the query context.

Do **not** weaken the strict full-table inventory/parser used by normal reconciliation:
foreign exact-prefix competitors and unsupported route forms remain relevant there and must
not be silently ignored.

This change removes an unnecessary cleanup failure mode where an unrelated foreign
multipath/nhid route elsewhere in `main` could otherwise make config-independent cleanup
abort before reaching daemon-owned state.

---

### EXP-004 overall decision

**EXP-004 result: PASS.**

The block resolves five gateway-boundary questions and produces four concrete
post-experiment changes/reviews:

1. make daemon forwarding ownership complete whenever vpn-gatewayd enables global IPv4
   forwarding;
2. add dynamic numeric interface-family semantics to the existing `interface` key using a
   trailing `%` sentinel, with ambiguity always fail-closed;
3. use marker-selective route inventory for config-independent cleanup while retaining the
   strict full inventory for reconciliation;
4. make standalone daemon startup safely create/validate its runtime directory instead of
   depending exclusively on systemd to create it.

The blackhole fail-closed route design and the per-table iptables cleanup transaction design
are retained as validated.

Runtime route restoration after VPN reconnect remains intentionally unimplemented in
RC2.5.1 and is now directly demonstrated as the next runtime-reconciliation concern.

Architecture and implementation are **not** modified by this experiment record itself.
They must be reviewed against these results in a separate post-EXP step.


## EXP-003 — First live end-to-end happy-path gateway

### Motivation

Validate the RC2.5.1 happy-path implementation on a real Debian 13 gateway with an
already-established OpenConnect transport and a real protected-network target. This is the
first test of the complete forwarding path rather than isolated route/firewall adapters.

### Topology

```text
allowed Windows LAN host
  -> <gateway-lan-ip>  vpn-gatewayd / ocserv
  -> vpns0 172.20.130.1
  -> 172.20.130.5     OpenConnect client (tun0)
  -> <oc-client-lan-ip>  client LAN side / ens18
  -> <lan-router-ip>    LAN router
  -> <protected-target-ip>     protected-network target
```

Gateway profile:

```toml
managed_vpns = ["oc"]
common_allowed_sources = []

[vpn.oc]
interface = "vpns0"
network = "172.20.130.0/29"
local_address = "172.20.130.1"
peers = ["172.20.130.5"]
routes = ["10.0.0.0/8"]
allowed_sources = ["<allowed-source>"]
```

OpenConnect client forwarding/NAT used for this test:

```text
net.ipv4.ip_forward = 1
-P FORWARD ACCEPT
-A POSTROUTING -s 172.20.130.0/29 -o ens18 -j MASQUERADE
```

### Boundary preflight

After the first RC2.5 live attempt exposed that Debian 13
`iptables-save` does not support `-w`, RC2.5.1 was produced. Before retrying the daemon,
the exact external CLI forms used by the corrected adapter were checked manually:

```text
iptables-save filter rc=0
iptables-save nat rc=0
iptables-restore rc=0
```

The tested restore form was an empty `*filter ... COMMIT` payload with
`iptables-restore -w 5 --noflush`; it made no policy changes.

### Result

**Run:** 2026-11-07/08 local lab time  
**Implementation:** RC2.5.1  
**Architecture:** RC2.4.1

Foreground startup completed and remained running.

Observed gateway state:

```text
net.ipv4.ip_forward = 1
blackhole 10.0.0.0/8 metric 65536
10.0.0.0/8 via 172.20.130.5 dev vpns0 metric 10 onlink
```

The route listings were queried separately by owned protocol (`201` for the blackhole and
`202` for the VPN unicast route).

Observed fixed policy included the expected daemon-owned chains and prefix jumps:

```text
INPUT       -> VPNG-OC-INPUT
FORWARD     -> VPNG-INGRESS
FORWARD     -> VPNG-RESERVED
FORWARD     -> VPNG-OC-FORWARD
POSTROUTING -> VPNG-OC-NAT
```

The profile FORWARD chain admitted only the configured source toward `10.0.0.0/8`, then
rejected the remaining traffic for that destination. The NAT chain contained:

```text
-o vpns0 -m addrtype ! --src-type LOCAL -j MASQUERADE
```

End-to-end comparison from the allowed Windows LAN host:

Before adding the test route:

```text
1  <lan-router-ip>
2  <protected-target-ip>
```

After adding `10.0.0.0/8 via <gateway-lan-ip>`:

```text
1  <gateway-lan-ip>
2  172.20.130.5
3  <lan-router-ip>
4  <protected-target-ip>
```

The target remained reachable after the route change. The trace therefore visibly traversed
the intended vpn-gatewayd host and OpenConnect peer before returning to the LAN router and
reaching the protected target.

### Decision

**EXP-003 result: PASS.**

RC2.5.1 is confirmed to provide a working initial happy path for this topology:

- startup cleanup and materialization complete successfully;
- `ip_forward` is enabled only after policy/route setup;
- owned blackhole and preferred VPN unicast route coexist as designed;
- fixed INPUT/FORWARD/NAT policy permits the configured source and egress;
- server-side MASQUERADE through `vpns0` works in the end-to-end path;
- the OpenConnect client can forward the tunnel traffic onward when its forwarding and
  egress MASQUERADE are configured;
- a real LAN client reaches a real `10.0.0.0/8` target through the complete path.

This experiment does **not** validate graceful shutdown cleanup, crash behavior, runtime
drift repair, periodic reconciliation, or Netlink self-healing. Those remain separate work.


**Current architecture:** [VPN Gateway Architecture RC2.4.1](RC2/vpn-gateway-architecture-rc2.wip.md)

This document is the laboratory record for implementation/research questions that must be resolved on the target Debian environment. Each experiment records:

- the architecture requirement that motivated it;
- the exact hypothesis and safety boundary;
- the procedure and artifacts;
- observed results;
- the resulting implementation/architecture decision.

Experimental results are not silently promoted into architecture. A result first appears here; if it changes a requirement or implementation contract, the corresponding architecture revision is referenced explicitly.



---

## EXP-002A — Address inventory follow-up

**Status:** COMPLETE — PASS  
**Architecture baseline:** RC2.4.1  
**Target:** Debian 13 gateway/test host, stock iproute2  
**Script:** `vpn-gateway-exp-002a-address-inventory.sh`

### Motivation

EXP-002 demonstrated that `ip -j -4 addr show` omits an interface with no IPv4 address.
RC2.4.1 changes `SubprocessKernelInterface.list_interface_ipv4()` to read
`ip -j addr show` and filter IPv4 records in Python.

This follow-up runs the **actual RC2.4.1 adapter** inside a disposable network namespace.

### Pass criteria

The adapter snapshot must report:

```text
empty0 -> frozenset()
p2p0   -> {172.20.140.1}
```

The P2P remote endpoint field is intentionally ignored; only `local` participates in
readiness.

### Procedure

```bash
git pull --ff-only
cd "design/experiments/EXP-002A Address inventory follow-up"
sudo ./vpn-gateway-exp-002a-address-inventory.sh
```

### Result

Observed output:

```text
empty0 = frozenset()
p2p0   = frozenset({IPv4Address('172.20.140.1')})
EXP-002A OVERALL=PASS
```

### Decision

**EXP-002A result: PASS.**

The corrected RC2.4.1 address inventory contract is confirmed on the target Debian 13 /
iproute2 environment:

- an existing interface with no IPv4 address remains present with an empty IPv4 set;
- a point-to-point interface is represented by its local IPv4 address;
- remote peer/address fields do not participate in readiness.

Together with EXP-002, this closes the live validation of the RC2.4.1 route/address
`SubprocessKernelInterface` boundary. The next implementation block is
`_apply_plan()` / `_verify_plan()`.


## EXP-002 — Route adapter iproute2 live smoke

**Status:** COMPLETE — FAIL (one actionable adapter mismatch)  
**Architecture baseline:** RC2.4  
**Target:** Debian 13 gateway/test host, stock iproute2  
**Script:** `vpn-gateway-exp-002-route-adapter-smoke.sh`  
**Script SHA256:** `57658923a76d94a4926968cfd2a2dd6bdf6a373190c73bc88e280005403ac346`

### Motivation

RC2.4 implements the route/address part of `SubprocessKernelInterface` against iproute2 JSON
and explicit `ip route add|del|replace` command forms. Before `_apply_plan()` and
`_verify_plan()` depend on this boundary, the assumptions must be checked against the
actual Debian 13 target environment.

The experiment verifies both JSON inventory shape and the exact mutation forms emitted by
the adapter.

### Safety boundary

The experiment does **not** change host routing, addresses, firewall, NAT or forwarding.

All interfaces, addresses and routes are created inside one disposable network namespace.
The namespace is removed explicitly before artifact packaging and also by an EXIT trap.

Host-visible effects are limited to:

- temporary network namespace creation/removal;
- files written into the current working directory.

### Hypotheses

- **H1 — numeric protocol inventory:** `ip -j -N -4 route show table main` represents
  a connected kernel route with numeric `RTPROT_KERNEL = 2`.
- **H2 — UNICAST round-trip:** the exact RC2.4 UNICAST form can be added, identically
  replaced, observed without canonical identity drift, and deleted using the full
  `RouteSpec` fields including `proto 202`, metric, via/dev and `onlink`.
- **H3 — BLACKHOLE round-trip:** the exact BLACKHOLE form with `proto 201 metric 65536`
  can be added and deleted.
- **H4 — RTPROT_BOOT normalization:** a route added without explicit protocol is represented
  either with omitted protocol or numeric `3`, and can subsequently be deleted with
  explicit `proto 3`.
- **H5 — IPv4 address inventory:** `ip -j -4 addr show` keeps an interface with no IPv4
  as an entry with empty `addr_info`, and a point-to-point-shaped record exposes the
  local address through `addr_info[].local` independently of `peer`.
- **H6 — supported route forms:** BLACKHOLE, UNREACHABLE, PROHIBIT, THROW and default
  UNICAST routes have the JSON type/protocol/metric representation expected by RC2.4.

### Procedure

From the repository root on the Debian 13 test host:

```bash
git pull --ff-only
cd "design/experiments/EXP-002 Route adapter iproute2 live smoke"
sudo ./vpn-gateway-exp-002-route-adapter-smoke.sh
```

The script creates:

```text
vpn-gateway-exp-002-<UTC timestamp>/
vpn-gateway-exp-002-<UTC timestamp>.tar.gz
vpn-gateway-exp-002-<UTC timestamp>.tar.gz.sha256
```

The result directory contains environment data, raw route/address JSON snapshots,
per-command return codes/stdout/stderr and `result.txt`.

### Result

**Run:** `2026-11-07T17:03:04Z`  
**Host:** `testing`  
**Archive SHA256:** `8f905a83df018cfeef5d4c00387b05beeaae5b0ee6b9f3f8a7988ab7c5badf1c`

Environment:

```text
Debian GNU/Linux 13.7 (trixie)
kernel: Linux 6.12.115+deb13.1-amd64
iproute2: 6.15.0
libbpf: 1.5.0
Python: 3.13.5
```

Observed analyzer result:

```text
H1 numeric route protocol inventory: PASS
H2 UNICAST add -> replace -> delete: PASS
H3 BLACKHOLE add -> delete: FAIL
H4 RTPROT_BOOT normalization/delete: PASS
H5 IPv4 address local/peer/empty interface shape: FAIL
H6 supported route types/default JSON shape: FAIL
OVERALL=FAIL
```

The raw observations show three distinct findings.

#### Finding A — `-N` numeric route types: analyzer false negatives

For non-UNICAST route types, `ip -j -N` returned numeric decimal strings:

```text
BLACKHOLE   -> "type": "6"
UNREACHABLE -> "type": "7"
PROHIBIT    -> "type": "8"
THROW       -> "type": "9"
```

RC2.4 adapter already accepts these numeric/string forms in `_parse_route_type()`.
Therefore the H3/H6 FAIL labels were caused by EXP-002 expecting textual type names,
not by an adapter defect.

H3's add/delete commands themselves succeeded and the BLACKHOLE route had the expected
`proto=201` and `metric=65536`.

#### Finding B — P2P remote-peer field: analyzer false negative

The point-to-point record was:

```json
{"family":"inet","local":"172.20.140.1","address":"172.20.140.2","prefixlen":32,...}
```

The remote endpoint is exposed as `address`, not `peer`, on this iproute2 build.
The adapter deliberately consumes only `addr_info[].local`, so the observed local address
matches the runtime readiness contract. No adapter change is required for P2P semantics.

#### Finding C — addressless interface omission: real adapter mismatch

`empty0` was absent from `ip -j -4 addr show`.

Therefore RC2.4 could not satisfy its own `KernelInterface.list_interface_ipv4()` contract:

```text
existing interface without IPv4 -> empty frozenset
missing key -> interface does not exist
```

This distinction is not currently required to decide readiness (both states are not-ready),
but it is part of the kernel-boundary contract and must not be represented incorrectly.

### Decision

EXP-002 produced one actionable implementation correction:

```text
ip -j -4 addr show
        ->
ip -j addr show
```

The adapter now reads the complete interface/address snapshot and filters
`addr_info[].family == "inet"` in Python. This preserves addressless interfaces as
empty IPv4 sets without introducing a second independently sampled `ip link` snapshot.

The route parser/mutator design is retained. Architecture RC2.4.1 records the actual
numeric route-type behavior and the corrected address inventory command.

A narrow EXP-002A validates the corrected adapter itself against the target iproute2.


## EXP-001 — Fixed firewall/NAT canonical round-trip

**Status:** COMPLETE — PASS  
**Target:** Debian 13 gateway/test host using `iptables-nft`  
**Script:** `vpn-gateway-exp-001-iptables-roundtrip.sh`  
**Script SHA256:** `25b3e9d44eb59846de6c1db8ef16e9c806cbd3f6137214baa9f41650a112bfe2`

### Motivation

RC2 makes fixed firewall/NAT verification a prerequisite for both bootstrap and every runtime reconciliation pass. The daemon must distinguish:

- `SAFE` — daemon-owned fixed firewall/NAT exactly matches policy;
- `UNSAFE` — readable state with confirmed drift;
- `UNKNOWN` — state cannot be interpreted reliably.

A direct canonical-text comparison is desirable only if the daemon-owned subset emitted by `iptables-save` is stable enough after `iptables-restore`. Otherwise RC2 requires a minimal normalizer/parser for the daemon-owned subset rather than a general firewall AST.

### Architecture references

- **§8.2 — Runtime fixed firewall/NAT verification:** fixed infrastructure is verified before route/interface reconciliation; parse/normalization inability is `UNKNOWN`.
- **§9 — Firewall and blackhole:** deterministic owned chains, rule order and built-in jump placement.
- **§11 — NAT:** per-profile `VPNG-<PROFILE>-NAT` and fixed `MASQUERADE` are part of fixed infrastructure.
- **§24 — Implementation notes:** explicitly requires a target-host `iptables-restore -> iptables-save` round-trip experiment before deciding whether a normalizer/parser is necessary.
- **Invariant 134:** `iptables-restore` is atomic per table/`COMMIT`, not a cross-table transaction.
- **Invariant 148:** `MASQUERADE` belongs to the fixed firewall/NAT template and is verified with the rest of the infrastructure.
- **Invariant 153:** expected inventory/canonical parse/normalization failure is `UNKNOWN`; programming failures are not hidden.

### Safety boundary

The experiment **must not modify the host firewall**.

Every apply/save cycle runs in a disposable Linux network namespace. Inside that namespace the experiment creates the same `VPNG-*` chains and built-in jumps that RC2 specifies, but the namespace has no production traffic. The namespace is deleted after every cycle and also by an `EXIT` trap.

Host-visible effects are limited to:

- temporary network namespace creation/removal;
- loading already-available netfilter functionality if the kernel does that lazily;
- writing the result directory/archive in the current working directory.

### Test policy

Two managed profiles are represented, matching the RC2 examples closely:

| profile | interface | VPN network | protected routes | effective sources |
|---|---|---|---|---|
| `backup` | `wg0` | `172.20.126.0/29` | `100.64.0.0/10`, `192.168.0.0/16` | `<protected-target-ip>/32` |
| `primary` | `vpns0` | `172.20.130.0/29` | `10.0.0.0/8` | `<protected-target-ip>/32`, `10.200.201.0/24` |

The payload includes:

- deterministic `INPUT`, `FORWARD`, and `POSTROUTING` jumps;
- `VPNG-INGRESS`;
- `VPNG-RESERVED`;
- profile INPUT/FORWARD chains;
- conntrack state matching;
- `REJECT --reject-with icmp-host-prohibited`;
- static `MASQUERADE` with `-m addrtype ! --src-type LOCAL`.

### Comparison view

The experiment deliberately does **not** implement the future daemon normalizer.

For comparison it removes only:

1. `iptables-save` comment lines beginning with `#` (including generated/completed timestamps);
2. blank lines.

Everything else is compared byte-for-byte, line-for-line. Therefore any remaining diff is useful evidence rather than being hidden by a speculative normalizer.

### Hypotheses

#### H1 — deterministic materialization

Applying the exact same RC2 fixed firewall/NAT payload with:

```text
iptables-restore --noflush
```

in three fresh network namespaces produces identical comparison views.

**Pass criterion:** run 1 == run 2 == run 3.

#### H2 — canonical round-trip

The raw `iptables-save` output from H1/run 1 can itself be restored with `iptables-restore --noflush` into a fresh namespace, and the resulting `iptables-save` comparison view is unchanged.

**Pass criterion:** initial save == save after replay.

### Procedure

Run on the Debian 13 target/test host:

```bash
chmod 700 vpn-gateway-exp-001-iptables-roundtrip.sh
sudo ./vpn-gateway-exp-001-iptables-roundtrip.sh
```

The script produces a directory such as:

```text
vpn-gateway-exp-001-20261107-120000Z/
```

and a matching `.tar.gz`.

Important files:

```text
environment.txt
payload.rules

payload-run-1.raw
payload-run-1.norm
payload-run-2.raw
payload-run-2.norm
payload-run-3.raw
payload-run-3.norm

replay-save-1.raw
replay-save-1.norm

diff-payload-1-vs-2.txt
diff-payload-1-vs-3.txt
diff-save-vs-replay.txt

result.txt
```

### Result

**Run:** `2026-11-07T10:02:04Z`  
**Host:** `mytvpn`  
**Archive SHA256:** `bace8dfcee7921525bb53d15eb53f7a2e0a25854c65abbb213ee472a68267536`

Environment:

```text
Debian GNU/Linux 13.7 (trixie)
kernel: Linux 6.12.115+deb13.1-amd64
iptables: v1.8.11 (nf_tables)
iptables-save: v1.8.11 (nf_tables)
iptables-restore: v1.8.11 (nf_tables)
iproute2: 6.15.0
nftables: 1.1.3
iptables alternative: /usr/sbin/iptables-nft
```

Observed result:

```text
EXP-001 fixed firewall/NAT canonical round-trip
H1 same payload on fresh namespaces: PASS
  run1_vs_run2=PASS
  run1_vs_run3=PASS
H2 save -> restore -> save: PASS

OVERALL=PASS
Interpretation: after removing only volatile comments/blank lines,
the daemon-owned filter+nat representation is text-stable in this test.
This supports a minimal canonical-text comparator for the tested subset.
```

All three generated diff files are empty.

Normalized snapshot SHA256 values:

```text
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-1.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-2.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  payload-run-3.norm
7e47e42865dd00c35dc9f1fcd61c9d906ebcb95283a575998bbf42ad4184a882  replay-save-1.norm
```

Therefore:

- **H1 PASS:** the same payload materialized identically in three fresh network namespaces.
- **H2 PASS:** `iptables-save -> iptables-restore --noflush -> iptables-save` was stable.
- The comparison view required removal only of `iptables-save` comment lines and blank lines.

#### Observed canonicalization relative to input payload

The input `iptables-restore` payload is **not** itself the canonical comparison form.

`iptables-save` changed representation in deterministic ways, including:

1. user-defined chain declarations were emitted in canonical order rather than payload declaration order;
2. rules were emitted grouped by their owning chain rather than preserving the interleaving present in the input payload;
3. at least one rule had match options reordered, e.g. the payload form

   ```text
   -A VPNG-BACKUP-INPUT -i wg0 -s 172.20.126.0/29 -d 172.20.126.1/32 ...
   ```

   was emitted canonically as

   ```text
   -A VPNG-BACKUP-INPUT -s 172.20.126.0/29 -d 172.20.126.1/32 -i wg0 ...
   ```

After that first canonicalization, the saved representation was stable across fresh namespaces and a save/restore/save replay.

The raw files happened to be byte-identical in this run because all four saves occurred within the same timestamp second. This is **not** treated as evidence that raw `iptables-save` comments are stable; comments remain excluded from comparison by design.

### Decision

**EXP-001 result: PASS.**

For the tested Debian 13 / `iptables-nft` environment, RC2 does **not** need a semantic rule normalizer.

Implementation direction:

1. Parse `iptables-save` only far enough to identify tables, chains, chain contents, daemon-owned `VPNG-*` resources, and exact positions/uniqueness of daemon jumps in built-in chains.
2. Treat the individual rule text emitted by `iptables-save` as the canonical rule representation for this tested backend.
3. Compare daemon-owned rule strings/order in that canonical save form.
4. Strip only explicitly volatile material demonstrated by the experiment (`# ...` comments and blank lines).
5. Do not compare the original `iptables-restore` payload text directly with `iptables-save` output: the backend deterministically canonicalizes declaration/rule ordering and some option ordering.
6. If a future Debian/iptables version produces a previously unseen canonicalization difference, classify unparseable/uncomparable inventory as `UNKNOWN` as required by RC2, record a new experiment, and extend the minimal parser/normalizer only for demonstrated behavior.

A **minimal structural parser/extractor is still required** because the daemon must isolate its owned subset and verify built-in jump positions without assuming ownership of whole `filter`/`nat` tables. What EXP-001 eliminates is the need for a broader semantic firewall-rule normalizer.

This decision directly resolves the implementation/research question in RC2 §24.

The result was incorporated into RC2.1: memory-only `iptables-save`/`iptables-restore` I/O, minimal structural parsing, and canonical `iptables-save` rule-string comparison are now explicit architecture requirements.

### Follow-up

EXP-001 is closed.

Next implementation consequence:

- `_compare_fixed_firewall_nat()` should use a small `iptables-save` structural parser/extractor plus canonical rule-string comparison, not a general iptables AST and not direct payload-text comparison.

The post-experiment architecture/deployment updates were incorporated in RC2.1.
