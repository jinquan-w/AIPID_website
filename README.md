# AIPID 温控系统

> **A**I-assisted **I**ntelligent **P**ID **I**nternet-based **D**ata Platform  
> 基于 AI 辅助的智能 PID 物联网数据平台

---

## 📋 项目概述

AIPID 温控系统是一个面向工业 PID 温控场景的云端数据管理平台，实现**边缘侧（PLC/树莓派）与云端之间的双向数据交互**：

- **上行 ↑**：边缘侧设备实时上传 PID 运行特征帧（KP、TI、TD、IAE 等指标）到云端存储
- **下行 ↓**：云端可下发 PID 参数调整指令给边缘侧设备执行
- **监控 📊**：Web 前端提供登录认证、注册、数据可视化看板、指令管理等功能

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
│  │  • SSL 终止（Let's Encrypt / 云厂商证书）         │   │
│  │  • 静态文件服务（Vue 构建产物）                    │   │
│  │  • API 反向代理 → Flask 后端                      │   │
│  │  • 安全头 / 限流 / 缓存                           │   │
│  └──────────────────────────────────────────────────┘   │
└──────────┬──────────────────────────────┬───────────────┘
           │                              │
┌──────────▼──────────┐    ┌──────────────▼──────────────┐
│   Vue 3 前端         │    │   Flask API (Gunicorn)      │
│   (静态文件)          │    │   • 用户认证/注册 (bcrypt)  │
│   • 登录/注册页面     │    │   • 特征帧上传/查询         │
│   • 数据仪表板        │    │   • 指令下发/确认           │
│   • 实时刷新(10s)    │    │   • 设备状态检测            │
│   • 手动下发PID指令   │    │   • 健康检查                │
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
| **前端** | Vue 3 + Vue Router + Axios | 单页应用，支持 History 路由模式 |
| **构建** | Vite | 快速开发服务器 + 生产构建 |
| **后端** | Flask + SQLAlchemy | RESTful API，ORM 数据库操作 |
| **WSGI** | Gunicorn | 生产级 Python WSGI 服务器，多进程并发 |
| **数据库** | MySQL 8.0 | 关系型数据库，支持 utf8mb4 |
| **反向代理** | Nginx | SSL 终止、静态文件服务、API 代理 |
| **部署** | Docker Compose / Shell 脚本 | 容器化或裸机部署 |
| **密码安全** | bcrypt | 密码哈希存储，不保存明文 |

---

## 📁 项目结构

```
AIPID_website/
├── backend/                      # Flask 后端
│   ├── app.py                    # 主应用 & 全部 API 路由
│   ├── config.py                 # 配置（数据库、Session、安全等）
│   ├── models.py                 # 数据模型（User, FeatureFrame, DownlinkCommand）
│   ├── wsgi.py                   # WSGI 入口
│   ├── gunicorn.conf.py          # Gunicorn 生产配置
│   ├── requirements.txt          # Python 依赖
│   └── Dockerfile                # Docker 镜像构建
│
├── frontend/                     # Vue 3 前端
│   ├── index.html                # HTML 入口
│   ├── package.json              # Node 依赖
│   ├── vite.config.js            # Vite 配置（含开发代理）
│   └── src/
│       ├── main.js               # 应用入口
│       ├── App.vue               # 根组件
│       ├── router/index.js       # 路由配置（/login, /register, /dashboard）
│       └── views/
│           ├── Login.vue         # 登录页面
│           ├── Register.vue      # 注册页面
│           └── Dashboard.vue     # 数据仪表板（10s 自动刷新）
│                                 #   • 特征帧列表展示
│                                 #   • 最新特征帧概览
│                                 #   • 待处理指令查看
│                                 #   • 恒温箱硬件状态（运行中/已停止/未连接）
│                                 #   • 手动下发 PID 指令弹窗
│
├── simulator/                    # 边缘侧设备模拟器
│   └── simulate_device.py        # 3 分钟训练模式模拟器
│
├── mysql/
│   └── init.sql                  # 数据库初始化脚本（4 张表）
│
├── nginx/
│   └── nginx.conf                # Nginx 配置（含 HTTPS 注释模板）
│
├── deploy/
│   └── deploy.sh                 # 一键部署脚本（Ubuntu/Debian）
│
├── docker-compose.yml            # Docker Compose 编排（MySQL + Backend + Nginx）
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

# 2. 配置环境变量（可选，有默认值）
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
# http://localhost
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

| 方法 | 路径 | 说明 | 请求体 |
|------|------|------|--------|
| POST | `/api/login` | 用户登录 | `{"username": "...", "password": "..."}` |
| POST | `/api/register` | 用户注册 | `{"username": "...", "password": "..."}` |
| POST | `/api/logout` | 用户登出 | - |
| GET | `/api/me` | 获取当前登录用户信息 | - |

### 特征帧（上行 - 边缘侧 → 云端）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/upload_frame` | 边缘侧上传特征帧 |
| GET | `/api/frames?limit=100` | 获取最近 N 条特征帧 |
| GET | `/api/frames/latest` | 获取最新一条特征帧 |

