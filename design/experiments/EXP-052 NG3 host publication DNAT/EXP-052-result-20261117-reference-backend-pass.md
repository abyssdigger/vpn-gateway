# EXP-052 final result — reference host-publication backend PASS

**Date:** 2026-11-17  
**Verdict:** **PASS**  
**Final evidence commit:** `32167df614193baf6a6e2cc9b76dfdae710ad39c`  
**GitHub Actions run:** `44167358884`  
**Job:** `linux-host-publication-dnat` / `134336862213`

## Final implementation under evidence

The final harness invokes `LinuxHostPublicationBackend` and
`converge_host_publication_once(...)` directly. The same implementation therefore owns both
the strict JSON observation and the nft transaction exercised by packet evidence.

It verifies:

- exact interface-selected TCP DNAT;
- exact IPv4-selected UDP DNAT;
- selector-less host-local publication;
- required `fib daddr type local` ownership guard;
- same-port foreign transit remains untouched;
- original external source reaches the managed listener;
- reverse conntrack translation returns from the original host IP/port;
- unrelated host-local listener remains untouched;
- exact owner inventory;
- empty-desired owner cleanup.

## Runtime prerequisite coverage

The backend separately observes, but does not mutate:

- ordinary-host IPv4 forwarding;
- explicit host interface existence and UP state;
- explicit host IPv4 local assignment.

Missing prerequisites yield `UNREADY` and no positive publication mutation. Unit coverage
for these cases passed in the same NG3 Python run.

## Markers

```text
EXP052_REFERENCE_BACKEND_CONVERGENCE=PASS
EXP052_INTERFACE_SELECTOR_NEGATIVE=PASS
EXP052_INTERFACE_SELECTOR_TRANSIT_UNTOUCHED=PASS
EXP052_INTERFACE_SELECTOR_TCP=PASS
EXP052_IPV4_SELECTOR_NEGATIVE=PASS
EXP052_IPV4_SELECTOR_UDP=PASS
EXP052_ANY_SELECTOR_TRANSIT_UNTOUCHED=PASS
EXP052_ANY_SELECTOR_TCP=PASS
EXP052_UNRELATED_HOST_LOCAL=PASS
EXP052_OWNER_INVENTORY=PASS
EXP052_OWNER_CLEANUP=PASS
EXP052_RESULT=PASS
```

## Semantic boundary

This PASS proves exact owned lower state for new-flow publication and cleanup of the nft owner
objects. It intentionally does not claim that deleting a NAT rule forcibly destroys already
established conntrack/session state. Such forced session termination is not part of the
current accepted `publish_vpn_server` requirement.
