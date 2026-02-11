# Bandwidth Keeper Pro

[![Python Version](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Flask Version](https://img.shields.io/badge/Flask-3.0.0-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

专为飞牛NAS打造的智能带宽保活工具，通过定时下载指定链接维持公网连接活跃，支持限速控制、钉钉通知、可视化配置等核心功能，兼容Docker/本地多环境部署。

## ✨ 核心特性
- 🎯 **飞牛NAS深度适配**：优化时区、文件路径、日志存储，完美兼容NAS生产环境
- ⏰ **灵活定时任务**：支持Cron表达式（每分钟/每小时/每天等），精准控制任务执行时间
- 🚦 **智能限速下载**：可选1/3/5MB/s限速或无限制，避免占用过多带宽
- 🔔 **钉钉消息通知**：任务执行结果实时推送至钉钉群，状态一目了然
- 🖥️ **友好Web界面**：可视化配置管理、日志实时查看，无需命令行操作
- 📜 **完善日志系统**：本地持久化日志+Docker标准输出，方便问题排查
- 🌐 **多环境兼容**：支持Windows/Linux本地运行，也可通过Docker部署（推荐NAS使用）
- 🛡️ **健壮容错处理**：配置自动备份、网络异常捕获、编码兼容（UTF-8）

## 🚀 部署方式

### 方式1：本地运行（开发/测试）
#### 环境要求
- Python 3.8+
- pip 20.0+

#### 部署步骤
1. **克隆代码仓库**
```bash
git clone https://github.com/mrzhangeh/bandwidth-keeper-pro.git
cd bandwidth-keeper-pro
```

2. **创建虚拟环境（可选但推荐）**
```bash
# Linux/Mac
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

3. **安装依赖**
```bash
pip install -r app/requirements.txt
```

4. **启动服务**
```bash
cd app
python app.py
```

5. **访问Web界面**
打开浏览器访问：`http://localhost:9016`

### 方式2：Docker运行（生产环境/飞牛NAS） 更推荐
#### 环境要求
- Docker 20.0+
- Docker Compose（可选）

#### 步骤1：编写Dockerfile
在项目根目录创建`Dockerfile`：
```dockerfile
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
```

#### 步骤2：构建并运行Docker镜像
```bash
# 构建镜像
docker build -t bandwidth-keeper-pro:latest .

# 运行容器（挂载配置/日志卷，确保数据持久化）
docker run -d \
  --name bandwidth-keeper \
  --restart always \
  -p 9016:9016 \
  bandwidth-keeper-pro:latest
```

#### 步骤3（可选）：Docker Compose部署
创建`docker-compose.yml`：
```yaml
version: '3.8'

services:
  bandwidth-keeper:
    build: .
    image: bandwidth-keeper-pro:latest
    container_name: bandwidth-keeper
    restart: always
    ports:
      - "9016:9016"
    volumes:
      - ./config:/config
      - ./logs:/logs
    environment:
      - TZ=Asia/Shanghai
      - PYTHONIOENCODING=utf-8
```

启动命令：
```bash
docker-compose up -d
```

## 📖 使用说明
### 1. 基础配置
1. 访问Web界面（`http://服务器IP:9016`）
2. **下载配置**：添加1-5个下载链接（推荐使用测速文件链接，如Hetzner测速节点）
3. **定时规则**：填写Cron表达式（格式：分 时 日 月 周，示例：`0 2 * * *` 每天凌晨2点执行）
4. **限速设置**：选择下载限速（无限制/1/3/5MB/s）
5. **钉钉通知**：填写钉钉机器人Webhook（可选，用于接收任务执行结果）
6. 点击「保存配置」生效

### 2. 手动执行任务
点击「立即执行」按钮，可手动触发一次下载任务，用于测试配置是否正常。

### 3. 查看执行日志
页面底部可查看最近150条执行日志，每30秒自动刷新，也可点击「刷新日志」手动更新。

## ⚙️ 配置说明
### Cron表达式支持
| 表达式         | 说明                 |
|----------------|----------------------|
| `*/1 * * * *`  | 每分钟执行（测试用） |
| `0 * * * *`    | 每小时整点执行       |
| `0 2 * * *`    | 每天凌晨2点执行      |
| `30 18 * * 1-5`| 工作日18:30执行      |

### 限速映射
| 选项         | 实际速度       |
|--------------|----------------|
| `unlimited`  | 无限制（推荐） |
| `1mbps`      | 1 MB/s (1024 KB/s) |
| `3mbps`      | 3 MB/s (3072 KB/s) |
| `5mbps`      | 5 MB/s (5120 KB/s) |

### 钉钉机器人配置
1. 打开钉钉群 → 智能群助手 → 添加机器人 → 自定义机器人
2. 复制Webhook地址（格式：`https://oapi.dingtalk.com/robot/send?access_token=xxx`）
3. 粘贴到Web界面的「钉钉通知」输入框中

## 🛠️ 技术栈
- **后端**：Flask（Web框架）、requests（HTTP请求）、schedule（定时任务）、pytz（时区处理）
- **前端**：原生HTML/CSS/JavaScript（无框架，轻量适配NAS）
- **部署**：Docker（容器化）、多平台兼容（Linux/Windows/macOS）

## 📝 常见问题
1. **任务执行失败（403 Forbidden）**：工具已内置User-Agent优化，若仍失败请更换下载链接
2. **定时任务不执行**：检查Cron表达式格式是否正确，或查看日志排查调度器错误
3. **Docker日志乱码**：已设置UTF-8编码，若仍乱码请检查Docker宿主机编码设置
4. **NAS部署后无法访问**：确保NAS的9016端口已开放，且容器网络模式为桥接


## 📄 许可证
本项目基于MIT许可证开源，详见[LICENSE](LICENSE)文件。

## 💡 贡献
欢迎提交Issue和PR，共同优化这个工具！提交前请确保代码符合PEP8规范，并测试功能完整性。
