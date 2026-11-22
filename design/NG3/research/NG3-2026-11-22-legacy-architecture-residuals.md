# NG3 — исследование остаточного содержимого legacy architecture.md

**Дата:** 2026-11-22  
**Исходный полный отчет:** `38607e247f39a87a361a4541e3dace6585c8d52a:design/NG3/architecture.md`  
**Текущая архитектура:** `design/NG3/structured-architecture.md`  
**Цель:** определить, существует ли в бывшем плоском отчете текущая архитектурная семантика,
которая не представлена в structured architecture и поэтому мешает окончательно вывести
`architecture.md` из нормативного обращения.

## Результат

**Нормативного текущего архитектурного решения, существующего только в
`design/NG3/architecture.md`, не найдено.**

Плоский отчет можно заменить tombstone-файлом. Историческое тело остается доступным через
Git history; переписывать исторические review/evidence, которые ссылались на него на своем
baseline, не требуется.

Один остаток имел самостоятельную архитектурную ценность: явный перечень deliberately
omitted generic machinery. Он перенесен в
`structured-architecture.md` §2.9.4 как следствие `VPNG-D001-R1.R1.R1`.

## Метод

Старый отчет был разобран по top-level и существенным nested sections. Для каждого блока
проверялось одно из четырех состояний:

1. **transferred** — текущая архитектурная семантика уже есть в structured architecture;
2. **owned elsewhere** — остаток является implementation/platform/evidence contract и имеет
   действующий источник вне architecture;
3. **historical/explanatory** — материал полезен только для понимания прошлого design path и
   не является current normative architecture;
4. **missing current architecture** — материал остается архитектурно необходимым и должен
   быть перенесен до retirement.

Категория 4 после анализа пуста.

## Disposition по бывшим разделам

| Бывший блок | Disposition | Текущий owner / основание |
| --- | --- | --- |
| executable reference evidence table | owned elsewhere | `implementation-traceability.md`, code/tests, experiment/review artifacts, `evidence-index.md` |
| §1 scope, managed-domain boundary, onboarding/systemd lifecycle | transferred | Spaces + A.001/B.001/C.007/C.009/D/E specs; `vpn-onboarding-release1.md` |
| §2 design scenarios S1–S6 | historical/explanatory | requirements и tests/evidence покрывают свойства; сами сценарные формулировки не являются architecture contract |
| §3 summary, VPN binding, configuration boundary | transferred | A.002/A.003/C.004, VPN external ends, configuration model |
| §4 PayloadTrafficManager | transferred | A.004 |
| §5 PayloadPolicyCalculator и return affinity semantics | transferred | A.005 + Private-network return-affinity artifact/interactions under C.001 |
| §6 AvailabilityPriorityCalculator | transferred | A.006 |
| §7 AvailabilityProbeAgent | transferred | A.007 |
| §8 ActiveProbeDriver / probe policy details | transferred + owned elsewhere | C.008/C.001/C.003; exact Linux mechanics remain code/EXP/review evidence |
| §9 NetworkPolicyAdapter/layout | transferred | C.001/C.002 |
| exact table/RPDB/metric pools, nft owner marker, iproute/nft JSON forms | owned elsewhere | `linux_policy_platform.py`, lower Drivers/Readers, EXP-028/029/031 and focused tests/reviews |
| §10 NetworkPolicyEnforcer / barriers / structural convergence | transferred | C.003/C.005/C.006 |
| exact command ordering, internal result enums, raw JSON/argv observations and CI run IDs | owned elsewhere | implementation + tests + EXP/review artifacts; not stable component API |
| §11 event contracts | transferred | Space interactions and A.004/A.007 InfoEvent contracts |
| §12 startup/shutdown/recovery | transferred | A.001 + B/C/E lifecycle components |
| §13 RuntimeStatusAgent + language boundary | transferred | A.008/A.009 and §2.9.3 |
| §14 requirement coverage table | transferred | §2.10 current coverage index |
| §15 deliberately omitted machinery | **transferred in this cleanup** | new §2.9.4 |
| §16 implementation freedoms/future extensions | transferred/superseded | config model, postponed requirements, A.001/A.009/E.002, onboarding docs |
| §17 requirements-driven architecture principle | transferred | requirement trace rules, §2.10 and `VPNG-D001-R1.R1.*` |

