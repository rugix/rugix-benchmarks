#!/usr/bin/env bash
set -euo pipefail
mkdir -p /etc/systemd/network
cat >/etc/systemd/network/10-management.network <<'NETWORK'
[Match]
Name=en* eth*
[Network]
DHCP=ipv4
LinkLocalAddressing=no
IPv6AcceptRA=no
NETWORK
systemctl enable systemd-networkd.service systemd-resolved.service ssh.service
ln -sf /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
