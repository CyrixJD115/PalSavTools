#!/usr/bin/env bash
# PalworldSaveTools — Linux setup dispatcher.
#
# Detects the host's package manager and delegates to the matching per-distro
# installer in this directory. Lets you just tell users "run setup/linux.sh"
# without making them identify their own distro family first.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ -x /usr/bin/pacman ]]; then
    exec "$HERE/linux-arch.sh" "$@"
elif [[ -x /usr/bin/apt-get ]]; then
    exec "$HERE/linux-debian.sh" "$@"
elif [[ -x /usr/bin/dnf ]]; then
    exec "$HERE/linux-fedora.sh" "$@"
fi

cat >&2 <<EOF
Could not detect a supported package manager (looked for pacman, apt-get, dnf).

Supported distro families: Arch, Debian/Ubuntu, Fedora/RHEL.
For anything else, install the equivalents manually — see setup/README.md for
the per-package mapping, then run:

    python3 setup/check_env.py

to verify the environment is complete.
EOF
exit 1
