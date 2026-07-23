#!/bin/bash
# ============================================================
# AIPID 温控系统 - 一键部署脚本
# 适用于 Ubuntu 22.04+ / Debian 12+
# 使用方式: sudo bash deploy.sh
# ============================================================

set -e

echo "========================================"
echo "  AIPID 温控系统 - 部署脚本"
echo "========================================"

# ---------- 配置（根据实际情况修改） ----------
DOMAIN="pid.yourcompany.com"          # 域名
MYSQL_ROOT_PASSWORD="your-password"   # MySQL root 密码
MYSQL_DATABASE="pid_control"          # 数据库名
MYSQL_USER="aipid"                    # 应用数据库用户
MYSQL_PASSWORD="aipid-password"       # 应用数据库密码
PROJECT_DIR="/opt/aipid"              # 项目部署目录
FRONTEND_DIR="${PROJECT_DIR}/frontend"
BACKEND_DIR="${PROJECT_DIR}/backend"

# ---------- 检查 root 权限 ----------
if [ "$EUID" -ne 0 ]; then
    echo "[ERROR] 请使用 sudo 运行此脚本"
    exit 1
fi

# ---------- 1. 系统更新 & 安装依赖 ----------
echo "[1/7] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq \
    nginx \
    mysql-server \
    python3 \
    python3-pip \
    python3-venv \
    nodejs \
    npm \
    git \
    certbot \
    python3-certbot-nginx

# ---------- 2. 创建项目目录 ----------
echo "[2/7] 创建项目目录..."
mkdir -p ${PROJECT_DIR}
mkdir -p ${FRONTEND_DIR}
mkdir -p ${BACKEND_DIR}

# ---------- 3. 配置 MySQL ----------
echo "[3/7] 配置 MySQL..."
systemctl start mysql
systemctl enable mysql

# 创建数据库和用户
mysql -u root <<EOF
CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE}
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'localhost'
    IDENTIFIED BY '${MYSQL_PASSWORD}';

GRANT ALL PRIVILEGES ON ${MYSQL_DATABASE}.*
    TO '${MYSQL_USER}'@'localhost';

FLUSH PRIVILEGES;
EOF

# 导入表结构
mysql -u ${MYSQL_USER} -p${MYSQL_PASSWORD} ${MYSQL_DATABASE} < \
    ${PROJECT_DIR}/mysql/init.sql

echo "[INFO] MySQL 配置完成"

# ---------- 4. 部署后端 ----------
echo "[4/7] 部署后端..."
cd ${BACKEND_DIR}

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt -q

# 创建 systemd 服务
cat > /etc/systemd/system/aipid-backend.service <<EOF
[Unit]
Description=AIPID Backend (Gunicorn)
After=network.target mysql.service

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=${BACKEND_DIR}
Environment="MYSQL_URI=mysql+pymysql://${MYSQL_USER}:${MYSQL_PASSWORD}@localhost/${MYSQL_DATABASE}"
Environment="SECRET_KEY=$(openssl rand -hex 32)"
ExecStart=${BACKEND_DIR}/venv/bin/gunicorn -c gunicorn.conf.py wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aipid-backend
systemctl start aipid-backend

echo "[INFO] 后端部署完成"

# ---------- 5. 构建前端 ----------
echo "[5/7] 构建前端..."
cd ${FRONTEND_DIR}
npm install --silent
npm run build

echo "[INFO] 前端构建完成"

# ---------- 6. 配置 Nginx ----------
echo "[6/7] 配置 Nginx..."
# 复制 Nginx 配置
cp ${PROJECT_DIR}/nginx/nginx.conf /etc/nginx/sites-available/aipid

# 替换域名占位符
sed -i "s/pid\.yourcompany\.com/${DOMAIN}/g" /etc/nginx/sites-available/aipid

# 启用站点
ln -sf /etc/nginx/sites-available/aipid /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 测试配置
nginx -t

systemctl enable nginx
systemctl restart nginx

echo "[INFO] Nginx 配置完成"

# ---------- 7. 配置 SSL 证书 ----------
echo "[7/7] 配置 SSL 证书（Let's Encrypt）..."
echo "[INFO] 请确保域名 ${DOMAIN} 已解析到本服务器 IP"
echo "[INFO] 执行以下命令获取 SSL 证书:"
echo "  certbot --nginx -d ${DOMAIN}"

echo ""
echo "========================================"
echo "  AIPID 温控系统 部署完成！"
echo "========================================"
echo ""
echo "访问地址: https://${DOMAIN}"
echo "默认管理员: admin / 123456"
echo ""
echo "管理命令:"
echo "  查看后端日志: journalctl -u aipid-backend -f"
echo "  重启后端:    systemctl restart aipid-backend"
echo "  重启 Nginx:  systemctl restart nginx"
echo "========================================"
