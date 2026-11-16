# EXP-047 — atomic local publication rule-pair mutation

## Purpose

Prove the mutation primitive for the EXP-046-backed publication-local owner class.

The managed IPv4 ForwardingGate does not protect `stack_input` / `stack_output`, so local
publication admission cannot be treated as an ordinary payload-policy step. The exact INPUT
and OUTPUT rules for one normalized publication endpoint must be changed as one nft
transaction and verified from a fresh whole-table observation.

## Candidate transaction

For one endpoint identity:

```text
add rule stack_output <exact source/protocol/sport/boundary> accept
add rule stack_input  <exact destination/protocol/dport/boundary> accept
```

submitted in one `nft -f -` batch.

Removal deletes both exact observed handles in one batch.

## Questions

1. Does one nft batch install both rules together and expose the real TCP/UDP publication
   endpoint only after the transaction commits?
2. If any command in the batch is invalid, does the transaction fail without leaving the
   first rule behind?
3. Does one delete batch remove both exact rules without affecting payload-forward, Device
   firewall or NAT owner objects?
4. Can exact post-write observation prove the pair state without a persistent handle registry?

## Decision

PASS opens publication-local mutation in the combined structural Executor as an atomic pair
operation. It does not make ForwardingGate a protection mechanism for local traffic and does
not authorize other local/system allow classes.
