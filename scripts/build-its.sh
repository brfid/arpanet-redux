#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 ITS_ROOT ITS_BUILD_RECEIPT" >&2
  exit 64
fi

its_root=$(CDPATH= cd -- "$1" && pwd)
receipt=$2
make_program=${MAKE:-make}
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
lock_dir="$its_root/.brfid-build.lock"
if ! mkdir "$lock_dir"; then
  echo "ITS build lock is busy: $lock_dir" >&2
  exit 75
fi
cleanup() {
  cleanup_status=$?
  trap - 0 1 2 15
  rmdir "$lock_dir" 2>/dev/null || true
  exit "$cleanup_status"
}
trap cleanup 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15

"$make_program" -C "$its_root" clean
"$make_program" -C "$its_root" EMULATOR=pdp10-ka its
"$make_program" -C "$its_root" EMULATOR=pdp10-ka its
"$script_dir/its-build-receipt.py" write "$its_root" "$receipt"
