#!/bin/sh

# Source this file from a run script. All mutable state uses the BRFID_ prefix.

brfid_runtime_init() {
  umask 077
  BRFID_MANAGED_PIDS=
  BRFID_NCP_CLIENT_PIDS=
  BRFID_SOCKET_NAMES=
  BRFID_SOCKET_DIR=
  BRFID_PORT_LEASE_PID=
  BRFID_PORT_LEASE_READY=
  BRFID_PORT_LEASE_RELEASED=
  BRFID_EXCLUSIVE_LEASE_DIR=
  BRFID_RUN_MANIFEST=
  BRFID_RUN_MANIFEST_FINISHED=0
  BRFID_RUN_OUTCOME=failed
  BRFID_CLEANED=0
  export BRFID_MANAGED_PIDS BRFID_NCP_CLIENT_PIDS
  export BRFID_SOCKET_NAMES BRFID_SOCKET_DIR
  export BRFID_PORT_LEASE_PID BRFID_PORT_LEASE_READY
  export BRFID_PORT_LEASE_RELEASED BRFID_EXCLUSIVE_LEASE_DIR
  export BRFID_RUN_MANIFEST
  export BRFID_RUN_MANIFEST_FINISHED BRFID_RUN_OUTCOME BRFID_CLEANED
}

brfid_register_pid() {
  case ${1-} in
    ''|*[!0-9]*)
      echo "invalid child PID: ${1-}" >&2
      return 64
      ;;
  esac
  BRFID_MANAGED_PIDS="$1 ${BRFID_MANAGED_PIDS-}"
  export BRFID_MANAGED_PIDS
}

brfid_unregister_pid() {
  case ${1-} in
    ''|*[!0-9]*)
      echo "invalid child PID: ${1-}" >&2
      return 64
      ;;
  esac
  brfid_remaining_pids=
  for brfid_registered_pid in ${BRFID_MANAGED_PIDS-}; do
    if [ "$brfid_registered_pid" != "$1" ]; then
      brfid_remaining_pids="$brfid_remaining_pids $brfid_registered_pid"
    fi
  done
  BRFID_MANAGED_PIDS=$brfid_remaining_pids
  export BRFID_MANAGED_PIDS
}

brfid_register_ncp_client_pid() {
  case ${1-} in
    ''|*[!0-9]*)
      echo "invalid NCP client PID: ${1-}" >&2
      return 64
      ;;
  esac
  BRFID_NCP_CLIENT_PIDS="$1 ${BRFID_NCP_CLIENT_PIDS-}"
  export BRFID_NCP_CLIENT_PIDS
}

brfid_unregister_ncp_client_pid() {
  case ${1-} in
    ''|*[!0-9]*)
      echo "invalid NCP client PID: ${1-}" >&2
      return 64
      ;;
  esac
  brfid_remaining_clients=
  for brfid_registered_client in ${BRFID_NCP_CLIENT_PIDS-}; do
    if [ "$brfid_registered_client" != "$1" ]; then
      brfid_remaining_clients="$brfid_remaining_clients $brfid_registered_client"
    fi
  done
  BRFID_NCP_CLIENT_PIDS=$brfid_remaining_clients
  export BRFID_NCP_CLIENT_PIDS
}

brfid_remove_ncp_client_socket() {
  case ${1-} in
    ''|*[!0-9]*)
      echo "invalid NCP client PID: ${1-}" >&2
      return 64
      ;;
  esac
  brfid_client_socket=/tmp/client.$1
  if [ -S "$brfid_client_socket" ]; then
    rm -f "$brfid_client_socket"
  fi
}

brfid_stop_pid_bounded() {
  brfid_stop_pid=$1
  brfid_stop_limit=${2:-5}
  if ! kill -0 "$brfid_stop_pid" 2>/dev/null; then
    wait "$brfid_stop_pid" 2>/dev/null || true
    return 0
  fi
  kill "$brfid_stop_pid" 2>/dev/null || true
  brfid_stop_elapsed=0
  while [ "$brfid_stop_elapsed" -lt "$brfid_stop_limit" ]; do
    if ! kill -0 "$brfid_stop_pid" 2>/dev/null; then
      break
    fi
    sleep 1
    brfid_stop_elapsed=$((brfid_stop_elapsed + 1))
  done
  if kill -0 "$brfid_stop_pid" 2>/dev/null; then
    kill -KILL "$brfid_stop_pid" 2>/dev/null || true
  fi
  wait "$brfid_stop_pid" 2>/dev/null || true
}

