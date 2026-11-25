# NG3 — configuration-driven managed Device presence

**Date:** 2026-11-25  
**Status:** research / requirement-and-architecture re-entry candidate  
**Current basis:** `VPNG-U001-R1.R3.R7*`, A.012, C.004, D.001

## 1. Причина возврата к вопросу

Закрытый `VPNG-U001-R1.R3.R7.R3` сейчас использует самый простой первый контракт:

```text
enabled Device
AND referenced by >= 1 enabled Profile
    -> managed VPN presence demanded
```

Последующее продуктовое уточнение восстановило изначально требуемую более общую модель.
Потребность в managed Device должна определяться не фактом пользовательского трафика, а
конфигурацией Profile и текущим количеством уже присутствующих VPN-интерфейсов.

Traffic-driven wake/sleep исследован отдельно и сохранен как необязательное будущее в
`design/future-possibilities.md`. Он не является текущей Device Manager model.

## 2. Требуемая семантическая форма

Каждый enabled Profile задает ожидаемое число одновременно поддерживаемых путей/интерфейсов
из своих разрешенных Device memberships.

Минимальная семантика значения:

```text
0
positive integer N
all
```

Точное имя и TOML spelling поля в этом research не выбираются.

Отсутствие будущего override должно сохранять нынешнее поведение `all`: все enabled managed
Devices, используемые Profile, остаются востребованными. Это позволяет расширить текущий
контракт без скрытого изменения существующей конфигурации.

`0` означает, что сам этот Profile не создает managed-presence demand. Уже существующий
внешний или независимо востребованный другим Profile путь по-прежнему может использоваться
обычной Profile policy.

## 3. Что именно считается warm satisfaction

Warm-target относится к **присутствию VPN endpoint/interface**, а не к доступности удаленной
сети и не к наличию payload traffic.

Текущий endpoint учитывается для Profile, если он:

- принадлежит enabled Device membership этого Profile;
- свежо наблюден в Private network;
- соответствует разрешенному selector/quota Device;
- может участвовать в обычной C.004 binding projection.

И managed, и externally prepared Device дают одинаковый вклад в фактическое число
присутствующих endpoints. Отличие только в actuation: A.012/D.001 вправе создать или удалить
только explicitly managed Device.

Следствия:

- отрицательный availability outcome не уменьшает warm count сам по себе;
- WireGuard peer/group availability не уменьшает warm count общего `wg0`;
- payload activity, первый пакет и idle timers не участвуют в расчете;
- исчезновение endpoint/interface уменьшает warm count и является основанием пересчитать
  managed demand.

## 4. Config-driven selection при дефиците

Для numeric target `N` Profile сначала учитывает уже присутствующие подходящие endpoints.
Если их меньше `N`, дополнительный managed demand выбирается детерминированно по существующей
baseline hierarchy:

```text
Profile.device_order
    -> Device.expected_interfaces order
        -> configured selector capacity
```

Не следует поднимать все отсутствующие managed Devices одновременно. В одном demand projection
достаточно выбрать минимальный следующий набор кандидатов, чья настроенная capacity способна
закрыть текущий дефицит. После A.012 convergence выполняется новое observation; если выбранный
Device не дал подтвержденного endpoint и дефицит сохранился, следующий cycle может расширить
demand следующим кандидатом.

Known lifecycle problem выбранного кандидата не должен навсегда резервировать теплый slot:
если endpoint не появился, следующий разрешенный managed candidate может стать востребованным.

Это сохраняет bounded start behavior и не превращает нулевое текущее состояние в
`wake all`.

## 5. Избыток и отсутствие ненужного churn

Numeric warm-target задает требуемое количество, а не точную постоянную identity каждого
поднятого Device.

Уже присутствующие endpoints удовлетворяют target. Отсутствующий более предпочтительный
managed Device не должен запускаться только ради замены уже присутствующего подходящего
Device, если warm-target и остальные product obligations уже удовлетворены.

Если присутствующих endpoints стало больше target, managed demand снимается прежде всего с
наименее предпочтительных управляемых memberships, пока это возможно без нарушения demand
других Profiles. Это только desired-presence decision: фактическое удаление остается под
существующим A.012 dependency-release gate и не может само по себе насильно разорвать
принадлежащее продукту текущее payload/return state.

Такой контракт согласуется с уже принятой общей линией: runtime discovery сохраняет
survivors, availability не переписывает structural membership, а ordinary active path не
вытесняется только из-за recovery более предпочтительного ordinary path.

## 6. Shared Device

Lifecycle object принадлежит Device, поэтому per-Profile demand агрегируется перед A.012:

```text
desired_present(Device) =
    OR(Profile demand for Device across all enabled Profiles)
```

Profile может перестать нуждаться в Device, но это не разрешает его остановку, пока другой
Profile продолжает его требовать.

Externally managed Device никогда не становится A.012 subject даже тогда, когда его endpoint
участвует в warm-count другого Profile.

## 7. `all`

`all` является отдельной простой семантикой, а не числом, вычисленным из текущего runtime.

