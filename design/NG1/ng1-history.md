# VPN-GATE NG1 historical implementation record

Status: **non-normative history/evidence companion**

This file preserves the implementation-history material that previously lived inside the
normative NG1 architecture. Current production semantics are defined only by
[vpn-gateway-architecture-ng1.md](vpn-gateway-architecture-ng1.md) and the current
configuration/runtime documents.

## 20. First executable ROU prototype boundary

The first executable ROU implementation is intentionally narrower than the full NG1
configuration model. It is a lifecycle and integrity prototype, not the first generic
configuration release.

ROU v0 may hard-code:

- one ROU instance and namespace;
- one host-facing veth pair;
- one OUTBOUND profile;
- one OpenConnect/ocserv prefix binding;
- the binding network and capacity;
- one protected test destination;
- one profile routing table and RPDB rule;
- one TCP and one UDP publication on the same external/internal ocserv port;
- the existing known-good ocserv configuration as the source for a derived runtime config.

The purpose is to prove the complete appliance control loop before adding a broad parser.

ROU v0 must distinguish two classes of change:

1. **normal binding lifecycle** — eligible `vpnsXX` interfaces may appear, disappear and
   reappear as clients connect and disconnect;
2. **structural owned-state drift** — unexpected mutation of ROU-owned profile routing,
   RPDB, firewall/NAT or appliance infrastructure.

For the first implementation, any change requiring structural reprojection uses a
protective forwarding barrier:

    set net.ipv4.ip_forward=0
        -> project complete owned state
        -> verify complete owned state
        -> set net.ipv4.ip_forward=1

This deliberately trades transient availability for a small and strong safety model while
the control loop is being validated.

A disappearing VPN binding is not itself corruption. Reconciliation recalculates admitted
bindings and fail-closed profile state from a fresh namespace snapshot. If no usable
binding remains, the profile table retains its blackholes and forwarding to that profile
remains fail-closed.

Initial live gates for ROU v0 are:

- clean creation from no namespace/veth;
- real ocserv startup and client reconnection through publication;
- correct materialization of the VPN interface inside the namespace;
- normal preferred-binding disappearance and survivor behavior;
- zero-binding fail-closed behavior;
- recovery after injected owned route/RPDB/firewall drift;
- detection of structural appliance drift that cannot be safely repaired in place;
- graceful shutdown and complete removal of owned host/netns resources.

General configuration parsing, multiple profiles, arbitrary selectors/transports, warm
capacity and BOU integration are explicitly deferred until these lifecycle gates pass.

### 20.1 Implemented ROU v0

The executable reference implementation is:

    design/NG1/code/python/rou_v0/

It is a clean NG1 implementation rather than an adaptation of the RC3 daemon. RC2/RC3
were used as evidence for already-proven kernel behavior and failure modes.

The implementation currently hard-codes the v0 lab boundary defined above and includes:

- namespace/veth creation and destruction;
- derived ocserv runtime configuration and process lifecycle inside the ROU namespace;
- host-side TCP publication relay;
- host-side UDP publication with independent per-external-peer associations;
- fresh-snapshot discovery of concrete `vpns+` interfaces by `(ifname, ifindex)`;
- capacity-2 metric allocation with survivor stability and delayed metric reuse across a
  verified REMOVE commit;
- a dedicated profile routing table with direct-dev unicast routes, protected blackhole and
  terminal blackhole default;
- an `iif host0` RPDB dispatch rule;
- OUTBOUND-only filter semantics and per-binding MASQUERADE;
- complete owned-state reconciliation under the forwarding barrier;
- semantic route/RPDB verification using `ip -j`;
- canonical filter/NAT verification using `iptables-legacy-save`;
- fatal isolation/cleanup on non-repairable appliance-infrastructure loss;
- read-only JSON status plus a single-instance runtime lock.

The EXP-011 one-peer UDP limitation is therefore not carried into v0: each external UDP
peer has its own connected internal UDP socket and return-path association.

