# Production implementation review 02 — routing-table/RPDB allocator

Role: external expert review focused on Linux FIB/RPDB semantics, representability and
future Rust migration.

## Scope

Reviewed `kernel_allocation.py`, allocator tests, Draft 4 routing invariants and Linux
UAPI routing-table constants.

## Kernel verification

Checked current Linux UAPI `include/uapi/linux/rtnetlink.h`:

- RT_TABLE_UNSPEC = 0
- RT_TABLE_COMPAT = 252
- RT_TABLE_DEFAULT = 253
- RT_TABLE_MAIN = 254
- RT_TABLE_LOCAL = 255
- RT_TABLE_MAX = 0xffffffff

The implementation correctly skips all reserved IDs and can continue allocating above 255
through the 32-bit RTA_TABLE space.

## Findings

No blocking or corrective finding remained after verification.

### Design observations accepted

- Profile table IDs are canonical by Profile ID rather than mapping insertion order. This
  makes Python/Rust behavior independent of map implementation.
- Numeric table stability is deliberately not promised across ActiveConfig generations;
  reprojection on configuration change is already within the verified transition model.
- Owned RPDB priorities use 1..N and reserve one final slot for terminal host0 fail-close.
  This maximizes the conventional priority space before main rule priority 32766 rather
  than inventing an arbitrary base such as 1000.
- Manual ActiveConfig duplicate destinations are rejected defensively even though the TOML
  parser already rejects them.

## Rust-alignment review

The allocator is a pure deterministic function over immutable config and returns typed
value objects. No ambient kernel state or mutable global allocator is required. This maps
directly to Rust iterators/Result and avoids persistence complexity for numeric IDs.

## Verdict

Approved. No recommendation remains in this scope.