Для Profile с `all` каждый enabled explicitly managed Device membership создает presence
demand независимо от текущего количества остальных endpoints. Это точно сохраняет нынешний
R7.R3 behavior и не зависит от того, сколько внешних интерфейсов уже присутствует.

## 8. Structurally impossible numeric target

Numeric `N` больше суммарной настроенной selector capacity enabled Device memberships
Profile не может быть достигнут даже в идеальном runtime и должен быть configuration error.

Временный runtime shortfall при допустимом `N` не является configuration error: это
наблюдаемое состояние, которое создает managed demand и/или diagnostic, если доступные
managed candidates исчерпаны.

## 9. Архитектурная граница

Нижний lifecycle менять не требуется:

```text
configuration + fresh endpoint presence
        |
ManagedDeviceDemandCalculator candidate
        |
desired managed Device set
        |
A.012 ManagedDeviceManager
        |
D.001 managed VPN Adapter
        |
fresh C.004 observation/binding
        |
payload / availability policy
```

Calculator является pure Machinery candidate. Он не запускает VPN и не владеет lifecycle.
A.012 остается единственным owner фактического managed base presence.

### Почему current presence нельзя брать из availability

A.007/D.002 evidence отвечает на другой вопрос: пригоден ли уже существующий path/peer/group
для удаленной сети. Использование этого evidence для managed presence превратило бы
availability в скрытую membership/lifecycle policy и нарушило действующий контракт, где
availability только понижает effective priority.

### Почему нужен pre-A.012 observation

A.012 сейчас выполняется до первой fresh C.004 binding projection. Numeric warm-target должен
видеть уже существующие внешние/managed endpoints до решения, кого дополнительно запускать.

Достаточная ordering candidate:

```text
Private network ready
    -> fresh C.004 endpoint observation (presence only)
    -> pure warm-demand projection
    -> A.012/D.001 convergence
    -> fresh C.004 observation + normal binding projection
    -> dependent payload/probe policy
```

Первое observation не должно commit payload binding state: оно является только свежим входом
в Calculator. Второе observation остается обычным authoritative binding postcondition после
возможной lifecycle mutation.

Синхронного цикла здесь нет: C.004 не зависит от A.012 и ничего не provision.

## 10. Requirement impact

Текущее Statement `VPNG-U001-R1.R3.R7.R3` стало слишком узким после восстановления
продуктовой потребности и должно быть пересмотрено.

Кандидат верхнего смысла:

> Базовая автоматизация жизненного цикла управляемого Device должна выводить требуемое
> присутствие VPN-экземпляра из конфигурационно заданной потребности enabled Profiles в
> поддерживаемом количестве текущих VPN-интерфейсов, агрегируя потребность всех Profiles;
> пользовательский трафик, первый пакет и время простоя не являются источниками этой
> потребности.

R7 parent, R7.R1 и R7.R2 не меняют смысла. До принятия новой decomposition R7.R3 должен
вернуться в `open`; текущий A.012 contribution к нему становится `partial`.

## 11. Configuration surface still intentionally open

Research фиксирует семантику `0 | N | all`, но не выбирает имя TOML field.

Имя должно описывать **количество поддерживаемых присутствующих путей**, а не «число резервов»:
иначе значение `0` становится двусмысленным (ноль резервных при одном обязательном active
или действительно ни одного warm path).

Это отдельная компактная configuration-format decision после принятия behavior semantics.

## 12. Implementation consequences after acceptance

Current implementation gaps are expected and localized:

1. A.002/current config needs normalized Profile warm-target.
2. A pure demand Calculator needs fresh endpoint-presence input and deterministic projection.
3. A.012 must consume the calculated desired set instead of
   `CurrentConfig.structural.active_device_ids`.
4. Alpha ordering needs one pre-A.012 fresh endpoint observation and the existing post-A.012
   fresh binding observation.
5. Individual managed Device failure must be representable without immediately preventing
   another candidate from satisfying the same Profile warm-target.
6. A.008 should eventually expose target/shortfall or at least the truthful resulting managed
   desired state; exact presentation is a separate diagnostic review.

No packet queue, traffic observer, idle timer or wake-trigger mechanism is needed.


## Product decision update — 2026-11-25: reserve is not warm

Later projectholder clarification refined §§2–8 without invalidating the configuration-driven
direction:

- `warm_paths` is the canonical current Profile field;
- its target counts only ordinary memberships;
- `:reserve` capacity does not enter the warm target and a present reserve path never reduces
  regular deficit;
- current external and managed ordinary paths both satisfy warm presence;
- A.012 first attempts/converges ordinary demand while retaining any already-needed reserve,
  then re-observes presence;
- only a still-present regular deficit after that phase may create a temporary reserve
  exception;
- regular demand remains active while reserve is present, so ordinary recovery automatically
  removes the reason for reserve without a separate lifecycle failback state machine;
- reserve release still waits for the existing dependency-release safety contract.

This update supersedes the earlier wording that treated every eligible membership uniformly
for warm counting. The preserved earlier text remains useful for the general config-driven
selection/aggregation conclusions. The accepted refined model is reviewed in
`design/reviews/NG3-2026-11-25-warm-paths-reserve-model-review.md`.
