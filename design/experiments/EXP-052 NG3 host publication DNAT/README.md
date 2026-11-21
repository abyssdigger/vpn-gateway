# EXP-052 — NG3 host-side server publication DNAT

## Status

PREPARED — evidence pending.

## Historical requirement context

When this experiment was prepared, the then-current requirement tree contained:

- **[VPNG0001-R1.R2.R4.R6.R3]** *Чтобы server-side VPN transports могли быть доступны извне без смешивания host-facing listener details с Profile routing policy.* | Transport publication, если требуется Device, принадлежит Device/transport boundary и в Release 1 задаётся `publish_vpn_server = "tcp|udp[/<host-IPv4|host-interface>]:<host-port-bundle>[><internal-port-bundle>]"` либо массивом таких строк. Port bundle использует ту же strict compact grammar `N[,N|A-B...]` без пробелов, duplicate/overlap ports запрещены. Отсутствие `>...` означает identity mapping каждого host port на тот же internal port; при явном internal bundle обе стороны разворачиваются в declared order в последовательности отдельных портов, должны иметь одинаковую cardinality и мапятся позиционно 1:1. Отсутствие host selector означает публикацию на допустимых host addresses. Потеря требуемой publication не должна оставаться незаметной. [`closed`]
- **[VPNG0001-R1.R2]** *Чтобы эксплуатация продукта не зависела от ручного воспроизведения его внутренней сетевой механики оператором.* | Пользователь должен задавать требуемое поведение через продуктовую конфигурацию и управляющие операции VPN-GATE; внутренние сетевые действия должны выполняться продуктом. [`closed`]
- **[VPNG0004-R4.R6.R1.R1]** *Чтобы внутренние изменения VPN-GATE не требовали знания или изменения несвязанных сетевых объектов хоста.* | Сетевые объекты и mutable state, необходимые для внутренней маршрутизации и policy VPN-GATE, должны принадлежать управляемому сетевому домену либо явно объявленной boundary-области; произвольные host routes/rules/firewall state не должны использоваться как скрытая часть внутренней модели VPN-GATE. [`closed`]
- **[VPNG0004-R4.R6.R1.R5.R1]** *Чтобы пользовательский Device firewall ограничивал VPN payload, не заставляя пользователя одновременно администрировать внутренний control/probe plane VPN-GATE.* | Пользовательские Device firewall rules должны влиять только на managed payload forwarding, а необходимые локальные `INPUT/OUTPUT` исключения для поддерживаемых VPN-GATE control, probe, publication или integration функций должен формировать и владеть сам VPN-GATE; такие исключения не должны становиться разрешением произвольного payload forwarding или изменением firewall обычного host network namespace. [`closed`]

These R/C IDs were later removed or reparented by the NG3 Purpose/parent refactor. They are
preserved here verbatim as the historical normative context that caused this experiment to be
prepared; they are not current requirement traceability. Current applicability is expressed
through live R/C links elsewhere in this dossier or in the central experiment registry.

## Requirement trace

Implements / verifies implementation feasibility for:

- `VPNG0001-R1.R3.R6.R1` — Device-owned server-side transport publication;
- `VPNG0001-R4` — internal network actions are performed by VPN-GATE rather than manually assembled by the user;
- `VPNG0004-R4.R6` — host-side mutable state used by VPN-GATE must live in an explicit owned boundary rather than ambient host state;
- `VPNG0004-R4.R6` — publication-specific managed-domain local admission remains a VPN-GATE-owned contribution;
- `VPNG0007-R7.R7` — this evidence unit exists only to validate an accepted requirement/architecture gap before implementation.

This experiment does not change product semantics or configuration grammar.

## Question

Can the already accepted `publish_vpn_server` host/internal mapping be realized as an exact,
bounded host-boundary nftables DNAT contribution while preserving the existing isolated
managed-domain publication admission contract?

The experiment intentionally evaluates only the lower Linux mechanism. Final production
object names, lifecycle composition and implementation language remain architecture/
implementation decisions.

## Why a new experiment is needed

Historical evidence on `legacy-main-ng1-2` proved a host-side userspace relay:

- EXP-010 proved a relay across a network-namespace boundary;
- EXP-011 proved real OpenConnect TCP/CSTP + UDP/DTLS through that relay.

