# AIPID 温控系统

> **A**I-assisted **I**ntelligent **P**ID **I**nternet-based **D**ata Platform  
> 基于 AI 辅助的智能 PID 物联网数据平台

---

## 📋 项目概述

AIPID 温控系统是一个面向工业 PID 温控场景的云端数据管理平台，实现**边缘侧（PLC/树莓派）与云端之间的双向数据交互**：

- **上行**：边缘侧设备实时上传 PID 运行特征帧（KP、TI、TD、IAE 等指标）到云端存储
- **下行**：云端可下发 PID 参数调整指令给边缘侧设备执行
- **监控**：Web 前端提供登录认证、数据可视化看板、指令管理等功能

### 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    公网 (域名)                           │
│              https://pid.yourcompany.com                 │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                    Nginx (HTTPS)                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │  • SSL 终止（Let's Encrypt / 阿里云证书）         │   │
│  │  • 静态文件服务（Vue 构建产物）                    │   │
│  │  • API 反向代理 → Flask 后端                      │   │
│  │  • 安全头 / 限流 / 缓存                           │   │
│  └──────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐    ┌──────────────▼──────────────┐
│   Vue 3 前端         │    │   Flask API (Gunicorn)      │
│   (静态文件)          │    │   • 用户认证 (bcrypt)       │
│   • 登录页面          │    │   • 特征帧上传/查询         │
│   • 数据仪表板        │    │   • 指令下发/确认           │
│   • 实时刷新          │    │   • 健康检查                │
└─────────────────────┘    └──────────────┬──────────────┘
                                          │
                               ┌──────────▼──────────────┐
                               │   MySQL 8.0              │
                               │   • users                │
                               │   • feature_frames       │
                               │   • downlink_commands    │
                               │   • experience_pool      │
                               └─────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **前端** | Vue 3 + Vue Router + Axios | 单页应用，支持 History 路由 |
| **构建** | Vite | 快速开发服务器 + 生产构建 |
| **后端** | Flask + SQLAlchemy | RESTful API |
| **WSGI** | Gunicorn | 生产级 Python WSGI 服务器 |
| **数据库** | MySQL 8.0 | 关系型数据库 |
| **反向代理** | Nginx | SSL 终止、静态文件服务、API 代理 |
| **部署** | Docker Compose / Shell 脚本 | 容器化或裸机部署 |

---

## 📁 项目结构

```
AIPID_website/
├── backend/                      # Flask 后端
│   ├── app.py                    # 主应用 & API 路由
│   ├── config.py                 # 配置（数据库、Session 等）
│   ├── models.py                 # 数据模型（User, FeatureFrame, DownlinkCommand）
│   ├── wsgi.py                   # WSGI 入口
│   ├── gunicorn.conf.py          # Gunicorn 生产配置
│   ├── requirements.txt          # Python 依赖
│   └── Dockerfile                # Docker 镜像构建
│
├── frontend/                     # Vue 3 前端
│   ├── index.html                # HTML 入口
│   ├── package.json              # Node 依赖
│   ├── vite.config.js            # Vite 配置
│   └── src/
│       ├── main.js               # 应用入口
│       ├── App.vue               # 根组件
│       ├── router/index.js       # 路由配置
│       └── views/
│           ├── Login.vue         # 登录页面
│           └── Dashboard.vue     # 数据仪表板
│
├── mysql/
│   └── init.sql                  # 数据库初始化脚本（4 张表）
│
├── nginx/
│   └── nginx.conf                # Nginx 生产配置
│
├── deploy/
│   └── deploy.sh                 # 一键部署脚本（Ubuntu/Debian）
│
├── docker-compose.yml            # Docker Compose 编排
├── .env.example                  # 环境变量模板
├── .gitignore
└── README.md
```

---

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/AIPID_website.git
cd AIPID_website

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 修改密码等配置

# 3. 构建前端
cd frontend
npm install
npm run build
cd ..

# 4. 启动所有服务
docker compose up -d

# 5. 访问
# https://localhost
# 默认管理员: admin / 123456
```

### 方式二：裸机部署（Ubuntu/Debian）

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/AIPID_website.git /opt/aipid

# 2. 运行部署脚本
cd /opt/aipid
sudo bash deploy/deploy.sh

# 3. 配置 SSL 证书
sudo certbot --nginx -d pid.yourcompany.com
```

### 方式三：开发环境

```bash
# 终端 1：启动后端
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py

# 终端 2：启动前端
cd frontend
npm install
npm run dev

# 访问: http://localhost:5173
```

---

## 🔌 API 接口文档

### 用户认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/login` | 用户登录 |
| POST | `/api/logout` | 用户登出 |
| GET | `/api/me` | 获取当前用户信息 |

### 特征帧（上行）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload_frame` | 边缘侧上传特征帧 |
| GET | `/api/frames?limit=100` | 获取最近 N 条特征帧 |
| GET | `/api/frames/latest` | 获取最新一条特征帧 |

### 指令（下行）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/issue_command` | 云端下发 PID 调整指令 |
| GET | `/api/pending_command` | 边缘侧查询待处理指令 |
| POST | `/api/apply_command/<batch_id>` | 边缘侧确认应用指令 |
| GET | `/api/commands?limit=50` | 获取指令下发记录 |

### 系统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |

### 特征帧数据字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | BIGINT | Unix 毫秒时间戳 |
| `kp` | FLOAT | 比例系数 |
| `ti` | FLOAT | 积分时间 |
| `td` | FLOAT | 微分时间 |
| `iae_60s` | FLOAT | 60 秒误差积分 |
| `var_power` | FLOAT | 功率方差 |
| `zero_cross_count` | TINYINT | 过零计数 |
| `avg_disturbance` | FLOAT | 平均扰动 |
| `current_power` | FLOAT | 当前功率 |
| `rpm_equivalent` | FLOAT | 等效转速 |
| `status_flag` | TINYINT | 状态标志（0=正常, 1=警告, 2=过载, 3=异常） |

---

## 🗄️ 数据库表结构

| 表名 | 说明 |
|------|------|
| `users` | 用户表（bcrypt 密码哈希） |
| `feature_frames` | 特征帧表（上行数据） |
| `downlink_commands` | 下行指令表 |
| `experience_pool` | 极端工况经验池 |

---

## 🔒 安全配置

1. **HTTPS**：Nginx 配置 SSL 证书（Let's Encrypt 或阿里云免费证书）
2. **密码安全**：bcrypt 哈希存储，不保存明文
3. **Session 安全**：Secure + HttpOnly + SameSite=Lax
4. **数据库隔离**：MySQL 仅监听 127.0.0.1，不对外暴露
5. **环境变量**：敏感配置通过环境变量注入，不写入代码

---

## 📊 生产部署架构要点

```
阿里云 DNS (域名解析)
    ↓
公司公网 IP (防火墙端口映射 443)
    ↓
Nginx (SSL 终止 + 反向代理)
    ↓
Gunicorn (多进程 Flask)
    ↓
MySQL (内网)
```

- **Nginx** 统一管理 HTTPS 证书，托管前端静态文件，反向代理 API 请求
- **Gunicorn** 多进程运行 Flask，提高并发处理能力
- **MySQL** 仅内网访问，不对外暴露端口
- **环境变量** 注入数据库连接串和密钥，不硬编码在配置文件中

---

## 📝 License

MIT
