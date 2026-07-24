"""
AIPID 温控系统 - Flask 后端主应用
生产环境使用 Gunicorn 启动: gunicorn -c gunicorn.conf.py wsgi:app
"""
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from config import Config
from models import db, User, FeatureFrame, DownlinkCommand
import bcrypt
from datetime import datetime, timedelta
import time
import os
from pathlib import Path

app = Flask(__name__)
app.config.from_object(Config)

# Session 配置
app.config.update(
    SESSION_COOKIE_DOMAIN=False,  # 允许所有域名
    SESSION_COOKIE_PATH='/',
)

CORS(app, supports_credentials=True, origins=['http://localhost', 'http://172.160.100.141'])
db.init_app(app)
BASE_DIR = Path(__file__).parent.parent


# ============================================================
#  应用初始化（首次请求时创建默认管理员）
# ============================================================

@app.before_request
def _init_app_once():
    """首次请求前初始化数据库和默认用户"""
    if not hasattr(app, '_initialized'):
        with app.app_context():
            db.create_all()
            if not User.query.filter_by(username='admin').first():
                hashed = bcrypt.hashpw('123456'.encode('utf-8'), bcrypt.gensalt())
                admin = User(
                    username='admin',
                    password_hash=hashed.decode('utf-8'),
                    role='admin'
                )
                db.session.add(admin)
                db.session.commit()
                print('[INFO] 默认管理员已创建: admin / 123456')
        app._initialized = True


# ============================================================
#  用户认证
# ============================================================

@app.route('/api/login', methods=['POST'])
def login():
    """用户登录"""
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'status': 'fail', 'message': '缺少用户名或密码'}), 400

    user = User.query.filter_by(username=data['username']).first()
    if user and bcrypt.checkpw(
        data['password'].encode('utf-8'),
        user.password_hash.encode('utf-8')
    ):
        session['user_id'] = user.id
        session.permanent = True
        return jsonify({'status': 'success', 'role': user.role})
    return jsonify({'status': 'fail', 'message': '用户名或密码错误'}), 401


@app.route('/api/register', methods=['POST'])
def register():
    """用户注册"""
    data = request.json
    if not data or 'username' not in data or 'password' not in data:
        return jsonify({'status': 'fail', 'message': '缺少用户名或密码'}), 400

    username = data['username'].strip()
    password = data['password']

    if len(username) < 2 or len(username) > 50:
        return jsonify({'status': 'fail', 'message': '用户名长度应为 2-50 个字符'}), 400
    if len(password) < 6:
        return jsonify({'status': 'fail', 'message': '密码长度不能少于 6 位'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'status': 'fail', 'message': '用户名已存在'}), 409

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    user = User(
        username=username,
        password_hash=hashed.decode('utf-8'),
        role='viewer'
    )
    db.session.add(user)
    db.session.commit()

    return jsonify({'status': 'success', 'message': '注册成功，请登录'})


@app.route('/api/logout', methods=['POST'])
def logout():
    """用户登出"""
    session.clear()
    return jsonify({'status': 'success'})


@app.route('/api/me', methods=['GET'])
def current_user():
    """获取当前登录用户信息"""
    if 'user_id' not in session:
        return jsonify({'status': 'fail'}), 401
    user = User.query.get(session['user_id'])
    if not user:
        return jsonify({'status': 'fail'}), 401
    return jsonify({'status': 'success', 'username': user.username, 'role': user.role})


# ============================================================
#  特征帧（上行 - 边缘侧 → 云端）
# ============================================================

@app.route('/api/upload_frame', methods=['POST'])
def upload_frame():
    """接收边缘侧上传的特征帧数据"""
    data = request.json
    required = [
        'timestamp', 'kp', 'ti', 'td', 'iae_60s', 'var_power',
        'zero_cross_count', 'avg_disturbance', 'current_power',
        'rpm_equivalent', 'status_flag'
    ]
    if not all(k in data for k in required):
        return jsonify({'error': 'Missing fields'}), 400

    frame = FeatureFrame(
        timestamp=data['timestamp'],
        action_trace_id=data.get('action_trace_id', 0),
        kp=data['kp'], ti=data['ti'], td=data['td'],
        iae_60s=data['iae_60s'], var_power=data['var_power'],
        zero_cross_count=data['zero_cross_count'],
        avg_disturbance=data['avg_disturbance'],
        current_power=data['current_power'],
        rpm_equivalent=data['rpm_equivalent'],
        status_flag=data['status_flag']
    )
    db.session.add(frame)
    db.session.commit()
    return jsonify({'status': 'ok', 'id': frame.id})


