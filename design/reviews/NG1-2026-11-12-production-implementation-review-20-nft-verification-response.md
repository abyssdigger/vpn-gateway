# Disposition — Production implementation review 20

All findings are resolved.

EXP-017 provides kernel evidence that numeric nft iif/oif is generation-specific and that
JSON observation preserves the numeric identity after same-name reuse.

Planner migration to nftables is now unblocked. Legacy iptables remains regression evidence
only and must not remain in the production Planner after the migration.
