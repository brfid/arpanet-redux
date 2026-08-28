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

socket_mode=$(stat -f '%Lp' "$BRFID_SOCKET_DIR" 2>/dev/null || stat -c '%a' "$BRFID_SOCKET_DIR")
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

rm -f "$run_dir/stdout" "$run_dir/stderr"
rmdir "$run_dir"
