# EXP-067 — NG3 one-shot ICMP Driver execution semantics

## Purpose

Prove the physical Release-1 ICMP one-shot command shape under the already selected probe
process/RPDB/local-nft mechanism, without selecting any user-facing timing knob.

The experiment uses a one-second timeout only as a test-local bounded deadline. Production
code may accept the timeout as a lower runtime parameter; this experiment does not make one
second a product guarantee.

## Scenario

Two disposable network namespaces are connected by one veth path.

In the managed namespace:

- `stack_output` and `stack_input` default DROP;
- EXP-024/066 probe-local rules admit only UID 4242 ICMP to/from the tested target and carry
  the dedicated conntrack mark;
- EXP-065-style RPDB rules select a dedicated probe table for UID 4242 + ICMP + exact target;
- the probe table contains exact /32 path routes plus a terminal blackhole default.

The ICMP process is launched as numeric UID/GID 4242 with `setpriv`.

Three technical cases are measured:

1. real remote peer replies -> ping exit 0;
2. exact routed but silent L2 target -> ping exit 1;
3. target with no route/precondition -> local execution failure -> exit other than 0/1.

## Acceptance

The experiment must establish the mapping needed by `ActiveProbeDriver`:

```text
exit 0 -> REPLY
exit 1 -> NO_REPLY
other  -> LOCAL_ERROR
```

and verify the successful lookup uses the dedicated probe table/path.

No host routing/nft state is modified.
