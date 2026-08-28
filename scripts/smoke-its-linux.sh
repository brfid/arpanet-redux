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
socket_dir=$(mktemp -d "${TMPDIR:-/tmp}/brfid-mixed-ncp.XXXXXX")
ncp62_socket="$socket_dir/ncp62"

ncp_pid=
imp6_pid=
imp62_pid=
host70_pid=

cleanup() {
  for process_id in "$host70_pid" "$imp62_pid" "$imp6_pid" "$ncp_pid"; do
    if [ -n "$process_id" ]; then
      kill "$process_id" 2>/dev/null || true
    fi
  done
  remaining=5
  while [ "$remaining" -gt 0 ]; do
    survivors=0
    for process_id in "$host70_pid" "$imp62_pid" "$imp6_pid" "$ncp_pid"; do
      if [ -n "$process_id" ] && kill -0 "$process_id" 2>/dev/null; then
        survivors=1
      fi
    done
    if [ "$survivors" -eq 0 ]; then
      break
    fi
    sleep 1
    remaining=$((remaining - 1))
  done
  for process_id in "$host70_pid" "$imp62_pid" "$imp6_pid" "$ncp_pid"; do
    if [ -n "$process_id" ] && kill -0 "$process_id" 2>/dev/null; then
      kill -KILL "$process_id" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  rm -f "$ncp62_socket"
  rmdir "$socket_dir" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

(cd "$test_dir" && NCP="$ncp62_socket" exec "$ncpd" 127.0.0.1 23001 23002) >"$results_dir/ncp62.stdout.log" 2>"$results_dir/ncp62.debug.log" &
ncp_pid=$!
(cd "$mini_dir" && exec "$h316_bin" "$repo_root/config/imp/mixed/imp6.simh") >"$results_dir/imp6.console.log" 2>"$results_dir/imp6.debug.log" &
imp6_pid=$!
(cd "$mini_dir" && exec "$h316_bin" "$repo_root/config/imp/mixed/imp62.simh") >"$results_dir/imp62.console.log" 2>"$results_dir/imp62.debug.log" &
imp62_pid=$!
(cd "$host70_work" && exec "$pdp10_bin" "$repo_root/config/hosts/its70-mixed.simh") >"$results_dir/host70.console.log" 2>"$results_dir/host70.debug.log" &
host70_pid=$!

elapsed=0
booted=0
while [ "$elapsed" -lt 300 ]; do
  sleep 5
  elapsed=$((elapsed + 5))
  for process_id in "$ncp_pid" "$imp6_pid" "$imp62_pid" "$host70_pid"; do
    if ! kill -0 "$process_id" 2>/dev/null; then
      echo "a simulator exited before the ${elapsed}s boot checkpoint" >&2
      exit 1
    fi
  done
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

echo "PASS: Linux NCP host 076 reached KA10/ITS host 106 through exactly two recovered 1973 IMPs."
