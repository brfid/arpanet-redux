#!/bin/sh

# Source this file from a run script. All mutable state uses the BRFID_ prefix.

brfid_runtime_init() {
  umask 077
  BRFID_MANAGED_PIDS=
  BRFID_SOCKET_PATHS=
  BRFID_SOCKET_DIRS=
  BRFID_PORT_LEASE_PID=
  BRFID_PORT_LEASE_READY=
  BRFID_PORT_LEASE_RELEASED=
  BRFID_CLEANED=0
  export BRFID_MANAGED_PIDS BRFID_SOCKET_PATHS BRFID_SOCKET_DIRS
  export BRFID_PORT_LEASE_PID BRFID_PORT_LEASE_READY
  export BRFID_PORT_LEASE_RELEASED BRFID_CLEANED
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
  printf '%s_pid=%s\n' "$brfid_start_name" "$BRFID_LAST_PID"
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
  brfid_socket_prefix=${TMPDIR:-/tmp}/brfid-ncp.XXXXXX
  BRFID_SOCKET_DIR=$(mktemp -d "$brfid_socket_prefix") || return 1
  chmod 700 "$BRFID_SOCKET_DIR"
  BRFID_SOCKET_DIRS="$BRFID_SOCKET_DIR ${BRFID_SOCKET_DIRS-}"
  export BRFID_SOCKET_DIR BRFID_SOCKET_DIRS
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
  BRFID_SOCKET_PATHS="$BRFID_NCP_SOCKET ${BRFID_SOCKET_PATHS-}"
  export BRFID_NCP_SOCKET BRFID_SOCKET_PATHS
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
  BRFID_CLEANED=1
  export BRFID_CLEANED

  for brfid_cleanup_pid in ${BRFID_MANAGED_PIDS-}; do
    brfid_stop_pid_bounded "$brfid_cleanup_pid" 5
  done
  if [ -n "${BRFID_PORT_LEASE_PID-}" ]; then
    brfid_stop_pid_bounded "$BRFID_PORT_LEASE_PID" 3
    BRFID_PORT_LEASE_PID=
  fi
  for brfid_cleanup_socket in ${BRFID_SOCKET_PATHS-}; do
    rm -f "$brfid_cleanup_socket"
  done
  for brfid_cleanup_directory in ${BRFID_SOCKET_DIRS-}; do
    rmdir "$brfid_cleanup_directory" 2>/dev/null || true
  done
  rm -f "${BRFID_PORT_LEASE_RELEASED-}" "${BRFID_PORT_LEASE_READY-}"
}

brfid_exit_trap() {
  brfid_exit_status=$?
  trap - 0 1 2 15
  brfid_cleanup
  exit "$brfid_exit_status"
}

brfid_install_cleanup_traps() {
  trap brfid_exit_trap 0
  trap 'exit 129' 1
  trap 'exit 130' 2
  trap 'exit 143' 15
}
