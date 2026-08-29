#!/bin/sh
# Restrict this netns (Home Assistant) to private networks + Docker DNS.
# Physical IoT devices are not NATed through this box; the house router
# must also deny WAN for the IoT VLAN. This stops HA Core from reaching
# Nabu Casa, Tuya cloud, GitHub, analytics, etc.
set -eu

filter_ready() {
  iptables -C OUTPUT -j HA-PRIVACY 2>/dev/null
}

ensure_chain() {
  iptables -N HA-PRIVACY 2>/dev/null || iptables -F HA-PRIVACY
  iptables -A HA-PRIVACY -o lo -j ACCEPT
  iptables -A HA-PRIVACY -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
    iptables -A HA-PRIVACY -m state --state ESTABLISHED,RELATED -j ACCEPT
  iptables -A HA-PRIVACY -d 127.0.0.0/8 -j ACCEPT
  iptables -A HA-PRIVACY -d 10.0.0.0/8 -j ACCEPT
  iptables -A HA-PRIVACY -d 172.16.0.0/12 -j ACCEPT
  iptables -A HA-PRIVACY -d 192.168.0.0/16 -j ACCEPT
  iptables -A HA-PRIVACY -d 169.254.0.0/16 -j ACCEPT
  iptables -A HA-PRIVACY -d 224.0.0.0/4 -j ACCEPT
  iptables -A HA-PRIVACY -j REJECT --reject-with icmp-net-prohibited
  if ! filter_ready; then
    iptables -I OUTPUT 1 -j HA-PRIVACY
  fi
}

ensure_v6() {
  if ! command -v ip6tables >/dev/null 2>&1; then
    return 0
  fi
  ip6tables -N HA-PRIVACY 2>/dev/null || ip6tables -F HA-PRIVACY
  ip6tables -A HA-PRIVACY -o lo -j ACCEPT
  ip6tables -A HA-PRIVACY -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT 2>/dev/null || \
    ip6tables -A HA-PRIVACY -m state --state ESTABLISHED,RELATED -j ACCEPT
  ip6tables -A HA-PRIVACY -d ::1/128 -j ACCEPT
  ip6tables -A HA-PRIVACY -d fe80::/10 -j ACCEPT
  ip6tables -A HA-PRIVACY -d fc00::/7 -j ACCEPT
  ip6tables -A HA-PRIVACY -d ff00::/8 -j ACCEPT
  ip6tables -A HA-PRIVACY -j REJECT --reject-with icmp6-adm-prohibited
  ip6tables -C OUTPUT -j HA-PRIVACY 2>/dev/null || ip6tables -I OUTPUT 1 -j HA-PRIVACY
}

lan_socks() {
  # Docker Desktop lab only: house LAN TCP via Windows SOCKS5.
  iptables -t nat -C OUTPUT -p tcp -d 192.168.0.0/24 -j REDIRECT --to-ports 12345 2>/dev/null || \
    iptables -t nat -A OUTPUT -p tcp -d 192.168.0.0/24 -j REDIRECT --to-ports 12345
}

ensure_chain
ensure_v6
if [ "${ENABLE_LAN_SOCKS:-1}" = "1" ]; then
  lan_socks
fi
echo "HA privacy egress installed (LAN/VPN only)"
