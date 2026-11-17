# EXP-052 — NG3 host-side server publication DNAT

## Status

PREPARED — evidence pending.

## Requirement trace

Implements / verifies implementation feasibility for:

- `VPNG0001-R1.R2.R4.R6.R3` — Device-owned server-side transport publication;
- `VPNG0001-R1.R2` — internal network actions are performed by VPN-GATE rather than manually assembled by the user;
- `VPNG0004-R4.R6.R1.R1` — host-side mutable state used by VPN-GATE must live in an explicit owned boundary rather than ambient host state;
- `VPNG0004-R4.R6.R1.R5.R1` — publication-specific managed-domain local admission remains a VPN-GATE-owned contribution;
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

The nft JSON inventory contains exactly the experiment-owned table, one NAT prerouting base
chain and three owner-marked DNAT rules. Deleting the disposable host namespace removes the
entire experiment-owned state.

## Procedure

The harness:

1. creates four disposable namespaces: host, primary client, alternate-ingress client and
   managed;
2. creates two external veth links plus one host/managed boundary veth;
3. configures only explicit experiment addresses/routes;
4. enables `net.ipv4.ip_forward=1` only in the disposable host namespace;
5. installs one experiment-owned nftables table with three DNAT rules;
6. starts internal TCP/UDP listeners and one unrelated host-local listener;
7. runs H1-H5 positive/negative packet checks, including same-port foreign transit;
8. validates the nft JSON owner representation;
9. removes every disposable namespace in `finally`.

Run:

```sh
sudo python3 "design/experiments/EXP-052 NG3 host publication DNAT/exp052_host_publication_dnat.py"
```

## PASS criterion

EXP-052 is PASS only if H1-H6 all pass in one run.

A PASS permits the next architecture/implementation unit to select a narrow host-boundary
publication realization based on this mechanism. It does not by itself prove the complete
runtime lifecycle, drift reconciliation or operator-status surface.