## Остаток 1 — historical design scenarios

S1–S6 были полезны как ранний способ проверить проектирование:

- explicitly managed payload;
- preferred path degradation;
- local presence != sufficient evidence;
- late stale observation;
- partial network mutation failure;
- partial cleanup failure.

Их точные текстовые сценарии не перенесены в structured architecture. Это сознательное
решение: structured architecture фиксирует обязанности, состояния и interactions, а не
дублирует scenario catalogue.

Смысл этих сценариев уже представлен requirements и executable/evidence boundaries:
policy scope, generation/context rejection, fresh observation, fail-closed convergence и
bounded cleanup. Поэтому отсутствие S1–S6 как отдельного раздела не создает architecture gap.

Если позднее понадобится единый reusable scenario catalogue, это должен быть отдельный
verification/research artifact, а не возврат сценариев в authoritative architecture.

## Остаток 2 — конкретные Linux platform facts

Плоский отчет содержал точные current-target значения и representation facts, например:

- high routing-table pools и RPDB priority pools;
- route protocol markers 201/202;
- concrete nft namespace/owner marker;
- metric constants;
- iproute2 JSON representation details;
- exact mutation argv/phase observations.

Structured C.002 намеренно оставляет эти значения injected/evidence-gated platform facts,
а не semantic API. Это правильная граница: верхняя архитектура требует disjoint resource
classes, precedence, deterministic allocation и ownership proof, но не делает конкретное
число частью component contract.

Конкретные значения уже существуют в executable platform contract, tests и соответствующих
EXP/review artifacts. Перенос чисел обратно в structured architecture создал бы второй
источник truth и ухудшил бы заменяемость lower realization.

**Disposition:** не переносить.

## Остаток 3 — подробные implementation algorithms и evidence observations

Старый отчет накапливал точные пошаговые алгоритмы, internal result names, CI run IDs,
raw JSON forms и конкретные Linux commands по мере реализации Enforcer/Drivers.

Structured architecture сохраняет требуемые архитектурные инварианты:

- fresh observe -> bounded actuation -> fresh verification;
- separate pure-priority vs structural transitions;
- verified ForwardingGate;
- exact-before-release;
- no stale-plan replay;
- restrictive failure postcondition;
- lower technical boundaries do not own semantic desired state.

Остальная детализация является implementation/evidence. Она уже проверяется code/tests и
зафиксирована в reviews/experiments. Сохранение ее в authoritative architecture дублировало
бы исполняемый контракт и снова создало бы stale flat-report problem.

**Disposition:** не переносить.

## Остаток 4 — deliberately omitted machinery

В отличие от Linux implementation details, этот блок выражал настоящее project-wide
архитектурное решение: не создавать generic/global machinery без accepted need.

Чтобы при retirement не потерять это решение, оно перенесено в structured architecture
§2.9.4. Перенос сохраняет отрицательную границу design, но не делает перечисленные механизмы
навсегда запрещенными: новый Requirement/Constraint может обосновать их появление.

## Исторические ссылки

Исторические review/research/evidence не переписываются. Их ссылка
`design/NG3/architecture.md` относится к тому tree/commit baseline, на котором запись была
создана.

После retirement текущий path является tombstone. Для чтения последнего полного тела перед
удалением используется:

`38607e247f39a87a361a4541e3dace6585c8d52a:design/NG3/architecture.md`

Это сохраняет историю без поддержания второго current architecture document.

## Итог

После переноса §15 и классификации остальных residuals:

- current architecture source: только `structured-architecture.md`;
- current implementation trace: `implementation-traceability.md`;
- concrete Linux facts: code/tests + experiments/reviews;
- historical flat architecture: Git history;
- `architecture.md`: только tombstone.

Дополнительной requirement decomposition для retirement не требуется: исследование не
обнаружило новой продуктовой семантики или capability gap.