@app.route('/api/frames', methods=['GET'])
def get_frames():
    """获取最近 N 条特征帧（供前端展示）"""
    limit = request.args.get('limit', 100, type=int)
    frames = FeatureFrame.query.order_by(
        FeatureFrame.timestamp.desc()
    ).limit(limit).all()
    return jsonify([{
        'id': f.id,
        'timestamp': f.timestamp,
        'action_trace_id': f.action_trace_id,
        'kp': f.kp, 'ti': f.ti, 'td': f.td,
        'iae_60s': f.iae_60s, 'var_power': f.var_power,
        'zero_cross_count': f.zero_cross_count,
        'avg_disturbance': f.avg_disturbance,
        'current_power': f.current_power,
        'rpm_equivalent': f.rpm_equivalent,
        'status_flag': f.status_flag,
        'created_at': f.created_at.isoformat() if f.created_at else None
    } for f in frames])


@app.route('/api/frames/batches', methods=['GET'])
def get_frame_batches():
    """
    获取特征帧批次列表
    按时间间隔分组：相邻帧间隔 > 60 秒视为不同批次
    返回批次摘要信息（最新批次包含具体帧数据）
    """
    limit = request.args.get('limit', 500, type=int)
    frames = FeatureFrame.query.order_by(
        FeatureFrame.timestamp.desc()
    ).limit(limit).all()

    if not frames:
        return jsonify({'batches': [], 'total_frames': 0, 'total_batches': 0})

    # 按时间间隔分组
    batches = []
    current_batch = [frames[0]]
    GAP_THRESHOLD_MS = 60 * 1000  # 60 秒

    for i in range(1, len(frames)):
        gap = current_batch[-1].timestamp - frames[i].timestamp
        if gap > GAP_THRESHOLD_MS:
            batches.append(current_batch)
            current_batch = []
        current_batch.append(frames[i])
    if current_batch:
        batches.append(current_batch)

    # 构建返回数据
    result = []
    for idx, batch in enumerate(batches):
        batch_frames = sorted(batch, key=lambda f: f.timestamp)
        first_ts = batch_frames[0].timestamp
        last_ts = batch_frames[-1].timestamp
        avg_iae = sum(f.iae_60s for f in batch_frames) / len(batch_frames)
        avg_status = max(f.status_flag or 0 for f in batch_frames)

        batch_info = {
            'batch_index': idx,
            'frame_count': len(batch_frames),
            'start_time': first_ts,
            'end_time': last_ts,
            'duration_sec': round((last_ts - first_ts) / 1000, 1),
            'avg_iae_60s': round(avg_iae, 4),
            'max_status': avg_status,
            'frames': []
        }

        # 最新批次（idx==0）包含具体帧数据
        if idx == 0:
            batch_info['frames'] = [{
                'id': f.id,
                'timestamp': f.timestamp,
                'action_trace_id': f.action_trace_id,
                'kp': f.kp, 'ti': f.ti, 'td': f.td,
                'iae_60s': f.iae_60s, 'var_power': f.var_power,
                'zero_cross_count': f.zero_cross_count,
                'avg_disturbance': f.avg_disturbance,
                'current_power': f.current_power,
                'rpm_equivalent': f.rpm_equivalent,
                'status_flag': f.status_flag,
                'fan_power': getattr(f, 'fan_power', None),
                'temperature': getattr(f, 'temperature', None),
                'created_at': f.created_at.isoformat() if f.created_at else None
            } for f in batch_frames]

        result.append(batch_info)

    return jsonify({
        'batches': result,
        'total_frames': len(frames),
        'total_batches': len(batches)
    })


