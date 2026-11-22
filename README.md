# A* 导航服务

本目录包含 A* 路径规划、命名点位与地图加载代码。地图包放在 `slam_map_demo/maps/<地图>/<版本>/`，由 `ROBOT_MAP` 选择。地图包需要 `meta.yaml`、`waypoints.yaml` 和 `mujoco/collision_hfield.npz`。Go2 仿真使用相同的地图 ID 和版本。

在本目录启动 A* 和 MCP。首次准备共享虚拟环境时，运行 `../.venv/bin/python -m pip install -r requirements.txt` 安装两者的 Python 依赖。 [A* 依赖](requirements.txt)

```bash
export ROBOT_PYTHON="$PWD/../.venv/bin/python"
export ROBOT_MAP=room1110/2026-11-11.2
bash scripts/run_robot_astar.sh start
"$ROBOT_PYTHON" -m astar_mcp.server
```

MCP 进程默认连接本机 A* 的 8765 端口，在 `http://127.0.0.1:8790/mcp` 提供 Streamable HTTP。`--nav-endpoint` 和 `--port` 可分别指定原生服务地址和 MCP 监听端口。

- `list_waypoints()` 返回地图版本和站位。
- `plan_route(start, goal)` 从地图位姿规划一个目标，返回 `plan_id` 和摘要。
- `get_plan(plan_id)` 返回保存的完整路径。MuJoCo 通过此工具取回路径并执行。MCP 进程重启后重新规划。
