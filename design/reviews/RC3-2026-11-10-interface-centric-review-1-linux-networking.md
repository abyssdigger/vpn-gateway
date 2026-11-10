# RC3 — interface-centric architecture review 1

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** Linux networking / routing / Netlink reviewer  
**Область:** RC3 architecture + normative terminology after EXP-009  
**Вердикт:** CHANGES REQUIRED

## Общая оценка

Переход от transport-peer model к concrete-interface model обоснован EXP-009 и делает
routing contract существенно проще. Direct `dev <interface>` routes согласуются с
проверенным OpenConnect behavior; отделение WireGuard `AllowedIPs` от Linux FIB также
корректно проведено.

Основная модель выглядит целостно:

- exact / prefix+ / ordered exact list;
- active predicate по expected `local_address`;
- direct proto-202 routes без transport next-hop;
- deterministic metrics;
- snapshot-decides / Netlink-wakes;
- partial multiple-interface availability как normal state.

Однако в нормативных документах остались несколько фрагментов прежней модели.

## Finding 1 — stale `prefix%` remains normative

Architecture продолжает ссылаться на `prefix%` как на существующий selector:

- §2.6 — IPv6 guard namespace;
- §9.2 — INPUT guard;
- §9.3 — FORWARD ingress guard.

При этом §4/§13/§15 уже объявляют `%` invalid syntax.

Это прямое нормативное противоречие. Все safety requirements должны быть выражены только
через три поддерживаемые формы:

- exact;
- prefix+;
- ordered exact list.

**Severity:** HIGH — conflicting safety/config contract.

## Finding 2 — stale `peers=[]` config-lint semantics

§7.2/§7.3 все еще требуют NOTE для `peers=[]` и называют `peers` исключением из
set-like duplicate normalization.

После удаления key `peers` из closed schema это невозможно: key должен быть unknown,
а managed profile с таким key должен fail config validation.

**Severity:** HIGH — contradictory config validator requirements.

## Finding 3 — terminology still exposes obsolete peer ambiguity

`terms-and-definitions.md` сохраняет:

- `absent` как отсутствие concrete/peer binding;
- `ambiguous` как selector или peer association ambiguity.

Новая architecture сознательно не имеет normal selector ambiguity и не имеет peer
association domain object.

Если эти строки оставить, они создают второй источник domain semantics.

Рекомендация:

- `absent` либо определить только как отсутствие candidate/active binding, либо удалить;
- `ambiguous` удалить как нормативный RC3 state; слово можно использовать только в
  обычном русском смысле при описании malformed inventory/config.

**Severity:** MEDIUM.

## Проверенные положительные свойства

1. Prefix active ordering не зависит от event arrival order.
2. Explicit list сохраняет priority slots при отсутствующих interfaces.
3. `name+ifindex` остается concrete identity.
4. Candidate с неверным local address остается guard-blocked.
5. Route metric не объявлен health detector.
6. Transport peer/handshake не участвуют в active binding truth.
7. Profile FAIL при zero paths отделен от whole-pass observability failure.

## Required disposition

После устранения Findings 1–3 архитектуру следует повторно проверить уже с позиции
firewall/security reviewer, поскольку изменение selector multiplicity непосредственно
меняет количество exact INPUT/FORWARD/NAT blocks.
