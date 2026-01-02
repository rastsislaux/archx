#!/usr/bin/env bash
set -euo pipefail

#
# Cycle wallpapers using awww/awww-daemon.
#
# Docs: https://codeberg.org/LGFae/awww/raw/branch/main/README.md
#
# Example:
#   bash ~/.config/archx/awww-wallpaper-cycle.sh --interval 600 --transition-type random
#

usage() {
  cat <<'EOF'
Usage: awww-wallpaper-cycle.sh [options]

Options:
  --dir DIR                Wallpaper directory (default: ~/.config/archx/wallpaper)
  --interval SECONDS       Interval between changes (default: 300)
  --log-file FILE          Write logs to FILE (default: $XDG_STATE_HOME/archx/awww-wallpaper-cycle.log)
  --outputs OUTPUTS        Outputs passed to `awww img -o ...` (optional)
  --transition-type TYPE   Transition type passed to `awww img --transition-type` (optional)
  --transition-step N      Transition step passed to `awww img --transition-step` (optional)
  --transition-fps N       Transition fps passed to `awww img --transition-fps` (optional)
  --shuffle                Shuffle wallpaper order each loop (default)
  --no-shuffle             Keep deterministic order
  --once                   Set one wallpaper and exit
  -h, --help               Show help
EOF
}

DIR="${HOME}/.config/archx/wallpaper"
INTERVAL="300"
STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"
LOG_FILE="${STATE_HOME}/archx/awww-wallpaper-cycle.log"
OUTPUTS=""
TRANSITION_TYPE=""
TRANSITION_STEP=""
TRANSITION_FPS=""
SHUFFLE="1"
ONCE="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="${2:?}"; shift 2 ;;
    --interval) INTERVAL="${2:?}"; shift 2 ;;
    --log-file) LOG_FILE="${2:?}"; shift 2 ;;
    --outputs) OUTPUTS="${2:?}"; shift 2 ;;
    --transition-type) TRANSITION_TYPE="${2:?}"; shift 2 ;;
    --transition-step) TRANSITION_STEP="${2:?}"; shift 2 ;;
    --transition-fps) TRANSITION_FPS="${2:?}"; shift 2 ;;
    --shuffle) SHUFFLE="1"; shift ;;
    --no-shuffle) SHUFFLE="0"; shift ;;
    --once) ONCE="1"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# Open a dedicated FD for logging so we can safely redirect command output.
exec 3>>"$LOG_FILE"

log() {
  # Timestamped log lines (local time).
  printf '[%(%Y-%m-%d %H:%M:%S)T] %s\n' -1 "$*" >&3
}

log "starting: dir=$DIR interval=${INTERVAL}s shuffle=$SHUFFLE once=$ONCE"

if ! command -v awww >/dev/null 2>&1; then
  log "ERROR: awww not found on PATH"
  echo "[archx] awww not found on PATH" >&2
  exit 1
fi
if ! command -v awww-daemon >/dev/null 2>&1; then
  log "ERROR: awww-daemon not found on PATH"
  echo "[archx] awww-daemon not found on PATH" >&2
  exit 1
fi

if [[ ! -d "$DIR" ]]; then
  log "ERROR: wallpaper dir not found: $DIR"
  echo "[archx] wallpaper dir not found: $DIR" >&2
  exit 1
fi

# Avoid starting multiple cyclers.
LOCK_DIR="${XDG_RUNTIME_DIR:-/tmp}"
mkdir -p "$LOCK_DIR"
LOCK_FILE="$LOCK_DIR/archx-awww-wallpaper.lock"
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "another instance is running (lock: $LOCK_FILE); exiting"
  echo "[archx] wallpaper cycler already running; exiting." >&2
  exit 0
fi

# Hyprland (or the caller) is responsible for starting awww-daemon.
if ! pgrep -x awww-daemon >/dev/null 2>&1; then
  log "ERROR: awww-daemon is not running"
  echo "[archx] awww-daemon is not running. Start it first (e.g. via Hyprland exec-once)." >&2
  exit 1
fi

build_awww_args() {
  local -a args
  args=(awww img)
  if [[ -n "$OUTPUTS" ]]; then
    args+=(-o "$OUTPUTS")
  fi
  args+=("$1")
  if [[ -n "$TRANSITION_TYPE" ]]; then
    args+=(--transition-type "$TRANSITION_TYPE")
  fi
  if [[ -n "$TRANSITION_STEP" ]]; then
    args+=(--transition-step "$TRANSITION_STEP")
  fi
  if [[ -n "$TRANSITION_FPS" ]]; then
    args+=(--transition-fps "$TRANSITION_FPS")
  fi
  printf '%s\0' "${args[@]}"
}

list_wallpapers() {
  # Keep extension list conservative; awww supports many formats.
  # See docs link above for full list.
  find "$DIR" -type f \
    \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' -o -iname '*.gif' \) \
    -print0
}

mapfile -d '' -t files < <(list_wallpapers)
if [[ ${#files[@]} -eq 0 ]]; then
  log "ERROR: no wallpapers found in $DIR"
  echo "[archx] no wallpapers found in $DIR" >&2
  exit 1
fi
log "found ${#files[@]} wallpapers under $DIR"

cycle_once() {
  local -a arr=("$@")
  if [[ "$SHUFFLE" == "1" ]]; then
    # Shuffle using shuf if available; otherwise fall back to sort order.
    if command -v shuf >/dev/null 2>&1; then
      mapfile -t arr < <(printf '%s\n' "${arr[@]}" | shuf)
    fi
  fi

  for f in "${arr[@]}"; do
    # shellcheck disable=SC2207
    IFS=$'\0' read -r -d '' -a args < <(build_awww_args "$f"; printf '\0')
    log "set wallpaper: $f"
    if ! "${args[@]}" >&3 2>&3; then
      log "WARN: awww failed for: $f"
    fi
    if [[ "$ONCE" == "1" ]]; then
      return 0
    fi
    sleep "$INTERVAL"
  done
}

while true; do
  cycle_once "${files[@]}"
  if [[ "$ONCE" == "1" ]]; then
    exit 0
  fi
done


