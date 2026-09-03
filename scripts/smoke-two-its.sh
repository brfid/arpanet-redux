#!/bin/sh

set -eu

if [ "$#" -ne 6 ]; then
  echo "usage: $0 ARPANET_ROOT ITS_ROOT H316_BIN PDP10_KA_BIN ITS_BUILD_RECEIPT RESULTS_DIR" >&2
  exit 64
fi

arpanet_root=$(CDPATH= cd -- "$1" && pwd)
its_root=$(CDPATH= cd -- "$2" && pwd)
h316_bin="$(CDPATH= cd -- "$(dirname "$3")" && pwd)/$(basename "$3")"
pdp10_bin="$(CDPATH= cd -- "$(dirname "$4")" && pwd)/$(basename "$4")"
its_build_receipt="$(CDPATH= cd -- "$(dirname "$5")" && pwd)/$(basename "$5")"
results_dir_input=$6
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps
mini_dir="$arpanet_root/mini"
its_host_base="$mini_dir/host70/106"
its_peer_base="$its_root/out/pdp10-ka"

for required in "$h316_bin" "$pdp10_bin" "$its_build_receipt" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh"; do
  if [ ! -e "$required" ]; then
    echo "missing required asset: $required" >&2
    exit 66
  fi
done
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  for source_dir in "$its_host_base" "$its_peer_base"; do
    if [ ! -f "$source_dir/$asset" ]; then
      echo "missing required ITS media: $source_dir/$asset" >&2
      exit 66
    fi
  done
done

brfid_acquire_exclusive_lease "$its_root/.brfid-build.lock"
"$repo_root/scripts/its-build-receipt.py" verify "$its_root" "$its_build_receipt"
"$repo_root/scripts/verify-simulator-binaries.py" --h316 "$h316_bin" --pdp10-ka "$pdp10_bin"

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" two-its-telnet "$repo_root"
brfid_manifest_add_git arpanet-in-a-box "$arpanet_root"
brfid_manifest_add_git pdp10-its "$its_root"
brfid_manifest_add_git h316-simh "$(git -C "$(dirname "$h316_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git ka10-simh "$(git -C "$(dirname "$pdp10_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_file its-build-receipt "$its_build_receipt" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file h316 "$h316_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp10-ka "$pdp10_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp6-config "$repo_root/config/imp/its-pair/imp6.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp62-config "$repo_root/config/imp/its-pair/imp62.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file host106-config "$repo_root/config/hosts/its106-pair.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file host176-config "$repo_root/config/hosts/its176-pair.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-manifest "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"

its_host_work="$results_dir/host106"
its_peer_work="$results_dir/host176"
mkdir -p "$its_host_work" "$its_peer_work"
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if ! cp -c -p "$its_host_base/$asset" "$its_host_work/$asset" 2>/dev/null; then
    cp -p "$its_host_base/$asset" "$its_host_work/$asset"
  fi
  if ! cp -c -p "$its_peer_base/$asset" "$its_peer_work/$asset" 2>/dev/null; then
    cp -p "$its_peer_base/$asset" "$its_peer_work/$asset"
  fi
  brfid_manifest_add_file "host106-$asset" "$its_host_work/$asset" "$repo_root/scripts/sha256-file.sh"
  brfid_manifest_add_file "host176-$asset" "$its_peer_work/$asset" "$repo_root/scripts/sha256-file.sh"
done

brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 6 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_two_host_ports
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
brfid_manifest_append udp.imp6.mi "$BRFID_IMP6_MI_PORT"
brfid_manifest_append udp.imp62.mi "$BRFID_IMP62_MI_PORT"
brfid_manifest_append udp.imp6.hi "$BRFID_IMP6_HI_PORT"
brfid_manifest_append udp.host106.imp "$BRFID_HOST_A_IMP_PORT"
brfid_manifest_append udp.imp62.hi "$BRFID_IMP62_HI_PORT"
brfid_manifest_append udp.host176.imp "$BRFID_HOST_B_IMP_PORT"
brfid_make_private_socket_dir
brfid_release_udp_lease_for_launch

brfid_start_process controller "$repo_root" "$results_dir/controller.stdout.log" "$results_dir/controller.stderr.log" \
  python3 "$repo_root/scripts/two-its-controller.py" \
  --h316 "$h316_bin" \
  --pdp10-ka "$pdp10_bin" \
  --mini-root "$mini_dir" \
  --its-host-work "$its_host_work" \
  --its-peer-work "$its_peer_work" \
  --imp6-config "$repo_root/config/imp/its-pair/imp6.simh" \
  --imp62-config "$repo_root/config/imp/its-pair/imp62.simh" \
  --its-host-config "$repo_root/config/hosts/its106-pair.simh" \
  --its-peer-config "$repo_root/config/hosts/its176-pair.simh" \
  --results-dir "$results_dir" \
  --manifest "$runtime_dir/run.env" \
  --ncc-observation-stream "$results_dir/ncc-observations.jsonl" >/dev/null
controller_pid=$BRFID_LAST_PID
if wait "$controller_pid"; then
  controller_status=0
else
  controller_status=$?
fi
brfid_unregister_pid "$controller_pid"
if [ "$controller_status" -ne 0 ]; then
  echo "two-ITS controller failed; see $results_dir/controller.stderr.log" >&2
  exit "$controller_status"
fi

grep -Fxq "passed" "$results_dir/outcome.txt"
grep -Fq "source_sha256=" "$results_dir/sentinel-evidence.txt"
grep -Fq "recovered_sha256=" "$results_dir/sentinel-evidence.txt"
brfid_assert_no_transport_errors "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$results_dir/host106.console.log" "$results_dir/host176.console.log"
brfid_cleanup
echo "PASS: host 176 used UT and TELSER to exchange a guest-originated payload with ITS host 106 through two recovered IMPs."
brfid_mark_run_passed
