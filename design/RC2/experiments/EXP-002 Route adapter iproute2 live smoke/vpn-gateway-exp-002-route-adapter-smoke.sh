#!/usr/bin/env bash
set -Eeuo pipefail

export LC_ALL=C
export LANG=C

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "ERROR: run as root (sudo)." >&2
    exit 2
fi

for cmd in ip python3 tar sha256sum uname; do
    command -v "$cmd" >/dev/null 2>&1 || {
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    }
done

STAMP="$(date -u +%Y%m%d-%H%M%SZ)"
OUT="vpn-gateway-exp-002-${STAMP}"
ARCHIVE="${OUT}.tar.gz"
NS="vpng-exp002-$$"

mkdir -m 700 "$OUT"

cleanup() {
    ip netns del "$NS" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

record_rc() {
    local name="$1"
    shift

    set +e
    "$@" >"$OUT/${name}.stdout" 2>"$OUT/${name}.stderr"
    local rc=$?
    set -e

    printf '%s\n' "$rc" >"$OUT/${name}.rc"
    return "$rc"
}

capture_routes() {
    local name="$1"
    ip netns exec "$NS" \
        ip -j -N -4 route show table main \
        >"$OUT/${name}.json"
}

capture_addresses() {
    local name="$1"
    ip netns exec "$NS" \
        ip -j -4 addr show \
        >"$OUT/${name}.json"
}

{
    echo "run_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "hostname=$(hostname)"
    echo "uname=$(uname -a)"
    echo "ip_version=$(ip -Version 2>&1)"
    echo "python_version=$(python3 --version 2>&1)"
    echo
    if [[ -r /etc/os-release ]]; then
        cat /etc/os-release
    fi
} >"$OUT/environment.txt"

# Disposable namespace only. No host routes, addresses, or firewall state are changed.
ip netns add "$NS"
ip -n "$NS" link set lo up

ip -n "$NS" link add vpns0 type dummy
ip -n "$NS" link set vpns0 up
ip -n "$NS" addr add 172.20.130.1/29 dev vpns0

# Addressless interface: validates the adapter contract that it remains visible.
ip -n "$NS" link add empty0 type dummy
ip -n "$NS" link set empty0 up

# Point-to-point-shaped address record: validates addr_info[].local vs peer.
ip -n "$NS" link add p2p0 type dummy
ip -n "$NS" link set p2p0 up
record_rc p2p-address-add \
    ip -n "$NS" addr add 172.20.140.1 peer 172.20.140.2/32 dev p2p0 || true

capture_addresses "addresses"
capture_routes "routes-initial"

# H2: exact daemon UNICAST command form: add -> identical replace -> exact delete.
record_rc unicast-add \
    ip netns exec "$NS" ip -4 route add unicast 10.0.0.0/8 \
        table main proto 202 metric 10 \
        via 172.20.130.6 dev vpns0 onlink || true
capture_routes "routes-unicast-add"

record_rc unicast-replace \
    ip netns exec "$NS" ip -4 route replace unicast 10.0.0.0/8 \
        table main proto 202 metric 10 \
        via 172.20.130.6 dev vpns0 onlink || true
capture_routes "routes-unicast-replace"

record_rc unicast-delete \
    ip netns exec "$NS" ip -4 route del unicast 10.0.0.0/8 \
        table main proto 202 metric 10 \
        via 172.20.130.6 dev vpns0 onlink || true
capture_routes "routes-unicast-delete"

# H3: exact daemon BLACKHOLE command form.
record_rc blackhole-add \
    ip netns exec "$NS" ip -4 route add blackhole 192.0.2.0/24 \
        table main proto 201 metric 65536 || true
capture_routes "routes-blackhole-add"

record_rc blackhole-delete \
    ip netns exec "$NS" ip -4 route del blackhole 192.0.2.0/24 \
        table main proto 201 metric 65536 || true
capture_routes "routes-blackhole-delete"

# H4: iproute2 default protocol representation. Inventory must normalize it to RTPROT_BOOT=3.
record_rc boot-add \
    ip netns exec "$NS" ip -4 route add unicast 198.51.100.0/24 \
        table main dev vpns0 || true
capture_routes "routes-boot-add"

# Test the command the adapter would emit after normalizing omitted protocol -> 3.
record_rc boot-delete-proto3 \
    ip netns exec "$NS" ip -4 route del unicast 198.51.100.0/24 \
        table main proto 3 dev vpns0 || true
capture_routes "routes-boot-delete"

# H1/H6: supported route types and default representation in real JSON.
record_rc special-blackhole \
    ip netns exec "$NS" ip -4 route add blackhole 203.0.113.0/25 \
        table main proto 71 metric 101 || true
record_rc special-unreachable \
    ip netns exec "$NS" ip -4 route add unreachable 203.0.113.128/26 \
        table main proto 72 metric 102 || true
record_rc special-prohibit \
    ip netns exec "$NS" ip -4 route add prohibit 203.0.113.192/27 \
        table main proto 73 metric 103 || true
record_rc special-throw \
    ip netns exec "$NS" ip -4 route add throw 203.0.113.224/28 \
        table main proto 74 metric 104 || true
record_rc default-add \
    ip netns exec "$NS" ip -4 route add unicast default \
        table main proto 75 metric 105 \
        via 172.20.130.6 dev vpns0 onlink || true

capture_routes "routes-supported-types"

set +e
python3 - "$OUT" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
failures: list[str] = []
observations: list[str] = []

def load_json(name: str):
    try:
        value = json.loads((out / name).read_text(encoding="utf-8"))
    except Exception as exc:
        failures.append(f"{name}: invalid JSON: {exc}")
        return []
    if not isinstance(value, list):
        failures.append(f"{name}: top-level JSON is not a list")
        return []
    return value

def rc(name: str) -> int:
    try:
        return int((out / f"{name}.rc").read_text(encoding="utf-8").strip())
    except Exception as exc:
        failures.append(f"{name}: missing/invalid rc: {exc}")
        return 999

def find_route(rows, dst: str):
    return [row for row in rows if isinstance(row, dict) and row.get("dst") == dst]

def protocol_value(row):
    return row.get("protocol", "<omitted>")

# H1: numeric kernel protocol on the connected route with -N.
initial = load_json("routes-initial.json")
connected = find_route(initial, "172.20.130.0/29")
if len(connected) != 1:
    failures.append(
        f"H1: expected one connected 172.20.130.0/29 route, got {connected!r}"
    )
else:
    proto = protocol_value(connected[0])
    observations.append(f"H1 connected protocol={proto!r}")
    if proto not in (2, "2"):
        failures.append(f"H1: connected route protocol is not numeric RTPROT_KERNEL=2: {proto!r}")

# H2: exact unicast add/replace/delete command forms.
for case in ("unicast-add", "unicast-replace", "unicast-delete"):
    if rc(case) != 0:
        failures.append(f"H2: {case} command failed")

uadd = load_json("routes-unicast-add.json")
urepl = load_json("routes-unicast-replace.json")
udel = load_json("routes-unicast-delete.json")
uadd_rows = find_route(uadd, "10.0.0.0/8")
urepl_rows = find_route(urepl, "10.0.0.0/8")
udel_rows = find_route(udel, "10.0.0.0/8")
if len(uadd_rows) != 1:
    failures.append(f"H2: unicast route missing/duplicated after add: {uadd_rows!r}")
if len(urepl_rows) != 1:
    failures.append(f"H2: unicast route missing/duplicated after replace: {urepl_rows!r}")
if uadd_rows and urepl_rows and uadd_rows[0] != urepl_rows[0]:
    failures.append(
        "H2: identical replace changed canonical JSON entry: "
        f"add={uadd_rows[0]!r}, replace={urepl_rows[0]!r}"
    )
if udel_rows:
    failures.append(f"H2: unicast route still present after delete: {udel_rows!r}")
if uadd_rows:
    row = uadd_rows[0]
    observations.append(f"H2 unicast entry={json.dumps(row, sort_keys=True)}")
    if protocol_value(row) not in (202, "202"):
        failures.append(f"H2: unicast protocol != 202: {protocol_value(row)!r}")
    if row.get("metric") != 10:
        failures.append(f"H2: unicast metric != 10: {row.get('metric')!r}")
    if row.get("gateway") != "172.20.130.6":
        failures.append(f"H2: unicast gateway mismatch: {row.get('gateway')!r}")
    flags = row.get("flags", [])
    if "onlink" not in flags:
        failures.append(f"H2: unicast onlink missing from flags: {flags!r}")

# H3: exact blackhole add/delete.
for case in ("blackhole-add", "blackhole-delete"):
    if rc(case) != 0:
        failures.append(f"H3: {case} command failed")

badd = load_json("routes-blackhole-add.json")
bdel = load_json("routes-blackhole-delete.json")
badd_rows = find_route(badd, "192.0.2.0/24")
bdel_rows = find_route(bdel, "192.0.2.0/24")
if len(badd_rows) != 1:
    failures.append(f"H3: blackhole route missing/duplicated after add: {badd_rows!r}")
else:
    row = badd_rows[0]
    observations.append(f"H3 blackhole entry={json.dumps(row, sort_keys=True)}")
    if row.get("type") != "blackhole":
        failures.append(f"H3: blackhole type mismatch: {row.get('type')!r}")
    if protocol_value(row) not in (201, "201"):
        failures.append(f"H3: blackhole protocol != 201: {protocol_value(row)!r}")
    if row.get("metric") != 65536:
        failures.append(f"H3: blackhole metric mismatch: {row.get('metric')!r}")
if bdel_rows:
    failures.append(f"H3: blackhole route still present after delete: {bdel_rows!r}")

# H4: omitted protocol is omitted or numerically boot=3, and proto 3 deletes it.
if rc("boot-add") != 0:
    failures.append("H4: boot-add command failed")
if rc("boot-delete-proto3") != 0:
    failures.append("H4: delete with explicit proto 3 failed")
boot = load_json("routes-boot-add.json")
boot_after = load_json("routes-boot-delete.json")
boot_rows = find_route(boot, "198.51.100.0/24")
if len(boot_rows) != 1:
    failures.append(f"H4: boot route missing/duplicated after add: {boot_rows!r}")
else:
    proto = protocol_value(boot_rows[0])
    observations.append(f"H4 boot protocol field={proto!r}")
    if proto not in ("<omitted>", 3, "3"):
        failures.append(f"H4: omitted protocol did not represent RTPROT_BOOT=3: {proto!r}")
if find_route(boot_after, "198.51.100.0/24"):
    failures.append("H4: boot route still present after explicit proto 3 delete")

# H5: address inventory semantics.
if rc("p2p-address-add") != 0:
    failures.append("H5: point-to-point-shaped address setup command failed")

addresses = load_json("addresses.json")
by_name = {
    row.get("ifname"): row
    for row in addresses
    if isinstance(row, dict) and isinstance(row.get("ifname"), str)
}
if "empty0" not in by_name:
    failures.append("H5: addressless interface empty0 omitted by `ip -j -4 addr show`")
else:
    observations.append(
        "H5 empty0 addr_info="
        + json.dumps(by_name["empty0"].get("addr_info"), sort_keys=True)
    )
    if by_name["empty0"].get("addr_info", []) != []:
        failures.append(
            f"H5: empty0 unexpectedly has IPv4 addr_info: {by_name['empty0'].get('addr_info')!r}"
        )

p2p = by_name.get("p2p0")
if p2p is None:
    failures.append("H5: p2p0 missing from address inventory")
else:
    infos = p2p.get("addr_info", [])
    matching = [
        info for info in infos
        if isinstance(info, dict) and info.get("local") == "172.20.140.1"
    ]
    if len(matching) != 1:
        failures.append(f"H5: expected p2p local address not found: {infos!r}")
    else:
        info = matching[0]
        observations.append(f"H5 p2p addr_info={json.dumps(info, sort_keys=True)}")
        if "peer" not in info:
            failures.append(f"H5: p2p record has no peer field: {info!r}")

# H6: all parser-supported route types + default are represented as expected.
for case in (
    "special-blackhole",
    "special-unreachable",
    "special-prohibit",
    "special-throw",
    "default-add",
):
    if rc(case) != 0:
        failures.append(f"H6: {case} command failed")

supported = load_json("routes-supported-types.json")
expected = {
    "203.0.113.0/25": ("blackhole", 71, 101),
    "203.0.113.128/26": ("unreachable", 72, 102),
    "203.0.113.192/27": ("prohibit", 73, 103),
    "203.0.113.224/28": ("throw", 74, 104),
    "default": (None, 75, 105),
}
for dst, (route_type, proto, metric) in expected.items():
    rows = find_route(supported, dst)
    if len(rows) != 1:
        failures.append(f"H6: expected one {dst} entry, got {rows!r}")
        continue
    row = rows[0]
    observations.append(f"H6 {dst} entry={json.dumps(row, sort_keys=True)}")
    if route_type is None:
        if row.get("type") not in (None, "unicast"):
            failures.append(f"H6: default route type mismatch: {row.get('type')!r}")
    elif row.get("type") != route_type:
        failures.append(f"H6: {dst} route type mismatch: {row.get('type')!r}")
    if protocol_value(row) not in (proto, str(proto)):
        failures.append(f"H6: {dst} protocol mismatch: {protocol_value(row)!r}")
    if row.get("metric") != metric:
        failures.append(f"H6: {dst} metric mismatch: {row.get('metric')!r}")

lines = [
    "EXP-002 kernel route/address adapter live smoke",
    "",
    "H1 numeric route protocol inventory: " + ("PASS" if not any(x.startswith("H1:") for x in failures) else "FAIL"),
    "H2 UNICAST add -> replace -> delete: " + ("PASS" if not any(x.startswith("H2:") for x in failures) else "FAIL"),
    "H3 BLACKHOLE add -> delete: " + ("PASS" if not any(x.startswith("H3:") for x in failures) else "FAIL"),
    "H4 RTPROT_BOOT normalization/delete: " + ("PASS" if not any(x.startswith("H4:") for x in failures) else "FAIL"),
    "H5 IPv4 address local/peer/empty interface shape: " + ("PASS" if not any(x.startswith("H5:") for x in failures) else "FAIL"),
    "H6 supported route types/default JSON shape: " + ("PASS" if not any(x.startswith("H6:") for x in failures) else "FAIL"),
    "",
]
lines.extend(observations)
lines.append("")
if failures:
    lines.append("OVERALL=FAIL")
    lines.append("")
    lines.extend(f"FAIL: {failure}" for failure in failures)
else:
    lines.append("OVERALL=PASS")
    lines.append(
        "Interpretation: RC2.4 route/address adapter assumptions match the tested "
        "Debian 13 iproute2 behavior."
    )

(out / "result.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
sys.exit(1 if failures else 0)
PY
ANALYZE_RC=$?
set -e

cleanup
trap - EXIT INT TERM

{
    echo
    echo "files:"
    find "$OUT" -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort
} >>"$OUT/environment.txt"

tar -czf "$ARCHIVE" "$OUT"
sha256sum "$ARCHIVE" >"${ARCHIVE}.sha256"

cat "$OUT/result.txt"
echo
echo "Artifacts:"
echo "  $OUT/"
echo "  $ARCHIVE"
echo "  ${ARCHIVE}.sha256"

exit "$ANALYZE_RC"