brfid_start_process() {
  if [ "$#" -lt 5 ]; then
    echo "usage: brfid_start_process NAME WORK_DIR STDOUT STDERR COMMAND [ARG ...]" >&2
    return 64
  fi
  brfid_start_name=$1
  brfid_start_directory=$2
  brfid_start_stdout=$3
  brfid_start_stderr=$4
  shift 4
  (
    CDPATH= cd -- "$brfid_start_directory"
    exec "$@"
  ) >"$brfid_start_stdout" 2>"$brfid_start_stderr" &
  BRFID_LAST_PID=$!
  brfid_register_pid "$BRFID_LAST_PID"
  export BRFID_LAST_PID
  if [ -n "${BRFID_RUN_MANIFEST-}" ]; then
    brfid_manifest_append "process.$brfid_start_name.pid" "$BRFID_LAST_PID"
  fi
  printf '%s_pid=%s\n' "$brfid_start_name" "$BRFID_LAST_PID"
}

brfid_run_child_bounded() {
  if [ "$#" -lt 3 ]; then
    echo "usage: brfid_run_child_bounded KIND SECONDS COMMAND [ARG ...]" >&2
    return 64
  fi
  brfid_bounded_kind=$1
  brfid_bounded_limit=$2
  shift 2
  case $brfid_bounded_kind in
    generic|ncp) ;;
    *)
      echo "invalid bounded child kind: $brfid_bounded_kind" >&2
      return 64
      ;;
  esac
  case $brfid_bounded_limit in
    ''|*[!0-9]*)
      echo "invalid timeout: $brfid_bounded_limit" >&2
      return 64
      ;;
  esac
  if [ "$brfid_bounded_limit" -lt 1 ]; then
    echo "timeout must be positive" >&2
    return 64
  fi

  "$@" &
  brfid_bounded_pid=$!
  brfid_register_pid "$brfid_bounded_pid"
  if [ "$brfid_bounded_kind" = ncp ]; then
    brfid_register_ncp_client_pid "$brfid_bounded_pid"
  fi

  brfid_bounded_elapsed=0
  while kill -0 "$brfid_bounded_pid" 2>/dev/null; do
    if [ "$brfid_bounded_elapsed" -ge "$brfid_bounded_limit" ]; then
      if [ "$brfid_bounded_kind" = ncp ]; then
        brfid_remove_ncp_client_socket "$brfid_bounded_pid"
      fi
      brfid_stop_pid_bounded "$brfid_bounded_pid" 2
      brfid_unregister_pid "$brfid_bounded_pid"
      if [ "$brfid_bounded_kind" = ncp ]; then
        brfid_unregister_ncp_client_pid "$brfid_bounded_pid"
      fi
      return 124
    fi
    sleep 1
    brfid_bounded_elapsed=$((brfid_bounded_elapsed + 1))
  done

  if [ "$brfid_bounded_kind" = ncp ]; then
    brfid_remove_ncp_client_socket "$brfid_bounded_pid"
  fi
  if wait "$brfid_bounded_pid"; then
    brfid_bounded_status=0
  else
    brfid_bounded_status=$?
  fi
  brfid_unregister_pid "$brfid_bounded_pid"
  if [ "$brfid_bounded_kind" = ncp ]; then
    brfid_unregister_ncp_client_pid "$brfid_bounded_pid"
  fi
  return "$brfid_bounded_status"
}

brfid_run_bounded() {
  if [ "$#" -lt 2 ]; then
    echo "usage: brfid_run_bounded SECONDS COMMAND [ARG ...]" >&2
    return 64
  fi
  brfid_generic_limit=$1
  shift
  brfid_run_child_bounded generic "$brfid_generic_limit" "$@"
}

brfid_run_ncp_client_bounded() {
  if [ "$#" -lt 2 ]; then
    echo "usage: brfid_run_ncp_client_bounded SECONDS COMMAND [ARG ...]" >&2
    return 64
  fi
  brfid_ncp_limit=$1
  shift
  brfid_run_child_bounded ncp "$brfid_ncp_limit" "$@"
}

