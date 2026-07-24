"""
AIPID 温控系统 - 边缘侧设备模拟器（3 分钟训练模式）
=====================================================
模拟树莓派通过 USB-RS485 连接设备后的行为：
  - 总时长 3 分钟（180 秒），每 5 秒上传一个特征帧，共 36 帧
  - 模拟训练模式：每 60 秒一个周期（55 秒稳态 + 5 秒扰动）
  - 周期 1：稳态运行（正常 PID 参数）
  - 周期 2：轻微扰动（负载变化）
  - 周期 3：显著扰动（模拟异常工况）
  - 同时模拟下行指令查询

用法：
  python simulate_device.py [--url http://localhost]

示例：
  # 连接本地 Docker 服务
  python simulate_device.py

  # 连接树莓派
  python simulate_device.py --url http://172.160.100.141
"""

import requests
import time
import random
import argparse
import sys
import math
from datetime import datetime


# ============================================================
#  配置
# ============================================================

BASE_URL = "http://localhost"
TOTAL_DURATION = 180       # 总时长 3 分钟
FRAME_INTERVAL = 5         # 每 5 秒一个特征帧
CYCLE_DURATION = 60        # 每个周期 60 秒
STEADY_DURATION = 55       # 稳态 55 秒
DISTURB_DURATION = 5       # 扰动 5 秒
TOTAL_FRAMES = TOTAL_DURATION // FRAME_INTERVAL  # 36 帧


# ============================================================
#  场景定义：3 个周期的基准参数
# ============================================================

# 周期 1：稳态运行
CYCLE_1_BASE = {
    "kp": 2.5, "ti": 60.0, "td": 15.0,
    "iae_60s": 0.5, "var_power": 0.1,
    "zero_cross_count": 2, "avg_disturbance": 0.1,
    "current_power": 45.0, "rpm_equivalent": 1500.0,
    "status_flag": 0,
    "noise_level": 0.05,  # 噪声幅度（相对值）
}

# 周期 2：轻微扰动
CYCLE_2_BASE = {
    "kp": 2.8, "ti": 55.0, "td": 12.0,
    "iae_60s": 2.0, "var_power": 0.8,
    "zero_cross_count": 5, "avg_disturbance": 0.8,
    "current_power": 55.0, "rpm_equivalent": 1800.0,
    "status_flag": 0,
    "noise_level": 0.10,
}

# 周期 3：显著扰动（模拟异常）
CYCLE_3_BASE = {
    "kp": 1.2, "ti": 80.0, "td": 5.0,
    "iae_60s": 8.0, "var_power": 3.5,
    "zero_cross_count": 15, "avg_disturbance": 2.5,
    "current_power": 80.0, "rpm_equivalent": 2500.0,
    "status_flag": 1,
    "noise_level": 0.20,
}

CYCLES = [CYCLE_1_BASE, CYCLE_2_BASE, CYCLE_3_BASE]


# ============================================================
#  数据生成
# ============================================================

def generate_frame(cycle_index, frame_in_cycle, elapsed):
    """
    根据当前周期和帧位置生成特征帧

    参数:
      cycle_index:    当前周期索引 (0, 1, 2)
      frame_in_cycle: 当前周期内的第几帧 (0~11)
      elapsed:        已运行秒数
    """
    base = CYCLES[cycle_index]
    now_ms = int(time.time() * 1000)

    # 判断是否在扰动阶段（周期内后 5 秒）
    in_disturbance = (elapsed % CYCLE_DURATION) >= STEADY_DURATION

    # 基础值 + 随机噪声
    noise = base["noise_level"]
    kp = round(base["kp"] * (1 + random.uniform(-noise, noise)), 4)
    ti = round(base["ti"] * (1 + random.uniform(-noise, noise)), 4)
    td = round(base["td"] * (1 + random.uniform(-noise, noise)), 4)

    # 扰动阶段：指标恶化
    if in_disturbance:
        iae_60s = round(base["iae_60s"] * random.uniform(1.5, 3.0), 4)
        var_power = round(base["var_power"] * random.uniform(2.0, 4.0), 4)
        zero_cross_count = base["zero_cross_count"] + random.randint(3, 8)
        avg_disturbance = round(base["avg_disturbance"] * random.uniform(2.0, 3.0), 4)
        current_power = round(base["current_power"] * random.uniform(1.1, 1.4), 2)
        rpm_equivalent = round(base["rpm_equivalent"] * random.uniform(1.1, 1.3), 2)
        status_flag = min(base["status_flag"] + 1, 3)  # 状态恶化
    else:
        iae_60s = round(base["iae_60s"] * (1 + random.uniform(-noise, noise)), 4)
        var_power = round(base["var_power"] * (1 + random.uniform(-noise, noise)), 4)
        zero_cross_count = max(0, base["zero_cross_count"] + random.randint(-2, 2))
        avg_disturbance = round(base["avg_disturbance"] * (1 + random.uniform(-noise, noise)), 4)
        current_power = round(base["current_power"] * (1 + random.uniform(-noise, noise)), 2)
        rpm_equivalent = round(base["rpm_equivalent"] * (1 + random.uniform(-noise, noise)), 2)
        status_flag = base["status_flag"]

    return {
        "timestamp": now_ms,
        "action_trace_id": cycle_index * 12 + frame_in_cycle,
        "kp": kp,
        "ti": ti,
        "td": td,
        "iae_60s": iae_60s,
        "var_power": var_power,
        "zero_cross_count": zero_cross_count,
        "avg_disturbance": avg_disturbance,
        "current_power": current_power,
        "rpm_equivalent": rpm_equivalent,
        "status_flag": status_flag,
    }


