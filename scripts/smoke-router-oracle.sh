#!/bin/sh

set -eu

if [ "$#" -ne 4 ]; then
  echo "usage: $0 LINUX_NCP_ROOT H316_BIN NCP_BUILD_RECEIPT RESULTS_DIR" >&2
  exit 64
fi

linux_ncp_root=$(CDPATH= cd -- "$1" && pwd)
h316="$(CDPATH= cd -- "$(dirname "$2")" && pwd)/$(basename "$2")"
ncp_build_receipt=$3
results_dir_input=$4
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps
test_dir="$linux_ncp_root/test"
apps_dir="$linux_ncp_root/apps"
ncpd="$linux_ncp_root/src/ncpd"

for required in "$ncpd" "$h316" "$apps_dir/ncp-ping" "$ncp_build_receipt" "$test_dir/impconfig.simh" "$test_dir/impcode.simh"; do
  if [ ! -e "$required" ]; then
    brfid_fail 66 "missing required asset: $required"
  fi
done

brfid_acquire_exclusive_lease "$linux_ncp_root/.brfid-build.lock"
"$repo_root/scripts/ncp-build-receipt.py" verify "$linux_ncp_root" "$ncp_build_receipt"
"$repo_root/scripts/verify-simulator-binaries.py" --h316 "$h316"

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" router-oracle "$repo_root"
brfid_manifest_add_git linux-ncp "$linux_ncp_root"
brfid_manifest_add_git h316-simh "$(git -C "$(dirname "$h316")" rev-parse --show-toplevel)"
brfid_manifest_add_file ncpd "$ncpd" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file ncp-ping "$apps_dir/ncp-ping" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file ncp-build-receipt "$ncp_build_receipt" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file h316 "$h316" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp2-config "$repo_root/config/imp/router-oracle/imp2.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp3-config "$repo_root/config/imp/router-oracle/imp3.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp4-config "$repo_root/config/imp/router-oracle/imp4.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$test_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$test_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-manifest "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"
brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 10 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_router_oracle_ports
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
brfid_manifest_append udp.imp2.mi1 "$BRFID_IMP2_MI1_PORT"
brfid_manifest_append udp.imp3.mi1 "$BRFID_IMP3_MI1_PORT"
brfid_manifest_append udp.imp2.mi2 "$BRFID_IMP2_MI2_PORT"
brfid_manifest_append udp.dead-modem "$BRFID_DEAD_MODEM_PORT"
brfid_manifest_append udp.imp3.mi2 "$BRFID_IMP3_MI2_PORT"
brfid_manifest_append udp.imp4.mi1 "$BRFID_IMP4_MI1_PORT"
brfid_manifest_append udp.imp2.hi "$BRFID_IMP2_HI_PORT"
brfid_manifest_append udp.ncp2.imp "$BRFID_NCP2_IMP_PORT"
brfid_manifest_append udp.imp3.hi "$BRFID_IMP3_HI_PORT"
brfid_manifest_append udp.ncp3.imp "$BRFID_NCP3_IMP_PORT"
brfid_make_private_socket_dir
brfid_ncp_socket host2
ncp2_socket=$BRFID_NCP_SOCKET
brfid_ncp_socket host3
ncp3_socket=$BRFID_NCP_SOCKET
brfid_release_udp_lease_for_launch

brfid_start_process ncp2 "$test_dir" "$results_dir/ncp2.stdout.log" "$results_dir/ncp2.debug.log" env NCP="$ncp2_socket" "$ncpd" 127.0.0.1 "$BRFID_IMP2_HI_PORT" "$BRFID_NCP2_IMP_PORT"
brfid_start_process ncp3 "$test_dir" "$results_dir/ncp3.stdout.log" "$results_dir/ncp3.debug.log" env NCP="$ncp3_socket" "$ncpd" 127.0.0.1 "$BRFID_IMP3_HI_PORT" "$BRFID_NCP3_IMP_PORT"
brfid_start_process imp2 "$test_dir" "$results_dir/imp2.console.log" "$results_dir/imp2.debug.log" "$h316" "$repo_root/config/imp/router-oracle/imp2.simh"
brfid_start_process imp3 "$test_dir" "$results_dir/imp3.console.log" "$results_dir/imp3.debug.log" "$h316" "$repo_root/config/imp/router-oracle/imp3.simh"
brfid_start_process imp4 "$test_dir" "$results_dir/imp4.console.log" "$results_dir/imp4.debug.log" "$h316" "$repo_root/config/imp/router-oracle/imp4.simh"

ready=0
ready_deadline=$(($(date +%s) + 75))
while [ "$(date +%s)" -lt "$ready_deadline" ]; do
  sleep 2
  brfid_assert_managed_alive
  brfid_assert_no_transport_errors "$results_dir/imp2.console.log" "$results_dir/imp2.debug.log" "$results_dir/imp3.console.log" "$results_dir/imp3.debug.log" "$results_dir/imp4.console.log" "$results_dir/imp4.debug.log"
  ready_remaining=$((ready_deadline - $(date +%s)))
  if [ "$ready_remaining" -lt 1 ]; then
    break
  fi
  if [ "$ready_remaining" -gt 8 ]; then
    ready_probe_limit=8
  else
    ready_probe_limit=$ready_remaining
  fi
  if brfid_run_ncp_client_bounded "$ready_probe_limit" env NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c1 003 >"$results_dir/ping-readiness.log" 2>&1; then
    ready=1
    break
  fi
done

if [ "$ready" -ne 1 ]; then
  brfid_fail 1 "router oracle did not become ready within 75s"
fi

brfid_run_ncp_client_bounded 30 env NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c3 003 >"$results_dir/ping-host-003.log" 2>&1
brfid_require "Required evidence missing: Reply from host 003: seq=3 in $results_dir/ping-host-003.log" grep -Fq "Reply from host 003: seq=3" "$results_dir/ping-host-003.log"

if brfid_run_ncp_client_bounded 20 env NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c1 004 >"$results_dir/ping-dead-host-004.log" 2>&1; then
  brfid_fail 1 "unexpected reply from dead host 004"
fi

"$repo_root/scripts/assert-log-evidence.py" router-dead "$results_dir/ncp2.debug.log" "$results_dir/ping-dead-host-004.log"
brfid_assert_managed_alive
brfid_assert_no_transport_errors "$results_dir/imp2.console.log" "$results_dir/imp2.debug.log" "$results_dir/imp3.console.log" "$results_dir/imp3.debug.log" "$results_dir/imp4.console.log" "$results_dir/imp4.debug.log"
brfid_cleanup
echo "PASS: Linux NCP host 002 reached host 003 through IMP 2 and IMP 3, and IMP 4 reported its missing host."
brfid_mark_run_passed