@app.route('/api/frames/batch/<int:batch_index>', methods=['GET'])
def get_batch_frames(batch_index):
    """
    获取指定批次的所有特征帧
    重新分组计算，返回该批次的所有帧数据
    """
    limit = request.args.get('limit', 500, type=int)
    frames = FeatureFrame.query.order_by(
        FeatureFrame.timestamp.desc()
    ).limit(limit).all()

    if not frames:
        return jsonify({'frames': [], 'batch_index': batch_index})

    # 重新分组（与 /api/frames/batches 逻辑一致）
    batches = []
    current_batch = [frames[0]]
    GAP_THRESHOLD_MS = 60 * 1000

    for i in range(1, len(frames)):
        gap = current_batch[-1].timestamp - frames[i].timestamp
        if gap > GAP_THRESHOLD_MS:
            batches.append(current_batch)
            current_batch = []
        current_batch.append(frames[i])
    if current_batch:
        batches.append(current_batch)

    if batch_index < 0 or batch_index >= len(batches):
        return jsonify({'frames': [], 'batch_index': batch_index}), 404

    batch = sorted(batches[batch_index], key=lambda f: f.timestamp)
    return jsonify({
        'batch_index': batch_index,
        'frame_count': len(batch),
        'frames': [{
            'id': f.id,
            'timestamp': f.timestamp,
            'action_trace_id': f.action_trace_id,
            'kp': f.kp, 'ti': f.ti, 'td': f.td,
            'iae_60s': f.iae_60s, 'var_power': f.var_power,
            'zero_cross_count': f.zero_cross_count,
            'avg_disturbance': f.avg_disturbance,
            'current_power': f.current_power,
            'rpm_equivalent': f.rpm_equivalent,
            'status_flag': f.status_flag,
            'fan_power': getattr(f, 'fan_power', None),
            'temperature': getattr(f, 'temperature', None),
            'created_at': f.created_at.isoformat() if f.created_at else None
        } for f in batch]
    })


@app.route('/api/frames/latest', methods=['GET'])
def get_latest_frame():
    """获取最新一条特征帧"""
    frame = FeatureFrame.query.order_by(
        FeatureFrame.timestamp.desc()
    ).first()
    if not frame:
        return jsonify({}), 404
    return jsonify({
        'id': frame.id,
        'timestamp': frame.timestamp,
        'kp': frame.kp, 'ti': frame.ti, 'td': frame.td,
        'iae_60s': frame.iae_60s, 'var_power': frame.var_power,
        'zero_cross_count': frame.zero_cross_count,
        'avg_disturbance': frame.avg_disturbance,
        'current_power': frame.current_power,
        'rpm_equivalent': frame.rpm_equivalent,
        'status_flag': frame.status_flag
    })


# ============================================================
#  下行指令（云端 → 边缘侧）
# ============================================================

@app.route('/api/issue_command', methods=['POST'])
def issue_command():
    """云端下发 PID 参数调整指令"""
    data = request.json
    # 生成 action_batch_id（简单自增）
    last = DownlinkCommand.query.order_by(
        DownlinkCommand.id.desc()
    ).first()
    batch_id = (last.action_batch_id + 1) if last else 1

    cmd = DownlinkCommand(
        action_batch_id=batch_id,
        delta_kp=data.get('delta_kp', 0.0),
        delta_ti=data.get('delta_ti', 0.0),
        delta_td=data.get('delta_td', 0.0),
        delta_k_ff=data.get('delta_k_ff', 0.0),
        confidence=data.get('confidence', 0.5),
        valid_time=data.get('valid_time', 60),
        fan_power=data.get('fan_power')  # None 表示沿用当前
    )
    db.session.add(cmd)
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'action_batch_id': batch_id,
        'confidence': cmd.confidence,
        'fan_power': cmd.fan_power
    })


