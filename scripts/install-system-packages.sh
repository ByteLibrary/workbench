#!/usr/bin/env bash
# Installs what the development machine needs from Ubuntu's package manager, and only that (ADR-0028 of
# the handbook): bootstrapping (git, curl, CA certificates), avahi-daemon, which announces the machine as
# bytelibrary.local so editors find it after its address changes, dnsmasq and nftables for the site
# allowlist (scripts/firewall.py), and Docker Engine from Docker's repository. Every other tool comes from
# mise. Safe to run again.
source "$(dirname "$0")/lib.sh"

[[ "$(. /etc/os-release && echo "$ID")" == ubuntu ]] || fail "The development machine runs Ubuntu; this is not Ubuntu."

packages=(git curl ca-certificates avahi-daemon dnsmasq-base nftables)
missing=()
for package in "${packages[@]}"; do
  dpkg-query --show --showformat='${Status}' "$package" 2>/dev/null | grep -q "install ok installed" || missing+=("$package")
done
if ((${#missing[@]} > 0)); then
  info "Installing ${missing[*]}"
  sudo apt-get update --quiet --quiet
  sudo apt-get install --yes --quiet --quiet "${missing[@]}"
fi
ok "System packages: ${packages[*]}"

if ! command -v docker >/dev/null; then
  info "Installing Docker Engine from Docker's repository"
  sudo install -m 0755 -d /etc/apt/keyrings
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
  codename="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $codename stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
  sudo apt-get update --quiet --quiet
  sudo apt-get install --yes --quiet --quiet docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
ok "Docker Engine"

if ! id -nG "$USER" | tr ' ' '\n' | grep -qx docker; then
  sudo usermod --append --groups docker "$USER"
  warn "You were added to the docker group; it takes effect in new sessions (reconnect to the machine)."
fi
