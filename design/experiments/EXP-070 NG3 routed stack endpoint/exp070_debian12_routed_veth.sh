#!/bin/sh
set -eu

H=e70d12h
S=e70d12s
L=e70d12l
R=e70d12r

cleanup() {
  ip netns del "$R" 2>/dev/null || true
  ip netns del "$L" 2>/dev/null || true
  ip netns del "$S" 2>/dev/null || true
  ip netns del "$H" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for ns in "$H" "$S" "$L" "$R"; do
  ip netns add "$ns"
  ip -n "$ns" link set lo up
done

ip link add hlan type veth peer name lhost
ip link set hlan netns "$H"
ip link set lhost netns "$L"

ip link add sremote type veth peer name rstack
ip link set sremote netns "$S"
ip link set rstack netns "$R"

ip link add vpng0 type veth peer name stack0
ip link set vpng0 netns "$H"
ip link set stack0 netns "$S"

ip -n "$H" addr add 192.0.2.1/24 dev hlan
ip -n "$L" addr add 192.0.2.2/24 dev lhost
ip -n "$S" addr add 198.51.100.1/30 dev sremote
ip -n "$R" addr add 198.51.100.2/30 dev rstack
ip -n "$R" addr add 10.70.0.2/32 dev lo

for x in hlan; do ip -n "$H" link set "$x" up; done
for x in lhost; do ip -n "$L" link set "$x" up; done
for x in sremote stack0; do ip -n "$S" link set "$x" up; done
for x in rstack; do ip -n "$R" link set "$x" up; done
ip -n "$H" link set vpng0 up

ip netns exec "$H" sysctl -qw net.ipv4.ip_forward=1
ip netns exec "$S" sysctl -qw net.ipv4.ip_forward=1
for spec in "$H:all" "$H:default" "$H:hlan" "$H:vpng0" "$S:all" "$S:default" "$S:sremote" "$S:stack0"; do
  ns=${spec%%:*}; iface=${spec#*:}
  ip netns exec "$ns" sysctl -qw "net.ipv4.conf.$iface.rp_filter=0"
done

ip -n "$L" route add 10.70.0.2/32 via 192.0.2.1 dev lhost
ip -n "$S" route add 10.70.0.2/32 via 198.51.100.2 dev sremote
ip -n "$R" route add 192.0.2.2/32 via 198.51.100.1 dev rstack

ip -n "$H" route add 10.70.0.2/32 dev vpng0
ip -n "$S" route add 192.0.2.2/32 dev stack0

echo "EXP070_D12_KERNEL=$(uname -r)"
echo "EXP070_D12_OS=$(sed -n 's/^PRETTY_NAME=//p' /etc/os-release | tr -d '"')"
echo "EXP070_D12_IP=$(ip -V)"

if ip netns exec "$L" ping -n -c 1 -W 1 10.70.0.2 >/tmp/no-proxy.out 2>&1; then
  echo "EXP070_D12_NO_PROXY=UNEXPECTED_PASS"
  cat /tmp/no-proxy.out
  exit 1
fi
echo "EXP070_D12_NO_PROXY=EXPECTED_FAIL"
echo "EXP070_D12_NO_PROXY_HOST_NEIGH=$(ip -n "$H" neigh show dev vpng0 | tr '\n' ';')"

ip -n "$H" neigh flush dev vpng0 || true
ip -n "$S" neigh flush dev stack0 || true
ip netns exec "$H" sysctl -qw net.ipv4.conf.vpng0.proxy_arp=1
ip netns exec "$S" sysctl -qw net.ipv4.conf.stack0.proxy_arp=1

if ! ip netns exec "$L" ping -n -c 2 -W 2 10.70.0.2 >/tmp/proxy.out 2>&1; then
  echo "EXP070_D12_PROXY_ARP=FAIL"
  cat /tmp/proxy.out
  echo "HOST_NEIGH=$(ip -n "$H" neigh show dev vpng0 | tr '\n' ';')"
  echo "STACK_NEIGH=$(ip -n "$S" neigh show dev stack0 | tr '\n' ';')"
  exit 1
fi

echo "EXP070_D12_PROXY_ARP=PASS"
echo "EXP070_D12_HOST_ROUTE=$(ip -n "$H" route show 10.70.0.2/32)"
echo "EXP070_D12_STACK_ROUTE=$(ip -n "$S" route show 192.0.2.2/32)"
echo "EXP070_D12_HOST_NEIGH=$(ip -n "$H" neigh show dev vpng0 | tr '\n' ';')"
echo "EXP070_D12_STACK_NEIGH=$(ip -n "$S" neigh show dev stack0 | tr '\n' ';')"
echo "EXP070_D12_RESULT=PASS"
