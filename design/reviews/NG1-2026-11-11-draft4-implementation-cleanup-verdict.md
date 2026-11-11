# Cleanup review — все пять применены корректно

## Проверка каждого

**C1 (firewall_intent docstring)** ✓

> Kernel materialization expands this intent to every currently bound interface of the referenced Device. No rule is emitted for absent, over-quota or otherwise unbound interfaces.

Точно закрывает вопрос «как intent → kernel rules».

**C2 (dispatch docstring)** ✓

> Exported for diagnostics/status and policy explanation. Kernel firewall materialization uses the equivalent ordered prefix-match rules directly; packets are not classified by calling this function at runtime.

Правильная формулировка — «эквивалентные правила напрямую, а не вызов функции на пакет».

**C3 (ValueError вместо assert)** ✓

```python
if profile.direction is None:
    raise ValueError(f"enabled Profile {profile.name!r} has no direction")
```

Плюс тест `test_enabled_profile_without_direction_is_rejected` с проверкой message. ✓

**C4 (three-level overlap test)** ✓

Проверил сортировку вручную. Для DEVICE_TO_HOST правил с `device_name=oc-main`:

- `specific`: /16, OUTBOUND → DROP. Sort key: (`-16`, `10.20.0.0`) → первый
- `broad`: /8, BIDIR → ACCEPT. (`-8`, `10.0.0.0`) → второй
- `default`: /0, OUTBOUND → DROP. (`0`, `0.0.0.0`) → третий

Наблюдаемое поведение:

- `10.20.5.5 → host`: matches /16 DROP first → dropped ✓
- `10.5.5.5 → host`: falls through /16, matches /8 ACCEPT → accepted ✓
- `1.1.1.1 → host`: falls through /16 and /8, matches /0 DROP → dropped ✓

Все три уровня проверяются. Именно тот case, который 2-rule тест не ловил.

**C5 (traffic_state multi-step docstring)** ✓

> Promotion is intentionally multi-step: disappearance is first projected while the old metric remains reserved; verified removal is committed; only a later reconcile may assign the freed slot...

Правильно — описывает двухкоммитную последовательность (verified removal → later reconcile → verified assignment).

**Additional (stale EXP-013 comment)** ✓

> UNAVAILABLE fallback is projected separately by route_intent.py; this function owns only stable normal-tier metric allocation.

Чистая граница ownership. Убрали «pending EXP-013» — не вводит в заблуждение через месяц.

## Проверка на возможные побочные эффекты

**Сортировка в `compile_new_flow_intents`:**

```python
key = (direction.value, device_name, -prefixlen, int(network_address), profile_name)
```

- `profile_name` tie-break фактически никогда не сработает, потому что `_validate_global_destinations` в config запрещает identical prefix у разных Profiles. Но defensive tie-break безвреден.
- Overlap at different prefixlen разрешён (`test_overlapping_different_prefixes_are_allowed`), и именно для этого случая работает `-prefixlen`.
- `/0` в C4 тесте конфликтует по overlap с `/8` и `/16`, но config validation это допускает — совпадает с реальным production case.

**`test_three_level_overlap_has_complete_longest_prefix_order` bypass config validation:**

Собирается через прямой `ActiveConfig({...}, {...})` в обход `parse_active_config`. Это okay — тест проекции, а не config parser. Если бы хотели проверить «config с такими тремя профилями проходит валидацию», добавили бы отдельный тест. Но и без него ясно: `10.20.0.0/16`, `10.0.0.0/8`, `0.0.0.0/0` — попарно разные prefixlen, overlap at different lengths разрешён → пройдёт.

## Verdict

Все шесть изменений (5 review items + 1 stale cleanup) применены корректно. Никаких побочных эффектов, семантика Draft 4 не меняется. Тестовый suite должен остаться зелёным, плюс один новый тест (`test_three_level_overlap_has_complete_longest_prefix_order`) и один дополнительный (`test_enabled_profile_without_direction_is_rejected`).

**Baseline остаётся NG1 Draft 4.** Maintenance commit на месте. Следующий этап без изменений — kernel materialization slice, начиная с live EnvironmentSnapshot collection и routing-table/RPDB allocation.
