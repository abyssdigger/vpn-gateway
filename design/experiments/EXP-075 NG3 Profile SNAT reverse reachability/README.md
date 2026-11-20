# EXP-075 — Profile SNAT identity reverse reachability

## Current evidence scope

The experiment retains a lower Linux integration fact used alongside:

- `VPNG0001-R1.R2.R4.R4.R4` — Profile source identity exists at the managed boundary;
- `VPNG0004-R4.R6.R1.R6` — translation state remains inside the managed domain.

It does **not** extend those requirements into a promise that core Profile SNAT owns ordinary
host routing. The tested /32 route form may be installed by a host-routing helper or by the
administrator. `VPNG0002-R2.R6` remains the STACK-side return-affinity requirement once the
reply is delivered back into the managed domain.

## Question

With the current selected architecture only:

- Profile SNAT is performed inside STACK;
- HOST owns `<snat identity>/32 dev vpng0`;
- the routed veth boundary has Proxy ARP enabled on both endpoints;

can a real reply addressed to the SNAT identity cross the addressless managed L3
boundary back into STACK without any additional stack-local route/address/proxy-neighbour
for the identity?

The experiment intentionally does **not** add such a workaround. A failure is an
architecture finding, not a test failure to be hidden.

## Execution

```bash
PYTHONPATH=design/NG3/code/python sudo --preserve-env=PYTHONPATH \
  python3 "design/experiments/EXP-075 NG3 Profile SNAT reverse reachability/exp075_profile_snat_reverse.py"
```
