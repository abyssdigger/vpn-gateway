# NG3 — requirement/component gate: EXP-036 prefix-scoped stateful return

**Дата:** 2026-11-16  
**Цикл:** `ng3-design-cycle-20261116-forward-policy-evidence-40m`  
**Review unit:** Linux/nft evidence for stateful return primitive paired with
the already proven outbound NEW primitive.

## Requirements

**Implements:** `VPNG0002-R2.R1.R2`, `VPNG0002-R2.R3.R3`,
`VPNG0001-R1.R3.R2`, `VPNG0001-R1.R3.R3`,
`VPNG0004-R4.R1`, `VPNG0004-R4.R2`, `VPNG0004-R4.R3.R2`.

**Constrained by:** `VPNG0002-R2.R3.C1`,
`VPNG0001-R1.R2.R4.R6.C1`.

Полные ancestry и closure повторно проверены в текущем NG3 tree.
Requirement `VPNG0002-R2.R3.R3` прямо разрешает stateful обслуживание
return traffic уже допустимых flows независимо от стороны инициатора;
оно не разрешает unsolicited reverse NEW. `R2.R1.R2` фиксирует remote
prefix semantics, поэтому return primitive не должен терять prefix scope.

**Requirement gate: PASS** для технического proof; user-visible semantics
не меняются.

## Component design

**Scenario:** Profile outbound разрешил NEW host->VPN flow к remote prefix.
Reply должен пройти через тот же current concrete path и host boundary,
но stale same-name interface generation или reply source вне current
remote prefix не должны получить разрешение.

**Components:** только экспериментальный harness, существующий nft lower
boundary и Linux packet path. Никакой production Executor/Manager не
добавляется.

**Proposed primitive:** reverse rule:
`ct state established,related + exact current iif/oif + ip saddr prefix + accept`.
Prefix обязателен для сохранения current Profile remote scope при retained
conntrack across structural policy changes. Handle/counter — observation only.

**Interactions / external facts:** outbound NEW rule из EXP-035 creates
conntrack; обратный ICMP packet получает established state. nft JSON,
rule counters and ping outcome подтверждаются независимо. Same-name
replacement использует новый ifindex; для исключения старого tuple state
используется новая host source identity.

**Necessity:** без return primitive успешный NEW request не означает
usable bidirectional flow. Слишком общий established rule может пережить
semantic narrowing через retained conntrack, поэтому необходим prefix scope.

**Constraint lifting:** эксперимент не снимает Release 1 multi-path inbound
constraint и не вводит новый product limit. Если primitive не работает,
блокируется только текущий lower filter design.

**Simplification:** одна outbound pair, один alternate remote source,
никакой firewall AST/flow registry/retry/persistent conntrack ownership.

**Evidence plan:** privileged GitHub netns: successful scoped ping; unsolicited
reverse NEW denied; separately permitted outbound to outside-prefix address
gets request through but reply denied by scoped return; same-name replacement
shows stale return rule fail-closed, then fresh return rule restores flow.
Record actual nft JSON.

**Component-design gate: PASS** for EXP-036 only.
