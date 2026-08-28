#!/bin/sh

set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 ARPANET_ROOT" >&2
  exit 64
fi

arpanet_root=$1
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
checksum_file="$repo_root/pins/arpanet-assets.sha256"

if [ ! -d "$arpanet_root/mini" ]; then
  echo "not an ARPANET in a Box checkout: $arpanet_root" >&2
  exit 66
fi

if command -v shasum >/dev/null 2>&1; then
  (cd "$arpanet_root" && shasum -a 256 -c "$checksum_file")
elif command -v sha256sum >/dev/null 2>&1; then
  (cd "$arpanet_root" && sha256sum -c "$checksum_file")
else
  echo "neither shasum nor sha256sum is available" >&2
  exit 69
fi
