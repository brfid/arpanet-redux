#!/bin/sh

set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 ARPANET_ROOT H316_BIN RESULTS_DIR" >&2
  exit 64
fi

arpanet_root=$(CDPATH= cd -- "$1" && pwd)
h316="$(CDPATH= cd -- "$(dirname "$2")" && pwd)/$(basename "$2")"
results_dir_input=$3
script_dir=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd)
lab_root=$(CDPATH= cd -- "$arpanet_root/../.." && pwd)
. "$repo_root/scripts/lib/runtime.sh"
brfid_runtime_init
brfid_install_cleanup_traps

mini_root="$arpanet_root/mini"
h316_root=$(git -C "$(dirname "$h316")" rev-parse --show-toplevel)
topology="$repo_root/config/topologies/ncc-alternate-path-fault.json"
imp5_config="$repo_root/config/imp/ncc-alternate-path/imp5.simh"
imp6_config="$repo_root/config/imp/ncc-alternate-path/imp6.simh"
imp7_config="$repo_root/config/imp/ncc-alternate-path/imp7.simh"
receiver="$repo_root/scripts/ncc-host-interface-proof.py"
reflector="$repo_root/scripts/ncc-direct-line-reflector.py"
evaluator="$repo_root/scripts/ncc-evaluate-line-loopback.py"
receiver_duration=${BRFID_NCC_RECEIVER_DURATION:-130}
forward_seconds=${BRFID_DIRECT_FORWARD_SECONDS:-45}
python_command=${PYTHON:-python3}
case $receiver_duration in
  ''|*[!0-9]*)
    echo "BRFID_NCC_RECEIVER_DURATION must be a positive integer" >&2
    exit 64
    ;;
esac
case $forward_seconds in
  ''|*[!0-9]*)
    echo "BRFID_DIRECT_FORWARD_SECONDS must be a positive integer" >&2
    exit 64
    ;;
esac
if [ "$receiver_duration" -le 0 ] || [ "$forward_seconds" -le 0 ] || [ "$forward_seconds" -ge "$receiver_duration" ]; then
  echo "the direct forwarding interval must be positive and shorter than the receiver duration" >&2
  exit 64
fi
reflector_duration=$((receiver_duration + 20))

for required in \
  "$h316" \
  "$mini_root/impconfig.simh" \
  "$mini_root/impcode.simh" \
  "$topology" \
  "$imp5_config" \
  "$imp6_config" \
  "$imp7_config" \
  "$receiver" \
  "$reflector" \
  "$evaluator"; do
  if [ ! -f "$required" ]; then
    echo "required input is missing: $required" >&2
    exit 66
  fi
done

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
runtime_dir="$results_dir/runtime"
mkdir "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" ncc-line-loopback "$repo_root"
brfid_manifest_add_git arpanet-in-a-box "$arpanet_root"
brfid_manifest_add_git h316-simh "$h316_root"
brfid_manifest_add_file h316 "$h316" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file shared-topology "$topology" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp5-config "$imp5_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp6-config "$imp6_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp7-config "$imp7_config" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file smoke-runner "$repo_root/scripts/smoke-ncc-line-loopback.sh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file receiver-controller "$receiver" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file direct-line-reflector "$reflector" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file result-evaluator "$evaluator" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_root/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_root/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file source-pins "$repo_root/pins/sources.lock.toml" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-pins "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_append experiment.receiver-duration-seconds "$receiver_duration"
brfid_manifest_append experiment.direct-forward-seconds "$forward_seconds"
brfid_manifest_append runtime.python-version "$($python_command --version 2>&1)"

"$repo_root/scripts/verify-sources.py" "$lab_root" --name arpanet-in-a-box --name h316-simh >"$results_dir/source-verification.log" 2>&1
"$repo_root/scripts/verify-assets.sh" mixed "$arpanet_root" >"$results_dir/asset-verification.log" 2>&1
"$repo_root/scripts/verify-simulator-binaries.py" --h316 "$h316" >"$results_dir/binary-verification.log" 2>&1

brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 10 "$runtime_dir" "$runtime_dir/ports.env"
set -- $BRFID_ALLOCATED_PORTS
BRFID_IMP5_DIRECT_PORT=$1
BRFID_IMP6_DIRECT_PORT=$2
BRFID_DIRECT_RELAY5_PORT=$3
BRFID_DIRECT_RELAY6_PORT=$4
BRFID_IMP5_ALT_PORT=$5
BRFID_IMP7_TO5_PORT=$6
BRFID_IMP7_TO6_PORT=$7
BRFID_IMP6_ALT_PORT=$8
BRFID_IMP5_HI_PORT=$9
shift 9
BRFID_NCC_HI_PORT=$1
export BRFID_IMP5_DIRECT_PORT BRFID_IMP6_DIRECT_PORT
export BRFID_DIRECT_RELAY5_PORT BRFID_DIRECT_RELAY6_PORT
export BRFID_IMP5_ALT_PORT BRFID_IMP7_TO5_PORT
export BRFID_IMP7_TO6_PORT BRFID_IMP6_ALT_PORT
export BRFID_IMP5_HI_PORT BRFID_NCC_HI_PORT
export BRFID_H316_MINI_ROOT="$mini_root"
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
for assignment in \
  "udp.imp5-direct=$BRFID_IMP5_DIRECT_PORT" \
  "udp.imp6-direct=$BRFID_IMP6_DIRECT_PORT" \
  "udp.direct-relay5=$BRFID_DIRECT_RELAY5_PORT" \
  "udp.direct-relay6=$BRFID_DIRECT_RELAY6_PORT" \
  "udp.imp5-alternate=$BRFID_IMP5_ALT_PORT" \
  "udp.imp7-to5=$BRFID_IMP7_TO5_PORT" \
  "udp.imp7-to6=$BRFID_IMP7_TO6_PORT" \
  "udp.imp6-alternate=$BRFID_IMP6_ALT_PORT" \
  "udp.imp5-hi1=$BRFID_IMP5_HI_PORT" \
  "udp.ncc-host=$BRFID_NCC_HI_PORT"; do
  brfid_manifest_append "${assignment%%=*}" "${assignment#*=}"
done

brfid_release_udp_lease_for_launch

brfid_start_process direct_reflector "$repo_root" "$results_dir/direct-reflector.stdout.log" "$results_dir/direct-reflector.stderr.log" \
  "$python_command" "$reflector" \
    --relay-a-port "$BRFID_DIRECT_RELAY5_PORT" \
    --relay-b-port "$BRFID_DIRECT_RELAY6_PORT" \
    --peer-a-port "$BRFID_IMP5_DIRECT_PORT" \
    --peer-b-port "$BRFID_IMP6_DIRECT_PORT" \
    --forward-seconds "$forward_seconds" \
    --duration "$reflector_duration" \
    --output "$results_dir/direct-reflector.json"
reflector_pid=$BRFID_LAST_PID
sleep 1

brfid_start_process receiver "$repo_root" "$results_dir/receiver.stdout.log" "$results_dir/receiver.stderr.log" \
  "$python_command" "$receiver" \
    --topology "$topology" \
    --interface-id binding:ncc-host0-imp5 \
    --duration "$receiver_duration" \
    --ready-interval 1 \
    --require-message \
    --require-trouble-report \
    --require-throughput-report \
    --event-record "$results_dir/historical-events.jsonl" \
    --run-id "$(basename "$results_dir")" \
    --output "$results_dir/receiver.json"
receiver_pid=$BRFID_LAST_PID
sleep 1

brfid_start_process imp5 "$mini_root" "$results_dir/imp5.console.log" "$results_dir/imp5.debug.log" "$h316" "$imp5_config"
brfid_start_process imp6 "$mini_root" "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" "$h316" "$imp6_config"
brfid_start_process imp7 "$mini_root" "$results_dir/imp7.console.log" "$results_dir/imp7.debug.log" "$h316" "$imp7_config"

while kill -0 "$receiver_pid" 2>/dev/null; do
  brfid_assert_managed_alive
  sleep 1
done
if wait "$receiver_pid"; then
  receiver_status=0
else
  receiver_status=$?
fi
brfid_unregister_pid "$receiver_pid"
brfid_manifest_append process.receiver.exit-status "$receiver_status"
if [ "$receiver_status" -ne 0 ]; then
  echo "NCC receiver failed" >&2
  exit "$receiver_status"
fi

kill -TERM "$reflector_pid"
if wait "$reflector_pid"; then
  reflector_status=0
else
  reflector_status=$?
fi
brfid_unregister_pid "$reflector_pid"
brfid_manifest_append process.direct-reflector.exit-status "$reflector_status"
if [ "$reflector_status" -ne 0 ]; then
  echo "direct-line reflector failed" >&2
  exit "$reflector_status"
fi

if "$python_command" "$evaluator" \
  --topology "$topology" \
  --events "$results_dir/historical-events.jsonl" \
  --receiver "$results_dir/receiver.json" \
  --reflector "$results_dir/direct-reflector.json" \
  --output "$results_dir/verdict.json"; then
  verdict_status=0
else
  verdict_status=$?
fi
brfid_manifest_append result.verdict "$results_dir/verdict.json"
brfid_manifest_append result.verdict-exit-status "$verdict_status"

brfid_assert_managed_alive
brfid_assert_no_transport_errors \
  "$results_dir/imp5.console.log" "$results_dir/imp5.debug.log" \
  "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" \
  "$results_dir/imp7.console.log" "$results_dir/imp7.debug.log"
brfid_cleanup
brfid_manifest_append cleanup.completed "$BRFID_CLEANED"
if [ "$verdict_status" -ne 0 ]; then
  echo "line-loopback verdict failed" >&2
  brfid_finish_run_manifest "$verdict_status"
  trap - 0 1 2 15
  exit "$verdict_status"
fi

brfid_mark_run_passed
brfid_finish_run_manifest 0
trap - 0 1 2 15
echo "PASS: both IMPs reported the direct line up, then looped through the live alternate path."
exit 0
