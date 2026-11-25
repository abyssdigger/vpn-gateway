# NG3 — traffic-driven presence для управляемого Device

**Статус:** исследование, не нормативный контракт  
**Дата:** 2026-11-25  
**Основание:** решение projectholder продолжить проектирование Device Manager после закрытия
базового структурно-востребованного жизненного цикла и отдельно исследовать подключение /
отключение VPN по фактической потребности.

## 1. Исходная граница

Текущий закрытый контракт `VPNG-U001-R1.R3.R7*` уже задает один законченный режим:

```text
явно управляемый Device
AND Device enabled
AND Device referenced by >= 1 enabled Profile
    -> базовая VPN-реализация требуется
```

A.012 `ManagedDeviceManager` владеет фактическим наличием базовой VPN-реализации,
D.001 подтверждает ее поколение и состояние, а C.004 отдельно подтверждает появившийся
`PathBinding`. При исчезновении структурной потребности A.012 удаляет базовую реализацию
только после подтвержденного снятия зависимого product-owned состояния.

Это уже полноценный вариант «по потребности», где потребность структурная. Запуск по
фактическому трафику и остановка после простоя R7.R3 намеренно не вводит.

Следующая функция поэтому не является исправлением A.012 или незакрытым остатком R7. Она
добавляет **другой источник presence demand** и требует отдельного продуктового решения.

## 2. Полезное разделение понятий

Для дальнейшего проектирования следует различать:

1. **structural eligibility** — Device включен и допустим для одного или нескольких enabled
   Profiles;
2. **presence demand** — требуется ли сейчас фактическая базовая VPN-реализация Device;
3. **VPN realization** — подтвержденное A.012/D.001 наличие конкретного поколения;
4. **path readiness** — подтвержденный C.004 binding и, где применимо, дополнительная
   integration/availability readiness;
5. **payload activity** — фактически наблюдаемый разрешенный полезный трафик, а не VPN control,
   keepalive или probe traffic.

Текущий режим фактически задает:

```text
structural eligibility -> presence demand
```

Traffic-driven режим может изменить только второй переход. Он не должен превращать packet
observation в альтернативного владельца VPN lifecycle и не должен считать сам факт запуска
доказательством готовности пути.

## 3. Что можно переиспользовать без нового lifecycle implementation

После принятия нового presence demand нижняя последовательность уже существует:

```text
presence demand appears
    -> A.012 requests D.001 present
    -> desired generation
    -> confirmed base realization
    -> fresh C.004 binding
    -> dependent policy/readiness

presence demand disappears
    -> stop new dependent use
    -> confirm product-owned dependencies released
    -> A.012 permits D.001 absent
    -> confirmed absence
```

Следовательно, traffic-driven режим не требует второго Device Manager, второго D.001 или
отдельного способа start/stop/restart. Новая архитектурная ответственность нужна только там,
где требуется наблюдать payload activity и формировать/удерживать presence demand во времени.

До принятия продуктовой семантики преждевременно фиксировать имя или тип такого компонента.
Если он появится, естественная граница — наблюдение traffic/current intent и публикация
presence-demand projection; A.012 остается единственным владельцем фактической базовой
реализации.

## 4. Первый исходящий пакет

Если VPN отсутствует, первый пакет, обнаруживший потребность, уже существует раньше, чем
появится подтвержденный path. Здесь есть два существенно разных продукта.

### Вариант A — trigger-and-drop

Пакет является только trigger:

```text
packet observed
    -> presence demand
    -> packet follows existing fail-closed zero-path behavior
    -> subsequent traffic can use VPN after readiness
```

Плюсы:

- не появляется packet queue/reinjection subsystem;
- semantics одинаково честна для TCP и UDP: первый пакет **может быть потерян**;
- lifecycle остается асинхронным относительно конкретного payload packet.

Минус — приложение должно пережить такую потерю; это нельзя скрывать под предположением,
что TCP всегда повторит передачу.

### Вариант B — bounded hold-and-forward

Продукт удерживает triggering payload до готовности VPN либо timeout, затем выпускает или
явно отбрасывает его.