### 指令（下行 - 云端 → 边缘侧）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/issue_command` | 云端下发 PID 调整指令 |
| GET | `/api/pending_command` | 边缘侧查询待处理指令 |
| POST | `/api/apply_command/<batch_id>` | 边缘侧确认应用指令 |
| GET | `/api/commands?limit=50` | 获取指令下发记录 |

### 设备状态

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/device/status` | 获取恒温箱硬件状态（基于 RS485 数据判断） |

返回示例：
```json
{"status": "running", "label": "运行中", "last_seen": 1784876442825, "last_seen_ago": 5.2}
```

状态判断逻辑：
| 状态 | 条件 | 颜色 |
|------|------|------|
| `running`（运行中） | 最近 30 秒内有特征帧上传 | 🟢 绿色 |
| `stopped`（已停止） | 有历史数据，但超过 30 秒未更新 | 🟠 橙色 |
| `offline`（未连接） | 从未收到过特征帧数据 | ⚪ 灰色 |

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

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户表 | username(唯一), password_hash(bcrypt), role(admin/viewer) |
| `feature_frames` | 特征帧表（上行数据） | timestamp, kp, ti, td, iae_60s, status_flag 等 |
| `downlink_commands` | 下行指令表 | action_batch_id(唯一), delta_kp/ti/td, confidence, applied |
| `experience_pool` | 极端工况经验池 | feature_frame_id(外键), reason |

---

## 🔒 安全配置

1. **HTTPS**：Nginx 配置 SSL 证书（Let's Encrypt 或云厂商免费证书）
2. **密码安全**：bcrypt 哈希存储，不保存明文
3. **Session 安全**：HttpOnly + SameSite=Lax，生产环境启用 Secure
4. **数据库隔离**：MySQL 仅监听 127.0.0.1，不对外暴露
5. **环境变量**：敏感配置通过环境变量注入，不写入代码
6. **CORS**：明确指定允许的 origins，不滥用通配符

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

## 🧪 边缘侧设备模拟器

`simulator/simulate_device.py` 是一个 Python 脚本，用于模拟树莓派通过 USB-RS485 连接温控设备后的行为，方便开发和测试。

### 功能

- **上行模拟**：每 5 秒生成一个特征帧并上传到 `/api/upload_frame`
- **下行模拟**：每 30 秒查询 `/api/pending_command`，如有指令则调用 `/api/apply_command` 确认应用
- **3 分钟训练模式**：模拟 3 个周期的工况变化

### 训练模式场景

| 周期 | 时间 | 工况 | 特征 |
|------|------|------|------|
| 周期 1 | 0~60s | 稳态运行 | KP≈2.5, TI≈60, TD≈15, IAE<1, 功率≈45W |
| 周期 2 | 60~120s | 轻微扰动 | KP≈2.8, TI≈55, TD≈12, IAE≈2, 功率≈55W |
| 周期 3 | 120~180s | 显著扰动（异常） | KP≈1.2, TI≈80, TD≈5, IAE≈8, 功率≈80W |

每个周期内：**55 秒稳态 + 5 秒扰动**，扰动阶段指标会明显恶化。

### 用法

```bash
# 连接本地 Docker 服务
python simulator/simulate_device.py

# 连接远程树莓派
python simulator/simulate_device.py --url http://172.160.100.141

# 指定间隔（默认 5 秒）
python simulator/simulate_device.py --interval 3
```

### 输出示例

```
[01/36]   0s/180s | 周期1 稳态 | KP=2.53 TI=61.1 TD=15.3 | IAE=0.52 Pwr=45.1 | 状态=正常 | ✓ frame_id=7
[12/36]  55s/180s | 周期1 ⚠ 扰动 | KP=2.44 TI=60.0 TD=15.0 | IAE=0.81 Pwr=53.8 | 状态=警告 | ✓ frame_id=18
[36/36] 176s/180s | 周期3 ⚠ 扰动 | KP=0.96 TI=85.1 TD=5.7 | IAE=21.64 Pwr=88.2 | 状态=过载 | ✓ frame_id=78
```

---

## 🐳 Docker Compose 服务说明

| 服务 | 镜像 | 端口 | 说明 |
|------|------|------|------|
| `mysql` | mysql:8.0 | 127.0.0.1:3306 | 数据库，带健康检查 |
| `backend` | 自构建 | 127.0.0.1:5000 | Flask + Gunicorn |
| `nginx` | nginx:1.25-alpine | 80 | 反向代理 + 静态文件 |

```bash
# 常用命令
docker compose up -d              # 启动所有服务
docker compose down               # 停止所有服务
docker compose logs -f backend    # 查看后端日志
docker compose build backend      # 重建后端镜像
docker compose up -d --force-recreate backend  # 重启后端
```

---

## 📝 License

MIT
