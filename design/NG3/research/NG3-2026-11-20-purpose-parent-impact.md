# VPN-GATE NG3 — Purpose/parent refactor impact assessment

**Status:** non-normative research artifact  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`  
**Promoted tree:** 178-node normative tree in `design/NG3/requirements.md`; the corrected
research copy is retained as the non-normative derivation record

## Главный вывод

После product-holder review большая часть исходных findings уже не является вопросом
«сохранять ли capability». Принятые решения в основном **исправляют продуктовую причинность,
разделяют capability и configuration contract и выносят implementation mechanisms из
requirement tree**.

Поэтому ожидаемый эффект текущего draft:

- **высокий documentation/traceability churn**;
- **низкий functional-code churn** для уже реализованных Release-1 функций;
- selected managed-domain/nft architecture может остаться фактически той же, но больше не
  является нормативной продуктовой семантикой сама по себе;
- historical reviews и experiment result files не переписываются задним числом;
- experiment README при удалении R/C получает только предусмотренный §5.1
  `Historical requirement context` с дословной старой формулировкой и актуальную traceability;
- normative promotion и remap current architecture/configuration/registry documents выполнены
  в этой research-ветке после итогового PASS.

## Принятый draft remap и ожидаемый эффект

| Область | Draft owner | Ожидаемый эффект |
| --- | --- | --- |
| Различимость входящего VPN-трафика | `VPNG0001-R3`; Release-1 config `VPNG0001-R4.R4.R4.R4` | **Medium docs / low code.** Текущая Profile SNAT dataplane может сохраниться; меняется product explanation и trace |
| Общая пользовательская конфигурация | `VPNG0001-R4` | **High docs / zero behavior.** Бывший `VPNG0001-R1.R2.*` config subtree получает новый ancestry; lifecycle operations остаются в `VPNG0005` |
| Ordinary→VPN NAT | capability `VPNG0001-R1.R4.R1`; config `VPNG0001-R4.R4.R6.R1` | **Medium trace / low code.** `use_outbound_nat` больше не служит основанием существования NAT capability |
| Дополнительные ограничения по VPN-ресурсу | `VPNG0001-R1.R4.R2`; per-path `.R1`; config `VPNG0001-R4.R4.R6.R2*` | **High trace / low current code.** Device firewall behavior сохраняется; future per-path selector относится к logical VPN path, не endpoint provenance |
| VPN server/client transport conditions | `VPNG0001-R1.R3.R6.R1/.R2`; config under `VPNG0001-R4.R4.R6` | **Medium trace / low code.** Publication/local integration implementations остаются, ancestry становится onboarding/channel-service oriented |
| Transport endpoint provenance | requirement subtree удалён | **Medium architecture cleanup / low current code.** Endpoint/peer остаётся adapter/lower fact; Release-1 core и явные probe targets от него не зависят |
| Host-routing automation | `VPNG0001-R5`; peaceful `.R1`, detailed Release-1 `.R1.R1`; aggressive `.R2` | **Medium-high trace / low code.** Peaceful helper остаётся Release-1 behavior; aggressive остаётся postponed |
| Availability criterion | `VPNG0003-R3.R6.R3.R1`; reuse `.R1.R1*`; ICMP-only `.C1`; timing `.C2` | **Medium trace / zero behavior.** Probe/config implementation не требует изменения |
| Host-state safety | mechanism-neutral `VPNG0004-R4.R6` | **Very high trace / near-zero runtime.** Managed domain/netns/nft остаются выбранной архитектурой, но должны ссылаться на product invariants/functions, а не на удалённый mechanism requirement |
| Protective mode | `VPNG0004-R5`; Release-1 limitation `.C1` | **Low current code / medium docs.** Capability остаётся postponed; future aggressive-helper composition получает честный safety owner |
| Return-flow stability | `VPNG0003-R4` | **Medium trace / low code.** Existing same-path forwarding behavior сохраняется; causal owner становится multi-path predictability, параллельно baseline/availability preference |
| Priority-only continuity | `VPNG0003-R3.R9` | **Medium trace / zero intended behavior change.** Non-disruptive reorder guarantee сохраняется; route-copy/staging implementation detail удалён из requirement semantics |
| Configuration update | `VPNG0005`, `VPNG0005-R5`, `VPNG0005-R5.R6`; отдельный reload requirement удалён | **Low-medium docs / low current code.** Alpha по-прежнему может применять новую конфигурацию через restart; обязательной операции `reload` нет |

## Архитектура: что меняется по смыслу

### Managed network domain

Самое большое изменение — не runtime, а ownership смысла.

Draft больше не требует отдельный managed network domain, namespace, boundary endpoints или
literal `INPUT/OUTPUT/FORWARD=DROP` как product requirements. Эти механизмы могут остаться
в `design/NG3/architecture.md`, потому что они являются выбранным способом выполнить:

- `VPNG0004-R4.R6` — внешнее host network state не должно обходить policy VPN-GATE;
- forwarding/policy requirements `VPNG0001-R1*` и `VPNG0002-R2*`;
- VPN-path acceptance/binding `VPNG0001-R1.R3*`;
- fail-closed/readiness requirements `VPNG0004-R4*`.

Следствие: при нормативном remap архитектурные секции не нужно «депроектировать» из netns.
Нужно удалить ложную трассировку вида «namespace существует, потому что requirement требует
namespace» и заменить её на «namespace выбран, чтобы реализовать перечисленные observable
invariants».

### Endpoint provenance

EXP-039 и исторические reviews остаются evidence того, что такой lower fact технически можно
получать для конкретной integration. Но current architecture не должна представлять
transport endpoint provenance как самостоятельную product capability.

Future per-path policy должна использовать logical VPN-path identity. Если lower adapter для
её materialization использует peer/endpoint, это внутренний architecture contract.

### Config versus capability

`config-model.md` должен после нормативного remap различать:

1. **что продукт умеет** — functional requirement;
2. **как пользователь выражает это в Release-1 config** — descendants `VPNG0001-R4*`.

Это особенно важно для `+snat`, `use_outbound_nat`, `firewall`,
`publish_vpn_server`, `allow_vpn_client`.

## Current documents requiring remap after normative promotion

Пока `design/NG3/requirements.md` остаётся нормативным snapshot-145 деревом, менять ссылки
в current architecture на provisional draft IDs было бы некорректно: architecture начала бы
ссылаться на несуществующие нормативные requirements. Поэтому в исследовательской ветке
сейчас фиксируется **remap plan**, а не частично ломающий traceability rewrite.

После явного принятия draft и замены нормативного requirements tree в одном согласованном
remap unit нужно проверить как минимум:

| Current document | Основной remap |
| --- | --- |
| `design/NG3/architecture.md` | config subtree; NAT/firewall/publication/client split; helper IDs; availability reuse; removal of provenance requirement; managed-domain `R4.R6.R1*` trace; protective mode |
| `design/NG3/config-model.md` | весь бывший `VPNG0001-R1.R2*` → `VPNG0001-R4*`; functional/config split; helper IDs; availability placement |
| `design/NG3/vpn-onboarding-release1.md` | client transport/control → `VPNG0001-R1.R3.R6.R2` + config contract; remove requirement-level managed-domain provenance assumptions |
| `design/deferrals/NG3-user-facing-policy-grammar.md` | config IDs and per-path firewall wording; historical decisions remain attributable to original baseline |
| `design/NG3/code/python/rou/README.md` | peaceful/aggressive helper trace IDs only; code semantics need not change |
| `design/vpn-gateway-experiments.md` | current selected-coverage descriptions may point to new IDs; historical experiment files retain their original requirement references |

Также необходимо искать все **current** non-historical documents, которые ссылаются на
удалённые `VPNG0001-R1.R3.R5*`, `VPNG0004-R4.R6.R1*`,
`VPNG0004-R4.R7*` или старые helper/config IDs.

## EXP-050 после удаления process-only requirement

`VPNG0007-R7.R7.R1.R1` больше не является актуальным requirement owner для EXP-050.
Технический результат эксперимента сохраняется без ретроактивного редактирования, а current
trace должен использовать `VPNG0001-R1.R3.C1.R1.R2`,
`VPNG0001-R1.R3.C3.R1`, `VPNG0004-R4.R6`,
`VPNG0005-R5.R4`, `VPNG0005-R5.R5`,
`VPNG0005-R5.R6.R2` и `VPNG0005-R5.R6.R3` в зависимости от проверяемого аспекта.

## Historical evidence policy

Не следует массово переписывать исторические review и сохранённые experiment result files:
они описывают requirement IDs и reasoning, существовавшие в момент проведения работы.
Переписывание их фактического содержания задним числом уничтожило бы provenance.

Для experiment dossier действует отдельное правило `PROJECT-CONVENTIONS.md` §5.1: если
ссылающийся R/C удалён, `README.md` получает `## Historical requirement context` с его
дословной исходной compact-form формулировкой, а текущая `## Requirement traceability`
указывает действующие продуктовые обязательства. Такая поясняющая запись не переписывает
технический Result.

