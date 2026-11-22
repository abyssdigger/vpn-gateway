# NG3 — исследование postponed per-path ограничений

**Дата:** 2026-11-22  
**Scope:** `VPNG-U001-R1.R4.R2.R1`, `VPNG-U001-R4.R4.R6.R2.R5`  
**Статус результата:** research complete; требования остаются `postponed`

## 1. Вывод

Postponement сейчас упирается **не в Linux/nft возможность фильтровать отдельный current
path**. Нижняя Device-firewall реализация уже строит отдельные current chains по
`LogicalPathId` и concrete endpoint.

Нерешенная product boundary — **долгоживущая пользовательская идентичность одного пути** и
ее композиция с Device-wide restriction.

Текущий internal `LogicalPathId(device_id, selector_index, slot_index)` нельзя напрямую
делать user-facing selector:

- `selector_index` зависит от положения selector в текущей конфигурации;
- `slot_index` стабилен внутри committed binding lifecycle, но не является durable
  идентичностью конкретного внешнего VPN-пути;
- runtime стартует с `DeviceBindingState.empty()`;
- initial prefix/quota slots заполняются в порядке fresh interface observation;
- после освобождения slot туда может быть детерминированно promoted другой endpoint.

Следовательно, запись вроде «ограничить `selector 1 / slot 0`» была бы стабильной
идентичностью **ячейки текущего binding**, но не гарантировала бы, что после restart или
replacement это тот же пользовательски различимый VPN-путь, ради которого введено
ограничение.

Runtime `ifname`, `ifindex`, transport endpoint или peer также нельзя превращать в
user-facing identity: это прямо запрещает `VPNG-U001-R4.R4.R6.R2.R5`.

## 2. Что уже готово

### 2.1. Внутренняя logical-path модель

Текущий binding contract уже отделяет:

```text
LogicalPathId
    = Device ID + selector position + stable quota slot

PathBinding
    = LogicalPathId -> current InterfaceIdentity(ifname, ifindex)
```

Endpoint replacement не обязан менять identity slot в пределах его binding lifecycle.
Profile ordering, availability и status уже используют `LogicalPathId`, а не concrete
endpoint.

Это правильная runtime boundary и ее не требуется заменять transport provenance.

### 2.2. Device firewall уже current-path-aware

`compile_device_firewall_policies()` сегодня:

1. получает current `RoutePriorityPathRoute` с `LogicalPathId`;
2. разрешает каждый path в exact current `InterfaceIdentity`;
3. создает отдельные direction chains для каждого current path;
4. не встраивает Device ID или runtime ifname в internal nft object identity.

То есть после появления normalized per-path restriction lower compiler уже имеет точку,
где можно выбрать отличающуюся effective policy для одного logical path.

Новый kernel discriminator для самой фильтрации не требуется: current ingress/egress
endpoint pair уже является lower realization текущего path binding.

## 3. Почему текущего slot ordinal недостаточно для user contract

Тестируемая binding semantics специально разрешает:

```text
prefix selector quota=2
fresh endpoints: vpns02, vpns00, vpns01

slot 0 <- vpns02
slot 1 <- vpns00
vpns01  <- waiting
```

При следующем процессе initial state снова пуст. Fresh observation может иметь другой порядок.
Кроме того, после disappearance другой waiting endpoint может занять освободившийся slot.

Это корректно для runtime logical slot: policy/availability продолжают работать с одной
ячейкой, а не с устаревшим interface object. Но это недостаточно для пользовательского
утверждения:

```text
"вот этому конкретному различимому VPN-пути разрешить меньше"
```

если внешний смысл пути не закреплен независимо от очередности обнаружения.

Поэтому re-entry не должен подменять `VPNG-U001-R4.R4.R6.R2.R5` синтаксисом, который
публикует internal ordinal.

## 4. Рекомендуемый product contract для re-entry

Ввести **configured path key** — стабильный opaque user ID, scoped внутри Device.

Концептуально:

```text
DevicePathRef
    = Device ID + configured path key

configured path key
    -> accepted binding discriminator/slot contract
    -> current internal LogicalPathId
    -> current concrete endpoint
```

Свойства:

1. key задается пользователем и не выводится из `ifname`, `ifindex`, peer или transport
   endpoint;
2. key уникален внутри Device;
3. per-path restriction ссылается на key;
4. binding replacement concrete endpoint не меняет key;
5. отсутствие current binding означает отсутствие usable path, а не перенос restriction на
   соседний path;
6. restriction автоматически следует за новым confirmed binding того же configured path key;
7. один и тот же Device/path restriction применяется независимо от Profile, который в данный
   момент использует этот path.

Точное TOML spelling в этом research **не выбирается**. Сначала должен быть принят semantic
contract; затем отдельный config-format decision может выбрать, например, nested path tables
или другую каноническую форму.

