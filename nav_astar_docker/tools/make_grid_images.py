"""为每个地图包生成二维栅格图，放在 <地图包>/grid/ 下：

- map.pgm + map.yaml：ROS map_server / Nav2 格式。障碍=占用(0)，无扫描数据=未知(205)，其余=空闲(254)，
  障碍判定与 nav_grid.py 相同（高于 FLOOR_MAX_HEIGHT 为障碍）。
- nav_preview.png：A* 实际使用的可通行区域预览。黑=障碍，灰=未扫描，浅绿=离障碍超过避障半径（A* 可走），
  白=空地但离障碍太近，红点=点位站位。

只依赖 numpy、scipy、yaml（PNG 用标准库 zlib 手写，不需要图像库）。

用法：python -I make_grid_images.py <地图根目录>   # 递归处理其中所有含 meta.yaml 的地图包
"""
import struct
import sys
import zlib
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from nav_grid import NavGrid, ROBOT_RADIUS, OBSTACLE_HEIGHT  # noqa: E402


def write_png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def process(map_dir):
    hf = np.load(map_dir / "mujoco" / "collision_hfield.npz")
    H, lo, res, observed = hf["heights"], hf["lo"], float(hf["resolution"]), hf["observed"]
    out = map_dir / "grid"
    out.mkdir(exist_ok=True)

    img = np.full(H.shape, 205, np.uint8)
    img[observed & (H <= OBSTACLE_HEIGHT)] = 254
    img[observed & (H > OBSTACLE_HEIGHT)] = 0
    with open(out / "map.pgm", "wb") as f:
        f.write(f"P5\n{img.shape[1]} {img.shape[0]}\n255\n".encode())
        f.write(img[::-1].tobytes())  # PGM 第一行在上方，地图 y 轴朝上
    # 高度场第 i 列的中心在 lo + i*res，左下角像素的左下角为 lo - res/2
    (out / "map.yaml").write_text(yaml.safe_dump({
        "image": "map.pgm", "mode": "trinary", "resolution": res,
        "origin": [float(lo[0] - res / 2), float(lo[1] - res / 2), 0.0],
        "negate": 0, "occupied_thresh": 0.65, "free_thresh": 0.25}, sort_keys=False))

    grid = NavGrid(H, lo, res, observed)
    rgb = np.full(H.shape + (3,), 160, np.uint8)            # 未扫描：灰
    rgb[observed & (H <= OBSTACLE_HEIGHT)] = (255, 255, 255)  # 空地：白
    rgb[grid.clearance > ROBOT_RADIUS] = (200, 235, 200)      # A* 可走：浅绿
    rgb[observed & (H > OBSTACLE_HEIGHT)] = (0, 0, 0)         # 障碍：黑
    for wp in yaml.safe_load(open(map_dir / "waypoints.yaml"))["waypoints"]:
        r, c = grid.to_cell([wp["stand_pose"]["x"], wp["stand_pose"]["y"]])
        rgb[max(r - 2, 0):r + 3, max(c - 2, 0):c + 3] = (220, 0, 0)
    write_png(out / "nav_preview.png", np.ascontiguousarray(rgb[::-1]))
    print(f"{map_dir}: {img.shape[1]}x{img.shape[0]} 栅格，分辨率 {res} m，"
          f"空闲 {np.mean(img == 254):.0%}，占用 {np.mean(img == 0):.0%}，未知 {np.mean(img == 205):.0%}")


if __name__ == "__main__":
    for meta in sorted(Path(sys.argv[1]).rglob("meta.yaml")):
        process(meta.parent)
