# Disposition — Production implementation review 10

All findings were accepted and fixed.

- availability is fresh for each projection snapshot;
- waiting metric promotion explicitly schedules an immediate second reconcile;
- verified runtime history is persisted before forwarding reopen;
- persistence failure is fail-closed;
- crash-reopen verification no longer mixes redundant live reads.

The event loop must honor `needs_immediate_reconcile` without waiting for an external
event.
