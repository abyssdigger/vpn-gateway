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
| EXP-061 | PASS | selected | Selected Release-1 Profile-routing-domain return affinity evidence. |
| EXP-062 | PASS | deferred | Concrete-path affinity is technically proven and retained as a possible future inbound/bidirectional multipath extension; the current baseline remains single-path until an explicit product decision re-enters this work. |
| EXP-063 | FAIL | not_selected | Transient packet-mark handoff across the cross-netns veth boundary failed and is rejected as the Profile/behavior association carrier. |
| EXP-064 | PASS | pending_decision | Fixed behavior lanes are technically proven, but adoption is blocked on whether VPNG0004-R4.R6.R1.R6.R1 truly requires full Profile identity to cross the host boundary or only the Profile-derived host behavior needed by its Purpose. |
