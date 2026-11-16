# EXP-017 preliminary GitHub result

Date: 2026-11-12  
Environment: GitHub-hosted Linux runner, privileged disposable network namespaces  
Status: **PRELIMINARY PASS — numeric nftables input-interface identity works as required**

This is supporting evidence, not the final Debian 13 target-kernel PASS.

## Procedure

A disposable ROU namespace received a veth named `vpn0`.

1. record its numeric ifindex A;
2. install nftables INPUT policy accepting ICMP only when `meta iif A`;
3. prove traffic through generation A is accepted;
4. delete/recreate the veth with the same name `vpn0`;
5. record a different numeric ifindex B;
6. prove traffic through B is rejected by the unchanged `meta iif A` rule;
7. add an explicit `meta iif B` rule;
8. prove traffic through B is then accepted.

## Observed result

```text
PASS A: numeric iif=2 admits original generation
PASS B: same-name/new-ifindex=3 does not inherit iif=2 rule
PASS C: explicit rule for fresh ifindex restores admission
EXP_017_PRELIMINARY_IIF=PASS
```

## Interpretation

On this kernel/userspace combination, nftables numeric input-interface matching follows the
interface index and therefore does not inherit admission merely because a fresh interface
reuses the same name.

This closes the basic primitive uncertainty and justifies implementing an ifindex-aware nft
policy backend for comprehensive testing.

## Remaining target gate

Final EXP-017 PASS still requires the target Debian 13 environment and the complete policy
surface:

- both numeric iif and oif;
- Profile NEW accept/drop;
- ESTABLISHED/RELATED bound pairs;
- Device envelope traversal;
- atomic full ruleset replacement;
- interface disappearance/replacement during reconcile.

Production default must not switch from the current backend solely on this preliminary
runner result.
