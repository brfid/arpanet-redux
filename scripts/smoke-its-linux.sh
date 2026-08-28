#!/bin/sh

set -eu

if [ "$#" -ne 6 ]; then
  echo "usage: $0 ARPANET_ROOT LINUX_NCP_ROOT H316_BIN PDP10_KA_BIN NCP_BUILD_RECEIPT RESULTS_DIR" >&2
  exit 64
fi

arpanet_root=$(CDPATH= cd -- "$1" && pwd)
linux_ncp_root=$(CDPATH= cd -- "$2" && pwd)
h316_bin="$(CDPATH= cd -- "$(dirname "$3")" && pwd)/$(basename "$3")"
pdp10_bin="$(CDPATH= cd -- "$(dirname "$4")" && pwd)/$(basename "$4")"
ncp_build_receipt=$5
results_dir_input=$6
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps
mini_dir="$arpanet_root/mini"
host70_base="$mini_dir/host70/106"
ncpd="$linux_ncp_root/src/ncpd"
ping_bin="$linux_ncp_root/apps/ncp-ping"
test_dir="$linux_ncp_root/test"

for required in "$h316_bin" "$pdp10_bin" "$ncpd" "$ping_bin" "$ncp_build_receipt" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh" "$host70_base/dskdmp.rim" "$host70_base/rp03.0" "$host70_base/rp03.1" "$host70_base/rp03.2" "$host70_base/rp03.3"; do
  if [ ! -e "$required" ]; then
    echo "missing required asset: $required" >&2
    exit 66
  fi
done


brfid_acquire_exclusive_lease "$linux_ncp_root/.brfid-build.lock"
"$repo_root/scripts/ncp-build-receipt.py" verify "$linux_ncp_root" "$ncp_build_receipt"
"$repo_root/scripts/verify-simulator-binaries.py" --h316 "$h316_bin" --pdp10-ka "$pdp10_bin"

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" its-linux "$repo_root"
brfid_manifest_add_git arpanet-in-a-box "$arpanet_root"
brfid_manifest_add_git linux-ncp "$linux_ncp_root"
brfid_manifest_add_git h316-simh "$(git -C "$(dirname "$h316_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git ka10-simh "$(git -C "$(dirname "$pdp10_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_file ncpd "$ncpd" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file ncp-ping "$ping_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file ncp-build-receipt "$ncp_build_receipt" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file h316 "$h316_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp10-ka "$pdp10_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp6-config "$repo_root/config/imp/mixed/imp6.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp62-config "$repo_root/config/imp/mixed/imp62.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file its70-config "$repo_root/config/hosts/its70-mixed.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-manifest "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"
host70_work="$results_dir/host70"
mkdir -p "$host70_work"
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if ! cp -c -p "$host70_base/$asset" "$host70_work/$asset" 2>/dev/null; then
    cp -p "$host70_base/$asset" "$host70_work/$asset"
  fi
done
brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 6 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_two_host_ports
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
brfid_manifest_append udp.imp6.mi "$BRFID_IMP6_MI_PORT"
brfid_manifest_append udp.imp62.mi "$BRFID_IMP62_MI_PORT"
brfid_manifest_append udp.imp6.hi "$BRFID_IMP6_HI_PORT"
brfid_manifest_append udp.host106.imp "$BRFID_HOST_A_IMP_PORT"
brfid_manifest_append udp.imp62.hi "$BRFID_IMP62_HI_PORT"
brfid_manifest_append udp.host076.imp "$BRFID_HOST_B_IMP_PORT"
brfid_make_private_socket_dir
brfid_ncp_socket host62
ncp62_socket=$BRFID_NCP_SOCKET
brfid_release_udp_lease_for_launch

brfid_start_process ncp62 "$test_dir" "$results_dir/ncp62.stdout.log" "$results_dir/ncp62.debug.log" env NCP="$ncp62_socket" "$ncpd" 127.0.0.1 "$BRFID_IMP62_HI_PORT" "$BRFID_HOST_B_IMP_PORT"
brfid_start_process imp6 "$mini_dir" "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$h316_bin" "$repo_root/config/imp/mixed/imp6.simh"
brfid_start_process imp62 "$mini_dir" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$h316_bin" "$repo_root/config/imp/mixed/imp62.simh"
brfid_start_process host70 "$host70_work" "$results_dir/host70.console.log" "$results_dir/host70.debug.log" "$pdp10_bin" "$repo_root/config/hosts/its70-mixed.simh"

elapsed=0
booted=0
while [ "$elapsed" -lt 300 ]; do
  sleep 5
  elapsed=$((elapsed + 5))
  brfid_assert_managed_alive
  brfid_assert_no_transport_errors "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$results_dir/host70.console.log" "$results_dir/host70.debug.log"
  if grep -Fq "IN OPERATION" "$results_dir/host70.console.log"; then
    booted=1
    break
  fi
done

if [ "$booted" -ne 1 ]; then
  echo "ITS did not reach its operational banner within ${elapsed}s" >&2
  exit 1
fi

grep -Fq "IN OPERATION" "$results_dir/host70.console.log"

ncp_ready=0
ncp_deadline=$(($(date +%s) + 90))
while [ "$(date +%s)" -lt "$ncp_deadline" ]; do
  brfid_assert_managed_alive
  brfid_assert_no_transport_errors "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$results_dir/host70.console.log" "$results_dir/host70.debug.log"
  ncp_remaining=$((ncp_deadline - $(date +%s)))
  if [ "$ncp_remaining" -lt 1 ]; then
    break
  fi
  if [ "$ncp_remaining" -gt 10 ]; then
    ncp_probe_limit=10
  else
    ncp_probe_limit=$ncp_remaining
  fi
  if brfid_run_ncp_client_bounded "$ncp_probe_limit" env NCP="$ncp62_socket" "$ping_bin" -c1 70 >"$results_dir/ping-readiness.log" 2>&1; then
    ncp_ready=1
    break
  fi
  sleep 2
done

if [ "$ncp_ready" -ne 1 ]; then
  echo "ITS NCP did not answer within 90s of the operational banner" >&2
  exit 1
fi

brfid_run_ncp_client_bounded 30 env NCP="$ncp62_socket" "$ping_bin" -c3 70 >"$results_dir/ping-its-host-106.log" 2>&1
grep -Fq "packet received" "$results_dir/imp6.debug.log"
grep -Fq "packet received" "$results_dir/imp62.debug.log"
"$repo_root/scripts/assert-log-evidence.py" mixed-conversion "$results_dir/imp6.debug.log" "$results_dir/ping-its-host-106.log"
brfid_assert_managed_alive
brfid_assert_no_transport_errors "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$results_dir/host70.console.log" "$results_dir/host70.debug.log"
brfid_cleanup
echo "PASS: Linux NCP host 076 reached KA10/ITS host 106 through exactly two recovered 1973 IMPs."
brfid_mark_run_passed
