# /vol1/1000/lin/keeper/app/Dockerfile
FROM python:3.11-slim-bookworm

# 设置时区和编码（飞牛NAS 关键！）
ENV TZ=Asia/Shanghai \
    PYTHONIOENCODING=utf-8 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    CONFIG_PATH=/config/config.json \
    LOG_PATH=/logs/execution.log

RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装依赖
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用代码
COPY . .

# 创建运行用户（安全最佳实践）
RUN useradd -m -u 1000 keeper && \
    chown -R keeper:keeper /app && \
    mkdir -p /config /logs && \
    chown keeper:keeper /config /logs

USER keeper
EXPOSE 9016

# 健康检查（Docker 监控）
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:9016/api/config || exit 1

# 启动命令
CMD ["python", "app.py"]