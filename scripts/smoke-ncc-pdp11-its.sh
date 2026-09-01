#!/bin/sh

set -eu

if [ "$#" -ne 8 ]; then
  echo "usage: $0 ARPANET_ROOT NETWORK_UNIX_ROOT IMP11A_ROOT H316_BIN PDP10_KA_BIN PDP11_BIN PDP11_BUILD_ROOT RESULTS_DIR" >&2
  exit 64
fi

arpanet_root=$(CDPATH= cd -- "$1" && pwd)
network_unix_root=$(CDPATH= cd -- "$2" && pwd)
imp11a_root=$(CDPATH= cd -- "$3" && pwd)
h316_bin="$(CDPATH= cd -- "$(dirname "$4")" && pwd)/$(basename "$4")"
pdp10_bin="$(CDPATH= cd -- "$(dirname "$5")" && pwd)/$(basename "$5")"
pdp11_bin="$(CDPATH= cd -- "$(dirname "$6")" && pwd)/$(basename "$6")"
pdp11_build_root=$(CDPATH= cd -- "$7" && pwd)
results_dir_input=$8
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps

python_command=${PYTHON:-python3}
receiver_duration=${BRFID_NCC_RECEIVER_DURATION:-150}
case $receiver_duration in
  ''|*[!0-9]*)
    echo "BRFID_NCC_RECEIVER_DURATION must be a positive integer" >&2
    exit 64
    ;;
esac
if [ "$receiver_duration" -le 0 ]; then
  echo "BRFID_NCC_RECEIVER_DURATION must be positive" >&2
  exit 64
fi

mini_dir="$arpanet_root/mini"
host106_base="$mini_dir/host70/106"
pdp11_receipt="$pdp11_build_root/pdp11-build-receipt.json"
pdp11_media="$pdp11_build_root/ncpd/guest/images"
topology="$repo_root/config/topologies/ncc-pdp11-its-coexistence.json"
imp5_config="$repo_root/config/imp/ncc-pdp11-its/imp5.simh"
imp6_config="$repo_root/config/imp/ncc-pdp11-its/imp6.simh"
imp7_config="$repo_root/config/imp/ncc-alternate-path/imp7.simh"
imp62_config="$repo_root/config/imp/pdp11-its/imp62.simh"
host106_config="$repo_root/config/hosts/its106-pair.simh"
pdp11_config="$repo_root/config/hosts/pdp11-176.simh"
receiver="$repo_root/scripts/ncc-host-interface-proof.py"
evaluator="$repo_root/scripts/ncc-evaluate-pdp11-its-coexistence.py"
controller="$repo_root/scripts/pdp11-its-controller.py"

for required in "$h316_bin" "$pdp10_bin" "$pdp11_bin" "$pdp11_receipt" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh" "$pdp11_media/ncp_root.rl01" "$pdp11_media/ncp_swap.rl01" "$topology" "$imp5_config" "$imp6_config" "$imp7_config" "$imp62_config" "$host106_config" "$pdp11_config" "$receiver" "$evaluator" "$controller"; do
  if [ ! -f "$required" ]; then
    echo "missing required integrated NCC smoke input: $required" >&2
    exit 66
  fi
done
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if [ ! -f "$host106_base/$asset" ]; then
    echo "missing required ITS media: $host106_base/$asset" >&2
    exit 66
  fi
done

