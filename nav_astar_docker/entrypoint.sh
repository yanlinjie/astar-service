#!/bin/sh
# 容器入口。地图由环境变量 NAV_MAP 选择（如 r2b_storage_ns/2026-11-01.3），不设时用 /data/DEFAULT_MAP。
#
#   serve                       启动 HTTP + WebSocket 服务（默认）
#   plan --start X Y --goals …  命令行规划一次，打印 JSON
#   scene-graph <子命令> …      场景图查询（find / goal / show / describe / list）
#   maps                        列出镜像内的地图
set -e
MAP="${NAV_MAP:-$(cat /data/DEFAULT_MAP)}"
DIR="/data/maps/$MAP"
cmd="${1:-serve}"
[ $# -gt 0 ] && shift

if [ "$cmd" = "maps" ]; then
  cat /data/MANIFEST.txt
  exit 0
fi
if [ ! -f "$DIR/meta.yaml" ]; then
  echo "镜像中没有地图 $MAP，可用的地图：" >&2
  grep -v '^#' /data/MANIFEST.txt | cut -d' ' -f1 >&2
  exit 1
fi

case "$cmd" in
  serve)
    exec python -I -u /app/scripts/nav_service.py serve "$DIR" \
      --host "$NAV_HOST" --http-port "$NAV_HTTP_PORT" --ws-port "$NAV_WS_PORT" "$@" ;;
  plan)
    exec python -I /app/scripts/nav_service.py plan "$DIR" "$@" ;;
  scene-graph)
    sub="$1"; shift
    exec python -I /app/scripts/scene_graph/query_scene_graph.py "$DIR" "$sub" "$@" ;;
  *)
    exec "$cmd" "$@" ;;
esac