### 20.2 Verification boundary

Rootless checks completed before the first live run:

- Python bytecode compilation;
- unit tests covering binding projection, capacity/overflow, delayed metric reuse,
  same-name/new-ifindex identity, fail-closed route/firewall projection and bootstrap
  handling of an absent profile table;
- two-peer UDP relay smoke;
- shell syntax validation of the live harness.

EXP-012 then completed the full live lifecycle/integrity gate on the dedicated Debian 13
test VM with `OVERALL=PASS`.

The successful live run proved:

- clean namespace/veth creation and teardown;
- real ocserv startup inside ROU;
- simultaneous DTLS for both real OpenConnect clients through independent UDP peer
  associations;
- two-path profile materialization and real payload forwarding;
- preferred-binding disappearance with survivor metric preservation and payload failover;
- fresh binding return without survivor churn;
- explicit zero-path fail-closed routing;
- route and firewall drift repair under an observable `ip_forward=0` barrier;
- fatal isolation/teardown after structural `host0` loss.

Three defects discovered during the live gate were corrected without weakening the
hypotheses: bootstrap flushing of a not-yet-created profile table, ocserv sec-mod
chroot-visible runtime socket placement, and an H8 harness command that initially targeted
the wrong routing table.

EXP-012 therefore closes the hard-coded ROU v0 verification boundary. Generic
configuration/domain-model work may proceed from this implementation while preserving the
verified lifecycle, fail-closed, allocation and integrity semantics.

## 21. Inheritance from RC2/RC3

NG1 changes topology and ownership, but it does **not** discard the engineering work already completed in RC2 and RC3.

RC2/RC3 contain substantial reusable material:

- live experiments against real Linux routing, iptables, WireGuard and OpenConnect behavior;
- fail-closed experiments and recovery observations;
- route/metric and blackhole behavior;
- interface disappearance/reappearance and ifindex identity lessons;
- reconciliation and fresh-snapshot design;
- ADD/REMOVE transition ordering;
- verification-before-commit rules;
- ownership and drift-repair lessons;
- IPv4/IPv6 prerequisite checks;
- configuration parsing/validation patterns;
- selector and binding-domain work;
- profile status and availability semantics;
- extensive Python reference code and regression tests;
- independent architecture/code reviews and the decisions made from them.

This material is a **design and experiment library**, not obsolete history.

NG1 work should explicitly mine RC2/RC3 before inventing or re-testing behavior that was already established.

At the same time RC3 is not normative for NG1. Any RC3 rule depending on the old host-integrated topology, shared host routing namespace, old firewall ownership or other superseded assumptions must be re-evaluated before reuse.

In short:

> NG1 reuses proven observations, invariants and implementation techniques from RC2/RC3 while deliberately replacing their top-level topology and ownership model.

Primary source material includes the existing experiment log under design/vpn-gateway-experiments.md, the RC2/RC3 architecture documents, reviews and the RC3 Python implementation.

### 21.1 ROU v0 -> production migration boundary

ROU v0 is executable evidence, not the production object model.

**Reuse/prove forward from v0:**

- namespace/veth lifecycle and teardown containment;
- publication relay behavior, including independent UDP peer associations;
- fresh observation and verification-before-commit;
- protective forwarding barrier for structural reprojection;
- direct-device routing observations;
- canonical firewall/NAT inspection techniques;
- fatal containment after unrecoverable appliance-infrastructure loss.

**Rewrite/generalize for production:**

- hard-coded binding/capacity -> Device/ExpectedInterface;
- one OUTBOUND Profile -> multiple Profiles with stateful direction semantics;
- fixed route metrics -> two-level Profile-local metric ranges;
- v0 filter shortcuts -> generated Profile guard + Device envelope;
- hard-coded configuration -> validated ActiveConfig;
- one transport instance -> generic Device binding/publication state.
