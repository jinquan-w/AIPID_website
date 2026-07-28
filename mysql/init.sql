-- ============================================================
-- AIPID 温控系统 - MySQL 数据库初始化脚本
-- 使用方式: mysql -u root -p < init.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS pid_control
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE pid_control;

-- -----------------------------------------------------------
-- 用户表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,       -- bcrypt 哈希
    role ENUM('admin', 'viewer') DEFAULT 'viewer',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 特征帧表（上行 - 边缘侧 → 云端）
-- 存储 PID 运行时的特征数据，每 5 秒一帧
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS feature_frames (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp BIGINT UNSIGNED NOT NULL,         -- Unix 毫秒时间戳
    action_trace_id INT UNSIGNED DEFAULT 0,     -- 动作追踪 ID

    -- PID 参数
    kp FLOAT,
    ti FLOAT,
    td FLOAT,

    -- 性能指标
    iae_60s FLOAT,                              -- 60秒误差积分
    var_power FLOAT,                            -- 功率方差

    -- 工况特征
    zero_cross_count TINYINT UNSIGNED,          -- 过零计数
    avg_disturbance FLOAT,                      -- 平均扰动
    current_power FLOAT,                        -- 当前功率
    rpm_equivalent FLOAT,                       -- 等效转速
    status_flag TINYINT,                        -- 状态标志

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_timestamp (timestamp DESC),
    INDEX idx_status (status_flag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 温度记录表（上行 - 边缘侧 → 云端）
-- 存储设备上传的实时温度数据，每 100ms 一条记录
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS temperature_records (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp BIGINT UNSIGNED NOT NULL,          -- Unix 毫秒时间戳
    temperature FLOAT NOT NULL,                  -- 当前温度（℃）
    target_temperature FLOAT DEFAULT NULL,       -- 目标/设定温度（℃）
    batch_id INT UNSIGNED DEFAULT NULL,          -- 关联的批次 ID（可选）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_temp_timestamp (timestamp DESC, batch_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 下行指令表（云端 → 边缘侧）
-- 记录云端下发的 PID 参数调整指令
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS downlink_commands (
    id INT AUTO_INCREMENT PRIMARY KEY,
    action_batch_id INT UNSIGNED UNIQUE NOT NULL,  -- 指令批次 ID

    -- PID 参数增量
    delta_kp FLOAT DEFAULT 0,
    delta_ti FLOAT DEFAULT 0,
    delta_td FLOAT DEFAULT 0,
    delta_k_ff FLOAT DEFAULT 0,                    -- 前馈系数增量

    confidence FLOAT DEFAULT 0.5,                   -- 置信度
    valid_time INT UNSIGNED DEFAULT 60,             -- 有效期（秒）
    fan_power FLOAT DEFAULT NULL,                   -- 风扇功率设定（NULL=沿用当前）
    issued_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 下发时间
    applied BOOLEAN DEFAULT FALSE,                  -- 是否已被边缘侧应用

    INDEX idx_applied (applied, issued_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -----------------------------------------------------------
-- 极端工况经验池
-- 记录极端工况下的特征帧，供后续分析优化
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS experience_pool (
    id INT AUTO_INCREMENT PRIMARY KEY,
    feature_frame_id INT NOT NULL,                  -- 关联特征帧
    reason VARCHAR(100),                            -- 记录原因
    stored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feature_frame_id)
        REFERENCES feature_frames(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
