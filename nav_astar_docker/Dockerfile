# A* 导航规划服务镜像：代码 + 地图数据全部打包在内，启动即用。
# 构建目录由 build.sh 生成，不要直接在本目录 docker build。
FROM python:3.10-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r /app/requirements.txt

# 地图数据体积大、变动少，放在代码前面，改代码后重新构建时不用重复复制地图
COPY data /data
COPY app /app
# 为每张地图生成二维栅格图（ROS map_server 格式 .pgm + .yaml，以及预览 .png），与 A* 的障碍判定一致
RUN python -I /app/make_grid_images.py /data/maps && chmod +x /app/entrypoint.sh

ENV PYTHONUNBUFFERED=1 \
    NAV_HOST=0.0.0.0 \
    NAV_HTTP_PORT=8765 \
    NAV_WS_PORT=8766
EXPOSE 8765 8766
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request;urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ['NAV_HTTP_PORT'], timeout=4)" || exit 1

WORKDIR /app
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["serve"]
