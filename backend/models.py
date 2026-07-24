"""
AIPID 温控系统 - 数据模型
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class User(db.Model):
    """用户表"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='viewer')  # admin | viewer
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FeatureFrame(db.Model):
    """
    特征帧表（上行数据）
    存储边缘侧上传的 PID 运行特征数据
    """
    __tablename__ = 'feature_frames'

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.BigInteger, nullable=False)  # Unix ms
    action_trace_id = db.Column(db.Integer)

    # PID 参数
    kp = db.Column(db.Float)
    ti = db.Column(db.Float)
    td = db.Column(db.Float)

    # 性能指标
    iae_60s = db.Column(db.Float)        # 60秒误差积分
    var_power = db.Column(db.Float)       # 功率方差

    # 工况特征
    zero_cross_count = db.Column(db.SmallInteger)  # 过零计数
    avg_disturbance = db.Column(db.Float)           # 平均扰动
    current_power = db.Column(db.Float)             # 当前功率
    rpm_equivalent = db.Column(db.Float)            # 等效转速
    status_flag = db.Column(db.SmallInteger)        # 状态标志

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DownlinkCommand(db.Model):
    """
    下行指令表
    记录云端下发的 PID 参数调整指令
    """
    __tablename__ = 'downlink_commands'

    id = db.Column(db.Integer, primary_key=True)
    action_batch_id = db.Column(db.Integer, unique=True, nullable=False)

    # PID 参数增量
    delta_kp = db.Column(db.Float)
    delta_ti = db.Column(db.Float)
    delta_td = db.Column(db.Float)
    delta_k_ff = db.Column(db.Float)      # 前馈系数增量

    confidence = db.Column(db.Float)       # 置信度
    valid_time = db.Column(db.Integer)     # 有效期（秒）
    fan_power = db.Column(db.Float, nullable=True)  # 风扇功率设定（None=沿用当前）
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    applied = db.Column(db.Boolean, default=False)  # 是否已被边缘侧应用
