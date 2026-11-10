# Ответ проекта на external optimization review: local_address

**Дата:** 2026-11-10  
**Review:** `RC3-2026-11-10-external-optimization-review-local-address.md`

## Disposition

### Finding 1 — local_address duplicates network

**ACCEPTED.**

После EXP-009 отдельный exact local host address не участвует ни в route derivation, ни в
peer association, ни в NAT/ACL. Единственная оставшаяся функция — qualification
candidate -> active binding.

Эта функция переносится на уже обязательный `profile.network`:

```text
active(candidate) =
    exists local IPv4 on candidate where address ∈ profile.network
```

### Finding 2 — exact host address unnecessarily narrows transports

**ACCEPTED.**

VPN-GATE больше не требует один одинаковый exact local IPv4 на всех concrete interfaces
профиля. Конкретная host-address assignment остается ответственностью transport config.

Это не означает, что interface считается active только по имени: наличие local IPv4 из
объявленной transport network по-прежнему обязательно.

### Finding 3 — retain network

**ACCEPTED.**

`network` сохраняется как самостоятельная нормативная сущность:

- transport address space;
- `VPNG-RESERVED` protection;
- protected-route overlap validation;
- candidate -> active applicability predicate.

## Additional clarification

Applicability использует только host IPv4 membership. Prefix length, показанная kernel для
конкретного tunnel address, не обязана совпадать с `profile.network`; P2P /32 local
representation допустима.

Address add/delete, меняющий membership в `profile.network`, остается policy-changing
active-binding transition.

Legacy `local_address` становится unknown profile key closed schema.

## Result

Optimization accepted. RC3 config/domain model больше не содержит отдельный
`local_address`.
