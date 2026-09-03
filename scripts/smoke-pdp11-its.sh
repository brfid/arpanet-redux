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

mini_dir="$arpanet_root/mini"
its_host_base="$mini_dir/host70/106"
pdp11_receipt="$pdp11_build_root/pdp11-build-receipt.json"
pdp11_media="$pdp11_build_root/ncpd/guest/images"

for required in "$h316_bin" "$pdp10_bin" "$pdp11_bin" "$pdp11_receipt" "$mini_dir/impconfig.simh" "$mini_dir/impcode.simh" "$pdp11_media/ncp_root.rl01" "$pdp11_media/ncp_swap.rl01"; do
  if [ ! -f "$required" ]; then
    echo "missing required PDP-11 smoke input: $required" >&2
    exit 66
  fi
done
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if [ ! -f "$its_host_base/$asset" ]; then
    echo "missing required ITS media: $its_host_base/$asset" >&2
    exit 66
  fi
done

brfid_acquire_exclusive_lease "$pdp11_build_root.lock"
"$repo_root/scripts/pdp11-build-receipt.py" verify "$pdp11_receipt"
"$repo_root/scripts/verify-simulator-binaries.py" \
  --h316 "$h316_bin" --pdp10-ka "$pdp10_bin" --pdp11 "$pdp11_bin"