brfid_assert_managed_alive() {
  for brfid_alive_pid in ${BRFID_MANAGED_PIDS-}; do
    if ! kill -0 "$brfid_alive_pid" 2>/dev/null; then
      echo "managed process exited early: PID $brfid_alive_pid" >&2
      return 1
    fi
  done
}

brfid_make_private_socket_dir() {
  if [ -n "${BRFID_SOCKET_DIR-}" ]; then
    echo "private NCP socket directory already exists" >&2
    return 64
  fi
  brfid_socket_prefix=${TMPDIR:-/tmp}/brfid-ncp.XXXXXX
  BRFID_SOCKET_DIR=$(mktemp -d "$brfid_socket_prefix") || return 1
  chmod 700 "$BRFID_SOCKET_DIR"
  export BRFID_SOCKET_DIR
}

brfid_ncp_socket() {
  case ${1-} in
    ''|*[!A-Za-z0-9_-]*)
      echo "invalid NCP socket name: ${1-}" >&2
      return 64
      ;;
  esac
  if [ -z "${BRFID_SOCKET_DIR-}" ]; then
    echo "call brfid_make_private_socket_dir first" >&2
    return 64
  fi
  BRFID_NCP_SOCKET="$BRFID_SOCKET_DIR/$1"
  if [ "$(printf '%s' "$BRFID_NCP_SOCKET" | wc -c | tr -d ' ')" -gt 96 ]; then
    echo "NCP Unix socket path is too long: $BRFID_NCP_SOCKET" >&2
    return 1
  fi
  BRFID_SOCKET_NAMES="$1 ${BRFID_SOCKET_NAMES-}"
  export BRFID_NCP_SOCKET BRFID_SOCKET_NAMES
}

brfid_create_results_dir() {
  if [ "$#" -ne 1 ]; then
    echo "usage: brfid_create_results_dir RESULTS_DIR" >&2
    return 64
  fi
  brfid_results_input=$1
  brfid_results_parent=$(dirname "$brfid_results_input")
  mkdir -p "$brfid_results_parent"
  if ! mkdir "$brfid_results_input"; then
    echo "could not create a new results directory: $brfid_results_input" >&2
    return 73
  fi
  BRFID_RESULTS_DIR=$(CDPATH= cd -- "$brfid_results_input" && pwd)
  export BRFID_RESULTS_DIR
}

brfid_acquire_exclusive_lease() {
  if [ "$#" -ne 1 ]; then
    echo "usage: brfid_acquire_exclusive_lease LOCK_DIR" >&2
    return 64
  fi
  if [ -n "${BRFID_EXCLUSIVE_LEASE_DIR-}" ]; then
    echo "an exclusive lease is already held" >&2
    return 64
  fi
  if ! mkdir "$1"; then
    echo "exclusive build/use lease is busy: $1" >&2
    echo "If no build or smoke is running, remove that empty stale lock directory manually." >&2
    return 75
  fi
  BRFID_EXCLUSIVE_LEASE_DIR=$1
  export BRFID_EXCLUSIVE_LEASE_DIR
}

brfid_manifest_append() {
  if [ "$#" -ne 2 ] || [ -z "${BRFID_RUN_MANIFEST-}" ]; then
    echo "usage: brfid_manifest_append KEY VALUE after manifest initialization" >&2
    return 64
  fi
  case $1 in
    ''|*[!A-Za-z0-9_.-]*)
      echo "invalid run-manifest key: $1" >&2
      return 64
      ;;
  esac
  printf '%s=%s\n' "$1" "$2" >>"$BRFID_RUN_MANIFEST"
}

brfid_manifest_init() {
  if [ "$#" -ne 3 ]; then
    echo "usage: brfid_manifest_init MANIFEST TOPOLOGY REPO_ROOT" >&2
    return 64
  fi
  BRFID_RUN_MANIFEST=$1
  brfid_manifest_topology=$2
  brfid_manifest_repo=$3
  if [ -e "$BRFID_RUN_MANIFEST" ]; then
    echo "run manifest already exists: $BRFID_RUN_MANIFEST" >&2
    return 73
  fi
  : >"$BRFID_RUN_MANIFEST"
  BRFID_RUN_OUTCOME=failed
  BRFID_RUN_MANIFEST_FINISHED=0
  export BRFID_RUN_MANIFEST BRFID_RUN_OUTCOME BRFID_RUN_MANIFEST_FINISHED
  brfid_manifest_append format 1
  brfid_manifest_append topology "$brfid_manifest_topology"
  brfid_manifest_append started_utc "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  brfid_manifest_append platform "$(uname -srm)"
  brfid_manifest_revision=$(git -C "$brfid_manifest_repo" rev-parse HEAD)
  brfid_manifest_append repository.revision "$brfid_manifest_revision"
  if [ -n "$(git -C "$brfid_manifest_repo" status --porcelain --untracked-files=no --ignore-submodules=dirty)" ]; then
    brfid_manifest_append repository.tracked_dirty 1
  else
    brfid_manifest_append repository.tracked_dirty 0
  fi
}

