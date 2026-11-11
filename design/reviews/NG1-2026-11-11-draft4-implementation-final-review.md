# NG1 Draft 4 + implementation — финальное ревью

## A. Draft 4 — C1 fix корректен

**§5.4A** теперь явно: *«Materialization of NEW-flow policy is explicit, not omission-based»*, с парой counterexamples (10.20.0.0/16 restricted vs 10.0.0.0/8 broad на общем `oc-main`). **Инвариант 61** закрепляет правило, **62** — операционное последствие multipath rebuild.

**D2** — §12 трёх-member example (три normal + shadow ECMP + blackhole). **D1** — CHANGELOG entry на месте.

**Концепт (§8.1) согласован с архитектурой:** пример с restricted/broad на shared device показан во всех трёх местах (concept, architecture, test).

## B. Код — соответствует Draft 4

Проверил по коду и тестам:

| Требование | Где реализовано | Покрыто тестом |
|---|---|---|
| explicit NEW verdict for every (Profile, Device, prefix, direction) | `firewall_intent.py::compile_new_flow_intents` | `test_firewall_intent.py` (4 кейса) |
| longest-prefix-first ordering, C1 counterexample | `-prefixlen` в sort key | `test_device_to_host_specific_drop_precedes_broad_accept` |
| filter-by-Device-then-longest-prefix для Device→host classification | `dispatch.py::classify_device_to_host_profile` | `test_device_to_host_filters_by_device_before_longest_prefix` |
| RPDB dispatch sorted prefixlen DESC, network ASC | `dispatch.py::compile_profile_dispatch` | `test_longest_prefix_then_network_address` |
| persistent shadow fallback (single direct, multi ECMP) | `route_intent.py::compile_profile_route_intents` | `test_route_intent.py` (8 кейсов) |
| UNAVAILABLE removes only normal, keeps fallback membership | `route_intent.py` | `test_unavailable_removes_only_normal_route` |
| terminal blackhole ниже fallback | `UNAVAILABLE_METRIC=65535 < BLACKHOLE_METRIC=65536` | `test_tail_order` + `test_all_unavailable_is_fallback_plus_blackhole` |
| normal metric space резервирует tail | `metrics.py::compile_profile_metric_layout` | `test_max_normal_capacity_fits` + `test_normal_capacity_cannot_consume_unavailable_metric` |
| stable normal slot preserved, removed not reusable until verified commit | `traffic_state.py` | `test_removed_slot_not_reused_before_verified_commit` |
| survivor order preserved, over-quota promotion in kernel-snapshot order | `device_engine.py::reconcile_devices` | `test_survivors_not_reordered_by_new_snapshot_order` |
| same-name/new-ifindex as fresh candidate | `ifindex` in `InterfaceIdentity` | `test_same_name_new_ifindex_is_fresh_candidate` |
| disabled device consumes no metric range | `compile_profile_metric_layout` skips disabled | `test_disabled_device_in_order_consumes_no_metric_space` |
| duplicate destinations forbidden globally | `_validate_global_destinations` | `test_duplicate_destination_across_profiles_rejected` |
| overlap same prefixlen forbidden, different allowed | `_validate_global_destinations` (dict-like) | `test_overlapping_different_prefixes_are_allowed` |

## C. Малые замечания (не блокеры)

### C1. `compile_new_flow_intents` — device-scoped intent, materializer expansion

Intent возвращает device_name, не interface identity. Materializer должен расширить до `-o <each bound interface of device>`. Это правильно (intent стабилен, не зависит от binding snapshot), но **не задокументировано**.

Рекомендация: одна строка в docstring и/или в README:
> `NewFlowRuleIntent` is device-scoped. Kernel materialization expands to every currently-bound interface of that Device; rules for absent/unbound interfaces are simply not emitted.

### C2. `classify_device_to_host_profile` — мёртвый публичный API

Экспортируется в `__init__.py`, покрыт двумя тестами, но **нигде не вызывается** в runtime path. Firewall работает по чистому prefix-match, а не через classification.

Не проблема — это разумный функционал для будущего status/diagnostics. Но стоит одну строку в docstring:
> Exported for future diagnostics/status use. Kernel firewall materialization uses prefix-match ordering directly, not runtime calls to this function.

### C3. `firewall_intent.py` — `assert profile.direction is not None`

```python
assert profile.direction is not None
```

Config validator гарантирует это для parsed configs, но `ActiveConfig` можно создать вручную (как в тестах). `AssertionError` — не самое чистое сообщение. Стоит `ValueError(f"enabled Profile {profile.name!r} has no direction")`.

### C4. Тест с 3 правилами одинакового направления

`test_device_to_host_specific_drop_precedes_broad_accept` покрывает 2 правила с разной prefixlen. Хорошо бы добавить тест с 3 overlapping правилами (например, 10.20.0.0/16 DROP, 10.0.0.0/8 ACCEPT, 0.0.0.0/0 DROP — mixed) для проверки полного sort. Not critical; 2-rule тест уже ловит основную ошибку.

### C5. `traffic_state.py` — "over-quota promotion to bound" многоходовка

Механизм (survivor keeps slot, new candidate appends, wait-for-slot until verified removal commit) работает и покрыт `test_slot_reusable_after_verified_removal_commit`. Но архитектурно этот многошаговый state transition (survivor disappears → verified commit → freed slot → next reconcile assigns to promoted candidate → verified commit) не прокомментирован в одном месте. Не баг, но заметка для maintenance.

### C6. `route_intent.py` — метрика нормалных routes для одно-bound без `waiting_for_slot`

`test_single_bound_member_still_has_shadow_fallback` — один bound, назначен metric 1, shadow fallback есть. Это правильно (persistent shadow даже для одного). ✓

Малый нюанс: если единственный bound оказался UNAVAILABLE, `normal_routes` пусто, `fallback_routes` содержит одного члена → одна direct route at 65535. Это правильное поведение. ✓

## D. Структурная проверка

- 62 инварианта, нумерация 1..62 без дыр. ✓
- Ссылки `§N.M` разрешаются. ✓
- CHANGELOG: Draft 4 entry на первом месте, EXP-013 closure упомянут. ✓
- Experiments: EXP-013 PASS в журнале + attempt-1 (harness false negative, честно задокументирован). ✓
- Rou-config не упоминает публикации/envelope TOML — соответствует "deferred". ✓
- Все `test_*` следуют unittest pattern. ✓

**27/27 rootless tests PASS** (per CHANGELOG) соответствуют. Не проверял прогон локально, но по коду тесты должны проходить.

## E. Verdict

**Draft 4 — production implementation baseline принят.**

Все замечания из предыдущего ревью (C1, D1, D2 + operational multipath) закрыты с конкретной реализацией и тестами. Пять малых заметок выше — не блокеры, могут быть закрыты одним terminology/clarification commit'ом параллельно с kernel materialization slice.