brfid_acquire_exclusive_lease "$pdp11_build_root.lock"
"$repo_root/scripts/pdp11-build-receipt.py" verify "$pdp11_receipt"
"$repo_root/scripts/verify-simulator-binaries.py" \
  --h316 "$h316_bin" --pdp10-ka "$pdp10_bin" --pdp11 "$pdp11_bin"

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
run_id=$(basename "$results_dir")
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" ncc-pdp11-its-coexistence "$repo_root"
brfid_manifest_add_git arpanet-in-a-box "$arpanet_root"
brfid_manifest_add_git network-unix-v6 "$network_unix_root"
brfid_manifest_add_git h316-simh "$(git -C "$(dirname "$h316_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git ka10-simh "$(git -C "$(dirname "$pdp10_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git imp11a-simh "$imp11a_root"
brfid_manifest_add_file pdp11-build-receipt "$pdp11_receipt" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file h316 "$h316_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp10-ka "$pdp10_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp11 "$pdp11_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file shared-topology "$topology" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp5-config "$imp5_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp6-config "$imp6_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp7-config "$imp7_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp62-config "$imp62_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file host106-config "$host106_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp11-config "$pdp11_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file smoke-runner "$repo_root/scripts/smoke-ncc-pdp11-its.sh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file application-controller "$controller" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file receiver-controller "$receiver" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file result-evaluator "$evaluator" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file source-pins "$repo_root/pins/sources.lock.toml" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-pins "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_append experiment.receiver-duration-seconds "$receiver_duration"
brfid_manifest_append runtime.python-version "$($python_command --version 2>&1)"

host106_work="$results_dir/host106"
pdp11_work="$results_dir/pdp11"
mkdir -p "$host106_work" "$pdp11_work/images"
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if ! cp -c -p "$host106_base/$asset" "$host106_work/$asset" 2>/dev/null; then
    cp -p "$host106_base/$asset" "$host106_work/$asset"
  fi
  brfid_manifest_add_file "host106-$asset" "$host106_work/$asset" "$repo_root/scripts/sha256-file.sh"
done
for asset in ncp_root.rl01 ncp_swap.rl01; do
  if ! cp -c -p "$pdp11_media/$asset" "$pdp11_work/images/$asset" 2>/dev/null; then
    cp -p "$pdp11_media/$asset" "$pdp11_work/images/$asset"
  fi
  brfid_manifest_add_file "pdp11-$asset" "$pdp11_work/images/$asset" "$repo_root/scripts/sha256-file.sh"
done

brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 14 "$runtime_dir" "$runtime_dir/ports.env"
set -- $BRFID_ALLOCATED_PORTS
BRFID_IMP5_DIRECT_PORT=$1
BRFID_IMP6_DIRECT_PORT=$2
BRFID_IMP5_ALT_PORT=$3
BRFID_IMP7_TO5_PORT=$4
BRFID_IMP7_TO6_PORT=$5
BRFID_IMP6_ALT_PORT=$6
BRFID_IMP6_MI_PORT=$7
BRFID_IMP62_MI_PORT=$8
BRFID_IMP5_HI_PORT=$9
shift 9
BRFID_NCC_HI_PORT=$1
BRFID_IMP6_HI_PORT=$2
BRFID_HOST_A_IMP_PORT=$3
BRFID_IMP62_HI_PORT=$4
BRFID_HOST_B_IMP_PORT=$5
export BRFID_IMP5_DIRECT_PORT BRFID_IMP6_DIRECT_PORT
export BRFID_IMP5_ALT_PORT BRFID_IMP7_TO5_PORT
export BRFID_IMP7_TO6_PORT BRFID_IMP6_ALT_PORT
export BRFID_IMP6_MI_PORT BRFID_IMP62_MI_PORT
export BRFID_IMP5_HI_PORT BRFID_NCC_HI_PORT
export BRFID_IMP6_HI_PORT BRFID_HOST_A_IMP_PORT
export BRFID_IMP62_HI_PORT BRFID_HOST_B_IMP_PORT
BRFID_H316_MINI_ROOT="$mini_dir"
BRFID_PDP11_DEBUG_LOG="$results_dir/pdp11-imp-debug.log"
export BRFID_H316_MINI_ROOT BRFID_PDP11_DEBUG_LOG
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
for assignment in \
  "udp.imp5-direct=$BRFID_IMP5_DIRECT_PORT" \
  "udp.imp6-direct=$BRFID_IMP6_DIRECT_PORT" \
  "udp.imp5-alternate=$BRFID_IMP5_ALT_PORT" \
  "udp.imp7-to5=$BRFID_IMP7_TO5_PORT" \
  "udp.imp7-to6=$BRFID_IMP7_TO6_PORT" \
  "udp.imp6-alternate=$BRFID_IMP6_ALT_PORT" \
  "udp.imp6-application=$BRFID_IMP6_MI_PORT" \
  "udp.imp62-application=$BRFID_IMP62_MI_PORT" \
  "udp.imp5-hi1=$BRFID_IMP5_HI_PORT" \
  "udp.ncc-host=$BRFID_NCC_HI_PORT" \
  "udp.imp6-hi2=$BRFID_IMP6_HI_PORT" \
  "udp.host106-imp=$BRFID_HOST_A_IMP_PORT" \
  "udp.imp62-hi2=$BRFID_IMP62_HI_PORT" \
  "udp.host176-imp=$BRFID_HOST_B_IMP_PORT"; do
  brfid_manifest_append "${assignment%%=*}" "${assignment#*=}"
done
brfid_make_private_socket_dir
brfid_manifest_append runtime.control-socket-namespace "$BRFID_SOCKET_DIR"
brfid_release_udp_lease_for_launch

brfid_start_process receiver "$repo_root" "$results_dir/receiver.stdout.log" "$results_dir/receiver.stderr.log" \
  "$python_command" "$receiver" \
    --topology "$topology" \
    --interface-id binding:ncc-host0-imp5 \
    --duration "$receiver_duration" \
    --require-trouble-report \
    --require-throughput-report \
    --event-record "$results_dir/historical-events.jsonl" \
    --run-id "$run_id" \
    --output "$results_dir/receiver.json"
receiver_pid=$BRFID_LAST_PID

brfid_start_process imp5 "$mini_dir" "$results_dir/imp5.console.log" "$results_dir/imp5.debug.log" "$h316_bin" "$imp5_config"
brfid_start_process imp7 "$mini_dir" "$results_dir/imp7.console.log" "$results_dir/imp7.debug.log" "$h316_bin" "$imp7_config"

brfid_start_process controller "$repo_root" "$results_dir/controller.stdout.log" "$results_dir/controller.stderr.log" \
  "$python_command" "$controller" \
    --h316 "$h316_bin" \
    --pdp10-ka "$pdp10_bin" \
    --pdp11 "$pdp11_bin" \
    --mini-root "$mini_dir" \
    --host106-work "$host106_work" \
    --pdp11-work "$pdp11_work" \
    --imp6-config "$imp6_config" \
    --imp62-config "$imp62_config" \
    --host106-config "$host106_config" \
    --pdp11-config "$pdp11_config" \
    --topology "$topology" \
    --results-dir "$results_dir" \
    --manifest "$runtime_dir/run.env"
controller_pid=$BRFID_LAST_PID

if wait "$controller_pid"; then
  controller_status=0
else
  controller_status=$?
fi
brfid_unregister_pid "$controller_pid"
brfid_manifest_append process.controller.exit-status "$controller_status"
if [ "$controller_status" -ne 0 ]; then
  echo "integrated PDP-11-to-ITS controller failed; see $results_dir/controller.stderr.log" >&2
  exit "$controller_status"
fi

if wait "$receiver_pid"; then
  receiver_status=0
else
  receiver_status=$?
fi
brfid_unregister_pid "$receiver_pid"
brfid_manifest_append process.receiver.exit-status "$receiver_status"
if [ "$receiver_status" -ne 0 ]; then
  echo "integrated NCC receiver failed; see $results_dir/receiver.stderr.log" >&2
  exit "$receiver_status"
fi

brfid_assert_no_transport_errors \
  "$results_dir/imp5.console.log" "$results_dir/imp5.debug.log" \
  "$results_dir/imp7.console.log" "$results_dir/imp7.debug.log" \
  "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" \
  "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" \
  "$results_dir/host106.console.log" "$results_dir/pdp11.console.log" \
  "$results_dir/pdp11-imp-debug.log"
brfid_cleanup
brfid_manifest_append cleanup.outer-runtime passed

"$python_command" "$evaluator" \
  --topology "$topology" \
  --events "$results_dir/historical-events.jsonl" \
  --receiver "$results_dir/receiver.json" \
  --application-evidence "$results_dir/application-evidence.txt" \
  --cleanup-evidence "$results_dir/cleanup-evidence.txt" \
  --outcome "$results_dir/outcome.txt" \
  --manifest "$runtime_dir/run.env" \
  --run-id "$run_id" \
  --output "$results_dir/verdict.json"
brfid_manifest_add_file verdict "$results_dir/verdict.json" "$repo_root/scripts/sha256-file.sh"

echo "PASS: Network UNIX reached ITS while NCC observed attributed reports from IMPs 5, 6, 7, and 62."
brfid_mark_run_passed
