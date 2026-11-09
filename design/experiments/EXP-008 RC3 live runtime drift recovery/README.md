# EXP-008 — RC3 live runtime drift recovery

This is a **live fault-injection experiment** on the dedicated vpn-gateway host.

It assumes EXP-007 has passed and the production-style profile resolves READY.

## Scope

The harness starts the actual RC3 daemon and tests:

1. deletion/restoration of one proto-202 route;
2. INPUT-only firewall drift with narrow repair;
3. FORWARD drift with the protective forwarding barrier;
4. graceful cleanup afterwards.

It does **not** stop/restart OpenConnect or remove the managed VPN interface. Interface
lifecycle is a separate experiment.

## Safety

Run only when no other vpn-gateway daemon/controller owns the host.

The harness requires a clean pre-state and refuses to start if it sees:

- `ip_forward=1`;
- existing `VPNG-*` resources;
- existing proto-201/proto-202 routes.

The script creates two foreign test chains, `EXP008-IN` and `EXP008-FWD`. A trap removes
them even on failure. The daemon is expected to preserve these foreign resources while
repairing its own prefix.

## Run

```bash
reset
git pull --ff-only
cd "design/experiments/EXP-008 RC3 live runtime drift recovery"

sudo ./vpn-gateway-exp-008-runtime-drift.sh \
    --config /etc/vpn-gateway/vpn-gateway.toml
```

On failure, keep the generated timestamped directory and send `result.txt` plus
`daemon.log`.


## Recorded result

Final run on 2026-11-09:

```text
PASS: H1 live startup
PASS: H2 proto-202 route recovery
PASS: H3 INPUT-only narrow repair
PASS: H4 FORWARD barrier repair
PASS: H5 graceful cleanup
OVERALL=PASS
archive=vpn-gateway-exp-008-20261109-210410Z.tar.gz
sha256_file=vpn-gateway-exp-008-20261109-210410Z.tar.gz.sha256
```

This closes the first live runtime-recovery gate. Interface disappearance/reappearance and
selector ambiguity remain intentionally out of scope for EXP-008.
