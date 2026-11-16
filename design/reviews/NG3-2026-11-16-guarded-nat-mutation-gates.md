# NG3 — requirement/component gates: guarded NAT-only mutation slice

**Дата:** 2026-11-16  
**Cycle:** `ng3-design-cycle-20261116-nat-observer-recovery-40m`  
**Scope:** bounded physical NAT-only lower reference under closed root barrier;
не полная structural policy activation.

## Requirement gate

**Implements:** `VPNG0001-R1.R2.R4.R6.R1`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R3.R2`, `VPNG0004-R4.R4`, `VPNG0004-R4.R5`.

**Constrained by:** `VPNG0001-R1.R2.R4.R6.C1`.

Проверено полное ancestry: первичные `VPNG0001`, `VPNG0004`
имеют Basis + Statement и [closed], производные уровни —
неподменённые Purpose + Statement, ограничение — Reason + Statement.
Актор — VPN-GATE / lower Driver; user policy не выбирается этой
операцией. Здесь нет новой NAT grammar, нового policy scope или
вопроса, требующего человеческого выбора.

Сценарий из требования: замена текущего endpoint при сохранении
ifname; старое признанное NAT rule по ifindex может остаться в owned
chain. На этапе structural transition передача неразрешённого
трафика запрещена. Уже принятый `ForwardingGate` обеспечивает
root fail-closed boundary. EXP-033 и EXP-034 доказывают kernel-level
форму и точный handle-delete.

**Requirement gate: PASS для bounded reference slice.**

## Component-design gate

**Scenario:** старая nft masquerade rule остаётся при новом
`(ifname, ifindex)`, а desired требует новой current rule.

**Components:** существующий `NetworkPolicyExecutor` (Direct Executor
для достижимого postcondition), `ForwardingGateBackend`, отдельный
lower Linux nft Driver, существующие read-only
`compare_payload_nft_scaffold`/`compare_payload_nat` (Direct Calculators).
Новый Engine, Adapter над Adapter, persistent store или event owner
не требуются.

**Responsibilities and interactions:** Executor получает уже
нормализованный NAT desired; сам не выбирает Device/Profile policy.
Закрывает gate, заново подтверждает `DISABLED`, получает authoritative
nft+interface snapshots, классифицирует весь принадлежащий продукту
объём. В маленьком slice допускаются только invariant chains и
полностью распознанные NAT postrouting rules; filter rules и другие
object types требуют другого полноправного classifier. Любая
неизвестная форма = отказ **до** mutation.
Строго одна semantic операция за шаг: exact stale-handle delete
или exact-current-ifindex add, новая полная observation после
команды, проверка ожидаемой перемены единственного rule и
неизменности остальных объектов.

**External facts:** Linux `ip -j link show`, `nft -j list ruleset`,
команды `nft add/delete rule`, managed-netns sysctl. EXP-033/034 —
соответствующие доказательства. Конкурирующие неожиданные изменения
не принимаются как свои, результат fail-closed.

**Traceability / necessity:** R1.R2.R4.R6.R1 требует материализовать
NAT intent, R1.R3.R2/R3 — exact endpoint identity, R4.R3.R2 и
R4.R4/R5 — структурную ограниченную mutation и authoritative
re-observation при failure. Без write Driver нижний NAT desired
не может быть достигнут. Без наблюдаемого whole-scope состояния
невозможно доказать отсутствие несанкционированного удаления.

**Constraints / lifting:** slice не умеет сохранять уже существующий
`payload_forward` ruleset при NAT-only operation; он обязан
отказать при наличии таких объектов. Это **не** признанный first-release
Constraint на пользователя: полная product capability остаётся
обязанностью следующего structural Executor вместе с forward/probe
policy classification и RPDB. Нельзя раскрывать forwarding ради
преодоления данной неполноты.

**Simplification:** нельзя добавлять retry loop, carry-forward
handles, кеш актуального правила, async outcome, second routing
policy, общий nft dispatcher. Только один Direct Executor attempt
с повторными наблюдениями.

**Evidence plan:** unit fake backend для command failure,
barrier loss, unclassified objects, stale/current duplicates,
postcondition mismatch; Linux netns physical add/delete.
Окончательное expert review перед принятием реализации.

**Component-design gate: PASS только для указанной bounded reference
unit. Product-level NAT actuation/re-enabling forwarding остаётся
за отдельной full structural gate.**
