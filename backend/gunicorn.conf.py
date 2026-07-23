"""
AIPID 温控系统 - Gunicorn 生产配置
启动: gunicorn -c gunicorn.conf.py app:app
"""
import multiprocessing
import os

# 绑定地址
bind = '0.0.0.0:5000'

# 工作进程数（通常为 CPU 核心数的 2-4 倍）
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式（推荐 gevent 或 sync）
worker_class = 'sync'

# 每个工作进程的最大并发连接数
worker_connections = 1000

# 超时设置
timeout = 60
keepalive = 60

# 日志
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# 进程名
proc_name = 'aipid_backend'

# 守护进程模式（生产环境建议用 systemd 管理，设为 False）
daemon = False

# 重启时优雅重载
graceful_timeout = 30

# 最大请求数（防止内存泄漏）
max_requests = 10000
max_requests_jitter = 1000
