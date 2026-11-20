# VPN-GATE NG3 — unresolved Purpose/parent questions

**Status:** non-normative research artifact  
**Branch:** `ng3-research-20261120-requirement-purpose-parent-consistency-30m`  
**Baseline:** main snapshot 145 `623a688e4080de56e5ac14675ffca028c3865d18`  
**Current research draft:** requirement remap through branch HEAD

Этот список содержит только решения, которые **остались нерешёнными после**
product-holder dispositions, записанных в
`NG3-2026-11-20-requirement-refactor-decisions.md`, и после их применения к
`NG3-2026-11-20-purpose-parent-corrected-requirements-draft.md`.

Исходный audit содержал 20 findings: 2 safe corrections и 18 вопросов, требовавших human
decision. В текущем draft 16 findings уже имеют disposition; остаются четыре.

## 1. Return affinity for remote-initiated flow

**Affected:** `VPNG0002-R2.R6`.

Текущий Statement требует, чтобы ответный трафик remote-initiated flow возвращался через тот
же VPN-канал, через который был принят исходный трафик.

Поведение выглядит необходимым для корректности и устойчивости established flow, но
immediate parent `VPNG0002-R2` описывает **явно заданную пользователем**
traffic/path/direction policy. Пользователь не задаёт same-ingress affinity как отдельную
policy, поэтому ancestry остаётся причинно нечестной.

Нужно выбрать causal owner:

- forwarding correctness / сохранение семантики уже принятого flow;
- flow stability;
- либо отдельный requirement, если это самостоятельная продуктовая гарантия.

Существующая реализация/evidence не является основанием для выбора parent: она подтверждает
реализуемость и текущее поведение, но не продуктовую причинность.

## 2. Priority-only make-before-break continuity

**Affected:** `VPNG0004-R4.R3.R1`.

Parent `VPNG0004-R4.R3` требует безопасного policy transition: промежуточное состояние не
должно разрешать forwarding, запрещённый старой или новой policy. Это допускает временно
более restrictive состояние.

Child дополнительно обещает не терять разрешённые paths при priority-only перестановке.
Это уже availability/continuity guarantee, а не следствие safety parent.

Нужно решить, принадлежит ли гарантия:

- path-preference/availability tree `VPNG0003`;
- отдельной continuity capability;
- либо safety/lifecycle tree после явного product decision, что non-disruptive priority
  transition является обязательной частью этой гарантии.

## 3. Reload

**Affected:** `VPNG0005-R5.R6.R4`.

Lifecycle ancestry гарантирует start/stop/restart. Текущий reload-node появляется только
условно: deployment interface должен иметь безопасную reload semantics **если** он такую
операцию предоставляет.

Нужно решить, является ли reload:

- самостоятельной обязательной product capability;
- либо контрактом deployment integration: интерфейс не должен рекламировать reload, пока
  безопасная semantics не определена.

Первый release уже допускает отсутствие reload; текущая alpha её не реализует, поэтому
решение в основном влияет на requirement/interface placement, а не на готовый runtime.

## 4. Second VPN lifecycle evidence gate

**Affected:** `VPNG0007-R7.R7.R1.R1`.

Parent `VPNG0007-R7.R7.R1` запрещает начинать зависимую integration development до PASS
базового applicability evidence. Child требует **после этого PASS** отдельный lifecycle /
aggressive-configuration experiment до принятия bounded-VPN lifecycle semantics.

Это следующий evidence gate, а не уточнение Statement текущего parent.

Нужно выбрать placement:

- sibling gate под `VPNG0007-R7.R7`;
- evidence child конкретного VPN lifecycle requirement;
- либо ненормативное development-process правило, если оно не является продуктовым или
  requirement-level обязательством.

## Уже закрытые adjacent findings

Следующие вопросы больше не являются unresolved и не должны снова появляться в decision
queue:

- Profile source identity / `+snat` поднят в самостоятельную capability;
- Device NAT/firewall и VPN transport/control capabilities отделены от config placement;
- transport endpoint provenance удалён из requirement tree;
- peaceful/aggressive host-routing helpers получили положительный общий parent;
- user-selected availability criterion подтверждён;
- Device-default/Profile-override перенесён из-под ICMP-only constraint;
- timing/hysteresis limitation вынесен в sibling constraint `VPNG0003-R3.R6.R3.R1.C2`;
- host-state safety сделан mechanism-neutral, managed network domain и literal DROP остаются
  architecture/evidence;
- protective mode поднят непосредственно под `VPNG0004`.

До решения четырёх вопросов выше нормативный remap `design/NG3/requirements.md` остаётся
неполным.
