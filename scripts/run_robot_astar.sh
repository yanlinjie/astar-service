#!/usr/bin/env bash
# Run the copied upstream A* service independently of the simulation stack.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ROBOT_ROOT="${ROBOT_ROOT:-$ROOT}"
ROBOT_MAP="${ROBOT_MAP:-family_house/v1}"
RUN_DIR="$ROOT/output/robot-astar-local"
PYTHON="${ROBOT_PYTHON:-$ROOT/.venv/bin/python}"
SERVICE="$ROBOT_ROOT/slam_map_demo/scripts/nav_service.py"
MAP_DIR="$ROBOT_ROOT/slam_map_demo/maps/$ROBOT_MAP"
mkdir -p "$RUN_DIR"
export OPENBLAS_NUM_THREADS=1
export OMP_NUM_THREADS=4

owned_service() {
  [[ -f "$RUN_DIR/service.pid" ]] || return 1
  local service_pid
  service_pid="$(cat "$RUN_DIR/service.pid")"
  [[ "$service_pid" =~ ^[0-9]+$ && -r "/proc/$service_pid/cmdline" ]] || return 1
  tr '\0' ' ' < "/proc/$service_pid/cmdline" | rg -Fq "$SERVICE"
}

case "${1:-start}" in
  start)
    if owned_service; then
      printf 'A* service is already running: http://127.0.0.1:8765\n'
      exit 0
    fi
    "$PYTHON" - "$MAP_DIR" <<'PY'
import socket, sys
from pathlib import Path
import websockets
map_dir = Path(sys.argv[1])
for name in ('meta.yaml', 'waypoints.yaml', 'mujoco/collision_hfield.npz'):
    if not (map_dir / name).is_file():
        raise SystemExit(f'Missing map resource: {map_dir / name}')
for port in (8765, 8766):
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', port))
PY
    nohup setsid "$PYTHON" -I -u "$SERVICE" serve "$MAP_DIR" \
      --host 127.0.0.1 --http-port 8765 --ws-port 8766 \
      </dev/null >>"$RUN_DIR/service.log" 2>&1 &
    service_pid=$!
    printf '%s\n' "$service_pid" > "$RUN_DIR/service.pid"
    for _ in {1..60}; do
      if ! kill -0 "$service_pid" 2>/dev/null; then
        printf 'A* service exited; see %s/service.log\n' "$RUN_DIR" >&2
        exit 1
      fi
      if curl --noproxy '*' -fsS --max-time 2 http://127.0.0.1:8765/health >"$RUN_DIR/health.json" 2>/dev/null; then
        printf 'A* HTTP http://127.0.0.1:8765; WebSocket ws://127.0.0.1:8766\n'
        exit 0
      fi
      sleep 0.5
    done
    printf 'A* startup not confirmed; see %s/service.log\n' "$RUN_DIR" >&2
    exit 1
    ;;
  status)
    curl --noproxy '*' -fsS --max-time 5 http://127.0.0.1:8765/health
    printf '\n'
    ;;
  stop)
    if ! owned_service; then
      printf 'No owned A* service is running.\n'; exit 0
    fi
    kill -TERM "$(cat "$RUN_DIR/service.pid")"
    for _ in {1..40}; do
      if ! owned_service; then
        printf 'A* service stopped.\n'; exit 0
      fi
      sleep 0.25
    done
    printf 'A* process has not exited; inspect service.pid.\n' >&2
    exit 1
    ;;
  *) printf 'Usage: %s {start|status|stop}\n' "$0" >&2; exit 2 ;;
esac
