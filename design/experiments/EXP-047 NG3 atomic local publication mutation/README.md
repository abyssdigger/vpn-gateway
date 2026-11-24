# EXP-047 — atomic local-publication nft mutation

## Purpose

Prove a mutation-safety mechanism for publication-local INPUT/OUTPUT rules.

The managed IPv4 ForwardingGate cannot protect locally delivered traffic, so local rule
convergence must not expose a partially applied rule set.

## Candidate mechanism

Use one nftables batch transaction (`nft -f -`) containing the complete publication-local
diff for the current observation:

- delete stale publication rules by exact observed handle;
- add all missing exact publication rules.

The batch must be all-or-nothing.

## Checks

1. A batch containing one valid local rule followed by a deliberate invalid command fails and
   leaves **no** partial first rule.
2. A valid four-rule TCP+UDP INPUT/OUTPUT batch applies completely.
3. A replacement batch that deletes the old four rules and then deliberately fails rolls back
   all deletions: the old rules remain exact.
4. A valid replacement batch atomically changes the publication port.
5. Unrelated owned payload-forward and NAT rules remain unchanged.

## Scope

This experiment proves nft transactional mutation only. It does not choose publication
grammar or permit probe/integration rules to reuse the publication owner marker.
