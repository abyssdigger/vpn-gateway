# NG3 — gates для EXP-034: точное удаление NAT-правила по nft handle

**Дата:** 2026-11-16  
**CD-цикл:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**Review unit:** доказательство технического поведения nftables для будущей
guarded physical NAT reconciliation; **не** внедрение продуктивной мутации.

## Requirements / Constraints

**Implements:**
- `VPNG0001-R1.R2.R4.R6.R1` — принятое Device NAT intent `none / masquerade`;
- `VPNG0001-R1.R3.R2` — сопоставление с конкретным current endpoint;
- `VPNG0001-R1.R3.R3` — no inheritance при одноимённой замене endpoint;
- `VPNG0004-R4.R3.R2` — guarded structural policy transition;
- `VPNG0004-R4.R4` — подтверждённый закрытый forwarding barrier;
- `VPNG0004-R4.R5` — authoritative re-observation after partial/failed operation.

**Constrained by:**
- `VPNG0001-R1.R2.R4.R6.C1` — не выводить user-facing grammar из kernel test.

В `design/NG3/requirements.md` проверены первичные `VPNG0001` и
`VPNG0004` с Basis/Statement, их полные цепочки Purpose/Statement и
ограничение Reason/Statement. Узлы закрыты, актор — VPN-GATE; новое
продуктовое решение не требуется. Эксперимент не изменяет требования.

**Requirement gate: PASS** для экспериментального доказательства, не
для промышленного add/delete.

## Scenario, component design, necessity

После замены интерфейса с прежним именем в owned `payload_postrouting`
может остаться stale NAT-правило по старому ifindex. Будущий
`NetworkPolicyExecutor` должен иметь возможность удалить **только**
подтверждённый объект и независимо подтвердить итоговый NAT desired state.

Из `design/component-model.md`: фактический nft/Linux interface
находится за нижним **Adapter/Driver**. Будущий **Executor** отвечает
за convergence к заданному desired state, а не за выбор NAT policy.
Уже принятый direct Calculator `compare_payload_nat` возвращает
current/stale/conflicts и реальный `handle`.
Эта review unit создаёт только изолированный **экспериментальный Runner**;
не добавляет публичного Driver/Executor или новый runtime state.

Внешняя техническая неизвестность: гарантирует ли nft на выбранном
Linux target, что `delete rule ... handle H` точно удаляет старый
распознанный объект после удаления interface, не затрагивая новый
объект с тем же ifname; возвращает ли несуществующий handle явную
ошибку без скрытого эффекта.

## Plan / interaction / external environment

- Один disposable netns и две independent veth-pairs.
- nft table/chain со строгими owner markers.
- Проверенный `ip_forward=0` во всё время эксперимента.
- Добавить exact-ifindex NAT rule; observe current.
- Удалить/воссоздать egress с прежним именем, но новым ifindex.
- Observe old rule как stale; добавить и подтвердить current new rule.
- Удалить **только old handle**, затем полностью переопросить nft
  и проверить, что current rule сохранилось без stale.
- Попробовать удалить заведомо отсутствующий handle, потребовать ошибку,
  затем сравнить полный актуальный NAT snapshot с предыдущим.

Все команды argv-based; namespace удаляется в `finally`.
Никакой продуктивный namespace или пользовательская конфигурация
не меняется.

## Constraint lifting / simplification / evidence

Результат уточняет технический способ реализации уже принятого
structural-safe NAT behavior, но не вводит нового продуктового
ограничения и не разрешает mutation при неподтвержденном ownership.
Не добавляем новую модель lifecycle/rollback/retry, event bus,
persistent handle cache или общий nft framework.

**Evidence plan:** GitHub Actions Linux job с `iproute2` и `nftables`,
вывод PASS/FAIL и запись результата в EXP-034. При отрицательном
результате заблокировать только exact-handle deletion и изменить
компонентное решение; не подставлять предположения.

**Component-design gate: PASS** для EXP-034.
Продуктивный NAT mutator остаётся **GATED** до результата эксперимента
и отдельного полномасштабного design-review по ownership +
ForwardingGate + postcondition.