brfid_create_results_dir "$results_dir_input"
results_dir=$BRFID_RESULTS_DIR
runtime_dir="$results_dir/runtime"
mkdir -p "$runtime_dir"
brfid_manifest_init "$runtime_dir/run.env" pdp11-its-telnet "$repo_root"
brfid_manifest_add_git arpanet-in-a-box "$arpanet_root"
brfid_manifest_add_git network-unix-v6 "$network_unix_root"
brfid_manifest_add_git h316-simh "$(git -C "$(dirname "$h316_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git ka10-simh "$(git -C "$(dirname "$pdp10_bin")" rev-parse --show-toplevel)"
brfid_manifest_add_git imp11a-simh "$imp11a_root"
brfid_manifest_add_file pdp11-build-receipt "$pdp11_receipt" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file h316 "$h316_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp10-ka "$pdp10_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp11 "$pdp11_bin" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp6-config "$repo_root/config/imp/its-pair/imp6.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp62-config "$repo_root/config/imp/pdp11-its/imp62.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file host106-config "$repo_root/config/hosts/its106-pair.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file pdp11-config "$repo_root/config/hosts/pdp11-176.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file message-journey-topology "$repo_root/config/topologies/pdp11-its-telnet.json" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-firmware "$mini_dir/impcode.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file imp-base-config "$mini_dir/impconfig.simh" "$repo_root/scripts/sha256-file.sh"
brfid_manifest_add_file asset-manifest "$repo_root/pins/arpanet-assets.sha256" "$repo_root/scripts/sha256-file.sh"

its_host_work="$results_dir/host106"
pdp11_work="$results_dir/pdp11"
mkdir -p "$its_host_work" "$pdp11_work/images"
for asset in dskdmp.rim rp03.0 rp03.1 rp03.2 rp03.3; do
  if ! cp -c -p "$its_host_base/$asset" "$its_host_work/$asset" 2>/dev/null; then
    cp -p "$its_host_base/$asset" "$its_host_work/$asset"
  fi
  brfid_manifest_add_file "host106-$asset" "$its_host_work/$asset" "$repo_root/scripts/sha256-file.sh"
done
for asset in ncp_root.rl01 ncp_swap.rl01; do
  if ! cp -c -p "$pdp11_media/$asset" "$pdp11_work/images/$asset" 2>/dev/null; then
    cp -p "$pdp11_media/$asset" "$pdp11_work/images/$asset"
  fi
  brfid_manifest_add_file "pdp11-$asset" "$pdp11_work/images/$asset" "$repo_root/scripts/sha256-file.sh"
done

brfid_reserve_udp_ports "$repo_root/scripts/reserve-udp-ports.py" 6 "$runtime_dir" "$runtime_dir/ports.env"
brfid_assign_two_host_ports
brfid_manifest_add_port_metadata "$runtime_dir/ports.env"
brfid_manifest_append udp.imp6.mi "$BRFID_IMP6_MI_PORT"
brfid_manifest_append udp.imp62.mi "$BRFID_IMP62_MI_PORT"
brfid_manifest_append udp.imp6.hi "$BRFID_IMP6_HI_PORT"
brfid_manifest_append udp.host106.imp "$BRFID_HOST_A_IMP_PORT"
brfid_manifest_append udp.imp62.hi "$BRFID_IMP62_HI_PORT"
brfid_manifest_append udp.host176.imp "$BRFID_HOST_B_IMP_PORT"
brfid_make_private_socket_dir
brfid_manifest_append runtime.control-socket-namespace "$BRFID_SOCKET_DIR"
BRFID_PDP11_DEBUG_LOG="$results_dir/pdp11-imp-debug.log"
export BRFID_PDP11_DEBUG_LOG
brfid_release_udp_lease_for_launch

brfid_start_process controller "$repo_root" "$results_dir/controller.stdout.log" "$results_dir/controller.stderr.log" \
  python3 "$repo_root/scripts/pdp11-its-controller.py" \
  --h316 "$h316_bin" \
  --pdp10-ka "$pdp10_bin" \
  --pdp11 "$pdp11_bin" \
  --mini-root "$mini_dir" \
  --its-host-work "$its_host_work" \
  --pdp11-work "$pdp11_work" \
  --imp6-config "$repo_root/config/imp/its-pair/imp6.simh" \
  --imp62-config "$repo_root/config/imp/pdp11-its/imp62.simh" \
  --its-host-config "$repo_root/config/hosts/its106-pair.simh" \
  --pdp11-config "$repo_root/config/hosts/pdp11-176.simh" \
  --topology "$repo_root/config/topologies/pdp11-its-telnet.json" \
  --ka10-ingress-trace \
  --results-dir "$results_dir" \
  --manifest "$runtime_dir/run.env" >/dev/null
controller_pid=$BRFID_LAST_PID
if wait "$controller_pid"; then
  controller_status=0
else
  controller_status=$?
fi
brfid_unregister_pid "$controller_pid"
if [ "$controller_status" -ne 0 ]; then
  echo "PDP-11-to-ITS controller failed; see $results_dir/controller.stderr.log" >&2
  exit "$controller_status"
fi

grep -Fxq "passed" "$results_dir/outcome.txt"
grep -Fq "connection_open=1" "$results_dir/application-evidence.txt"
grep -Fq "remote_time=structured" "$results_dir/application-evidence.txt"
grep -Fq "correlated_inter_imp_traffic=both-directions" "$results_dir/application-evidence.txt"
grep -Fq "message_journey_observations=11" "$results_dir/application-evidence.txt"
grep -Fq "message_journey_state=missing-boundary" "$results_dir/application-evidence.txt"
grep -Fq "message_journey_first_boundary=boundary:reply:6" "$results_dir/application-evidence.txt"
journey_sha=$("$repo_root/scripts/sha256-file.sh" "$results_dir/message-journey.jsonl" | awk '{print $1}')
grep -Fxq "sha256.message-journey=$journey_sha" "$runtime_dir/run.env"
grep -Fq "surviving_owned_processes=0" "$results_dir/cleanup-evidence.txt"
brfid_assert_no_transport_errors \
  "$results_dir/imp6.console.log" "$results_dir/imp6.debug.log" \
  "$results_dir/imp62.console.log" "$results_dir/imp62.debug.log" \
  "$results_dir/host106.console.log" "$results_dir/pdp11.console.log" \
  "$results_dir/pdp11-imp-debug.log"
brfid_cleanup
brfid_manifest_append cleanup.outer-runtime passed
echo "PASS: Network UNIX host 176 used TELNET to execute :TIME on ITS host 106 through two recovered IMPs."
brfid_mark_run_passed