brfid_manifest_add_git() {
  if [ "$#" -ne 2 ]; then
    echo "usage: brfid_manifest_add_git NAME CHECKOUT" >&2
    return 64
  fi
  brfid_manifest_git_revision=$(git -C "$2" rev-parse HEAD)
  brfid_manifest_append "source.$1.revision" "$brfid_manifest_git_revision"
  if [ -n "$(git -C "$2" status --porcelain --untracked-files=no --ignore-submodules=dirty)" ]; then
    brfid_manifest_append "source.$1.tracked_dirty" 1
  else
    brfid_manifest_append "source.$1.tracked_dirty" 0
  fi
}

brfid_manifest_add_file() {
  if [ "$#" -ne 3 ]; then
    echo "usage: brfid_manifest_add_file NAME FILE SHA256_HELPER" >&2
    return 64
  fi
  if ! brfid_manifest_hash_line=$("$3" "$2"); then
    echo "could not hash run-manifest file: $2" >&2
    return 1
  fi
  brfid_manifest_digest=${brfid_manifest_hash_line%% *}
  if [ "${#brfid_manifest_digest}" -ne 64 ]; then
    echo "invalid SHA-256 length for run-manifest file: $2" >&2
    return 1
  fi
  case $brfid_manifest_digest in
    *[!0-9A-Fa-f]*|'')
      echo "invalid SHA-256 for run-manifest file: $2" >&2
      return 1
      ;;
  esac
  brfid_manifest_append "sha256.$1" "$brfid_manifest_digest"
  brfid_manifest_append "path.$1" "$2"
}

brfid_manifest_add_port_metadata() {
  if [ "$#" -ne 1 ]; then
    echo "usage: brfid_manifest_add_port_metadata PORTS_FILE" >&2
    return 64
  fi
  while IFS='=' read -r brfid_port_key brfid_port_value; do
    case $brfid_port_key in
      count|families|port_[0-9]*)
        brfid_manifest_append "udp.$brfid_port_key" "$brfid_port_value"
        ;;
    esac
  done <"$1"
}

brfid_mark_run_passed() {
  BRFID_RUN_OUTCOME=passed
  export BRFID_RUN_OUTCOME
}

brfid_finish_run_manifest() {
  if [ -z "${BRFID_RUN_MANIFEST-}" ] || [ "${BRFID_RUN_MANIFEST_FINISHED:-0}" -eq 1 ]; then
    return 0
  fi
  brfid_manifest_exit_status=$1
  if [ "$brfid_manifest_exit_status" -ne 0 ]; then
    BRFID_RUN_OUTCOME=failed
    export BRFID_RUN_OUTCOME
  fi
  brfid_manifest_append finished_utc "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  brfid_manifest_append outcome "${BRFID_RUN_OUTCOME:-failed}"
  brfid_manifest_append exit_status "$brfid_manifest_exit_status"
  BRFID_RUN_MANIFEST_FINISHED=1
  export BRFID_RUN_MANIFEST_FINISHED
}

