FROM python:3.10-slim

# 设置时区和编码
ENV TZ=Asia/Shanghai
ENV PYTHONIOENCODING=utf-8

# 创建工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY app/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ .

# 创建配置和日志目录并设置权限（关键修复！）
RUN mkdir -p /config /logs && \
    chown -R 65534:65534 /config /logs  # 使用 UID 65534 (nobody)

# 暴露端口
EXPOSE 9016

# 启动命令
CMD ["python", "app.py"]