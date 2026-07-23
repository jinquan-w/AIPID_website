"""
AIPID 温控系统 - Flask 后端主应用
生产环境使用 Gunicorn 启动: gunicorn -w 4 -b 0.0.0.0:5000 app:app
"""
from flask import Flask, request, jsonify, session
from flask_cors import CORS
from config import Config
from models import db, User, FeatureFrame, DownlinkCommand
import bcrypt
from datetime import datetime, timedelta
import os
from pathlib import Path

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)
db.init_app(app)
BASE_DIR = Path(__file__).parent.parent


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
        valid_time=data.get('valid_time', 60)
    )
    db.session.add(cmd)
    db.session.commit()
    return jsonify({
        'status': 'ok',
        'action_batch_id': batch_id,
        'confidence': cmd.confidence
    })


@app.route('/api/pending_command', methods=['GET'])
def pending_command():
    """边缘侧查询当前有效（未应用且在有效期内）的指令"""
    now = datetime.utcnow()
    cmd = DownlinkCommand.query.filter(
        DownlinkCommand.applied == False,
        DownlinkCommand.issued_at + timedelta(
            seconds=DownlinkCommand.valid_time
        ) > now
    ).order_by(DownlinkCommand.issued_at.desc()).first()
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
        'issued_at': c.issued_at.isoformat() if c.issued_at else None,
        'applied': c.applied
    } for c in cmds])


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
