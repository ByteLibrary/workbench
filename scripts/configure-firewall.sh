#!/usr/bin/env bash
# Installs the site allowlist (scripts/firewall.sh): a systemd service that applies it at boot and
# whenever a sites file changes, the local resolver as the machine's and containers' DNS, and the
# firewall rules. Safe to run again.
source "$(dirname "$0")/lib.sh"

personal_sites="$HOME/.config/bytelibrary/allowed-sites"
mkdir -p "$(dirname "$personal_sites")"
if [[ ! -f "$personal_sites" ]]; then
  printf '%s\n' "# Sites allowed only on this machine, one domain per line; each covers its subdomains." \
    "# Applied as soon as this file changes. See workbench's firewall/allowed-sites.txt." >"$personal_sites"
fi

# Writes a root-owned file from standard input, and reports whether it changed.
write_system_file() {
  local file="$1" content
  content="$(cat)"
  if [[ -f "$file" ]] && [[ "$(sudo cat "$file")" == "$content" ]]; then return 1; fi
  sudo install -d -m 0755 "$(dirname "$file")"
  printf '%s\n' "$content" | sudo tee "$file" >/dev/null
}

changed=0
write_system_file /etc/systemd/system/bytelibrary-dns.service <<EOF && changed=1
[Unit]
Description=ByteLibrary allowlist resolver (workbench scripts/firewall.sh)
After=network.target

[Service]
ExecStart=/usr/sbin/dnsmasq --keep-in-foreground --conf-file=/etc/bytelibrary/dnsmasq.conf
Restart=on-failure
EOF
write_system_file /etc/systemd/system/bytelibrary-firewall.service <<EOF && changed=1
[Unit]
Description=ByteLibrary site allowlist (workbench scripts/firewall.sh)
After=network.target docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
# Services start without HOME, which the scripts' shared settings use.
Environment=HOME=/root
Environment=BYTELIBRARY_PERSONAL_SITES=$personal_sites
ExecStart=$REPOSITORY_DIR/scripts/firewall.sh apply

[Install]
WantedBy=multi-user.target
EOF
write_system_file /etc/systemd/system/bytelibrary-firewall.path <<EOF && changed=1
[Unit]
Description=Apply the ByteLibrary site allowlist when a sites file changes

[Path]
PathChanged=$REPOSITORY_DIR/firewall/allowed-sites.txt
PathChanged=$personal_sites
Unit=bytelibrary-firewall.service

[Install]
WantedBy=multi-user.target
EOF
if ((changed)); then sudo systemctl daemon-reload; fi
sudo systemctl enable --quiet bytelibrary-firewall.service bytelibrary-firewall.path
if ! sudo systemctl restart bytelibrary-firewall.service; then
  sudo journalctl --unit bytelibrary-firewall.service --unit bytelibrary-dns.service --lines 15 --no-pager --output cat |
    while read -r line; do warn "$line"; done
  fail "The site allowlist did not start; its log is above."
fi
sudo systemctl start bytelibrary-firewall.path

# The machine asks the allowlist resolver; systemd-resolved keeps tracking the network's DNS servers,
# which the resolver forwards allowed names to.
if write_system_file /etc/systemd/resolved.conf.d/bytelibrary.conf <<<$'[Resolve]\nDNSStubListener=no'; then
  sudo systemctl restart systemd-resolved
fi
if [[ -L /etc/resolv.conf ]] || ! grep -qx 'nameserver 127.0.0.1' /etc/resolv.conf; then
  sudo rm -f /etc/resolv.conf
  printf '%s\n' "# The allowlist resolver (workbench scripts/firewall.sh)." "nameserver 127.0.0.1" |
    sudo tee /etc/resolv.conf >/dev/null
fi

# Containers ask the same resolver, on Docker's bridge.
docker_config=/etc/docker/daemon.json
docker_dns="$(sudo cat "$docker_config" 2>/dev/null | python3 -c '
import json, sys
text = sys.stdin.read()
config = json.loads(text) if text.strip() else {}
config["dns"] = ["172.17.0.1"]
print(json.dumps(config, indent=2))')"
if write_system_file "$docker_config" <<<"$docker_dns"; then
  sudo systemctl restart docker
fi

ok "Firewall: only allowed sites are reachable (scripts/firewall.sh blocked shows what was refused)"
