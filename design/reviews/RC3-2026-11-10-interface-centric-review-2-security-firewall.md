# RC3 — interface-centric architecture review 2

**Дата:** 2026-11-10  
**Роль внешнего эксперта:** network security / firewall orchestration reviewer  
**Область:** fail-closed behavior, IPv4/IPv6 boundary, transition ordering  
**Вердикт:** CHANGES REQUIRED

## Общая оценка

После review 1 selector grammar и route model согласованы. Multi-interface firewall
materialization в целом сохраняет прежний fail-closed contract:

- wildcard используется только в deny guard;
- allowing INPUT/FORWARD/NAT используют exact active names;
- active-set change идет через isolation barrier;
- blackhole остается config-derived;
- NAT проверяется до route materialization.

Обнаружена одна существенная safety gap и один связанный contract gap.

## Finding 1 — runtime IPv6 prerequisites are not explicitly revalidated

§2.6 требует `disable_ipv6=1` для всех существующих interfaces guard namespace и
говорит, что prerequisites должны сохраняться во время RUN.

Но §8.4 ordinary reconciliation после `list_interfaces()` сразу строит snapshot и
классифицирует policy transition. Повторная проверка:

- global IPv6 forwarding/default state;
- per-interface `disable_ipv6` для newly appeared matching interface

не включена в нормативную последовательность.

Это особенно важно после новой `prefix+` semantics: появление второго, третьего и т.д.
matching interface теперь штатно, а не ambiguity/failure.

**Required behavior:** каждый reconciliation pass после fresh interface inventory и до
materialization allowing policy обязан проверить IPv6 prerequisites для всего current
guard namespace. Violation during RUN должна запрещать продолжение ordinary apply и
переводить daemon в fail-closed isolation path; daemon не должен молча исправлять
admin-owned IPv6 sysctls.

**Severity:** HIGH.

## Finding 2 — “candidate-only change requires no barrier” is too broad

§8.4 утверждает, что candidate-only change без active-set change не требует heavy barrier.

Для IPv4 policy это верно. Но новый matching candidate, не имеющий expected
`local_address`, все равно входит в guard namespace и поэтому расширяет множество
существующих interfaces, для которых §2.6 требует `disable_ipv6=1`.

Следовательно, candidate-only transition можно считать policy-neutral только **после**
успешной IPv6 prerequisite verification.

**Severity:** MEDIUM; derived from Finding 1.

## Проверенные положительные свойства

1. Exact blocks precede prefix deny guard, поэтому active interface не блокируется guard.
2. Matching-but-inactive candidate не получает ACCEPT/NAT/routes.
3. Explicit-list namespace overlap запрещен config validator.
4. Active-set transition disables IPv4 forwarding before NAT/filter/route mutation.
5. Prefix metric renumbering occurs only with active-set change and therefore is inside the
   protective transition path.
6. Partial availability does not weaken protected-destination REJECT or blackhole.
7. Transport peer health cannot accidentally open policy because it is no longer an input.

## Required disposition

Добавить runtime IPv6 revalidation и явно ограничить candidate-only no-barrier rule
условием successful prerequisite check. После этого нужен отдельный config/domain review:
ordered explicit list и prefix runtime metrics имеют разные stability semantics и должны
быть без противоречий отражены validator/model/status contracts.
