# A* 导航规划服务（Docker）

把 A* 导航规划服务和它用到的全部地图数据打包成一个镜像 `robot-nav-astar`。
启动容器后，局域网内任何设备都可以通过 HTTP 或 WebSocket 请求路径规划，宿主机不需要 conda 环境，也不需要源码目录。

接口与原来宿主机上运行的 `nav_service.py` 完全相同（地址、端口、请求和返回字段都不变），
详细字段说明见镜像内 `/app/docs/导航规划服务接口文档.md`，或源码目录 `slam_map_demo/导航规划服务接口文档.md`。

## 日常使用

```bash
cd /home/oc/projects/robot/nav_astar_docker
docker compose up -d            # 启动（开机后 Docker 会自动拉起，除非手动 down 过）
docker compose logs -f          # 查看请求日志
docker compose down             # 停止
```

调用（把 IP 换成运行容器的电脑，当前为 192.168.104.191）：

```bash
curl http://192.168.104.191:8765/health
curl http://192.168.104.191:8765/waypoints
curl "http://192.168.104.191:8765/plan?x=0&y=0&goals=广告牌,厕所通道"
curl -X POST http://192.168.104.191:8765/plan -H 'Content-Type: application/json' \
     -d '{"start": {"x": 0, "y": 0, "yaw": 0}, "goals": ["广告牌", "厕所通道"], "step": 0.2}'
# WebSocket：ws://192.168.104.191:8766，消息格式见接口文档
```

`goals` 中的一项也可以是坐标对象（仅 POST / WebSocket），如 `{"x": 2, "y": 3, "yaw": 1.57}`，可与名称混用。
沿规划结果在 MuJoCo 中行走：交给同一台电脑上的仿真控制服务（8770 端口，见 `slam_map_demo/仿真控制服务接口文档.md`）。

| 端口 | 协议 | 用途 |
|---|---|---|
| 8765 | HTTP | `/health`、`/waypoints`、`/scene_graph`、`/plan` |
| 8766 | WebSocket | 同上，消息中的 `type` 字段区分 |

## 切换地图

镜像里打包了多张地图，一个容器同时只加载一张，由环境变量 `NAV_MAP` 指定。
修改 `docker-compose.yml` 中的 `NAV_MAP`，再执行 `docker compose up -d` 即可（几秒钟）。

| `NAV_MAP` | 说明 | 场景图 |
|---|---|---|
| `room1110/2026-11-11.2` | room1110 地图（2026-11-10 采集），XT16 激光 + D435i + 3DGS 耦合重建，CloudCompare 点选坐标系与 4 个点位（默认） | 无 |
| `go2_room_selfbuilt/2026-11-09.2` | room 地图，自建 SLAM，与激光定位同一坐标系 | 无 |
| `r2b_storage_ns/2026-11-01.3` | r2b 仓库，nerfstudio 重建 | 有 |
| `go2_room_onboard/2026-11-05.1` | room 地图，Go2 机载 SLAM | 无 |
| `r2b_storage/2026-10-28.2` | r2b 仓库，激光 SLAM | 无 |
| `hilti_exp14/2026-10-28.2` | Hilti 数据集 | 无 |
| `habitat_apartment_1/2026-10-27.1` | Habitat 公寓扫描 | 无 |

查看镜像内的地图和文件：`docker run --rm robot-nav-astar maps`。

需要同时提供两张地图时，再起一个容器并换一组端口，例如：

```bash
docker run -d --name nav-astar-r2b --restart unless-stopped -e NAV_MAP=r2b_storage_ns/2026-11-01.3 \
  -p 8775:8765 -p 8776:8766 robot-nav-astar
```

## 场景图目标（仅带场景图的地图）

地图带场景图时，`goals` 里的名称在点位库中都匹配不到，会再到场景图中按关键词找物体或区域，
目标为物体旁边的到达站位（朝向物体），返回的 `goal` 多出 `type`（`object` / `region`）和 `region`（所在区域）两个字段：

```bash
curl "http://<IP>:8765/plan?x=0&y=0&goals=obj_17"           # 用物体编号
curl "http://<IP>:8765/plan?x=0&y=0&goals=标定板"            # 名称唯一时直接用名称
curl "http://<IP>:8765/plan?x=0&y=0&goals=东侧通道里的手推车"  # 同名物体有多个时加上所在区域
curl "http://<IP>:8765/scene_graph"                          # 列出所有物体和区域：编号、名称、别名、站位
```