# ============================================================
#  上行：上传特征帧
# ============================================================

def upload_frame(frame):
    """上传特征帧到云端"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/upload_frame",
            json=frame,
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get('id')
        else:
            return False, f"HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, "连接失败"
    except Exception as e:
        return False, str(e)


# ============================================================
#  下行：查询并应用指令
# ============================================================

def check_pending_command():
    """查询云端是否有待处理的指令"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/pending_command",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            if data and "action_batch_id" in data:
                return data
        return None
    except Exception:
        return None


def apply_command(batch_id):
    """模拟边缘侧应用指令"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/apply_command/{batch_id}",
            timeout=5
        )
        return resp.status_code == 200
    except Exception:
        return False


# ============================================================
#  状态标志文本
# ============================================================

STATUS_TEXT = {0: "正常", 1: "警告", 2: "过载", 3: "异常"}
PHASE_TEXT = {True: "⚠ 扰动", False: "稳态"}


# ============================================================
#  主流程
# ============================================================

def main():
    global BASE_URL

    parser = argparse.ArgumentParser(
        description="AIPID 边缘侧设备模拟器（3 分钟训练模式）"
    )
    parser.add_argument(
        "--url", "-u",
        type=str,
        default=BASE_URL,
        help=f"服务器地址，默认 {BASE_URL}"
    )
    args = parser.parse_args()
    BASE_URL = args.url.rstrip("/")

    print("=" * 70)
    print("  AIPID 边缘侧设备模拟器 — 3 分钟训练模式")
    print("=" * 70)
    print(f"  服务器地址:  {BASE_URL}")
    print(f"  总时长:      {TOTAL_DURATION} 秒 ({TOTAL_DURATION//60} 分钟)")
    print(f"  特征帧间隔:  {FRAME_INTERVAL} 秒")
    print(f"  总帧数:      {TOTAL_FRAMES} 帧")
    print(f"  周期模式:    每 {CYCLE_DURATION} 秒 = {STEADY_DURATION}s 稳态 + {DISTURB_DURATION}s 扰动")
    print("-" * 70)
    print(f"  周期 1: 稳态运行")
    print(f"  周期 2: 轻微扰动")
    print(f"  周期 3: 显著扰动（异常）")
    print("-" * 70)

    frame_count = 0
    success_count = 0
    start_time = time.time()
    last_cmd_check = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= TOTAL_DURATION:
                print("\n" + "=" * 70)
                print(f"  ✅ 模拟完成！共上传 {frame_count} 帧，成功 {success_count} 帧")
                print("=" * 70)
                break

            # 计算当前周期和帧位置
            cycle_index = min(int(elapsed // CYCLE_DURATION), 2)
            frame_in_cycle = int((elapsed % CYCLE_DURATION) // FRAME_INTERVAL)
            in_disturbance = (elapsed % CYCLE_DURATION) >= STEADY_DURATION

            # 生成并上传特征帧
            frame = generate_frame(cycle_index, frame_in_cycle, elapsed)
            frame_count += 1

            ok, result = upload_frame(frame)
            if ok:
                success_count += 1
                status = f"✓ frame_id={result}"
            else:
                status = f"✗ {result}"

            # 打印进度
            progress = f"{elapsed:3.0f}s/{TOTAL_DURATION}s"
            cycle_label = f"周期{cycle_index + 1}"
            phase = PHASE_TEXT[in_disturbance]
            status_text = STATUS_TEXT.get(frame["status_flag"], "未知")
            print(f"  [{frame_count:02d}/{TOTAL_FRAMES}] {progress} | "
                  f"{cycle_label} {phase} | "
                  f"KP={frame['kp']:.2f} TI={frame['ti']:.1f} TD={frame['td']:.1f} | "
                  f"IAE={frame['iae_60s']:.2f} Pwr={frame['current_power']:.1f} | "
                  f"状态={status_text} | {status}")

            # 下行：每 30 秒检查一次指令
            if elapsed - last_cmd_check >= 30:
                last_cmd_check = elapsed
                cmd = check_pending_command()
                if cmd:
                    print(f"\n  📥 发现待处理指令 | batch_id={cmd['action_batch_id']} | "
                          f"ΔKP={cmd.get('delta_kp', 0):+.3f} "
                          f"ΔTI={cmd.get('delta_ti', 0):+.1f} "
                          f"ΔTD={cmd.get('delta_td', 0):+.1f}")
                    if apply_command(cmd["action_batch_id"]):
                        print(f"  ✓ 指令已应用\n")
                    else:
                        print(f"  ✗ 指令应用失败\n")

            # 等待到下一个帧时间
            time.sleep(FRAME_INTERVAL)

    except KeyboardInterrupt:
        print("\n" + "-" * 70)
        print(f"  模拟器已手动停止 | 已上传 {frame_count} 帧，成功 {success_count} 帧")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
