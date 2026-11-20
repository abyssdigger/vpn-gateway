# EXP-076 — combined Profile SNAT dataplane

## Requirement trace

Core Profile-SNAT acceptance evidence for:

- `VPNG0001-R1.R2.R4.R4.R4`;
- `VPNG0001-R1.R2.R4.R4.R4.R1`;
- `VPNG0001-R1.R2.R4.R4.R4.C1`;
- `VPNG0001-R1.R2.R4.R4.R4.C2`;
- `VPNG0002-R2.R6`;
- `VPNG0004-R4.R6.R1.R6`;
- `VPNG0004-R4.R6.R1.R6.R1`.

## Topology and assertions

A real HOST↔STACK routed boundary carries three VPN-originated UDP flows:

- Profile A: `+snat` to `198.19.255.10`;
- Profile B: `+snat` to the same shared identity;
- Profile C: no Profile SNAT.

The STACK forward chain is `policy drop`. NEW admission matches only each original
remote source; there is no allow rule matching the translated identity. Therefore successful
A/B delivery proves firewall/policy precedes postrouting SNAT.

The experiment also requires:

- A and B both appear to the LAN server as the same SNAT identity and both replies return
  under the tested host-integration route;
- C appears as its original remote source and its reply returns;
- authoritative NAT observation contains exactly the two Profile SNAT rules;
- HOST contains no Profile SNAT nft owner;
- as ancillary lower integration evidence, the SNAT identity host route uses the stack
  service next hop, while ordinary remote destinations remain device-only.

The host route assertion is not a claim that core Profile SNAT owns host routing; equivalent
routing may be supplied by a separate helper or by the administrator.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-076 NG3 combined Profile SNAT/exp076_combined_profile_snat.py"
```