brfid_reserve_udp_ports() {
  if [ "$#" -ne 4 ]; then
    echo "usage: brfid_reserve_udp_ports HELPER COUNT STATE_DIR READY_FILE" >&2
    return 64
  fi
  brfid_lease_helper=$1
  brfid_lease_count=$2
  brfid_lease_state=$3
  brfid_lease_ready=$4
  brfid_lock_root=${BRFID_PORT_LOCK_ROOT:-${TMPDIR:-/tmp}/brfid-udp-port-locks-$(id -u)}
  mkdir -p "$brfid_lease_state"
  rm -f "$brfid_lease_ready"
  python3 "$brfid_lease_helper" \
    --count "$brfid_lease_count" \
    --lock-root "$brfid_lock_root" \
    --ready-file "$brfid_lease_ready" \
    --owner-pid "$$" \
    >"$brfid_lease_state/lease.stdout.log" \
    2>"$brfid_lease_state/lease.stderr.log" &
  BRFID_PORT_LEASE_PID=$!
  BRFID_PORT_LEASE_READY=$brfid_lease_ready
  export BRFID_PORT_LEASE_PID BRFID_PORT_LEASE_READY

  brfid_lease_elapsed=0
  while [ "$brfid_lease_elapsed" -lt 10 ] && [ ! -s "$brfid_lease_ready" ]; do
    if ! kill -0 "$BRFID_PORT_LEASE_PID" 2>/dev/null; then
      wait "$BRFID_PORT_LEASE_PID" 2>/dev/null || true
      echo "UDP reservation helper exited before becoming ready" >&2
      return 1
    fi
    sleep 1
    brfid_lease_elapsed=$((brfid_lease_elapsed + 1))
  done
  if [ ! -s "$brfid_lease_ready" ]; then
    echo "UDP reservation helper did not become ready" >&2
    return 1
  fi

  BRFID_PORT_COUNT=$(sed -n 's/^count=//p' "$brfid_lease_ready")
  BRFID_PORT_LEASE_RELEASED=$(sed -n 's/^released=//p' "$brfid_lease_ready")
  case $BRFID_PORT_COUNT in
    ''|*[!0-9]*)
      echo "invalid UDP reservation metadata" >&2
      return 1
      ;;
  esac
  if [ "$BRFID_PORT_COUNT" -lt 1 ] || [ -z "$BRFID_PORT_LEASE_RELEASED" ]; then
    echo "incomplete UDP reservation metadata" >&2
    return 1
  fi
  BRFID_ALLOCATED_PORTS=
  brfid_port_index=0
  while [ "$brfid_port_index" -lt "$BRFID_PORT_COUNT" ]; do
    brfid_port_value=$(sed -n "s/^port_${brfid_port_index}=//p" "$brfid_lease_ready")
    case $brfid_port_value in
      ''|*[!0-9]*)
        echo "invalid UDP port metadata at index $brfid_port_index" >&2
        return 1
        ;;
    esac
    BRFID_ALLOCATED_PORTS="$BRFID_ALLOCATED_PORTS $brfid_port_value"
    brfid_port_index=$((brfid_port_index + 1))
  done
  export BRFID_PORT_COUNT BRFID_PORT_LEASE_RELEASED BRFID_ALLOCATED_PORTS
}

brfid_assign_two_host_ports() {
  if [ "${BRFID_PORT_COUNT:-0}" -ne 6 ]; then
    echo "two-host topology requires exactly six allocated ports" >&2
    return 64
  fi
  set -- $BRFID_ALLOCATED_PORTS
  BRFID_IMP6_MI_PORT=$1
  BRFID_IMP62_MI_PORT=$2
  BRFID_IMP6_HI_PORT=$3
  BRFID_HOST_A_IMP_PORT=$4
  BRFID_IMP62_HI_PORT=$5
  BRFID_HOST_B_IMP_PORT=$6
  export BRFID_IMP6_MI_PORT BRFID_IMP62_MI_PORT
  export BRFID_IMP6_HI_PORT BRFID_HOST_A_IMP_PORT
  export BRFID_IMP62_HI_PORT BRFID_HOST_B_IMP_PORT
}

brfid_assign_router_oracle_ports() {
  if [ "${BRFID_PORT_COUNT:-0}" -ne 10 ]; then
    echo "router oracle requires exactly ten allocated ports" >&2
    return 64
  fi
  set -- $BRFID_ALLOCATED_PORTS
  BRFID_IMP2_MI1_PORT=$1
  BRFID_IMP3_MI1_PORT=$2
  BRFID_IMP2_MI2_PORT=$3
  BRFID_DEAD_MODEM_PORT=$4
  BRFID_IMP3_MI2_PORT=$5
  BRFID_IMP4_MI1_PORT=$6
  BRFID_IMP2_HI_PORT=$7
  BRFID_NCP2_IMP_PORT=$8
  BRFID_IMP3_HI_PORT=$9
  shift 9
  BRFID_NCP3_IMP_PORT=$1
  export BRFID_IMP2_MI1_PORT BRFID_IMP3_MI1_PORT
  export BRFID_IMP2_MI2_PORT BRFID_DEAD_MODEM_PORT
  export BRFID_IMP3_MI2_PORT BRFID_IMP4_MI1_PORT
  export BRFID_IMP2_HI_PORT BRFID_NCP2_IMP_PORT
  export BRFID_IMP3_HI_PORT BRFID_NCP3_IMP_PORT
}

