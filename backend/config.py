"""
AIPID 温控系统 - 配置模块
生产环境通过环境变量覆盖敏感配置
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


class Config:
    """应用配置"""

    # ---------- 密钥 ----------
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-to-a-random-secret-key'

    # ---------- 数据库 ----------
    # 生产环境通过环境变量 MYSQL_URI 设置，例如:
    # mysql+pymysql://user:password@内网IP:3306/pid_control
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'MYSQL_URI',
        'mysql+pymysql://root:admin@localhost/pid_control'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }

    # ---------- Session 安全 ----------
    SESSION_COOKIE_SECURE = True       # 生产环境 HTTPS 下启用
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 28800  # 8 小时

    # ---------- 上传限制 ----------
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
