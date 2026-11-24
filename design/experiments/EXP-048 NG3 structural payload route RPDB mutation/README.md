# EXP-048 — structural payload route/RPDB mutation primitives

## Purpose

Prove the physical Linux mutation primitives required by the accepted NG3 structural
transaction ordering for payload routing.

EXP-029 already proves the current numeric JSON representation of managed high-table routes
and RPDB rules. EXP-048 proves mutation and activation semantics:

- terminal blackhole guard can be prepared first;
- desired path route can be prepared while the table is still unreachable;
- host-boundary RPDB dispatch is the activation switch into the prepared table;
- when dispatch is active and the path route disappears, the terminal guard blocks fallback
  to ambient/main routing;
- exact route/rule deletion preserves unrelated state.

## Topology

Disposable namespaces:

```text
HOST -> managed -> VPN
               \-> ALT
```

Both VPN and ALT expose the same test destination `203.0.113.48/32` but return different
UDP payloads. Managed main routing initially chooses ALT.

The payload table is `0x80000000`, with:

- guard protocol 201;
- path protocol 202;
- terminal guard metric `0xffffffff`;
- payload RPDB priority `0x4000`.

## Sequence

1. With no managed RPDB dispatch, real host traffic reaches ALT.
2. Add the terminal blackhole default to the payload table; traffic still reaches ALT.
3. Add the desired VPN path route to the payload table; traffic still reaches ALT.
4. Add the exact payload RPDB rule:
   `priority + iif host-boundary + to destination + lookup payload-table`.
   Traffic now reaches VPN.
5. Delete only the exact VPN path route while dispatch remains active.
   Traffic must fail; it must not fall through to ALT.
6. Re-add the path route and confirm VPN traffic resumes.
7. Delete the exact RPDB dispatch rule; traffic returns to ALT.
8. Delete the prepared path/guard routes and verify unrelated route/RPDB objects remain.

## Accepted command candidates

```text
route add/del blackhole default
    table <payload-table>
    proto <guard-proto>
    metric <terminal-guard-metric>

route add/del unicast <destination>
    table <payload-table>
    proto <path-proto>
    metric <metric>
    via <gateway>
    dev <current-ifname>

rule add/del
    priority <priority>
    iif <current-host-boundary-ifname>
    to <destination>
    lookup <payload-table>
```

PASS accepts these only as lower structural primitives. It does not authorize standalone
RPDB activation; the production Executor must retain the accepted
`ForwardingGate=DISABLED -> routes -> nft -> RPDB -> verify` ordering.
