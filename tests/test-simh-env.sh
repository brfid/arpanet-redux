#!/bin/sh

set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 H316_BIN PDP10_KA_BIN" >&2
  exit 64
fi

h316_bin=$1
pdp10_bin=$2
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
fixture=$script_dir/fixtures/env-expansion.simh
probe_dir=$(mktemp -d "${TMPDIR:-/tmp}/brfid-simh-env.XXXXXX")

cleanup() {
  rm -f "$probe_dir/h316.log" "$probe_dir/pdp10-ka.log"
  rmdir "$probe_dir" 2>/dev/null || true
}
trap cleanup 0
trap 'exit 129' 1
trap 'exit 130' 2
trap 'exit 143' 15

BRFID_ENV_PROBE=54321 "$h316_bin" "$fixture" >"$probe_dir/h316.log" 2>&1
BRFID_ENV_PROBE=54321 "$pdp10_bin" "$fixture" >"$probe_dir/pdp10-ka.log" 2>&1

grep -Fq "BRFID_ENV_PROBE=54321" "$probe_dir/h316.log"
grep -Fq "BRFID_ENV_PROBE=54321" "$probe_dir/pdp10-ka.log"
echo "PASS: both simulator forks expand environment variables in command files."