Current architecture/registries должны фиксировать, какой новый requirement использует
сохранённое evidence и что именно из старого evidence остаётся применимым после semantic remap.

## Functional code impact accepted so far

Текущий draft сам по себе не требует переписывать working behavior следующих областей:

- Profile source translation:
  `payload_nat_desired.py`, `payload_network_policy_desired.py`,
  `alpha_runtime.py`;
- Device firewall:
  `device_policy.py`, `device_firewall_compiler.py`,
  `device_firewall_policy_compiler.py`, composite nft code;
- publication:
  `host_publication_policy.py`, `linux_host_publication.py`;
- VPN client transport/control:
  `local_integration_policy.py` и local nft owner;
- peaceful helper:
  `release1_host_route_helper.py` и Linux host-routing backend;
- availability:
  availability description/resolver/probe runtime;
- managed-domain implementation:
  `managed_network_domain.py`, controller lifecycle, managed-netns routing/nft owners.

Код меняется только если итоговый trace review обнаружит, что текущая реализация была
необходима только удалённому implementation-specific requirement и не нужна новым product
invariants. Последние два product-holder решения сами по себе не требуют изменения уже
работающего поведения: continuity-гарантия сохранена, а обновление конфигурации в alpha может
по-прежнему выполняться через restart.

## Итоговая оценка

Для уже принятых refactor decisions:

**high documentation/traceability churn, low functional-code churn.**

Самая трудоёмкая операция — remap `architecture.md` и связанных current contracts — выполнена
после нормативного promotion. Remap делался по смыслу, а не глобальной заменой IDs: старые
nodes, split между product capability, configuration contract и architecture mechanism,
получили раздельную трассировку. Финальный stale-reference audit current NG3 documents и
experiment dossiers подтверждает отсутствие удалённых IDs в активной traceability.
