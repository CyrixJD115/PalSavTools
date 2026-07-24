#!/usr/bin/env bash
# Fetch python-build-standalone (install_only_stripped) for the host triple
# into ./python/, so the POC runs without a system Python install.
#
# Usage:  scripts/fetch_pbs.sh [target-triple]
# Default target-triple = $(rustc -vV | sed -n 's/^host: //p')
set -euo pipefail

PBS_TAG="20260718"          # astral-sh/python-build-standalone release
PY_VERSION="3.13.14"        # CPython version shipped in that release

cd "$(dirname "$0")/.."

TARGET="${1:-$(rustc -vV | sed -n 's/^host: //p')}"
ASSET="cpython-${PY_VERSION}+${PBS_TAG}-${TARGET}-install_only_stripped.tar.gz"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/${ASSET}"

if [ -x "python/bin/python3" ]; then
  echo "python/ already present ($(./python/bin/python3 --version))"
  exit 0
fi

echo "Fetching $ASSET ..."
curl -fSL --retry 3 -o pbs.tar.gz "$URL"
tar -xzf pbs.tar.gz
rm -f pbs.tar.gz
echo "Done: $(./python/bin/python3 --version) at python/ (target: $TARGET)"