- 名称对应多个物体时（如「纸箱」有 5 个、「手推车」有 4 个）返回失败，并列出候选编号和所在区域，与点位重名的处理方式一致；
- 只用关键词匹配，不做「印着 DGX 的纸箱」这类 CLIP 语义检索（需要 GPU 和约 1.6 GB 的模型，没有放进镜像）；
- 点位库中的名称优先：例如「北侧通道」会先匹配到点位「北侧通道尽头」。

命令行查询场景图（与 `query_scene_graph.py` 用法相同）：

```bash
docker run --rm -e NAV_MAP=r2b_storage_ns/2026-11-01.3 robot-nav-astar scene-graph list object
docker run --rm -e NAV_MAP=r2b_storage_ns/2026-11-01.3 robot-nav-astar scene-graph goal obj_17 --from 0 0
docker run --rm -e NAV_MAP=r2b_storage_ns/2026-11-01.3 robot-nav-astar scene-graph describe --from 0 0
```

## 不启动服务，规划一次

```bash
docker run --rm robot-nav-astar plan --start 0 0 --goals 广告牌 厕所通道 --step 0.2
```

## 镜像内容

```
/app/scripts/nav_service.py            HTTP + WebSocket 服务、点位名称解析
/app/scripts/nav_grid.py               A* 搜索、离障碍距离、路径拉直
/app/scripts/map_to_mujoco.py          只用到其中的障碍高度阈值（0.12 m）
/app/scripts/scene_graph/              场景图查询库与命令行工具
/app/docs/                             本说明、接口文档、场景图说明
/data/maps/<地图>/<版本>/
    meta.yaml                          地图编号、版本、坐标系
    waypoints.yaml                     点位库
    mujoco/collision_hfield.npz        碰撞高度场，A* 导航栅格由它生成
    dense_map.pcd                      稠密点云（高度场的来源）
    scene_graph/                       场景图：scene_graph.json、物体图像向量、裁剪图、俯视图（有则带）
    grid/map.pgm、map.yaml             二维栅格图，ROS map_server / Nav2 格式（构建时生成）
    grid/nav_preview.png               A* 可通行区域预览：黑=障碍，灰=未扫描，浅绿=可走，白=离障碍太近，红=点位
/data/MANIFEST.txt                     地图与文件清单
```

没有放进镜像的内容（与规划无关）：视觉网格 `mesh/`、高斯模型 `gaussians/`、激光定位缓存 `localization/`、
建图轨迹，以及 `/mnt/sda2/robot_download` 下的原始录制包、nerfstudio 训练数据等。

把栅格图或点云拷出来查看：

```bash
docker create --name tmp robot-nav-astar && docker cp tmp:/data/maps ./maps_from_image && docker rm tmp
```

## 更新地图或代码后重新构建

代码和地图的源头仍是 `slam_map_demo`，镜像只是打包结果。改了点位库、重建了地图或改了脚本后：

```bash
cd /home/oc/projects/robot/nav_astar_docker
./build.sh                 # 从 slam_map_demo 复制所需文件到 build/context 并构建，约 1 分钟
docker compose up -d       # 用新镜像重建容器
```

- 要打包的地图在 `maps.txt` 中列出，每行一个，加一行即可加入新地图；
- 每次构建同时打上时间标签（如 `robot-nav-astar:20261109-2318`），新版本有问题时，
  把 `docker-compose.yml` 中的 `image` 改成旧标签即可回退；
- 构建时 pip 走清华镜像源，并沿用宿主机的代理环境变量。

## 迁到别的电脑

```bash
docker save robot-nav-astar:latest | gzip > robot-nav-astar.tar.gz     # 约 250 MB
# 拷到目标电脑后
docker load < robot-nav-astar.tar.gz
docker run -d --name nav-astar --restart unless-stopped -p 8765:8765 -p 8766:8766 robot-nav-astar
```

## 与旧方式的关系

原来的宿主机进程（`python -I -u scripts/nav_service.py serve ...`）已停止，端口 8765、8766 改由容器提供。
需要临时改回宿主机运行时，先 `docker compose down` 释放端口，再按接口文档中的命令启动。
