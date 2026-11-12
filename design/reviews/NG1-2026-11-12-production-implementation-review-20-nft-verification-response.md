# Disposition — Production implementation review 20

All findings are resolved.

EXP-017 provides kernel evidence that numeric nft iif/oif is generation-specific and that
JSON observation preserves the numeric identity after same-name reuse.

Planner migration to nftables is now unblocked. Legacy iptables remains regression evidence
only and must not remain in the production Planner after the migration.


## Post-review evidence correction

A later EXP-017 phase exposed a narrower observation fact than the original disposition
stated: nft JSON does **not** always preserve a live numeric meta iif/oif as a numeric
right-hand value; it may render the live interface name.

The kernel-generation conclusion remains valid, but the observation mechanism was changed.

Production rules now carry compiler-owned generation comments
`vpng-ifref:iif:<ifindex>` / `vpng-ifref:oif:<ifindex>`. EXP-017 proves those comments
remain observable while numeric kernel matches retain generation isolation. The verifier
uses the comment multiset rather than assuming the meta-match RHS is numeric.

This correction supersedes the sentence above claiming that JSON itself always preserves
the numeric RHS.
