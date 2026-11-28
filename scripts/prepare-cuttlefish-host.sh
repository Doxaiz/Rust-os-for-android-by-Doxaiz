#!/usr/bin/env bash
# DISPOSABLE ubuntu-24.04 GitHub hosted VM only: modifies KVM/group/AppArmor.
# No images downloaded and no cloud resources created by this script.
set -euo pipefail
[ "${GITHUB_ACTIONS:-}" = true ] && [ "${RUNNER_ENVIRONMENT:-}" = github-hosted ] || {
    echo 'Refusing system changes outside a GitHub hosted disposable runner' >&2
    exit 1
}
# shellcheck disable=SC1091
. /etc/os-release
[ "$ID" = ubuntu ] && [ "$VERSION_ID" = 24.04 ] || { echo 'Expected Ubuntu 24.04' >&2; exit 1; }
[ -e /dev/kvm ]
echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' |
    sudo tee /etc/udev/rules.d/99-kvm4all.rules >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger --name-match=kvm
sudo curl --fail --silent --show-error --location --retry 5 \
    --output /etc/apt/trusted.gpg.d/android-cuttlefish.asc \
    https://us-apt.pkg.dev/doc/repo-signing-key.gpg
echo 'deb https://us-apt.pkg.dev/projects/android-cuttlefish-artifacts android-cuttlefish main' |
    sudo tee /etc/apt/sources.list.d/android-cuttlefish.list >/dev/null
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends cuttlefish-base
sudo usermod -aG kvm,cvdnetwork,render "$(id -un)"
sudo modprobe -a vhost_vsock vhost_net
sudo systemctl restart cuttlefish-host-resources
if [ -e /proc/sys/kernel/apparmor_restrict_unprivileged_userns ]; then
    sudo sysctl -q -w kernel.apparmor_restrict_unprivileged_userns=0
fi
ip -brief link show | grep cvd
