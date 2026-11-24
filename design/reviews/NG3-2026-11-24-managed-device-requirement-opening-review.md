# NG3 2026-11-24 — managed Device requirement opening review

**Scope:** promote the accepted managed-Device product decision from declaration/research into
the normative requirement tree without claiming architecture closure.

## Verdict

**PASS — MANAGED DEVICE AND WIREGUARD MULTIPEER WORK ARE CORRECTLY OPENED AS NORMATIVE WORK.**

## Findings and dispositions

### F1 — optional managed Device lifecycle is a new derived product obligation

**Decision:** accepted.  
**Resolution:** fixed.

`VPNG-U001-R1.R3.R7` now requires an explicitly enabled VPN-GATE-owned preparation/lifecycle
path for supported Devices. Absence of that explicit choice preserves the existing external
VPN onboarding/lifecycle path.

The existing first-release constraints remain valid because they state what Release 1 was not
required to own; they are not permanent prohibitions.

### F2 — backward compatibility is explicit rather than inferred

**Decision:** accepted.  
**Resolution:** fixed.

`R7.R1` prohibits configuration/lifecycle mutation of Devices for which management was not
explicitly enabled. Existing observation and binding remain the supported path for them.

### F3 — lifecycle operations require confirmed postconditions

**Decision:** accepted.  
**Resolution:** fixed.

`R7.R2` distinguishes desired configuration from the actually running VPN generation and
requires confirmed start/stop/restart outcomes. Concrete endpoint usability remains subject to
the existing binding contract.

### F4 — structural demand is selected; packet-triggered demand is not silently added

**Decision:** accepted.  
**Resolution:** fixed.

`R7.R3` ties the first managed-lifecycle demand to the existing enabled-and-referenced Device
condition. Packet-triggered connection and idle shutdown are explicitly outside this
requirement.

### F5 — WireGuard same-prefix peer redundancy is not a child of lifecycle management

**Decision:** accepted.  
**Resolution:** fixed.

The first draft placed the WireGuard peer-redundancy need below R7. Review rejected that causal
shape: lifecycle ownership does not create the user need for same-prefix peer redundancy.

The capability is therefore the sibling `VPNG-U001-R1.R3.R8` under supported VPN-channel
integration. Its later architecture may compose with R7, but the requirement tree does not
invent that causality.

### F6 — status is correctly open

**Decision:** accepted.

The five new nodes have no accepted architecture closure candidate. `open` is therefore the
correct status; no implementation is authorized merely by opening the requirements.

Static check: current tree has 225 unique normative IDs and no duplicate ID.

The NG3 unit/traceability job passed on the initial R7 commit
`fe268fb26ca14188c4ffd910b0a8641d2ac8098f`; subsequent commits only corrected the
requirement ancestry and Russian wording before this review.

## Result

The next development unit may now define EXP-088 against `VPNG-U001-R1.R3.R7*` and
`VPNG-U001-R1.R3.R8` without using the research declaration as substitute authority.
