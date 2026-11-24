# EXP-073 — NG3 routed managed-L3 stateful return

Status: **PASS** — gateway-less stateful return confirmed on routed managed-L3 boundary

## Question

Does the selected EXP-053 stateful host-return mechanism preserve forwarded and host-local
reply steering when the primary HOST <-> STACK boundary is the new routed-veth/Proxy-ARP
managed-L3 endpoint and the return table contains only `default dev <boundary>` with no
peer gateway address?

## Shape

```text
REMOTE -- STACK == unnumbered routed veth == HOST -- LAN
                  Proxy ARP both ends

HOST return table:
    default dev vpng0

fwmark rule:
    return-mark -> return table
```

The test uses the production `build_linux_host_boundary_desired`,
`LinuxHostBoundaryRouteBackend`, route-dependency convergence and
`LinuxHostReturnNftBackend` inside disposable namespaces.

## PASS

- desired state contains a stateful return route with `via=None`;
- marked host lookup of the remote address selects the boundary device with no gateway;
- unmarked host lookup deliberately selects the wrong ordinary LAN default;
- remote-initiated forwarded TCP receives its reply through STACK;
- remote-initiated host-local TCP receives its reply through STACK;
- host `main` contains no remote-prefix route.

## Result

See `EXP-073-result-20261119.md`. Workflow run `44604743687`, job
`linux-routed-managed-l3-stateful-return` (`135845485540`) completed with
`EXP073_RESULT=PASS`.
## Post-result lifecycle

- Logical evidence state: **PROVEN FACT / SUPERSEDED DESIGN**.
- Current disposition: **historical_only**.
- Applicability: **утратил применимость к текущей реализации**.

The experiment validly proved the removed stateful host-return owner on the routed boundary.
Current replies return by managed destination and STACK flow affinity instead; no exact
one-for-one successor is claimed, and no current runtime module implements this mechanism.

