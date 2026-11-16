# VPN-GATE NG2 — Linux instance infrastructure lifecycle

**Статус:** нормативный проект NG2  
**Дата:** 2026-11-14  
**Область:** namespace/veth infrastructure below runtime bootstrap

## 1. Migration baseline

NG2 сохраняет уже принятую NG1 instance topology без изменения user-visible schema:

```text
host namespace                         ROU namespace
----------------                       ----------------
<host_interface>  <--- veth --->       host0
<host_address>                         <inner_address>
                                       default via <host_address>
```

Instance configuration version 1 остается источником:

- namespace;
- host_interface;
- host_address;
- inner_address.

Внутреннее имя `host0` остается фиксированным для schema version 1.

Этот unit не меняет TOML contract.

## 2. Ownership

Instance lifecycle владеет только infrastructure resources конкретного ROU instance:

- named network namespace;
- host-side veth;
- namespace-side `host0`;
- explicit IPv4 addresses на veth pair;
- namespace loopback state;
- namespace main-table default route через host-side address.

Он не владеет:

- payload routes/RPDB;
- nft policy;
- owner rules;
- VPN dynamic interfaces;
- publication relay;
- host firewall/NAT.

Network policy полностью остается за `LinuxNetworkRulesAdapter`.

## 3. Startup containment

Любой существующий namespace перед structural verification сначала переводится в
protective forwarding closure через тот же
`LinuxNetworkDriver.close_forwarding_verified()`.

Это относится и к partially-present instance, если namespace существует: lifecycle сначала
пытается закрыть forwarding, затем сообщает structural failure.

Нельзя сначала долго инспектировать/reconcile'ить stale namespace с открытым forwarding.

## 4. Presence states

Допустимы только два исходных состояния:

```text
namespace absent + host veth absent
    -> create fresh instance

namespace present + host veth present
    -> protective close
    -> exact infrastructure verification
```

Partial state:

```text
namespace present XOR host veth present
```

является structural FAILURE. Lifecycle не угадывает ownership, не adopt'ит чужой link и не
пытается автоматически склеить половину instance.

Если namespace присутствует, protective close выполняется до возврата failure.

## 5. Fresh creation

Create sequence:

1. require namespace and host interface both absent;
2. create namespace;
3. immediately establish protective forwarding closure inside it;
4. create veth pair `<host_interface> <-> host0`;
5. move `host0` into namespace;
6. assign explicit host/inner IPv4 addresses;
7. set host veth UP;
8. set namespace loopback and `host0` UP;
9. install namespace default route via host-side address;
10. fresh-verify infrastructure.

Failure after namespace creation performs best-effort teardown of owned resources.

No nft table is created here. First owner reconcile is the first network-policy
materialization.

## 6. Existing-instance verification

Verification requires:

- namespace exists;
- host interface exists, is veth and UP;
- `host0` exists in namespace, is veth and UP;
- configured host IPv4 address/prefix is present;
- configured inner IPv4 address/prefix is present;
- namespace default route points via configured host address and `host0`;
- host-side and namespace-side veth expose reciprocal kernel peer ifindexes
  (`ifindex/link_index`), proving that the two expected names are the same veth pair.

Verification is read-only after protective close. Peer identity is taken from current kernel
link metadata; no process-history peer registry is introduced.

## 7. Teardown

Destroy sequence:

1. if namespace exists, protective-close forwarding best effort;
2. delete namespace best effort;
3. delete surviving host veth best effort;
4. fresh-verify namespace and host veth are absent.

Teardown is infrastructure lifecycle, not Adapter `cleanup(owner)`.

Normal runtime shutdown should release Manager/Adapter policy first when possible; service
crash containment may close forwarding without requiring semantic cleanup.

## 8. Boundary to runtime bootstrap

Successful `ensure_instance()` proves only fail-closed infrastructure readiness.

The ordinary production entry point is:

```text
bootstrap_linux_network_rules_adapter_for_instance(spec)
```

It calls `ensure_linux_instance()` and then independently re-verifies protective closure
through namespace bootstrap before exposing the Adapter. The lower-level namespace helper
remains available for already-managed infrastructure boundaries.

The repeated close is intentional idempotent safety verification at an architectural
boundary, not hidden reliance on call history.

## 9. Evidence

Required evidence:

- unit state-machine tests for absent/present/partial instance states;
- exact command/verification tests;
- privileged disposable namespace create -> verify -> restart ensure -> destroy;
- restart ensure begins from deliberately open IPv4/IPv6 forwarding and proves closure;
- no nft table is created by instance lifecycle.
