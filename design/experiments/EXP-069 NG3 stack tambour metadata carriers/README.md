# EXP-069 — сохранность metadata на границе stack → managed tambour

## Статус

COMPLETE — **PASS**. См. `EXP-069-result-20261119.md`.

## Требования

Эксперимент дает физическое evidence для уже принятых требований:

- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`.

Он не вводит новую продуктовую семантику и не меняет выбранную архитектуру сам по себе.

## Контекст и вопрос

Текущая Release-1 архитектура использует выбранный EXP-064 carrier: фиксированные
host-boundary behavior lanes. EXP-063 уже доказал, что transient `skb/meta mark`,
выставленный в managed stack, не сохраняется как usable tag после перехода через
cross-netns veth.

EXP-069 не повторяет EXP-063 как открытую гипотезу. `meta mark` включен только как
regression control. Эксперимент проверяет более широкое пространство доступной Linux
metadata и отвечает на два отдельных вопроса:

1. Может ли какой-либо локальный, не передаваемый on-wire carrier сохранить выбранный
   stack-side behavior class через существующую границу `stack -> managed tambour`
   без дополнительной veth-пары?
2. Если carrier сохраняется, может ли managed tambour надежно потребить его до обычной
   host-owned обработки, сохранить только внутренний NAT class, выполнить gateway SNAT
   и не затронуть соседний unmarked flow?

Технический PASS эксперимента не означает автоматическую замену EXP-064. Любой найденный
carrier требует отдельного post-result review и архитектурного решения.

## Стенд

Стенд полностью disposable и создается внутри privileged Linux GitHub Actions runner.

```text
REMOTE namespace
    payload source 10.69.0.2
    |
    | veth
    v
STACK namespace
    analogue: managed stack
    |
    | existing cross-netns veth under test
    v
HOST namespace
    early owned nft hooks = managed tambour
    later route/NAT path = ordinary host processing
    |
    | veth
    v
LAN namespace
    TCP observer 192.0.2.2
```

Адреса transit links принадлежат только disposable stand:

```text
REMOTE <-> STACK   198.18.69.0/30
STACK  <-> HOST    198.18.70.0/30
HOST   <-> LAN     192.0.2.0/30
```

Никакие host-global routes/firewall rules runner не изменяются: все сетевые мутации
происходят внутри создаваемых namespaces. Cleanup удаляет namespaces даже при FAIL.

### Граница tambour

Отдельный namespace для tambour намеренно **не** создается. Проверяемая production-shaped
граница — это cross-netns veth из managed stack в host namespace. Managed tambour в этом
опыте — ранние явно owned nft hooks на принимающем конце этой границы. Они должны
прочитать carrier и, если это возможно, снять его до обычного host route lookup.

## Preflight

Harness выполняет последовательность из operational runbook:

1. **Diagnose:** проверяет root, наличие `ip`, `nft`, `python3`, печатает kernel/ip/nft versions.
2. **Restore/create:** создает только уникальные disposable namespaces/veth/routes для опыта.
3. **Verify:** запускает baseline TCP flow `REMOTE -> STACK -> HOST -> LAN` без metadata;
   LAN обязан увидеть исходный source `10.69.0.2`.
4. Только после baseline запускаются metadata mutations.

## Кандидаты

Основной simultaneous pass пытается активировать все поддержанные runner'ом кандидаты:

| Candidate | Класс | Внешняя семантика | Примечание |
| --- | --- | --- | --- |
| `meta mark` | packet-local | нет | известный отрицательный regression control из EXP-063 |
| `meta priority` | packet-local | нет on-wire | может иметь локальную QoS/tc семантику |
| `meta pkttype` | packet-local derived | нет on-wire | переопределяет skb packet type; семантически сомнительный, но проверяется как крайний кандидат |
| `meta secmark` | packet-local | нет on-wire | может иметь локальную security/LSM семантику |
| `meta nftrace` | packet-local | нет | diagnostic metadata |
| `ct mark` | conntrack-local | нет | conntrack namespace-local state |
| `ct label` | conntrack-local | нет | conntrack namespace-local state |
| `ct secmark` | conntrack-local | нет | conntrack/security state |
| `ct zone` | conntrack-domain | нет | особый pre-conntrack selector; не считается обычным clearable marker |
| IPv4 DSCP | on-wire control | **да** | только positive control; продуктовым carrier не является |

Каждый expression сначала отдельно материализуется в disposable nft table. Если runner/kernel
не поддерживает конкретный expression, результат для него — `UNAVAILABLE`, а не FAIL всего
эксперимента.

Не включены в simultaneous pass:

- route realm / `rtclassid` — route-derived, а не независимая packet stamp;
- VLAN/PCP и MAC coding — меняют L2 on-wire representation;
- GRE/VXLAN/Geneve/custom encapsulation — создают новый transport protocol;
- BPF map keyed by flow — side channel, а не metadata самого передаваемого flow;
- read-only nft metadata, которую нельзя произвольно назначить как class tag.

Они могут получить отдельные follow-up experiments, только если более простые carriers не
дают достаточного результата.

## Phase A — survival

Запускается один TCP flow:

```text
SYN -> handshake -> 3 request/reply exchanges -> FIN/close
```

Для VPN→ordinary leg STACK одновременно выставляет все поддержанные candidates с
различимыми magic values.

Точки наблюдения:

```text
STACK
  stamp
  -> source observer (доказывает, что значение действительно установлено)
  -> existing cross-netns veth
