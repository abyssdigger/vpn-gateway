# NG3 — requirement/component gate: EXP-035 nft NEW-flow forward rule

**Дата:** 2026-11-16
**Цикл:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`
**CYCLE_INTERVAL:** 40 минут.
**Review unit:** технический Linux/nft эксперимент для одного нижнего
правила NEW-flow admission; без продуктивной nft-мутации.

## Requirements / Constraints

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0002-R2.R5.R1`, `VPNG0001-R1.R3.R2`,
`VPNG0001-R1.R3.R3`, `VPNG0004-R4.R1`,
`VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

Полные ancestry проверены по текущему `design/NG3/requirements.md`.
Первичные `VPNG0001`, `VPNG0002`, `VPNG0004`: внешнее
`Basis` — интервью заказчика 2026-11-15, normative `Statement`,
статус `[closed]`. Производные узлы `Purpose + Statement`
соответствуют родительскому обязательству. Ограничения
`Reason + Statement` ограничивают Release 1 multi-path inbound
и неподтвержденную внешнюю grammar. Актор — VPN-GATE.
Продуктовые обещания не изменяются.

**Requirement gate: PASS** только для технической проверки выбранного
низкоуровневого механизма.

## Scenario / Component design

**Scenario:** исходный host-boundary `host0` пересылает новый IPv4
flow к одному текущему concrete VPN path `vpn0`, когда destination
попадает в разрешённый prefix. Иной источник, путь или destination
не должны получать неявное разрешение от этой rule; после замены
`vpn0` на одноимённый новый ifindex прежнее правило не может
разрешить трафик нового endpoint.

**Components:** текущий `payload_forward` base chain с
`policy drop` и owner marker, нижняя nft Driver/Adapter
и pure Observer. Экспериментальный harness — test code, не
производственный компонент.

**Responsibilities / interactions:** нижний Adapter получает из
`ip -j link show` свежие числовые ifindices; в disposable namespace
материализует опытное правило; затем независимо наблюдает nft JSON
и проверяет реальные пакеты. Поведенческая семантика Profile
остается в `PayloadPolicyCalculator`, а не в nft Driver.
**Нельзя** принимать порядок независимых allow rules за
most-specific Profile classification (включая разные Devices).
В этом experiment только одна Profile/prefix гипотеза,
multi-profile semantics не проверяются.

**External environment:** настоящее Linux kernel forwarding,
nft packet path и реальный JSON на GitHub Ubuntu runner.
Обязателен fail-closed baseline, negative controls и смена ifindex.

**Necessity:** EXP-033 доказывал NAT `meta iif/oif`, но не доказывал
совместную filter expression/ct state/prefix semantics. Необходимо
получить actual lower evidence, прежде чем принимать parser/Driver
для filtering.

**Constraints / lifting:** experiment не создаёт user-facing
лимита и не доказывает готовность inbound или stateful return
traffic. Выводы ограничены одной lower primitive.
Не проверенная full-policy композиция сохраняет gate,
не блокируя независимые реализационные единицы.

**Simplification:** нет общего firewall AST, lookup-кеша,
асинхронной координации, persistent handles или нового policy Engine.

**Evidence plan:** GitHub CI privileged temporary namespaces:
настоящий route + packet test, nft `-j` observation,
положительный case, три negative controls и same-name
replacement. Эксперимент хранит raw facts и вывод; отдельное
внутреннее экспертное ревью с verdict.

**Component-design gate: PASS** для EXP-035; полноценный
filter/nft Executor не разрешён до отдельного design gate.
