# VPN-GATE NG3 experiment register

The active `main` contains only experiments belonging to the current NG3 line.
Historical experiments EXP-001..EXP-027 remain preserved on the corresponding legacy
branches and may be referenced explicitly when their kernel claim is reused.

Current experiment directories:

| Range | Scope |
| --- | --- |
| EXP-028..EXP-034 | lower policy space, structural routing, forwarding barrier, nft ownership/scaffold and payload NAT |
| EXP-035..EXP-040 | payload forwarding, return path, endpoint provenance and managed INPUT/OUTPUT scaffold |
| EXP-041..EXP-047 | Device firewall and local publication |
| EXP-048 | structural route/RPDB mutation |
| EXP-049 | administrator VPN onboarding applicability |
| EXP-050 | bounded VPN lifecycle applicability |
| EXP-051 | first functioning alpha |
| EXP-052 | host-side server publication DNAT lower evidence |
| EXP-053 | host-side conntrack return steering into managed stack |
| EXP-054 | host underlay endpoint pinning before full-tunnel bootstrap |
| EXP-055 | composite host-boundary actuation |
| EXP-056 | host-ingress bootstrap bypass without main-table capture |
| EXP-057 | nft-marked host bootstrap without main-table routes |
| EXP-058 | dedicated bootstrap table preserving ordinary main specificity |
| EXP-059 | paired RPDB bootstrap with suppress-prefixlength |
| EXP-060 | selected paired-RPDB host bootstrap backend |
| EXP-061 | stack established-flow return affinity across host boundary |
| EXP-062 | inbound multipath concrete-path affinity inside managed stack |
| EXP-063 | Profile-association handoff for ordinary-side gateway NAT |
| EXP-064 | fixed host-boundary behavior lanes for remote-initiated traffic |
| EXP-065 | Release-1 probe RPDB uidrange/ipproto/target selector shape |
| EXP-066 | Release-1 probe local nft owner representation / ifindex-generation shape |
| EXP-067 | Release-1 one-shot ICMP Driver execution / exit semantics |
| EXP-068 | continuous availability failover and sticky recovery |
| EXP-069 | stack-to-tambour metadata carrier search |
| EXP-070 | routed managed-stack endpoint candidates / Debian 12 routed-veth portability |
| EXP-071 | managed-boundary dataplane race: netkit L3 vs routed veth |
| EXP-072 | managed-L3 endpoint device-only host bootstrap equivalence |
| EXP-073 | routed managed-L3 gateway-less stateful return |

Each experiment directory owns its README, harness and result evidence. The experiment number
is stable; historical results are not renumbered when referenced from NG3.


## Result vs disposition

The experiment artifact owns the technical **Result**. The registry owns the later
project-level **Disposition**. A disposition is assigned or changed only after the experiment
has completed and its result has been discussed; it never changes the technical Result.

Canonical dispositions:

- `pending_decision` — experiment completed, adoption decision not yet made;
- `selected` — evidence/mechanism is selected for current architecture;
- `not_selected` — technically available evidence/mechanism is deliberately not adopted;
- `deferred` — adoption decision or use is intentionally postponed behind a named gate;
- `superseded` — a newer experiment/result replaces this one for the same decision;
- `historical_only` — retained only as historical evidence/context.

### Disposition ledger

| Experiment | Result | Disposition | Note |
| --- | --- | --- | --- |
| EXP-014 | PREPARED / UNPROVEN | superseded | Historical predecessor for remote-initiated multi-path return pinning; EXP-062 is the current scoped experiment. |
| EXP-025 | TARGET-CONFIRMED NEGATIVE FINDING | historical_only | Proves stale probe conntrack identity can survive interface replacement; retained as a real lower-level limitation, but not by itself a Release-1 correctness failure. |
| EXP-026 | PRIVILEGED-CI PASS / target confirmation open | not_selected | Narrow probe-class conntrack cleanup works in CI, but Release 1 deliberately does not adopt it: the complexity is not justified without material payload/path or accumulated-availability harm; re-enter only if such harm is demonstrated. |
| EXP-060 | PASS | selected | Selected paired-RPDB host-bootstrap backend is confirmed. The former red CI state was an authoritative observer bug: Linux split `dst` and `dstlen` for non-/32 RPDB prefixes; normalization was fixed without changing routing semantics. |
| EXP-061 | PASS | selected | Selected Release-1 Profile-routing-domain return affinity evidence. |
| EXP-062 | PASS | deferred | Concrete-path affinity is technically proven and retained as a possible future inbound/bidirectional multipath extension; the current baseline remains single-path until an explicit product decision re-enters this work. |
| EXP-063 | FAIL | not_selected | Transient packet-mark handoff across the cross-netns veth boundary failed and is rejected as the Profile/behavior association carrier. |
| EXP-064 | PASS | selected | Fixed behavior lanes are the selected Release-1 carrier for the already-decided host-side return/NAT behavior; the revised VPNG0004-R4.R6.R1.R6.R1 requires correct gateway-NAT applicability, not literal Profile identity on the host side. |
| EXP-065 | PASS | selected | Confirms current Linux representation/lookup behavior for the tested uidrange + ICMP + target selector subset. It does **not** prove that subset sufficient for multi-path path discrimination; recovered EXP-022/023 evidence requires an additional exact `oif` selector. |
| EXP-066 | PASS | selected | Confirms current nft JSON/handle shape for the accepted EXP-024 probe local OUTPUT/INPUT admission and proves same-name/new-ifindex replacement exposes the old raw ifindex instead of falsely confirming the replacement. |
| EXP-067 | PASS | selected | Confirms one-shot ICMP execution under the selected non-root UID/RPDB/nft probe plane and the technical mapping exit 0=reply, exit 1=no-reply, other=local error; test timeout is not a product guarantee. |
| EXP-068 | PASS | selected | Confirms the already accepted continuous-availability failover and sticky-recovery chain on real Linux route state. |
| EXP-069 | PASS | pending_decision | No tested direct nft-usable local-only carrier survived stack -> tambour; DSCP survived only as an on-wire field. Post-result architecture disposition remains open. |
| EXP-070 | PASS | selected | Selects the managed-L3-endpoint shape. Release 1 uses Debian-12-compatible routed veth + Proxy ARP as the default primary boundary backend; netkit L3 remains a compatible alternate realization. The stack-SNAT subtest does not supersede existing gateway-NAT semantics. |
| EXP-071 | PASS | selected | Selected as performance evidence for the dual managed-L3-endpoint backend contract: no demonstrated dataplane reason requires netkit or excludes the Debian-12-compatible routed-veth backend. |
| EXP-072 | PASS | selected | Confirms the production paired-RPDB bootstrap can use device-only `dev vpng0` routes with identical `/0`, main-specificity, nested-managed, dynamic-main, stack-bypass and cleanup semantics over routed veth + Proxy ARP and netkit L3. |
| EXP-073 | PASS | selected | Confirms the selected EXP-053 stateful host-return owner uses the same gateway-less managed-L3 endpoint contract: return table `default dev vpng0`, no remote route in host `main`, forwarded and host-local replies both return through STACK. |
