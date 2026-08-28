#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"

brfid_runtime_init
brfid_make_private_socket_dir
brfid_ncp_socket host-a

case $BRFID_NCP_SOCKET in
  "$BRFID_SOCKET_DIR"/host-a) ;;
  *)
    echo "private NCP socket path was not constructed correctly" >&2
    exit 1
    ;;
esac

socket_mode=$(python3 -c 'import os, stat, sys; print(f"{stat.S_IMODE(os.stat(sys.argv[1]).st_mode):o}")' "$BRFID_SOCKET_DIR")
if [ "$socket_mode" != 700 ]; then
  echo "private NCP socket directory mode is $socket_mode, expected 700" >&2
  exit 1
fi

run_dir=$(mktemp -d "${TMPDIR:-/tmp}/brfid-runtime-test.XXXXXX")
brfid_start_process sleeper "$run_dir" "$run_dir/stdout" "$run_dir/stderr" python3 -c 'import signal, time; signal.signal(signal.SIGTERM, lambda *_: exit(0)); time.sleep(30)' >/dev/null
sleeper_pid=$BRFID_LAST_PID
brfid_assert_managed_alive
sleep 1
brfid_cleanup

if kill -0 "$sleeper_pid" 2>/dev/null; then
  echo "managed child survived cleanup" >&2
  exit 1
fi

brfid_runtime_init
results_path="$run_dir/results/one"
brfid_create_results_dir "$results_path"
if brfid_create_results_dir "$results_path" 2>"$run_dir/collision.stderr"; then
  echo "duplicate results directory was accepted" >&2
  exit 1
else
  collision_status=$?
fi
if [ "$collision_status" -ne 73 ]; then
  echo "duplicate results directory returned $collision_status, expected 73" >&2
  exit 1
fi

if brfid_run_bounded 1 python3 -c 'import time; time.sleep(30)'; then
  echo "bounded command unexpectedly completed" >&2
  exit 1
else
  bounded_status=$?
fi
if [ "$bounded_status" -ne 124 ]; then
  echo "bounded command returned $bounded_status, expected 124" >&2
  exit 1
fi
if [ -n "$BRFID_MANAGED_PIDS" ]; then
  echo "completed bounded child remained registered" >&2
  exit 1
fi

brfid_run_bounded 5 true
if [ -n "$BRFID_MANAGED_PIDS" ]; then
  echo "successful bounded child remained registered" >&2
  exit 1
fi

lease_dir="$run_dir/exclusive.lock"
brfid_acquire_exclusive_lease "$lease_dir"
if (
  . "$repo_root/scripts/lib/runtime.sh"
  brfid_runtime_init
  brfid_acquire_exclusive_lease "$lease_dir"
) 2>"$run_dir/lease.stderr"; then
  echo "a second exclusive lease was accepted" >&2
  exit 1
else
  lease_status=$?
fi
if [ "$lease_status" -ne 75 ]; then
  echo "contended exclusive lease returned $lease_status, expected 75" >&2
  exit 1
fi

BRFID_RUN_MANIFEST="$run_dir/hash-failure.env"
export BRFID_RUN_MANIFEST
: >"$BRFID_RUN_MANIFEST"
if brfid_manifest_add_file missing "$run_dir/does-not-exist" "$repo_root/scripts/sha256-file.sh" 2>"$run_dir/hash-failure.stderr"; then
  echo "failed hash helper was accepted" >&2
  exit 1
fi
if [ -s "$BRFID_RUN_MANIFEST" ]; then
  echo "failed hash helper appended manifest data" >&2
  exit 1
fi

BRFID_RUN_MANIFEST="$run_dir/nonzero-status.env"
BRFID_RUN_MANIFEST_FINISHED=0
BRFID_RUN_OUTCOME=passed
export BRFID_RUN_MANIFEST BRFID_RUN_MANIFEST_FINISHED BRFID_RUN_OUTCOME
: >"$BRFID_RUN_MANIFEST"
brfid_finish_run_manifest 9
grep -Fq "outcome=failed" "$BRFID_RUN_MANIFEST"
grep -Fq "exit_status=9" "$BRFID_RUN_MANIFEST"
if [ "$(grep -c '^finished_utc=' "$BRFID_RUN_MANIFEST")" -ne 1 ] || [ "$(grep -c '^outcome=' "$BRFID_RUN_MANIFEST")" -ne 1 ] || [ "$(grep -c '^exit_status=' "$BRFID_RUN_MANIFEST")" -ne 1 ]; then
  echo "run manifest terminal block was not unique" >&2
  exit 1
fi

if brfid_run_ncp_client_bounded 1 python3 -c 'import os, socket, sys, time; open(sys.argv[1], "w", encoding="ascii").write(str(os.getpid())); path = f"/tmp/client.{os.getpid()}"; sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM);
try:
    sock.bind(path)
except PermissionError:
    sys.exit(77)
time.sleep(30)' "$run_dir/ncp.pid"; then
  echo "bounded NCP client unexpectedly completed" >&2
  exit 1
else
  ncp_status=$?
fi
if [ "$ncp_status" -eq 77 ]; then
  echo "SKIP: test environment prohibits Unix-domain socket binds" >&2
elif [ "$ncp_status" -ne 124 ]; then
  echo "bounded NCP client returned $ncp_status, expected 124" >&2
  exit 1
fi
ncp_pid=$(cat "$run_dir/ncp.pid")
if [ -e "/tmp/client.$ncp_pid" ]; then
  echo "bounded NCP client socket survived cleanup" >&2
  exit 1
fi

space_tmp="/tmp/brfid space $$"
mkdir "$space_tmp"
TMPDIR=$space_tmp
export TMPDIR
brfid_make_private_socket_dir
brfid_ncp_socket spaced
brfid_cleanup
if [ -e "$BRFID_SOCKET_DIR" ]; then
  echo "private socket directory with spaces survived cleanup" >&2
  exit 1
fi
if [ -e "$lease_dir" ]; then
  echo "exclusive build/use lease survived cleanup" >&2
  exit 1
fi

rm -f "$run_dir/stdout" "$run_dir/stderr" "$run_dir/collision.stderr" "$run_dir/ncp.pid" "$run_dir/lease.stderr" "$run_dir/hash-failure.env" "$run_dir/hash-failure.stderr" "$run_dir/nonzero-status.env"
rmdir "$results_path"
rmdir "$run_dir/results"
rmdir "$space_tmp"
rmdir "$run_dir"
