# Ответ проекта на RC3 interface-centric review 2

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-interface-centric-review-2-security-firewall.md`

## Finding 1 — runtime IPv6 revalidation

**ACCEPTED WITH STRONGER OPERATIONAL SEMANTICS.**

§2.6 и §8.4 теперь требуют global/per-interface IPv6 prerequisite verification на каждом
полном reconciliation pass до построения allowing policy.

При violation daemon:

- не пытается исправлять admin-owned IPv6 sysctl;
- не продолжает ordinary allowing apply;
- best-effort выключает IPv4 forwarding;
- применяет isolation filter, если это возможно;
- остается IPv4 `ISOLATED` с high-severity diagnostic;
- не возвращается автоматически в ACTIVE без исправления host prerequisites и restart.

Отдельно сохранено предупреждение: IPv4 ISOLATED не является IPv6 protection.

## Finding 2 — candidate-only no-barrier wording

**ACCEPTED.**

Candidate-only transition считается IPv4 policy-neutral только после successful IPv6
prerequisite verification для current guard namespace.

## Result

Firewall/NAT transition contract теперь учитывает появление новых matching interfaces во
время RUN не только как IPv4 selector event, но и как изменение множества interfaces,
подлежащих mandatory IPv6 prerequisite check.
