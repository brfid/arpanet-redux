#!/bin/sh

set -eu

if [ "$#" -ne 5 ]; then
  echo "usage: $0 ARPANET_ROOT LINUX_NCP_ROOT H316_BIN PDP10_KA_BIN RESULTS_DIR" >&2
  exit 64
fi

arpanet_root=$(CDPATH= cd -- "$1" && pwd)
linux_ncp_root=$(CDPATH= cd -- "$2" && pwd)
h316_bin="$(CDPATH= cd -- "$(dirname "$3")" && pwd)/$(basename "$3")"
pdp10_bin="$(CDPATH= cd -- "$(dirname "$4")" && pwd)/$(basename "$4")"
results_dir_input=$5
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

if [ -e "$results_dir_input" ]; then
  echo "results directory already exists: $results_dir_input" >&2
  exit 73
fi

for required in "$h316_bin" "$pdp10_bin" "$ncpd" "$ping_bin" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh" "$host70_base/dskdmp.rim" "$host70_base/rp03.0" "$host70_base/rp03.1" "$host70_base/rp03.2" "$host70_base/rp03.3"; do
  if [ ! -e "$required" ]; then
    echo "missing required asset: $required" >&2
    exit 66
  fi
done

mkdir -p "$results_dir_input"
results_dir=$(CDPATH= cd -- "$results_dir_input" && pwd)
host70_work="$results_dir/host70"
mkdir -p "$host70_work"
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if ! cp -c -p "$host70_base/$asset" "$host70_work/$asset" 2>/dev/null; then
    cp -p "$host70_base/$asset" "$host70_work/$asset"
  fi
done
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 6 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_two_host_ports
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

sleep 30
grep -Fq "IN OPERATION" "$results_dir/host70.console.log"
grep -Fq "packet received" "$results_dir/imp6.debug.log"
grep -Fq "packet received" "$results_dir/imp62.debug.log"

(cd "$test_dir" && NCP="$ncp62_socket" "$ping_bin" -c3 70) >"$results_dir/ping-its-host-106.log" 2>&1
grep -Fq "Reply from host 106: seq=3" "$results_dir/ping-its-host-106.log"
brfid_assert_no_transport_errors "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" "$results_dir/host70.console.log" "$results_dir/host70.debug.log"

echo "PASS: Linux NCP host 076 reached KA10/ITS host 106 through exactly two recovered 1973 IMPs."