Those results establish feasibility of the publication boundary, but the current Release-1
grammar additionally supports compact host/internal port mapping. Before choosing a current
NG3 lower mechanism, this experiment checks whether Linux conntrack DNAT can provide that
mapping without introducing a userspace per-flow relay into the reference runtime.

## Disposable topology

All objects live in disposable network namespaces:

```text
external client
  198.51.100.2
       |
       | ext0
       v
host namespace
  198.51.100.1 + 198.51.100.5
  nft publication_prerouting
       |
       | boundary
       v
managed namespace
  192.0.2.2
  internal TCP/UDP listeners
```

A second external namespace reaches the host through a different ingress interface and is
used only for the negative interface-selector check.

The host namespace enables IPv4 forwarding only inside this disposable experiment namespace.
No runner-host sysctl or firewall state is modified.

## Hypotheses

### H1 — exact interface-selected TCP translation

A TCP packet entering through the selected host interface on external port 44443 is DNATed to
the managed listener on 192.0.2.2:8443. The managed listener observes the original external
client source address, and the client observes the reply as coming from the original
198.51.100.1:44443 endpoint.

The same destination arriving through another host interface must not match. Traffic entering through the selected interface for a non-local transit destination on the same port must also remain untouched.

### H2 — exact IPv4-selected UDP translation

UDP to 198.51.100.1:44444 is DNATed to 192.0.2.2:8444 and reverse conntrack translation
returns the datagram from 198.51.100.1:44444.

The same port addressed to 198.51.100.5 must not match.

### H3 — omitted selector means no additional host address/interface restriction

TCP to the second host address 198.51.100.5:44445 is translated to
192.0.2.2:8445 when the rule carries no interface/address selector. Omitted selector still means host-local publication, not capture of arbitrary transit traffic with the same destination port.

### H4 — unrelated host-local traffic remains unrelated

A host-local TCP listener on 198.51.100.1:45555 remains reachable unchanged. The publication
table must not redirect or otherwise capture that flow.

### H5 — unrelated transit remains unrelated

TCP transit from the primary external client to 203.0.113.2 on publication ports must pass through the disposable host namespace to the real transit listener and must not be DNATed. This is the negative ownership gate for both the interface-selected and selector-less forms.

The selected lower rule therefore requires a pre-DNAT local-destination proof (`fib daddr type local`) for publication forms that do not already identify one exact local IPv4 address.

### H6 — owned lower representation is explicit and disposable

The reference `LinuxHostPublicationBackend` converges exactly one owned host-publication
table, one NAT prerouting base chain and three owner-marked DNAT rules, then freshly observes
the exact desired state. Explicit empty-desired convergence removes that owner table before
disposable namespace teardown.

## Procedure

The harness:

1. creates four disposable namespaces: host, primary client, alternate-ingress client and
   managed;
2. creates two external veth links plus one host/managed boundary veth;
3. configures only explicit experiment addresses/routes;
4. enables `net.ipv4.ip_forward=1` only in the disposable host namespace;
5. invokes the reference `LinuxHostPublicationBackend` to converge three desired DNAT rules;
6. starts internal TCP/UDP listeners and one unrelated host-local listener;
7. runs H1-H5 positive/negative packet checks, including same-port foreign transit;
8. validates the backend's strict nft JSON owner observation;
9. converges empty desired state and confirms owner-table absence;
10. removes every disposable namespace in `finally`.

Run:

```sh
sudo python3 "design/experiments/EXP-052 NG3 host publication DNAT/exp052_host_publication_dnat.py"
```

## PASS criterion

EXP-052 is PASS only if H1-H6 all pass in one run.

A PASS permits the next architecture/implementation unit to select a narrow host-boundary
publication realization based on this mechanism. It does not by itself prove the complete
runtime lifecycle, drift reconciliation or operator-status surface.


## Final reference-backend evidence

The experiment now drives the production-shaped Python reference backend rather than a
hand-written nft script. Final run `44167358884`, job `134336862213`, confirms:

- strict host owner convergence;
- interface/IPv4/selector-less traffic semantics;
- foreign transit remains untouched;
- exact owner observation;
- explicit owner cleanup back to table absence.

Rootless unit coverage in the same run additionally verifies explicit selector loss
(interface absent/down, exact IPv4 absent) becomes `UNREADY` without acquiring host
interface/address/sysctl ownership.
