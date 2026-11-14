# VPN-GATE NG2 — runtime/bootstrap assembly

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-14  
**Область:** запуск Linux network-policy runtime до первого owner reconcile

## 1. Цель

Этот bootstrap unit закрывает lifecycle gap между созданием/перезапуском процесса и
первым вызовом `NetworkRulesAdapter.apply()`.

Конкретный Linux `NetworkRulesAdapter` уже закрывает forwarding перед каждой своей
mutation. Этого недостаточно для startup: после restart в dedicated ROU namespace могут
оставаться stale route/nft resources и ранее включенный IPv4/IPv6 forwarding до того,
как первый owner request вообще будет обработан.

Нормативное правило:

> runtime не публикует готовый к использованию Linux NetworkRulesAdapter до fresh
> подтверждения protective closure: `net.ipv4.ip_forward=0`,
> `net.ipv6.conf.all.forwarding=0` и
> `net.ipv6.conf.default.forwarding=0`.

## 2. Граница ответственности

Bootstrap assembly находится ниже runtime event model и выше concrete Linux Driver.

Он не является новым Manager и не публикует Events. Это синхронная startup assembly,
которая:

1. получает concrete Linux Driver;
2. выполняет protective forwarding close;
3. требует fresh verification закрытого forwarding;
4. только после успеха создает/возвращает concrete `LinuxNetworkRulesAdapter`.

После возврата Adapter обычный runtime может начинать owner reconciliation.

Bootstrap не:

- интерпретирует payload/Profile policy;
- очищает stale routes/nft до появления desired owner state;
- восстанавливает previous owner generations;
- открывает forwarding;
- создает отдельную policy поверх Adapter.

Stale physical resources остаются закрыты forwarding barrier и будут классифицированы /
пересобраны первым обычным Adapter reconcile.

## 3. Driver contract

Concrete Linux Driver предоставляет Direct operation:

```text
close_forwarding_verified() -> LinuxDriverResult
```

SUCCESS означает, что:

- `net.ipv4.ip_forward=0` установлен;
- `net.ipv6.conf.all.forwarding=0` и `net.ipv6.conf.default.forwarding=0` установлены;
- после mutation выполнено новое наблюдение;
- новое наблюдение подтвердило все три значения.

FAILURE означает, что protective close не доказан. В этом случае bootstrap не возвращает
рабочий Adapter.

Эта операция техническая и не знает owner/payload semantics, поэтому принадлежит Driver.

## 4. Bootstrap result

Bootstrap contract концептуально:

```text
bootstrap_linux_network_rules_adapter(
    backend,
    local_interface
) -> SUCCESS(adapter) | FAILURE(diagnostic)
```

Returned Adapter создается только после доказанного forwarding close.

Failure не синтезирует runtime state и не запускает event graph. Startup caller решает,
как представить/логировать startup failure.

## 5. Restart semantics

Process-history loss не должен создавать окно forwarding:

```text
process starts
    -> protective IPv4/IPv6 close + fresh verify
    -> construct/publish Adapter
    -> first owner reconcile
    -> Adapter structural verification
    -> Adapter may reopen forwarding only for verified effective policy
```

Следовательно stale Linux state между process start и first reconcile может существовать,
но не должно пропускать forwarded payload traffic.

## 6. Existing namespace execution

Concrete production assembly may target an already existing named network namespace:

```text
host command runner
    -> NetworkNamespaceLinuxRunner(namespace)
    -> LinuxNetworkDriver
    -> protective bootstrap gate
    -> LinuxNetworkRulesAdapter
```

`NetworkNamespaceLinuxRunner` only scopes Linux commands with `ip netns exec`. It does
not create, delete, rename or repair the namespace and does not own host-side veth/transport
plumbing.

The helper
`bootstrap_linux_network_rules_adapter_in_namespace(namespace, local_interface, ...)`
therefore assumes that the namespace and its local-facing interface already exist. Failure
to enter the namespace is a bootstrap failure; it is not repaired implicitly.

This keeps namespace lifecycle ownership separate from network-policy ownership.

## 7. Evidence

Этот unit требует:

- unit test, что Adapter не возвращается при failed/unverified protective close;
- privileged namespace integration test со stale policy и `ip_forward=1`, доказывающий,
  что bootstrap сначала переводит forwarding в `0`;
- regression, что обычный Adapter после bootstrap способен выполнить normal apply и
  открыть forwarding только после своей final verification.

## 8. Не входит в этот unit

Отдельными review units остаются:

- создание/удаление network namespace и host-side transport plumbing;
- RuntimeStateManager event assembly;
- startup loading/normalization configuration;
- shutdown orchestration;
- persistent technical allocation across process restart.
