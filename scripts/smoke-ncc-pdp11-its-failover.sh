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
failover_mode=${BRFID_FAILOVER_MODE:-formal}
receiver_duration=${BRFID_NCC_RECEIVER_DURATION:-300}
relay_duration=${BRFID_APPLICATION_RELAY_DURATION:-420}
max_terminal_input_bytes=${BRFID_TELNET_MAX_INPUT_BYTES:-1048576}
max_terminal_output_bytes=${BRFID_TELNET_MAX_OUTPUT_BYTES:-8388608}
max_terminal_chunk_bytes=${BRFID_TELNET_MAX_CHUNK_BYTES:-4096}
case $failover_mode in
  formal|terminal) ;;
  *)
    brfid_fail 64 "unsupported application-failover mode: $failover_mode"
    ;;
esac
for setting in "$receiver_duration" "$relay_duration"; do
  case $setting in
    ''|*[!0-9]*)
      brfid_fail 64 "receiver and relay durations must be positive integers"
      ;;
  esac
  if [ "$setting" -le 0 ]; then
    brfid_fail 64 "receiver and relay durations must be positive"
  fi
done
for setting in "$max_terminal_input_bytes" "$max_terminal_output_bytes" "$max_terminal_chunk_bytes"; do
  case $setting in
    ''|*[!0-9]*)
      brfid_fail 64 "terminal byte limits must be positive integers"
      ;;
  esac
  if [ "$setting" -le 0 ]; then
    brfid_fail 64 "terminal byte limits must be positive"
  fi
done

mini_dir="$arpanet_root/mini"
host106_base="$mini_dir/host70/106"
pdp11_receipt="$pdp11_build_root/pdp11-build-receipt.json"
pdp11_media="$pdp11_build_root/ncpd/guest/images"
topology="$repo_root/config/topologies/ncc-pdp11-its-application-failover.json"
imp5_config="$repo_root/config/imp/ncc-pdp11-its/imp5.simh"
imp6_config="$repo_root/config/imp/ncc-pdp11-its-failover/imp6.simh"
imp7_config="$repo_root/config/imp/ncc-pdp11-its-failover/imp7.simh"
imp62_config="$repo_root/config/imp/ncc-pdp11-its-failover/imp62.simh"
host106_config="$repo_root/config/hosts/its106-pair.simh"
pdp11_config="$repo_root/config/hosts/pdp11-176.simh"
receiver="$repo_root/scripts/ncc-host-interface-proof.py"
relay="$repo_root/scripts/ncc-direct-line-relay.py"
controller="$repo_root/scripts/pdp11-its-failover-controller.py"
evaluator="$repo_root/scripts/ncc-evaluate-pdp11-its-failover.py"

for required in "$h316_bin" "$pdp10_bin" "$pdp11_bin" "$pdp11_receipt" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh" "$pdp11_media/ncp_root.rl01" "$pdp11_media/ncp_swap.rl01" "$topology" "$imp5_config" "$imp6_config" "$imp7_config" "$imp62_config" "$host106_config" "$pdp11_config" "$receiver" "$relay" "$controller" "$evaluator"; do
  if [ ! -f "$required" ]; then
    brfid_fail 66 "missing required application-failover input: $required"
  fi
done
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if [ ! -f "$host106_base/$asset" ]; then
    brfid_fail 66 "missing required ITS media: $host106_base/$asset"
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
cut_request="$runtime_dir/application-link-cut.request"
cut_state="$results_dir/application-link-cut-state.json"
if [ "$failover_mode" = terminal ]; then
  run_kind=pdp11-its-interactive-failover
else
  run_kind=ncc-pdp11-its-application-failover
fi
brfid_manifest_init "$runtime_dir/run.env" "$run_kind" "$repo_root"
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
brfid_manifest_add_file smoke-runner "$repo_root/scripts/smoke-ncc-pdp11-its-failover.sh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file application-controller "$controller" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file receiver-controller "$receiver" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file direct-line-relay "$relay" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file result-evaluator "$evaluator" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file source-pins "$repo_root/pins/sources.lock.toml" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-pins "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_append experiment.receiver-duration-seconds "$receiver_duration"
brfid_manifest_append experiment.relay-duration-seconds "$relay_duration"
brfid_manifest_append interactive.failover-mode "$failover_mode"
brfid_manifest_append terminal.max-input-bytes "$max_terminal_input_bytes"
brfid_manifest_append terminal.max-output-bytes "$max_terminal_output_bytes"
brfid_manifest_append terminal.max-chunk-bytes "$max_terminal_chunk_bytes"
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

brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 18 "$runtime_dir" "$runtime_dir/ports.env"
set -- $BRFID_ALLOCATED_PORTS
BRFID_IMP5_DIRECT_PORT=$1
BRFID_IMP6_DIRECT_PORT=$2
BRFID_IMP5_ALT_PORT=$3
BRFID_IMP7_TO5_PORT=$4
BRFID_IMP7_TO6_PORT=$5
BRFID_IMP6_ALT_PORT=$6
BRFID_IMP6_MI_PORT=$7
BRFID_IMP62_MI_PORT=$8
BRFID_APP_RELAY6_PORT=$9
shift 9
BRFID_APP_RELAY62_PORT=$1
BRFID_IMP62_TO7_PORT=$2
BRFID_IMP7_TO62_PORT=$3
BRFID_IMP5_HI_PORT=$4
BRFID_NCC_HI_PORT=$5
BRFID_IMP6_HI_PORT=$6
BRFID_HOST_A_IMP_PORT=$7
BRFID_IMP62_HI_PORT=$8
BRFID_HOST_B_IMP_PORT=$9
export BRFID_IMP5_DIRECT_PORT BRFID_IMP6_DIRECT_PORT
export BRFID_IMP5_ALT_PORT BRFID_IMP7_TO5_PORT
export BRFID_IMP7_TO6_PORT BRFID_IMP6_ALT_PORT
export BRFID_IMP6_MI_PORT BRFID_IMP62_MI_PORT
export BRFID_APP_RELAY6_PORT BRFID_APP_RELAY62_PORT
export BRFID_IMP62_TO7_PORT BRFID_IMP7_TO62_PORT
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
  "udp.application-relay6=$BRFID_APP_RELAY6_PORT" \
  "udp.application-relay62=$BRFID_APP_RELAY62_PORT" \
  "udp.imp62-to7=$BRFID_IMP62_TO7_PORT" \
  "udp.imp7-to62=$BRFID_IMP7_TO62_PORT" \
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

brfid_start_process application_relay "$repo_root" "$results_dir/application-relay.stdout.log" "$results_dir/application-relay.stderr.log" \
  "$python_command" "$relay" \
    --relay-a-port "$BRFID_APP_RELAY62_PORT" \
    --relay-b-port "$BRFID_APP_RELAY6_PORT" \
    --peer-a-port "$BRFID_IMP62_MI_PORT" \
    --peer-b-port "$BRFID_IMP6_MI_PORT" \
    --cut-request "$cut_request" \
    --cut-state "$cut_state" \
    --duration "$relay_duration" \
    --output "$results_dir/application-relay.json"
relay_pid=$BRFID_LAST_PID

receiver_pid=
if [ "$failover_mode" = formal ]; then
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
fi

brfid_start_process imp5 "$mini_dir" "$results_dir/imp5.console.log" "$results_dir/imp5.debug.log" "$h316_bin" "$imp5_config"
brfid_start_process imp7 "$mini_dir" "$results_dir/imp7.console.log" "$results_dir/imp7.debug.log" "$h316_bin" "$imp7_config"

set -- \
  "$python_command" "$controller" \
  --h316 "$h316_bin" \
  --pdp10-ka "$pdp10_bin" \
  --pdp11 "$pdp11_bin" \
  --mini-root "$mini_dir" \
  --host106-work "$host106_work" \
  --pdp11-work "$pdp11_work" \
  --imp6-config "$imp6_config" \
  --imp62-config "$imp62_config" \
  --imp7-debug "$results_dir/imp7.debug.log" \
  --host106-config "$host106_config" \
  --pdp11-config "$pdp11_config" \
  --topology "$topology" \
  --results-dir "$results_dir" \
  --manifest "$runtime_dir/run.env" \
  --cut-request "$cut_request" \
  --cut-state "$cut_state"
