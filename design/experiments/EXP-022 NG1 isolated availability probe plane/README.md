# EXP-022 — NG1 isolated Profile-binding probe plane

**Status:** READY FOR TARGET RUN  
**Architecture baseline:** NG1 Profile-binding availability/control reset after EXP-021  
**Type:** disposable-netns RPDB / routing-table / nft isolation experiment

## Purpose

Prove that an active availability condition can continue to test one concrete bound
interface while that interface is not a usable payload path in a Profile, without placing
probe routes in Profile payload tables.

Availability itself is not being reduced to ICMP. ICMP is only the first active condition
mechanism under test.

## Mechanism under test

A probe process runs as a dedicated uid/gid with no capabilities and binds its socket to
the concrete interface.

The proposed probe-only RPDB selector combines:

```text
uidrange <probe-uid>
+ ipproto icmp
+ to <target>/32
+ oif <concrete-interface>
    -> lookup <dedicated-probe-table>
```

The dedicated table contains only a routed path through the selected peer plus a terminal
failure route:

```text
<target>/32 via <selected-peer> dev <concrete-interface>
unreachable default
```

The target is deliberately **not directly connected** to the tested interface. This is
important: the experiment must prove that the RPDB/table supplies the route, rather than
merely prove that `ping -I` can reach a directly attached peer.

Probe nft admission is separate and narrow:

- OUTPUT: probe uid + concrete numeric oif + exact target + echo-request;
- INPUT: concrete numeric iif + exact target + echo-reply.

Debian trixie `ip-rule(8)` documents that `oif` is available only for packets originating
from local sockets bound to a device. It also supports `uidrange`, `ipproto` and `to`
selectors in the same rule. EXP-022 verifies the combined behavior on the actual target
kernel rather than treating the documentation as sufficient evidence.

## Disposable topology

```text
                         primary condition path
                    198.18.221.0/30
 target 203.0.113.22/32 on lo
            pri0 <--------------------> vpn0
                                        |
                                        |  exp22-rou
                                        |
 target 203.0.113.22/32 on lo
            altp0 <-------------------> alt0
                    198.18.222.0/30
                         ordinary/main path

            host0 <-------------------> lan0
                    198.18.223.0/30
```

ROU's ordinary/main route to the target deliberately uses `alt0`. Only the dedicated
probe table has a route to the same target through `vpn0`.

## Questions

1. Does the combined RPDB selector send only the dedicated, interface-bound local probe to
   the probe table?
2. Can ordinary forwarded payload continue through the ordinary/main path without seeing
   the probe table?
3. Does an unbound probe with the same uid fail to consume the probe table?
4. Does a bound process with the wrong uid fail to consume the probe admission?
5. Can the bound probe continue while no payload route through `vpn0` exists?
6. If the primary condition path is broken while the alternate ordinary path remains live,
   does the bound probe fail rather than escape through `alt0`?
7. What happens to the RPDB `oif` rule and probe table after same-name/new-ifindex
   recreation?
8. What happens after deliberate exact-ifindex reuse? In particular, can stale RPDB+nft
   state become effective again if only the probe route is recreated?

## Decision boundary

EXP-022 does not choose:

- user-facing configuration grammar;
- probe interval/timeout/hysteresis;
- condition composition beyond the current all-required model;
- manual inhibit or scheduling APIs;
- the final runtime component name.

It proves or rejects the isolated control-plane primitive first.

## Artifact

`exp-022-isolated-probe-plane.sh`
