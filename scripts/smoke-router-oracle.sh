#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 LINUX_NCP_ROOT RESULTS_DIR" >&2
  exit 64
fi

linux_ncp_root=$(CDPATH= cd -- "$1" && pwd)
results_dir_input=$2
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps
test_dir="$linux_ncp_root/test"
apps_dir="$linux_ncp_root/apps"
ncpd="$linux_ncp_root/src/ncpd"
h316="$test_dir/simh/BIN/h316"

if [ -e "$results_dir_input" ]; then
  echo "results directory already exists: $results_dir_input" >&2
  exit 73
fi

for required in "$ncpd" "$h316" "$apps_dir/ncp-ping" "$test_dir/impconfig.simh" "$test_dir/impcode.simh"; do
  if [ ! -e "$required" ]; then
    echo "missing required asset: $required" >&2
    exit 66
  fi
done

mkdir -p "$results_dir_input"
results_dir=$(CDPATH= cd -- "$results_dir_input" && pwd)
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 10 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_router_oracle_ports
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

elapsed=0
ready=0
while [ "$elapsed" -lt 75 ]; do
  sleep 5
  elapsed=$((elapsed + 5))
  brfid_assert_managed_alive
  brfid_assert_no_transport_errors "$results_dir/imp2.console.log" "$results_dir/imp2.debug.log" "$results_dir/imp3.console.log" "$results_dir/imp3.debug.log" "$results_dir/imp4.console.log" "$results_dir/imp4.debug.log"
  if (cd "$test_dir" && NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c1 003) >"$results_dir/ping-readiness.log" 2>&1; then
    ready=1
    break
  fi
done

if [ "$ready" -ne 1 ]; then
  echo "router oracle did not become ready within ${elapsed}s" >&2
  exit 1
fi

(cd "$test_dir" && NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c3 003) >"$results_dir/ping-host-003.log" 2>&1
grep -Fq "Reply from host 003: seq=3" "$results_dir/ping-host-003.log"

if (cd "$test_dir" && NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c1 004) >"$results_dir/ping-dead-host-004.log" 2>&1; then
  echo "unexpected reply from dead host 004" >&2
  exit 1
fi

grep -Fq "Host is not up." "$results_dir/ping-dead-host-004.log"
brfid_assert_no_transport_errors "$results_dir/imp2.console.log" "$results_dir/imp2.debug.log" "$results_dir/imp3.console.log" "$results_dir/imp3.debug.log" "$results_dir/imp4.console.log" "$results_dir/imp4.debug.log"
echo "PASS: Linux NCP host 002 reached host 003 through IMP 2 and IMP 3, and IMP 4 reported its missing host."
