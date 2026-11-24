# EXP-054 — NG3 host underlay endpoint pinning before full-tunnel bootstrap

## Status

PREPARED / UNPROVEN — historical_only.

The experiment lost current applicability before execution. No technical result is claimed.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

**[VPNG-U002-R2.R3.R1.R1]** *Чтобы разрешенный ordinary-to-VPN flow действительно попадал в изолированный routing domain без ручного дублирования внутренней VPN-GATE policy администратором.* | Для каждого enabled Profile, разрешающего ordinary-side initiation (`outbound` или `bidirectional`), VPN-GATE должен создавать и удалять только необходимые ему явные host-boundary routing contributions, направляющие Profile destinations в managed network domain; эти contributions являются эксплуатационно управляемым состоянием VPN-GATE, а администратор обязан не удалять и не подменять их конфликтующей host routing policy во время работы сервиса. [closed]
**[VPNG-U002-R2.R3.R1.R1.R1]** *Чтобы host bootstrap не завернул обратно в managed stack уже вышедший из него VPN transport, server reply или иной stack-origin traffic.* | Host-boundary bootstrap должен применять managed-destination capture только к ordinary/local initiation и сохранять ordinary host routing для пакетов, уже пришедших на host через explicit managed-domain boundary; если lower realization не может доказанно различить эти случаи, до активации bootstrap должны быть созданы эквивалентные явные исключения. [closed]
- **[VPNG-U004-R4.R6.R1.R1]** *Чтобы внутренние изменения VPN-GATE не требовали знания или изменения несвязанных сетевых объектов хоста.* | Сетевые объекты и mutable state, необходимые для внутренней маршрутизации и policy VPN-GATE, должны принадлежать управляемому сетевому домену либо явно объявленной boundary-области; произвольные host routes/rules/firewall state не должны использоваться как скрытая часть внутренней модели VPN-GATE. [`closed`]

The first two requirement IDs were removed from the current tree on 2026-11-20 when the old
direction-derived host-routing ownership model was rejected. They remain here only to record
the historical question that produced EXP-054; they are not current requirement links.
Current host-routing acceptance is reviewed separately, and EXP-054 has no current acceptance role.

## Question

Can VPN-GATE safely preserve an exact external VPN transport endpoint through the ordinary host
path, then activate full-tunnel-style catch-all bootstrap routing toward the managed stack,
without changing the ordinary host default route?

## Topology

```text
endpoint/gateway namespace
    loopback 198.51.100.10/32
    192.0.2.2/30
          |
          | ordinary uplink
          |
host namespace
    192.0.2.1/30
    default via 192.0.2.2
    10.255.0.1/30
          |
          | managed-stack boundary
          |
stack namespace
    10.255.0.2/30
```

The endpoint is deliberately not on-link from the host. Before bootstrap capture, host reachability
to `198.51.100.10` depends on the ordinary default route through `192.0.2.2`.

Full-tunnel capture is represented by the conventional split-default pair:

```text
0.0.0.0/1 via 10.255.0.2
128.0.0.0/1 via 10.255.0.2
```

These routes are more specific than the ordinary default but less specific than an exact
endpoint pin.

## Hypotheses

### H1 — ordinary path is freshly observable

Before any managed bootstrap route is installed, `ip -j route get 198.51.100.10` reports the
ordinary gateway and interface.

### H2 — exact endpoint pin preserves transport reachability

VPN-GATE can materialize:

```text
198.51.100.10/32 via 192.0.2.2 dev <ordinary-uplink>
```

from the freshly observed route facts. After the split-default capture routes are added, the
endpoint lookup and real packet delivery still use the ordinary uplink.

### H3 — ordinary non-endpoint traffic is captured

A representative non-endpoint destination covered by the split default resolves through the
managed-stack boundary, proving the catch-all bootstrap became active.

### H4 — pin removal demonstrates necessity

While the split-default routes remain active, deleting only the endpoint pin makes endpoint
lookup resolve through the managed-stack boundary and real endpoint delivery fail.

### H5 — cleanup restores the original ordinary path

Removing the split-default routes restores the original ordinary route to the endpoint without
requiring replacement of the host default route.

## Procedure

Run:

```sh
sudo python3 "design/experiments/EXP-054 NG3 host underlay endpoint pinning/exp054_underlay_endpoint_pinning.py"
```

The harness creates disposable namespaces, performs H1-H5, prints explicit markers, and
removes all namespaces in `finally`.

## PASS criterion

EXP-054 is PASS only if H1-H5 pass in one run.

A PASS permits implementation of a bounded underlay-pin planner/observer and host bootstrap
actuator. It does not decide how arbitrary vendor VPN endpoints are discovered; Release-1
client-side exact endpoints already exist in normalized `allow_vpn_client` intent.
## Post-result lifecycle

- Logical evidence state: **PREPARED / UNPROVEN**.
- Current disposition: **historical_only**.
- Applicability: **утратил применимость до завершения эксперимента**.

The prepared endpoint-pin mechanism was made unnecessary by the managed-boundary ingress
bypass proven later by EXP-056 and by the current authoritative host-routing contract proven
by EXP-074. No positive technical result is inferred from this prepared experiment.

