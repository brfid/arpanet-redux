#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 LINUX_NCP_ROOT BUILD_RECEIPT" >&2
  exit 64
fi

linux_ncp_root=$(CDPATH= cd -- "$1" && pwd)
build_receipt=$2
make_program=${MAKE:-make}
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
build_lock="$linux_ncp_root/.brfid-build.lock"

if ! mkdir "$build_lock"; then
  echo "NCP build lock is busy: $build_lock" >&2
  echo "If no build is running, remove that empty stale lock directory manually." >&2
  exit 75
fi

build_cleanup() {
  build_status=$?
  trap - 0 1 2 15
  rmdir "$build_lock" 2>/dev/null || true
  exit "$build_status"
}

trap build_cleanup 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15

"$make_program" -B -C "$linux_ncp_root/src" ncpd libncp.a
"$make_program" -B -C "$linux_ncp_root/apps" ncp-ping
"$script_dir/ncp-build-receipt.py" write "$linux_ncp_root" "$build_receipt"