## 5. Что делать с prefix selector quota > 1

Здесь находится реальный оставшийся design choice.

### Вариант A — адресуемы только однозначные selector slots

Configured path key разрешается привязать только к selector с capacity 1. Prefix family с
quota > 1 остается группой взаимозаменяемых runtime slots и не получает индивидуальных
user-facing path restrictions.

Плюсы:

- минимальная модель;
- не нужен durable sub-discriminator внутри prefix family;
- exact/prefix selector остается discovery contract.

Минус: часть logical paths остается неадресуемой индивидуально.

### Вариант B — каждый quota slot получает configured path key

Например, prefix selector quota 3 объявляет три stable path keys.

Само по себе это **недостаточно**. Текущий admission order после process restart может
привязать другой concrete endpoint к тому же slot/key. Для корректности нужен дополнительный
stable binding discriminator, который отличает members prefix family независимо от fresh
observation order.

Этот discriminator может быть integration-specific lower fact, но его user-facing identity
все равно остается configured path key. Transport peer/endpoint допустим как Adapter/binding
evidence, но не как public selector.

### Рекомендация

Для первого re-entry выбрать **A** как минимально достаточную capability, если product
принимает, что individually restricted path должен быть individually distinguishable уже в
Device binding contract.

Вариант B следует добавлять только вместе с отдельным requirement/design для durable
sub-binding discriminator. Не следует сохранять binding-state journal только ради того,
чтобы случайный первый observation order выглядел как stable product identity.

## 6. Семантика ограничения

Per-path policy является **дополнительным ограничением**, не override Device firewall:

```text
effective permission(path)
    = Profile permission
    AND Device-wide restriction
    AND optional path restriction
```

Она не может:

- разрешить то, что запрещено Profile;
- разрешить то, что запрещено Device-wide firewall;
- менять Profile membership/direction;
- создавать path при отсутствии binding.

Это следует из parent `VPNG-U001-R1.R4.R2`: Device/path policy может только сужать общую
traffic policy.

## 7. Lower firewall composition

Текущая Device chain использует first-match rules, где `allow` lower'ится в `return`, а
explicit policy заканчивается terminal DROP. Поэтому per-path policy нельзя безопасно
реализовать простым «заменить Device rules для этого path»: это создало бы возможность
расширения.

Нормальная lower composition должна сохранить два независимых restrictive gates:

```text
path-specific gate
    AND
Device-wide gate
```

Практически это может быть wrapper/nested-chain composition либо эквивалентный заранее
скомпилированный intersection. Текущий lower model запрещает два параллельных owned jumps с
одинаковой ingress/egress pair, поэтому materialization потребует небольшого расширения C.001
Device-firewall structure/compiler/observer, но не нового Linux feasibility experiment:
jump/return/terminal-drop primitives уже являются production machinery.

## 8. Требуемая decomposition перед снятием postponement

Для `VPNG-U001-R1.R4.R2.R1` нужны как минимум descendants, фиксирующие:

1. user-selected path restriction может только сужать Device/Profile permission;
2. restriction связывается с stable configured path identity, а не endpoint;
3. missing/replaced binding не переносит restriction на другой path;
4. effective path policy является conjunction Device-wide + path-specific restrictions.

Для `VPNG-U001-R4.R4.R6.R2.R5` нужны descendants, фиксирующие:

1. canonical user reference = Device + configured path key;
2. key uniqueness/validation и dangling-reference rejection;
3. связь key с binding discriminator;
4. Release/config update behavior при удалении/переименовании path key;
5. отдельно выбранную границу поддержки multi-slot prefix selectors.

После этого оба postponed узла можно вернуть в active frontier. Сейчас прямой
`postponed -> closed` был бы преждевременным: архитектура не содержит configured path key
и conjunctive per-path firewall composition.

## 9. Что не требуется исследовать заново

На текущем evidence нет причины открывать новые эксперименты для:

- nft interface-pair discrimination;
- same-name/new-ifindex generation semantics;
- отдельной current chain на logical path;
- Device-wide ordered firewall actions;
- transport endpoint provenance как самостоятельной product capability.

Эти механизмы уже покрыты текущей production architecture/evidence. Следующий шаг — product
decomposition и выбор path-addressability contract, а не новый Linux probe.

## 10. Re-entry recommendation

**Оставить оба требования `postponed` до принятия path-addressability decision.**

Рекомендуемый следующий design block:

1. принять configured path key как user identity;
2. решить, что первая версия individually addressable path ограничивается capacity-1
   selectors либо добавить durable sub-binding discriminator для quota > 1;
3. разложить два postponed requirements на перечисленные descendants;
4. после acceptance перевести их из `postponed` в текущий frontier и проектировать
   normalized intent / C.001 conjunction.
