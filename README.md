# A* 导航 MCP

A* 加载 `slam_map_demo/maps/<地图>/<版本>/` 下的地图包。地图包包含 `meta.yaml`、`waypoints.yaml` 和 `mujoco/collision_hfield.npz`。MuJoCo 使用相同的地图 ID 和版本。

## 安装和启动

在仓库根目录执行。

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m astar_mcp.server --map room1110/2026-11-11.2
```

服务地址为 `http://127.0.0.1:8790/mcp`，可用 `--host` 和 `--port` 修改。按 Ctrl+C 停止。

| MCP 工具 | 用途 |
|---|---|
| `list_waypoints()` | 查询地图 ID、版本和命名站位 |
| `plan_route(start, goal)` | 根据当前地图位姿规划到一个目标，返回 `plan_id` |
| `get_plan(plan_id)` | 返回保存的路径，供 MuJoCo 执行 |

`start` 为 `{"x": 0, "y": 0, "yaw": 0}` 形式的地图位姿。`goal` 可以是站位名、编号或同格式坐标。`yaw` 可省略，距离和角度分别使用米和弧度。路径保存在服务内存中，重启后重新规划。
