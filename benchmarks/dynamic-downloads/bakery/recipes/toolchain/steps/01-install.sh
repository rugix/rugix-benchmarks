#!/usr/bin/env bash
set -euo pipefail
tar -xzf "${RECIPE_DIR}/files/runtime.tar.gz" -C /
install -D -m 0600 "${RECIPE_DIR}/files/id_rsa.pub" /root/.ssh/authorized_keys
install -D -m 0644 "${RECIPE_DIR}/files/ca.crt" /etc/rauc/ca.cert.pem
install -D -m 0644 "${RECIPE_DIR}/files/rauc-dbus.conf" /usr/share/dbus-1/system.d/de.pengutronix.rauc.conf
printf 'PasswordAuthentication no\nPermitRootLogin prohibit-password\n' >/etc/ssh/sshd_config.d/benchmark.conf