HOST / managed tambour
  -> first observer (проверяет точное magic value)
  -> consume/clear, где это допустимо
  -> ordinary host processing
```

Для каждого candidate:

- `SURVIVED`: source counter > 0 и tambour exact-value counter > 0;
- `LOST`: source counter > 0, tambour counter = 0;
- `INCONCLUSIVE_SOURCE_NOT_OBSERVED`: setter не дал доказуемого source-side значения;
- `UNAVAILABLE`: expression не может быть материализован на текущем runner.

IPv4 DSCP обязан дать `SURVIVED`. Это positive control того, что сам flow и boundary
observation работают. Если DSCP не наблюдается, EXP-069 считается FAIL/inconclusive.

### Negative control

После marked flow запускается второй TCP flow через ту же topology, но на другом TCP port и
**без каких-либо stamp rules**. Ни один tambour exact-magic counter не должен увеличиться.

Это исключает ложное survival из-за остаточного state предыдущего flow или слишком широкого
matcher.

## Phase B — NAT / cleanup interaction

Phase B выполняется отдельно для каждого `SURVIVED` candidate, который можно однозначно
потребить/очистить до ordinary host route lookup.

```text
STACK
  set candidate
    |
    v
HOST / managed tambour prerouting
  exact candidate match
  -> establish internal tambour-owned NAT conntrack class
  -> clear original boundary candidate
  -> later pre-route check: original candidate absent
    |
    v
HOST postrouting / managed gateway-NAT contribution
  internal NAT class -> masquerade
    |
    v
LAN
```

Для marked flow требуется одновременно:

- exact candidate действительно классифицировал flow;
- исходный boundary marker после consume больше не наблюдается;
- NAT rule сработал;
- LAN видит source `192.0.2.1`.

Затем через ту же ruleset запускается соседний unmarked TCP flow. Для него:

- classifier counter не увеличивается;
- NAT counter не увеличивается;
- LAN видит исходный `10.69.0.2`.

`ct zone` автоматически не допускается в Phase B: это selector conntrack domain, а не
обычная metadata, которую можно безопасно снять после lookup.

DSCP может пройти Phase B только как контроль технической процедуры очистки/NAT; даже PASS
не делает его допустимым продуктовым carrier, поскольку DSCP является внешним IP field.

## Result criterion

`EXP069_RESULT=PASS` означает, что:

- baseline stand работоспособен;
- capability probing корректно отделил `UNAVAILABLE`;
- Phase A получил валидный positive control;
- negative control не дал ложных marker hits;
- все Phase-B проверки для реально surviving clearable candidates прошли.

Итоговый result должен отдельно перечислить:

- поддержанные и недоступные candidates;
- `SURVIVED` / `LOST` по каждому;
- local-only survivors;
- on-wire control survivors;
- результаты NAT/cleanup interaction;
- соответствие нового `meta mark` наблюдения историческому EXP-063.

Выбор или отказ от нового carrier является отдельным `Disposition` и не записывается
автоматически из технического результата.

## Post-result lifecycle

- Logical evidence state: **PROVEN FACT / SUPERSEDED DESIGN**.
- Current disposition: **historical_only**.
- Applicability: **утратил применимость к текущей реализации**.

The technical PASS remains evidence about the tested metadata carriers. The product no longer
exports a Profile/behavior class across this boundary and no host behavior-lane carrier exists,
so the carrier-selection question itself is no longer a current architecture decision.

