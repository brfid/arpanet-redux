#!/bin/sh

set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 ARPANET_ROOT H316_BIN RESULTS_DIR" >&2
  exit 64
fi

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/ncc-line-scenario.sh"

brfid_run_ncc_line_scenario loopback "$repo_root" "$@"
