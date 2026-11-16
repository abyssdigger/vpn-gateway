# NG3 — экспертное ревью authoritative payload NAT observation / comparison

**Дата:** 2026-11-16  
**CD-ветка:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**Review unit:** строгая read-only классификация фактических NAT-правил с сопоставлением с `PayloadNatDesiredState`.  
**Основание:** нормативные gates зафиксированы в
`design/reviews/NG3-2026-11-16-payload-nat-observer-recovery-gates.md`.

## Scope и проверенные изменения

- `design/NG3/architecture.md` — точные `Implements:` и `Constrained by:`,
  сценарий, границы компонентов, simplification и evidence plan.
- `payload_nat_observation.py` — чистое преобразование `NftNamespaceObservation`,
  fresh `InterfaceIdentity` и normalized NAT desired в
  `confirmed/missing/stale/conflicts`.
- `test_payload_nat_observation.py` — unit regression для strict nft expression,
  ifindex/name, повторов, невидимых/неожиданных форм, пропавшего scaffold,
  замены интерфейса при сохранении имени.
- `integration_payload_nat_observation.py` + `ng3-python.yml` — реальный nft
  и интерфейсный inventory в одноразовом netns; mutation существует только
  внутри тестовой среды, не в продуктовой реализации.
- `__init__.py`, `README.md` — экспорт и корректная фиксация ограниченного scope.

## Проверка трассировки и component model

**Implements:** `VPNG0001-R1.R2.R4.R6.R1`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R3.R2`, `VPNG0004-R4.R4`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0001-R1.R2.R4.R6.C1`.

- `VPNG0001` и `VPNG0004` имеют принятые `Basis + Statement`;
  производные предки имеют `Purpose + Statement`, ограничение —
  `Reason + Statement`. Актор и нижняя область действия определены.
- Выбор **Direct Calculator** соответствует `design/component-model.md`:
  входы явные, вывод синхронный, нет I/O, владельца жизненного цикла,
  сохранённой истории, повторных попыток или событий.
- Существующий `LinuxNftNamespaceBackend` владеет границей нижней технической
  области; разбор актуального NFT состояния не смешивается с выбором
  пользовательской политики и не меняет `NatIntent`.
- `payload_postrouting` классифицируется полностью: чужой комментарий
  или неизвестная форма внутри принадлежащей продукту цепочки — конфликт,
  а не объект для безусловной очистки.
- Текущий текстовый ifname разрешается в полный `InterfaceIdentity`;
  удалённый numeric ifindex остаётся stale и не сопоставляется с новым
  одноименным endpoint. Handle — идентификатор фактического правила,
  не идентификатор требуемой семантики.
- Результат observer не означает, что остальные объекты `table ip vpn_gate`
  проверены, или что `ForwardingGate` открыт/закрыт. Этот Calculator
  не способен авторизовать создание или удаление NAT-правил.

## Findings и disposition

**F-01 — ACCEPTED + FIXED.**
Свойство `PayloadNatComparison.conflict_free` могло быть истолковано как
общий показатель безопасности всей nft-таблицы или разрешение на mutation.
Это нарушало бы структурный барьер, хотя сама текущая функция read-only.
В коммите `bfa0b37c5ec8df18d9d6e2ba8c1a0b4f840d395d`
добавлено явное ограничение: свойство характеризует только конфликты
в наблюдаемой NAT-цепочке; для физического изменения нужны отдельные
полные проверки ownership и `ForwardingGate`.
Проверено повторным полным GitHub CI.

**F-02 — ACCEPTED + FIXED (evidence gap).**
Синтетические nft JSON unit-тесты не доказывали, что конкретный parser
читает реальные nft-объекты после замены интерфейса с прежним именем.
Добавлен `integration_payload_nat_observation.py` в CI; тест подтвердил
current, missing, stale, desired replacement и чужой owner marker.

**Отложенный scope (не дефект данного read-only unit):** физические add/delete,
повторное наблюдение после ошибок, полный состав policy и открытие
forwarding остаются за отдельным design/implementation gate
`NetworkPolicyExecutor / ForwardingGate`. Этот review не выдает PASS на mutation.

Отклонённых findings: нет. Открытых accepted findings в данном unit: нет.

## Evidence

GitHub Actions `NG3 Python`, commit
`bfa0b37c5ec8df18d9d6e2ba8c1a0b4f840d395d`,
run [43858047521](https://github.com/abyssdigger/vpn-gateway/actions/runs/43858047521):

- **PASS** — 286 rootless unit tests;
- **PASS** — реальный EXP-033 exact-ifindex NAT;
- **PASS** — `NG3 live payload NAT observer / same-name ifindex replacement`;
- **PASS** — все 8 jobs, включая nft-owner/scaffold, forwarding-gate,
  route-priority и policy-platform интеграции.

Реальное платформенное поведение не выдумано: оно подтверждено EXP-033
и новым интеграционным observer test. Повторный успешный CI относится
к HEAD после принятого исправления F-01.

## Simplification / product-scope verdict

Новых user-facing полей, состояний, событий, persistent объектов,
policy-routing классификаторов или асинхронных компонентов нет.
Runtime NAT mutation по-прежнему отсутствует. Изменение не расширяет
scope и не сужает принятую полезность NAT-capability.

**FINAL VERDICT: PASS — read-only authoritative NAT observation/comparison
закрыта, accepted findings устранены.** Следующая независимая review unit:
проектирование точной guarded NAT mutation и её postcondition/evidence.
