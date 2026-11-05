simba_log_to_stdout() {
  [[ ${SIMBA_LOG_TO_STDOUT:-} == "1" || -z ${SIMBA_INSTALL_LOG_FILE:-} ]]
}

simba_log_line() {
  if simba_log_to_stdout; then
    echo "$1"
  else
    echo "$1" >>"$SIMBA_INSTALL_LOG_FILE"
  fi
}

start_install_log() {
  if ! simba_log_to_stdout; then
    mkdir -p "$(dirname "$SIMBA_INSTALL_LOG_FILE")"
    touch "$SIMBA_INSTALL_LOG_FILE"
    chmod 666 "$SIMBA_INSTALL_LOG_FILE" 2>/dev/null || true
  fi

  export SIMBA_START_TIME="${SIMBA_START_TIME:-$(date '+%Y-%m-%d %H:%M:%S')}"
  export SIMBA_START_EPOCH="${SIMBA_START_EPOCH:-$(date +%s)}"

  simba_log_line "=== Simba Setup Started: $SIMBA_START_TIME ==="
}

stop_install_log() {
  local end_time end_epoch duration mins secs
  end_time=$(date '+%Y-%m-%d %H:%M:%S')
  end_epoch=$(date +%s)

  simba_log_line "=== Simba Setup Completed: $end_time ==="

  if [[ -n ${SIMBA_START_EPOCH:-} ]]; then
    duration=$((end_epoch - SIMBA_START_EPOCH))
    mins=$((duration / 60))
    secs=$((duration % 60))
    simba_log_line "Simba setup: ${mins}m ${secs}s"
  fi
}

run_logged() {
  local script="$1"
  local exit_code errexit_was_set=0

  simba_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Starting: $script"

  case $- in
    *e*)
      errexit_was_set=1
      set +e
      ;;
  esac

  local runner=(bash -eE)
  if [[ ${SIMBA_INSTALL_DEBUG:-} == "1" ]]; then
    runner=(bash -x -eE)
  fi

  if simba_log_to_stdout; then
    PS4='+ ${BASH_SOURCE[0]##*/}:${LINENO}:${FUNCNAME[0]:-main}: ' \
      "${runner[@]}" -c 'source "$1"' bash "$script" </dev/null 2>&1
  else
    PS4='+ ${BASH_SOURCE[0]##*/}:${LINENO}:${FUNCNAME[0]:-main}: ' \
      "${runner[@]}" -c 'source "$1"' bash "$script" </dev/null >>"$SIMBA_INSTALL_LOG_FILE" 2>&1
  fi

  exit_code=$?
  (( errexit_was_set )) && set -e

  if (( exit_code == 0 )); then
    simba_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Completed: $script"
  else
    simba_log_line "[$(date '+%Y-%m-%d %H:%M:%S')] Failed: $script (exit code: $exit_code)"
  fi

  return $exit_code
}
