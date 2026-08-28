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
socket_dir=$(mktemp -d "${TMPDIR:-/tmp}/brfid-router-ncp.XXXXXX")
ncp2_socket="$socket_dir/ncp2"
ncp3_socket="$socket_dir/ncp3"

imp2_pid=
imp3_pid=
imp4_pid=
ncp2_pid=
ncp3_pid=

cleanup() {
  for process_id in "$ncp3_pid" "$ncp2_pid" "$imp4_pid" "$imp3_pid" "$imp2_pid"; do
    if [ -n "$process_id" ]; then
      kill "$process_id" 2>/dev/null || true
    fi
  done
  remaining=5
  while [ "$remaining" -gt 0 ]; do
    survivors=0
    for process_id in "$ncp3_pid" "$ncp2_pid" "$imp4_pid" "$imp3_pid" "$imp2_pid"; do
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
  for process_id in "$ncp3_pid" "$ncp2_pid" "$imp4_pid" "$imp3_pid" "$imp2_pid"; do
    if [ -n "$process_id" ] && kill -0 "$process_id" 2>/dev/null; then
      kill -KILL "$process_id" 2>/dev/null || true
    fi
  done
  wait 2>/dev/null || true
  rm -f "$ncp2_socket" "$ncp3_socket"
  rmdir "$socket_dir" 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$test_dir"

NCP="$ncp2_socket" "$ncpd" 127.0.0.1 22001 22002 >"$results_dir/ncp2.stdout.log" 2>"$results_dir/ncp2.debug.log" &
ncp2_pid=$!
NCP="$ncp3_socket" "$ncpd" 127.0.0.1 22003 22004 >"$results_dir/ncp3.stdout.log" 2>"$results_dir/ncp3.debug.log" &
ncp3_pid=$!

"$h316" "$repo_root/config/imp/router-oracle/imp2.simh" >"$results_dir/imp2.console.log" 2>"$results_dir/imp2.debug.log" &
imp2_pid=$!
"$h316" "$repo_root/config/imp/router-oracle/imp3.simh" >"$results_dir/imp3.console.log" 2>"$results_dir/imp3.debug.log" &
imp3_pid=$!
"$h316" "$repo_root/config/imp/router-oracle/imp4.simh" >"$results_dir/imp4.console.log" 2>"$results_dir/imp4.debug.log" &
imp4_pid=$!

sleep 40

for process_id in "$ncp2_pid" "$ncp3_pid" "$imp2_pid" "$imp3_pid" "$imp4_pid"; do
  if ! kill -0 "$process_id" 2>/dev/null; then
    echo "a router-oracle process exited during startup" >&2
    exit 1
  fi
done

NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c3 003 >"$results_dir/ping-host-003.log" 2>&1
grep -Fq "Reply from host 003: seq=3" "$results_dir/ping-host-003.log"

if NCP="$ncp2_socket" "$apps_dir/ncp-ping" -c1 004 >"$results_dir/ping-dead-host-004.log" 2>&1; then
  echo "unexpected reply from dead host 004" >&2
  exit 1
fi

grep -Fq "Host is not up." "$results_dir/ping-dead-host-004.log"
echo "PASS: Linux NCP host 002 reached host 003 through IMP 2 and IMP 3, and IMP 4 reported its missing host."