if [ "$failover_mode" = terminal ]; then
  set -- "$@" \
    --mode terminal \
    --max-terminal-input-bytes "$max_terminal_input_bytes" \
    --max-terminal-output-bytes "$max_terminal_output_bytes" \
    --max-terminal-chunk-bytes "$max_terminal_chunk_bytes"
  if (CDPATH= cd -- "$repo_root" && "$@"); then
    controller_status=0
  else
    controller_status=$?
  fi
else
  brfid_start_process controller "$repo_root" "$results_dir/controller.stdout.log" "$results_dir/controller.stderr.log" "$@"
  controller_pid=$BRFID_LAST_PID
  if wait "$controller_pid"; then
    controller_status=0
  else
    controller_status=$?
  fi
  brfid_unregister_pid "$controller_pid"
fi
brfid_manifest_append process.controller.exit-status "$controller_status"
if [ "$controller_status" -ne 0 ]; then
  if [ "$failover_mode" = terminal ]; then
    BRFID_FAILURE_REASON="interactive application-failover controller failed; retained result: $results_dir"
    brfid_error "$BRFID_FAILURE_REASON"
  else
    BRFID_FAILURE_REASON="application-failover controller failed; see $results_dir/controller.stderr.log"
    brfid_error "$BRFID_FAILURE_REASON"
  fi
  exit "$controller_status"
fi

if [ "$failover_mode" = formal ]; then
  if wait "$receiver_pid"; then
    receiver_status=0
  else
    receiver_status=$?
  fi
  brfid_unregister_pid "$receiver_pid"
  brfid_manifest_append process.receiver.exit-status "$receiver_status"
  if [ "$receiver_status" -ne 0 ]; then
    brfid_fail "$receiver_status" "application-failover NCC receiver failed"
  fi
fi

kill -TERM "$relay_pid"
if wait "$relay_pid"; then
  relay_status=0
else
  relay_status=$?
fi
brfid_unregister_pid "$relay_pid"
brfid_manifest_append process.application-relay.exit-status "$relay_status"
if [ "$relay_status" -ne 0 ]; then
  brfid_fail "$relay_status" "application-link relay failed"
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

if [ "$failover_mode" = terminal ]; then
  brfid_require "Scenario evaluator failed; see $results_dir/verdict.json" "$python_command" "$evaluator" \
    --profile interactive-terminal \
    --topology "$topology" \
    --relay "$results_dir/application-relay.json" \
    --cut-state "$cut_state" \
    --application-evidence "$results_dir/application-evidence.txt" \
    --message-journey "$results_dir/message-journey.jsonl" \
    --terminal-session "$results_dir/terminal-session.jsonl" \
    --cleanup-evidence "$results_dir/cleanup-evidence.txt" \
    --outcome "$results_dir/outcome.txt" \
    --manifest "$runtime_dir/run.env" \
    --run-id "$run_id" \
    --output "$results_dir/verdict.json"
else
  brfid_require "Scenario evaluator failed; see $results_dir/verdict.json" "$python_command" "$evaluator" \
    --topology "$topology" \
    --receiver "$results_dir/receiver.json" \
    --relay "$results_dir/application-relay.json" \
    --cut-state "$cut_state" \
    --application-evidence "$results_dir/application-evidence.txt" \
    --message-journey "$results_dir/message-journey.jsonl" \
    --cleanup-evidence "$results_dir/cleanup-evidence.txt" \
    --outcome "$results_dir/outcome.txt" \
    --manifest "$runtime_dir/run.env" \
    --run-id "$run_id" \
    --output "$results_dir/verdict.json"
fi
brfid_manifest_add_file verdict "$results_dir/verdict.json" "$repo_root/scripts/sha256-file.sh"

if [ "$failover_mode" = terminal ]; then
  echo "PASS: one human-operated Network UNIX TELNET session reached ITS before and after the direct application-link cut through IMP 7."
else
  echo "PASS: one Network UNIX TELNET session reached ITS before and after the direct application-link cut through IMP 7."
fi
brfid_mark_run_passed
