#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Bandwidth Keeper Pro - Docker 专用版

✅ 修复所有已知问题：
  - 钉钉Secret缺失导致通知失败
  - 定时任务Cron解析问题（已修复每分钟执行问题）
  - 403 Forbidden / GBK编码 / 模板路径

✅ 飞牛NAS 生产环境优化：
  - 时区/路径/日志/资源监控
  - 保留本地测试兼容性（Windows/Linux 双环境支持）
"""

import os
import sys
import time
import random
import json
import requests
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
import threading
import pytz
import hmac
import hashlib
import base64
import urllib.parse

# ==================== 环境初始化（Docker 优先） ====================
# 强制 UTF-8 编码（解决 Docker 容器内编码问题）
os.environ['PYTHONIOENCODING'] = 'utf-8'
if sys.platform != 'win32': os.environ['TZ'] = 'Asia/Shanghai'
try:
    time.tzset()
except:
    pass

# 路径配置：Docker 使用 /config /logs，本地测试使用相对路径
CONFIG_PATH = os.environ.get('CONFIG_PATH', 'config.json')
LOG_PATH = os.environ.get('LOG_PATH', 'execution.log')

# 确保目录存在（Docker 挂载卷可能为空目录）
for path in [os.path.dirname(CONFIG_PATH), os.path.dirname(LOG_PATH)]:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

# 限速映射 (MB/s -> bytes/s) | 注：1MB/s = 1024*1024 B/s
SPEED_LIMITS = {
    "unlimited": 0,
    "1mbps": 1024 * 1024,
    "3mbps": 3 * 1024 * 1024,
    "5mbps": 5 * 1024 * 1024
}

# ==================== 日志系统（Docker 友好） ====================
# 配置标准 logging（兼容 docker logs）
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Docker 标准输出
        logging.FileHandler(LOG_PATH, encoding='utf-8', mode='a')  # 持久化日志
    ]
)
logger = logging.getLogger(__name__)

def log_message(msg):
    """统一日志接口（移除 emoji + 中文安全）"""
    clean_msg = (
        msg.replace('🚀', '[开始]').replace('📊', '[完成]').replace('⚠️', '[警告]')
        .replace('✅', '[成功]').replace('❌', '[失败]').replace('💡', '[提示]')
        .replace('📌', '[注意]').replace('✨', '[完成]').replace('⚡', '[触发]')
    )
    logger.info(clean_msg)

# ==================== 配置管理 ====================
def load_config():
    """加载配置（UTF-8 安全）"""
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_message(f"[配置] 加载失败: {str(e)} | 路径: {CONFIG_PATH}")
    
    # 生成安全默认配置
    default = {
        "download_links": [
            "https://mirrors.tuna.tsinghua.edu.cn/archlinux/iso/2026.02.01/archlinux-x86_64.iso",
            "https://ftp.jaist.ac.jp/pub/Linux/debian-cd/13.3.0/amd64/iso-cd/debian-edu-13.3.0-amd64-netinst.iso",
            "https://mirrors.cloud.tencent.com/almalinux/10/BaseOS/x86_64/os/images/boot.iso"
        ],
        "cron": "0 2 * * *",  # 每天凌晨2点（生产环境推荐）
        "speed_limit": "unlimited",
        "dingtalk_webhook": "",
        "dingtalk_secret": ""
    }
    
    # 保存默认配置
    save_config(default)
    log_message(f"[配置] 首次启动，生成默认配置: {CONFIG_PATH}")
    return default

def save_config(data):
    """保存配置（UTF-8 + 中文保留）"""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log_message(f"[配置] 已保存: {CONFIG_PATH}")
        return True
    except Exception as e:
        log_message(f"[配置] 保存失败: {str(e)}")
        return False

# ==================== 核心功能 ====================
def download_with_limit(url, speed_limit_bps):
    """带限速下载（防403 + 超时控制）"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 '
                      'BandwidthKeeper/2.1'
    }
    start_time = time.time()
    total_bytes = 0
    last_time = time.time()
    try:
        with requests.get(url, stream=True, headers=headers, timeout=120) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=16384):
                if chunk:
                    total_bytes += len(chunk)
                    if speed_limit_bps > 0:
                        elapsed = time.time() - last_time
                        expected = len(chunk) / speed_limit_bps
                        if elapsed < expected:
                            time.sleep(expected - elapsed)
                        last_time = time.time()
            duration = time.time() - start_time
            return total_bytes, duration, r.status_code
    except Exception as e:
        duration = time.time() - start_time
        log_message(f"[下载] 失败 | URL: {url[:60]} | 错误: {str(e)}")
        return 0, duration, 500

