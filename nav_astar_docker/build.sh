#!/usr/bin/env bash
# 把 A* 导航规划所需的代码和地图数据整理到 build/context，再构建镜像。
#
#   ./build.sh            构建镜像 robot-nav-astar:latest（同时打上日期标签）
#   ./build.sh --stage    只整理构建目录，不构建
#
# 代码和地图都从 slam_map_demo 复制（那里是唯一的源头）；改了点位、重建了地图或改了脚本后，重新运行本脚本即可。
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEMO="$HERE/../slam_map_demo"
CTX="$HERE/build/context"
IMAGE="${IMAGE:-robot-nav-astar}"
TAG="$(date +%Y%m%d-%H%M)"

rm -rf "$CTX"
mkdir -p "$CTX/app/scripts/scene_graph" "$CTX/app/docs" "$CTX/data/maps"

# ---------- 代码 ----------
# nav_service.py：HTTP/WebSocket 服务；nav_grid.py：A* 与障碍判定；
# map_to_mujoco.py：只用到其中的障碍高度阈值 FLOOR_MAX_HEIGHT（顶层只依赖 numpy/scipy/yaml）
for f in nav_service.py nav_grid.py map_to_mujoco.py; do
  cp "$DEMO/scripts/$f" "$CTX/app/scripts/"
done
# 场景图运行时查询库与命令行工具（构建场景图的 build_scene_graph.py 需要 GPU 和大模型，不放进镜像）
for f in scene_graph.py query_scene_graph.py; do
  cp "$DEMO/scripts/scene_graph/$f" "$CTX/app/scripts/scene_graph/"
done
cp "$HERE/tools/make_grid_images.py" "$HERE/entrypoint.sh" "$HERE/requirements.txt" "$CTX/app/"
cp "$HERE/README.md" "$CTX/app/docs/README.md"
cp "$DEMO/导航规划服务接口文档.md" "$CTX/app/docs/"
cp "$DEMO/scripts/scene_graph/README.md" "$CTX/app/docs/场景图说明.md"
cp "$HERE/Dockerfile" "$CTX/"

# ---------- 地图 ----------
# 每个地图包只取规划相关的文件：
#   meta.yaml                    地图编号、版本、坐标系
#   waypoints.yaml               点位库（目标名称 → 站位）
#   mujoco/collision_hfield.npz  碰撞高度场，A* 导航栅格由它生成
#   dense_map.pcd                稠密点云（高度场的来源，供查看、重新生成栅格）
#   scene_graph/                 场景图（有则带上）
# 不带：mesh（视觉网格）、gaussians、localization（激光定位缓存）、轨迹等与规划无关的文件
MANIFEST="$CTX/data/MANIFEST.txt"
echo "# 镜像内地图清单，生成时间 $(date '+%F %T')" > "$MANIFEST"
DEFAULT=""
while read -r m; do
  m="${m%%#*}"; m="$(echo "$m" | xargs)"
  [ -z "$m" ] && continue
  [ -z "$DEFAULT" ] && DEFAULT="$m"
  src="$DEMO/maps/$m"; dst="$CTX/data/maps/$m"
  for f in meta.yaml waypoints.yaml mujoco/collision_hfield.npz; do
    [ -f "$src/$f" ] || { echo "缺少 $src/$f" >&2; exit 1; }
  done
  mkdir -p "$dst/mujoco"
  cp "$src/meta.yaml" "$src/waypoints.yaml" "$dst/"
  cp "$src/mujoco/collision_hfield.npz" "$dst/mujoco/"
  [ -f "$src/dense_map.pcd" ] && cp "$src/dense_map.pcd" "$dst/"
  [ -d "$src/scene_graph" ] && cp -r "$src/scene_graph" "$dst/"
  echo "$m  $(du -sh "$dst" | cut -f1)  $(cd "$dst" && find . -type f | sort | tr '\n' ' ')" >> "$MANIFEST"
done < "$HERE/maps.txt"
echo "$DEFAULT" > "$CTX/data/DEFAULT_MAP"
cat "$MANIFEST"
echo "构建目录：$CTX（$(du -sh "$CTX" | cut -f1)），默认地图 $DEFAULT"

[ "${1:-}" = "--stage" ] && exit 0

# --network host：构建时 pip 能用到宿主机的代理设置
docker build --network host \
  --build-arg HTTP_PROXY="${HTTP_PROXY:-}" --build-arg HTTPS_PROXY="${HTTPS_PROXY:-}" \
  --build-arg NO_PROXY="${NO_PROXY:-}" \
  -t "$IMAGE:latest" -t "$IMAGE:$TAG" "$CTX"
echo "镜像 $IMAGE:latest / $IMAGE:$TAG 构建完成"