@app.route('/api/pending_command', methods=['GET'])
def pending_command():
    """边缘侧查询当前有效（未应用且在有效期内）的指令"""
    now = datetime.utcnow()
    # 先查出所有未应用的指令，再在 Python 中过滤有效期
    cmd = DownlinkCommand.query.filter(
        DownlinkCommand.applied == False
    ).order_by(DownlinkCommand.issued_at.desc()).first()
    if cmd:
        expire_at = cmd.issued_at + timedelta(seconds=cmd.valid_time)
        if expire_at <= now:
            cmd = None
    if not cmd:
        return jsonify({})
    return jsonify({
        'action_batch_id': cmd.action_batch_id,
        'delta_kp': cmd.delta_kp,
        'delta_ti': cmd.delta_ti,
        'delta_td': cmd.delta_td,
        'delta_k_ff': cmd.delta_k_ff,
        'confidence': cmd.confidence,
        'valid_time': cmd.valid_time,
        'fan_power': cmd.fan_power,
        'issued_at': cmd.issued_at.isoformat() if cmd.issued_at else None
    })


@app.route('/api/apply_command/<int:batch_id>', methods=['POST'])
def apply_command(batch_id):
    """边缘侧确认应用指令"""
    cmd = DownlinkCommand.query.filter_by(
        action_batch_id=batch_id
    ).first()
    if cmd:
        cmd.applied = True
        db.session.commit()
        return jsonify({'status': 'applied'})
    return jsonify({'error': 'not found'}), 404


@app.route('/api/commands', methods=['GET'])
def get_commands():
    """获取所有已下发的指令记录（供前端查看）"""
    limit = request.args.get('limit', 50, type=int)
    cmds = DownlinkCommand.query.order_by(
        DownlinkCommand.issued_at.desc()
    ).limit(limit).all()
    return jsonify([{
        'action_batch_id': c.action_batch_id,
        'delta_kp': c.delta_kp,
        'delta_ti': c.delta_ti,
        'delta_td': c.delta_td,
        'delta_k_ff': c.delta_k_ff,
        'confidence': c.confidence,
        'valid_time': c.valid_time,
        'fan_power': c.fan_power,
        'issued_at': c.issued_at.isoformat() if c.issued_at else None,
        'applied': c.applied
    } for c in cmds])


# ============================================================
#  设备状态
# ============================================================

@app.route('/api/device/status', methods=['GET'])
def device_status():
    """
    获取恒温箱硬件状态
    基于 RS485 接口数据判断：
      - running:  最近 30 秒内有特征帧上传
      - stopped:  有历史数据，但超过 30 秒未更新
      - offline:  从未收到过特征帧数据
    """
    latest = FeatureFrame.query.order_by(
        FeatureFrame.timestamp.desc()
    ).first()

    if not latest:
        return jsonify({
            'status': 'offline',
            'label': '未连接',
            'last_seen': None
        })

    now_ms = int(time.time() * 1000)
    elapsed = (now_ms - latest.timestamp) / 1000  # 秒

    if elapsed <= 30:
        device_status = 'running'
        label = '运行中'
    else:
        device_status = 'stopped'
        label = '已停止'

    return jsonify({
        'status': device_status,
        'label': label,
        'last_seen': latest.timestamp,
        'last_seen_ago': round(elapsed, 1)
    })


# ============================================================
#  健康检查
# ============================================================

@app.route('/api/health', methods=['GET'])
def health():
    """健康检查接口（供 Nginx 或监控系统使用）"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()})


# ============================================================
#  启动入口（仅开发调试用，生产使用 Gunicorn）
# ============================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # 插入默认管理员（仅首次运行）
        if not User.query.filter_by(username='admin').first():
            hashed = bcrypt.hashpw('123456'.encode('utf-8'), bcrypt.gensalt())
            admin = User(
                username='admin',
                password_hash=hashed.decode('utf-8'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print('[INFO] 默认管理员已创建: admin / 123456')

    # 开发模式使用自签名证书
    cert_file = BASE_DIR / 'certs' / 'raspberrypi.local+1.pem'
    key_file = BASE_DIR / 'certs' / 'raspberrypi.local+1-key.pem'
    if cert_file.exists() and key_file.exists():
        app.run(
            host='0.0.0.0', port=5000,
            ssl_context=(str(cert_file), str(key_file)),
            debug=True
        )
    else:
        app.run(host='0.0.0.0', port=5000, debug=True)