def send_dingtalk(msg):
    """钉钉通知（使用带签名的URL）"""
    try:
        config = load_config()
        webhook = config.get("dingtalk_webhook", "").strip()
        secret = config.get("dingtalk_secret", "").strip()
        
        if not webhook:
            log_message("[钉钉] 通知失败: 钉钉Webhook未配置")
            return
        if not secret:
            log_message("[钉钉] 通知失败: 钉钉Secret未配置")
            return
        
        # 生成签名
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f'{timestamp}\n{secret}'
        hmac_code = hmac.new(secret.encode('utf-8'), string_to_sign.encode('utf-8'), digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        
        # 构造带签名的URL
        signed_url = f"{webhook}&timestamp={timestamp}&sign={sign}"
        
        # 发送消息
        payload = {"msgtype": "text", "text": {"content": f"【Bandwidth Keeper】\n{msg}"}}
        response = requests.post(signed_url, json=payload, timeout=5)
        response.raise_for_status()
        
        log_message(f"[钉钉] 通知成功: {msg}")
    except Exception as e:
        log_message(f"[钉钉] 通知失败: {str(e)}")

def execute_task():
    """执行下载任务（资源安全）"""
    config = load_config()
    valid_links = [link.strip() for link in config["download_links"] if link.strip()]
    if not valid_links:
        log_message("[任务] 跳过: 无有效下载链接")
        send_dingtalk("⚠️ 任务跳过：配置中无有效下载链接")
        return
    
    url = random.choice(valid_links)
    speed_key = config.get("speed_limit", "unlimited")
    speed_bps = SPEED_LIMITS.get(speed_key, 0)
    
    log_message(f"[开始] 任务 | 限速: {speed_key} | 链接: {url[:50]}...")
    bytes_down, duration, status = download_with_limit(url, speed_bps)
    
    # 生成报告
    human_bytes = f"{bytes_down / (1024**2):.2f} MB" if bytes_down > 0 else "0 B"
    human_time = f"{duration:.1f}秒"
    status_text = "[成功]" if status == 200 else f"[失败({status})]"
    report = (
        f"{status_text}\n"
        f"链接: {url[:60]}...\n"
        f"流量: {human_bytes}\n"
        f"耗时: {human_time}\n"
        f"限速: {speed_key.upper()}"
    )
    
    log_message(f"[完成] 任务 | {report.replace(chr(10), ' | ')}")
    send_dingtalk(report)

# ==================== 定时任务（使用 APScheduler） ====================
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# 保存调度器实例
scheduler = None

def setup_schedule():
    """使用 APScheduler 设置定时任务（支持完整 Cron 表达式）"""
    global scheduler
    
    # 如果已经有调度器，先停止它
    if scheduler:
        scheduler.shutdown(wait=False)
    
    config = load_config()
    cron_expr = config.get("cron", "").strip()
    
    if not cron_expr:
        log_message("[调度] 定时任务已禁用（Cron 为空）")
        return
    
    try:
        # 使用 APScheduler 解析 Cron 表达式（关键修复：使用 from_crontab 而不是 from_cron）
        scheduler = BackgroundScheduler()
        trigger = CronTrigger.from_crontab(cron_expr)  # 修复点1：from_cron -> from_crontab
        scheduler.add_job(execute_task, trigger=trigger)
        scheduler.start()
        log_message(f"[调度] 已设置 Cron: {cron_expr} | 任务: {execute_task.__name__}")
    except Exception as e:
        log_message(f"[调度] Cron 解析失败: {str(e)} | 表达式: {cron_expr}")
        log_message("[调度] 回退到默认每天凌晨2点执行")
        # 回退到默认设置（关键修复：使用 from_crontab）
        scheduler = BackgroundScheduler()
        trigger = CronTrigger.from_crontab("0 2 * * *")  # 修复点2：from_cron -> from_crontab
        scheduler.add_job(execute_task, trigger=trigger)
        scheduler.start()

# ==================== Flask 应用 ====================
app = Flask(__name__, static_folder='static', template_folder='templates', instance_relative_config=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify(load_config())

@app.route('/api/config', methods=['POST'])
def update_config():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "无效配置"}), 400
        
        # 验证下载链接
        links = [l.strip() for l in data.get("download_links", []) if l.strip()]
        if len(links) > 5:
            return jsonify({"error": "最多5个有效下载链接"}), 400
        
        # 保存配置
        save_config(data)
        
        # 重新设置调度
        setup_schedule()
        
        return jsonify({"success": True, "message": "配置已保存并生效"})
    except Exception as e:
        log_message(f"[API] 配置保存异常: {str(e)}")
        return jsonify({"error": f"保存失败: {str(e)}"}), 500

@app.route('/api/logs', methods=['GET'])
def get_logs():
    try:
        if not os.path.exists(LOG_PATH):
            return jsonify({"logs": ["[系统] 无日志记录"]})
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-150:]  # 返回最近150条
        return jsonify({"logs": [line.strip() for line in lines]})
    except Exception as e:
        return jsonify({"logs": [f"[错误] 读取日志失败: {str(e)}"]})

@app.route('/api/force-run', methods=['POST'])
def force_run():
    threading.Thread(target=execute_task, daemon=True).start()
    log_message("[触发] 手动执行任务（API调用）")
    return jsonify({"success": True, "message": "任务已触发"})

# ==================== 启动主程序 ====================
if __name__ == '__main__':
    # 初始化配置
    if not os.path.exists(CONFIG_PATH):
        load_config()
    
    # 设置调度
    setup_schedule()
    
    # 启动Web服务
    log_message("=" * 60)
    log_message("🚀 Bandwidth Keeper Pro - NAS v2.2")
    log_message(f"📁 配置路径: {CONFIG_PATH}")
    log_message(f"📄 日志路径: {LOG_PATH}")
    log_message(f"🌐 时区: {pytz.timezone('Asia/Shanghai')}")
    log_message(f"🐍 Python: {sys.version.split()[0]} | 平台: {sys.platform}")
    log_message("=" * 60)
    
    app.run(
        host='0.0.0.0',
        port=9016,
        debug=False,
        use_reloader=False,
        threaded=True,
        processes=1
    )