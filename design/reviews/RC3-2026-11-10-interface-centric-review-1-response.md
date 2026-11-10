# Ответ проекта на RC3 interface-centric review 1

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-interface-centric-review-1-linux-networking.md`

## Disposition

### Finding 1 — stale `prefix%`

**ACCEPTED.**

Исправлены §2.6, §9.2 и §9.3. Safety contract теперь перечисляет только exact,
`prefix+` и explicit ordered list. `prefix%` остается только там, где явно указан как
unsupported legacy syntax.

### Finding 2 — stale `peers=[]`

**ACCEPTED.**

Удалены NOTE и duplicate-semantics старого `peers`. §7 теперь согласован с closed
schema: transport peer list отсутствует, explicit interface list имеет order semantics и
запрещает duplicates.

### Finding 3 — obsolete peer ambiguity terminology

**ACCEPTED.**

`absent` переопределен только через candidate/active concrete binding. Нормативная
строка `ambiguous` удалена из RC3 glossary: normal selector multiplicity не является
ambiguity, peer association больше не существует.

## Result

Все три замечания внесены в нормативные документы. Следующий независимый проход должен
проверять firewall/NAT safety при нескольких simultaneous active interfaces.
