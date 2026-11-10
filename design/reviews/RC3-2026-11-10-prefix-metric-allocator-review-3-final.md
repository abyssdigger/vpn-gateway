# RC3 — prefix metric allocator review 3 — final

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** cross-domain routing / lifecycle auditor  
**Область:** final architecture after reviews 1–2  
**Вердикт:** **ACCEPT — NO FINDINGS**

## Проверенный контракт

### Exact selector

- единственный active interface;
- UNICAST metric = 10;
- metric строго меньше BLACKHOLE.

### Explicit ordered list

- config order является гарантированным route-priority contract;
- slots = 10,20,30... без renumbering при отсутствующих элементах;
- config validator запрещает любой slot с metric >= BLACKHOLE_METRIC.

### Prefix selector

- route preference между interfaces не является контрактом VPN-GATE;
- metric является уникальным техническим значением;
- continuous `ConcreteBinding(name, ifindex)` сохраняет metric;
- новая binding получает следующее свободное значение от cursor;
- occupied values пропускаются;
- wrap происходит до BLACKHOLE_METRIC;
- любая выделенная UNICAST metric строго меньше BLACKHOLE_METRIC;
- freed hole не обязана использоваться до wrap-around;
- same name + new ifindex является fresh allocation; совпадение численной metric
  допустимо, но не гарантировано;
- restart reset allocator допустим после cleanup proto 202;
- exhausted allocator не создает partial desired state.

## Verified-state boundary

Provisional prefix mapping/cursor входят в immutable reconciliation snapshot.

OWNED routes, active binding state и allocator mapping/cursor commit-ятся одной
verified-state boundary только после успешной проверки. Failed apply/verification
оставляет предыдущий verified allocator state.

Runtime snapshot/domain projection failure, включая allocator exhaustion, приводит к
fail-closed isolation path; startup failure остается hard.

## Policy interaction

ASCII active_order для prefix сохранен только для:

- canonical filter/NAT/status construction;
- reproducible traversal of simultaneously new bindings.

Он не является route-priority contract.

Появление новой prefix binding по-прежнему является policy-changing transition из-за
новых exact firewall/NAT/route resources, но не вызывает renumbering существующих
prefix routes.

## Blackhole relation

Общий invariant:

```text
0 < daemon-owned UNICAST metric < BLACKHOLE_METRIC
```

явно действует на exact, explicit list и prefix allocator.

При текущих constants 65536/10/10 prefix allocator имеет 6553 slots. Это operational
capacity текущих constants, а не архитектурный предел модели.

## Structural checks

- 99 invariants remain sequential;
- §4.4, §8.1–8.4, §8.8, §14, §18, §23.1/23.3, §24.1 and invariants agree;
- no remaining ASCII-derived prefix metric contract found;
- no uint32-only explicit-list bound remains;
- status reports actual interface/metric mapping without promising prefix preference.

## Conclusion

**ACCEPT — NO FINDINGS.**

The architecture is ready for the corresponding Python implementation change.