brfid_assert_no_transport_errors() {
  for brfid_transport_log do
    if [ -f "$brfid_transport_log" ] && grep -Eiq "bind error|Can't open Datagram socket|UNRECOVERABLE I/O ERROR|tmxr_put_packet_ln\(\) failed" "$brfid_transport_log"; then
      echo "simulated transport failed; see $brfid_transport_log" >&2
      return 1
    fi
  done
}

brfid_release_udp_lease_for_launch() {
  if [ -z "${BRFID_PORT_LEASE_PID-}" ] || [ -z "${BRFID_PORT_LEASE_RELEASED-}" ]; then
    echo "no active UDP reservation" >&2
    return 64
  fi
  rm -f "$BRFID_PORT_LEASE_RELEASED"
  kill -USR1 "$BRFID_PORT_LEASE_PID"
  brfid_release_elapsed=0
  while [ "$brfid_release_elapsed" -lt 5 ] && [ ! -s "$BRFID_PORT_LEASE_RELEASED" ]; do
    if ! kill -0 "$BRFID_PORT_LEASE_PID" 2>/dev/null; then
      echo "UDP reservation helper exited during handoff" >&2
      return 1
    fi
    sleep 1
    brfid_release_elapsed=$((brfid_release_elapsed + 1))
  done
  if [ ! -s "$BRFID_PORT_LEASE_RELEASED" ]; then
    echo "UDP reservation helper did not acknowledge handoff" >&2
    return 1
  fi
}

brfid_cleanup() {
  if [ "${BRFID_CLEANED:-0}" -eq 1 ]; then
    return 0
  fi
  brfid_cleanup_status=0

  for brfid_cleanup_client in ${BRFID_NCP_CLIENT_PIDS-}; do
    brfid_remove_ncp_client_socket "$brfid_cleanup_client" || brfid_cleanup_status=1
  done
  for brfid_cleanup_pid in ${BRFID_MANAGED_PIDS-}; do
    brfid_stop_pid_bounded "$brfid_cleanup_pid" 5
  done
  if [ -n "${BRFID_PORT_LEASE_PID-}" ]; then
    brfid_stop_pid_bounded "$BRFID_PORT_LEASE_PID" 3
    BRFID_PORT_LEASE_PID=
  fi
  for brfid_cleanup_socket_name in ${BRFID_SOCKET_NAMES-}; do
    rm -f "$BRFID_SOCKET_DIR/$brfid_cleanup_socket_name" || brfid_cleanup_status=1
  done
  if [ -n "${BRFID_SOCKET_DIR-}" ]; then
    if [ -d "$BRFID_SOCKET_DIR" ] && ! rmdir "$BRFID_SOCKET_DIR" 2>/dev/null; then
      brfid_cleanup_status=1
    fi
  fi
  rm -f "${BRFID_PORT_LEASE_RELEASED-}" "${BRFID_PORT_LEASE_READY-}" || brfid_cleanup_status=1
  if [ -n "${BRFID_EXCLUSIVE_LEASE_DIR-}" ] && [ -d "$BRFID_EXCLUSIVE_LEASE_DIR" ]; then
    if ! rmdir "$BRFID_EXCLUSIVE_LEASE_DIR" 2>/dev/null; then
      brfid_cleanup_status=1
    fi
  fi
  if [ "$brfid_cleanup_status" -eq 0 ]; then
    BRFID_CLEANED=1
    export BRFID_CLEANED
  fi
  return "$brfid_cleanup_status"
}

brfid_exit_trap() {
  brfid_exit_status=$?
  trap - 0 1 2 15
  brfid_cleanup || true
  brfid_finish_run_manifest "$brfid_exit_status"
  exit "$brfid_exit_status"
}

brfid_install_cleanup_traps() {
  trap brfid_exit_trap 0
  trap 'exit 129' 1
  trap 'exit 130' 2
  trap 'exit 143' 15
}
