#!/bin/sh

set -eu

if [ "$#" -ne 6 ]; then
  echo "usage: $0 NETWORK_UNIX_ROOT IMP11A_ROOT PDP11_BIN BASE_ROOT BASE_SWAP BUILD_ROOT" >&2
  exit 64
fi

network_unix_root=$(CDPATH= cd -- "$1" && pwd)
imp11a_root=$(CDPATH= cd -- "$2" && pwd)
pdp11_bin="$(CDPATH= cd -- "$(dirname "$3")" && pwd)/$(basename "$3")"
base_root="$(CDPATH= cd -- "$(dirname "$4")" && pwd)/$(basename "$4")"
base_swap="$(CDPATH= cd -- "$(dirname "$5")" && pwd)/$(basename "$5")"
build_root_input=$6
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
python_program=${PYTHON:-python3}
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps

for required in "$pdp11_bin" "$base_root" "$base_swap"; do
  if [ ! -f "$required" ]; then
    echo "missing PDP-11 build input: $required" >&2
    exit 66
  fi
done

"$python_program" "$repo_root/scripts/pdp11_base.py" verify "$base_root" "$base_swap"
brfid_acquire_exclusive_lease "$build_root_input.lock"
"$repo_root/scripts/verify-simulator-binaries.py" --pdp11 "$pdp11_bin"
brfid_create_results_dir "$build_root_input"
build_root=$BRFID_RESULTS_DIR
telnet_build="$build_root/telnet"
ncpd_build="$build_root/ncpd"

"$python_program" "$repo_root/scripts/research/build-guest-telnet.py" \
  --network-unix-v6-root "$network_unix_root" \
  --pdp11 "$pdp11_bin" \
  --root-image "$base_root" \
  --swap-image "$base_swap" \
  --work-dir "$telnet_build"

"$python_program" "$repo_root/scripts/research/build-guest-ncpd.py" \
  --network-unix-v6-root "$network_unix_root" \
  --pdp11 "$pdp11_bin" \
  --root-image "$telnet_build/guest/images/ncp_root.rl01" \
  --swap-image "$telnet_build/guest/images/ncp_swap.rl01" \
  --work-dir "$ncpd_build"

"$repo_root/scripts/pdp11-build-receipt.py" write \
  "$network_unix_root" \
  "$imp11a_root" \
  "$pdp11_bin" \
  "$base_root" \
  "$base_swap" \
  "$telnet_build" \
  "$ncpd_build" \
  "$build_root/pdp11-build-receipt.json"

brfid_cleanup
echo "PASS: built receipt-bound PDP-11 TELNET media in $build_root"