Это уже новая data-plane обязанность: нужны ограничение памяти/очереди, timeout, backpressure,
порядок пакетов, cleanup при failed activation и доказательство отсутствия bypass разрешающей
policy. Такой вариант нельзя получить добавлением таймера в A.012.

**Выбор A/B является product decision.**

## 5. Inbound и bidirectional

Отсутствующий VPN не способен получить удаленный payload, который сам бы его разбудил.
Поэтому обычный payload-trigger естественно существует только со стороны, где трафик виден
до создания VPN.

Для inbound-only Profile возможны только отдельные решения, например:

- не разрешать traffic-driven sleep и сохранять structural presence;
- иметь внешний explicit wake/control trigger;
- наблюдать protocol-specific transport attempt до VPN realization и использовать его как
  wake event.

Последний вариант уже зависит от конкретной VPN-технологии, меняет attack surface и не
является обычным payload demand.

Для bidirectional Profile outbound traffic может разбудить VPN, но пока Device спит,
неожиданный remote-initiated inbound exchange будет недоступен. Это должно быть частью
явного пользовательского контракта, а не скрытым следствием implementation.

**Минимальная допустимая область первого traffic-driven режима — отдельное product decision;
ее нельзя автоматически вывести из существующего `direction`.**

## 6. Несколько Devices одного Profile

Текущий structural режим может держать присутствующими все явно управляемые Devices,
которые входят в active structural demand. После перехода к traffic demand отсутствие path
само становится нормальным состоянием, поэтому при первом trigger необходимо решить, какой
Device или набор Devices разбудить.

Семантически различаются как минимум:

1. **wake all eligible managed Devices** — ближе всего к нынешней готовности к failover, но
   дает меньшую экономию;
2. **wake highest-baseline candidate** — экономнее, но backup сначала отсутствует и failover
   включает дополнительную lifecycle latency;
3. **prefer already-present eligible Device** — может быстрее обслужить пакет и сэкономить
   запуск, но превращает lifecycle state в новый модификатор установленного baseline preference.

Текущая availability policy не отвечает на этот вопрос: она упорядочивает уже существующие
пути и не является политикой стоимости запуска отсутствующего VPN.

**Нельзя молча трактовать `device_order` или reserve как готовую lifecycle-demand policy.**

## 7. Device, используемый несколькими Profiles

Фактическая VPN-реализация принадлежит Device, а не одному Profile. Поэтому независимо от
того, где возникает trigger, withdrawal demand безопасен только после агрегации всех
актуальных потребителей Device.

Минимальный инвариант:

```text
Device presence demand =
    OR(all currently applicable demand sources for this Device)
```

Один Profile не должен остановить общий Device, пока другой Profile продолжает требовать его
наличие. Если в будущем разные Profile получат разные traffic/structural policies, эта
агрегация становится обязательной явной частью семантики.

## 8. Что считается activity для idle shutdown

VPN-level traffic непригоден как простой критерий idle:

- WireGuard keepalive может идти без payload need;
- peer/group/A.007 probes являются служебным evidence traffic;
- lifecycle/status/control operations также не означают пользовательскую полезную нагрузку.

Наиболее чистый кандидат — activity только от **разрешенного product payload**, уже
классифицированного как принадлежащий Profile/Device path.

Но остается отдельный вопрос established flows. Два разных контракта:

- **packet-idle:** после timeout без payload packets Device можно остановить, даже если
  conntrack/session-like state еще существует;
- **flow-pinned:** наличие применимого established flow удерживает presence независимо от
  текущей тишины пакетов.

Первый проще и имеет конечный timeout, но может намеренно оборвать долго молчащий обмен.
Второй лучше сохраняет flow continuity, но требует надежного bounded наблюдения flow state,
правил для UDP и решения, когда stale flow перестает удерживать Device.

Существующий return-affinity contract для remote-initiated exchange не определяет этот
lifecycle choice автоматически. Поэтому выбор packet-idle / flow-pinned является отдельным
product decision.

## 9. Race и hysteresis

Даже после выбора основных semantics traffic demand не должен напрямую вызывать
`start/stop` на каждый пакет.

Нужны как минимум логические состояния:

```text
ABSENT
STARTING
PRESENT
IDLE_PENDING
STOPPING
PROBLEM
```

