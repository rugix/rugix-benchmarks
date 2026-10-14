#!/bin/bash
# Create a private Linux link with receiver-side kernel delay and shaping.
set -euo pipefail
BENCH_DELAY="${1:?one-way delay in milliseconds}"
BENCH_RATE="${2:?link rate in bits per second}"
for BENCH_MODULE in sch_netem sch_tbf ifb veth act_mirred cls_matchall; do
    modprobe "$BENCH_MODULE"
done
ip netns add bench-origin
ip link add bench-client address 52:54:00:ca:00:01 type veth peer name bench-server
ip link set bench-server netns bench-origin
sysctl -qw net.ipv6.conf.bench-client.disable_ipv6=1
ip netns exec bench-origin sysctl -qw net.ipv6.conf.all.disable_ipv6=1
ip netns exec bench-origin sysctl -qw net.ipv6.conf.default.disable_ipv6=1
ip link set bench-client mtu 1500 up
ip address add 10.0.3.15/24 dev bench-client
ip netns exec bench-origin ip link set lo up
ip netns exec bench-origin ip link set bench-server address 52:54:00:ca:00:02 mtu 1500 up
ip netns exec bench-origin ip address add 10.0.3.2/24 dev bench-server
ethtool -K bench-client tso off gso off gro off
ip netns exec bench-origin ethtool -K bench-server tso off gso off gro off
ip link add bench-ifb type ifb
ip link set bench-ifb up
ip netns exec bench-origin ip link add bench-ifb type ifb
ip netns exec bench-origin ip link set bench-ifb up
tc qdisc add dev bench-client handle ffff: ingress
tc filter add dev bench-client parent ffff: protocol all matchall action mirred egress redirect dev bench-ifb
ip netns exec bench-origin tc qdisc add dev bench-server handle ffff: ingress
ip netns exec bench-origin tc filter add dev bench-server parent ffff: protocol all matchall action mirred egress redirect dev bench-ifb
tc qdisc replace dev bench-ifb root handle 1: tbf rate "${BENCH_RATE}bit" burst 256kb limit 8mb
tc qdisc replace dev bench-ifb parent 1:1 handle 10: netem delay "${BENCH_DELAY}ms" limit 10000
ip netns exec bench-origin tc qdisc replace dev bench-ifb root handle 1: tbf rate "${BENCH_RATE}bit" burst 256kb limit 8mb
ip netns exec bench-origin tc qdisc replace dev bench-ifb parent 1:1 handle 10: netem delay "${BENCH_DELAY}ms" limit 10000
ip -4 route get 10.0.3.2
ip netns exec bench-origin ip -4 route get 10.0.3.15
