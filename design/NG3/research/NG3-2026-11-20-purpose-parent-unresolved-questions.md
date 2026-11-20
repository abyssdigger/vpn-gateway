# VPN-GATE NG3 — unresolved Purpose/parent questions

**Status:** non-normative research artifact  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`

Этот список содержит только решения, которые нельзя честно вывести из immediate-parent
Statements без нового human decision. Вопрос не означает, что capability плохая или что
текущая реализация неверна; он означает, что текущая requirement ancestry не доказывает,
почему capability обязательна именно как child данного parent.

## 1. Profile source identity / NAT

**Affected:** `VPNG0001-R1.R2.R4.R4.R4` и его descendants.

Нужно решить, откуда берется продуктовая обязанность предоставлять Profile `+snat`.
Текущий parent описывает обязательные поля Profile и запрет на leakage Linux details, но не
обещает управление source identity.

Варианты:

1. подтвердить отдельное внешнее/product-holder основание и дать capability собственную
   причинную ветку;
2. привязать ее к уже существующему более высокому forwarding/policy requirement, если
   project holder считает source identity частью управляемого forwarding contract;
3. удалить capability из normative tree, если это была только архитектурная возможность.

## 2. Device transport capabilities

**Affected:** `VPNG0001-R1.R2.R4.R6.R1`, `.R2`, `.R3`, `.R4`.

`VPNG0001-R1.R2.R4.R6` честно отвечает на вопрос **где** хранить Device-scoped policy,
если такая policy существует. Но он не доказывает, почему продукт обязан предоставить:

- outbound masquerade;
- Device firewall;
- VPN-server publication;
- client-side transport/control admission.

Нужно отдельно подтвердить продуктовую необходимость каждой capability либо явно записать,
что они являются независимыми externally requested children другого requirement.

Особенно `.R4` причинно тяготеет к onboarding/integration branch, а не к общей
Device-policy placement branch.

## 3. Transport endpoint provenance

**Affected:** `VPNG0001-R1.R3.R5`.

Нужно решить, является ли endpoint provenance самостоятельной поддерживаемой capability или
только optional lower fact для будущих функций. Current Purpose перечисляет availability и
endpoint-scoped firewall convenience — то есть объясняет consumers, а не immediate parent
«принять/идентифицировать/использовать VPN channel».

## 4. Peaceful host-routing helper

**Affected:** `VPNG0001-R2.R2`.

Project history явно содержит решение «Release 1 must provide peaceful helper», но current
parent `VPNG0001-R2` только **ограничивает влияние** явно включенных host-side функций и не
требует существования helper.

Нужно зафиксировать, от какого product need происходит обязанность предоставить helper:
например, от требования пользоваться VPN-GATE без ручной сборки host routes — если именно
это является accepted product promise.

## 5. Aggressive host-routing helper

**Affected:** `VPNG0001-R2.R3` и postponed descendants.

Нужно подтвердить, существует ли отдельная продуктовая обязанность когда-либо предоставить
authoritative/aggressive helper. Текущий parent не требует такой функции, а только
ограничивает её влияние, если она существует.

Если это future option, честнее держать ее вне mandatory requirement tree до явного
project-holder decision либо дать ей отдельное основание.

## 6. Return affinity for remote-initiated flow

**Affected:** `VPNG0002-R2.R6`.

Same-ingress reply behavior выглядит полезным и текущая реализация имеет сильное evidence,
но immediate parent `VPNG0002-R2` — про **явно заданную пользователем policy**
traffic/path/direction. Пользователь не задаёт same-ingress affinity как отдельную policy.

Нужно выбрать настоящий causal parent: forwarding correctness, flow stability, explicit
policy preservation или отдельный requirement.

## 7. User-selected availability criterion

**Affected:** `VPNG0003-R3.R6.R3.R1` и descendants.

Parent требует evidence, которое действительно наблюдает существенную пригодность path.
Из этого не следует единственный способ — дать пользователю механизм+target.

Нужно подтвердить, что user-selectable criterion является именно product promise, а не
выбранной конфигурационной архитектурой. Если promise подтвержден, ему нужен parent,
который уже содержит различие пользовательских критериев/сценариев.

## 8. Host-network isolation versus safety tree

**Affected:** `VPNG0004-R4.R6`.

Purpose этого узла почти буквально отвечает `VPNG0001-R2` (не менять несвязанный host
network state), но находится под `VPNG0004-R4` (не допускать unsafe forwarding при
ошибке/неопределенности).

Нужно решить, является ли non-interference частью safety promise или отдельной веткой
primary routing requirement. После решения потребуется reparent/remap всего subtree.

## 9. Managed network domain as Requirement or Architecture

**Affected:** `VPNG0004-R4.R6.R1`.

Даже если isolation/non-interference requirement сохраняется, отдельный managed network
domain — один конкретный способ его реализации. Current architecture сама пишет, что
namespace является architecture choice и может быть заменен другим механизмом.

Нужно решить, защищает ли requirement **абстрактную isolated owned network domain boundary**
как обязательный product/development invariant, или требование должно остаться
mechanism-neutral, а domain/netns — только architecture.

## 10. Literal default DROP hooks

**Affected:** `VPNG0004-R4.R6.R1.R5`.

Нужно решить, что нормативно требуется:

- поведенческий default-deny для managed local/forwarding surfaces; или
- буквально Linux `INPUT=DROP`, `OUTPUT=DROP`, `FORWARD=DROP`.

Первый вариант является requirement-level поведением; второй выглядит выбранной nft/Linux
реализацией и должен остаться в architecture/evidence.

## 11. Administrative payload containment

**Affected:** `VPNG0004-R4.R7`.

Fail-closed core safety не требует публичной enter/leave containment operation. Нужна
отдельная human decision: это самостоятельная operator capability или только возможная
future composition для aggressive helper/recovery.

## 12. Reload

**Affected:** `VPNG0005-R5.R6.R4`.

Current lifecycle requirement гарантирует start/stop/restart, а reload появляется только
условно «если deployment interface объявляет reload». Нужно решить, является ли это
продуктовой обязанностью VPN-GATE или контрактом конкретной deployment integration.

Если reload не является product capability, requirement лучше заменить architecture/interface
rule: нельзя рекламировать reload, пока она не имеет безопасной semantics.

## 13. Second VPN lifecycle evidence gate

**Affected:** `VPNG0007-R7.R7.R1.R1`.

Parent требует не начинать зависимую integration development до PASS basic applicability.
Child требует **после PASS** отдельный lifecycle experiment. Это следующий gate, а не
уточнение предыдущего Statement.

Нужно решить placement: sibling под `VPNG0007-R7.R7`, evidence child соответствующей
VPN lifecycle requirement или ненормативное development-process правило.