Это не обязательно новые публичные состояния A.012: часть может принадлежать будущему
presence-demand owner. Важны свойства:

- повторные triggers во время STARTING коалесцируются;
- новый payload trigger во время IDLE_PENDING отменяет withdrawal;
- после withdrawal базовая реализация все равно удаляется только по существующему
  dependency-safe A.012 path;
- failed start не становится confirmation;
- failed stop не становится absence;
- retry/backoff не должен превращаться в неограниченный durable command journal.

Точные таймеры и retry policy следует определять после product decisions, а не до них.

## 10. Пользовательская гранулярность

Фактический lifecycle объект — Device, но demand возникает из использования Device
Profiles. Поэтому возможны разные config surfaces:

- Device-level mode для всех его memberships;
- Profile↔Device membership-level override;
- смешанная модель с Device default + membership override.

Для первого расширения Device-level mode проще, но он не позволяет одному Profile держать
общий Device always-on, а другому использовать тот же Device on-demand с собственной
политикой. Выбор гранулярности должен следовать реальному пользовательскому сценарию, а не
удобству parser.

До решения в normative config **не вводятся** поля вроде
`presence = "traffic"` или `idle_timeout`. Они допустимы только как иллюстрации candidate
representation.

## 11. Технические вопросы после продуктового решения

После выбора semantics потребуются дешевые целевые проверки, а не новый общий VPN prototype.

### Для любого traffic-driven режима

Нужно доказать, что при нулевом current path triggering outbound payload можно наблюдать в
контролируемой VPN-GATE области, не разрешая ему обойти fail-closed policy и не создавая
ложный PathBinding.

### Если выбран trigger-and-drop

Достаточно подтвердить:

- trigger виден до drop;
- один burst не создает шторм lifecycle requests;
- последующий payload после confirmed readiness проходит обычным путем.

### Если выбран hold-and-forward

Нужен отдельный эксперимент packet queue/reinjection с bounded memory/time, ordering,
cleanup и policy revalidation после wake. Без такого evidence архитектуру выбирать нельзя.

### Если выбран flow-pinned idle

Нужен отдельный источник current flow truth и доказательство его semantics для TCP/UDP;
нельзя просто использовать счетчик интерфейса или существование conntrack entry без
принятого срока жизни.

## 12. Требуемые решения projectholder перед нормативной ветвью

Исследование оставляет четыре минимальных product gates.

### D1. Судьба первого outbound packet

- **A:** trigger-and-drop допустим;
- **B:** продукт обязан bounded hold-and-forward.

### D2. Direction scope первого режима

- **A:** traffic-driven presence сначала только для outbound-capable использования, а
  inbound-only сохраняет structural presence;
- **B:** требуется также отдельный remote/external wake semantics до первой реализации.

### D3. Несколько eligible Devices

- **A:** первый demand поднимает все eligible managed Devices;
- **B:** только highest-baseline отсутствующий candidate;
- **C:** уже-present eligible Device может быть предпочтен отсутствующему baseline leader.

Это решение должно отдельно описать, когда поднимается backup после failure.

### D4. Idle criterion

- **A:** packet-idle timeout достаточен;
- **B:** applicable established flow удерживает Device, а timeout применяется только при
  отсутствии таких flows.

После D1–D4 можно решать гранулярность config и формировать Requirement candidate. До этого
код A.012 менять не требуется.

## 13. Предварительный архитектурный вывод

Traffic-driven presence совместима с текущим Device Manager без второго lifecycle owner.

Наиболее устойчивое разделение выглядит так:

```text
normalized intent + current Profile/Device applicability
                |
payload activity observation / timers
                |
        presence-demand projection
                |
              A.012
                |
              D.001
                |
       confirmed VPN realization
                |
              C.004
                |
        current payload paths
```

Стрелка `presence-demand projection -> A.012` является кандидатной будущей границей, а не
уже принятым API. Она нужна только если D1–D4 делают traffic-demand самостоятельной
семантической обязанностью.

Главный вывод исследования: нижний lifecycle уже достаточен. Следующий риск находится не в
start/stop implementation, а в пользовательской семантике того, **когда** Device должен
считаться востребованным и что продукт обещает пакету/потоку на границе sleep/wake.
