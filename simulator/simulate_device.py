"""
AIPID 温控系统 - 边缘侧设备模拟器（3 分钟训练模式）
=====================================================
模拟树莓派通过 USB-RS485 连接设备后的行为：
  - 总时长 3 分钟（180 秒）
  - 温度数据：每 100ms 上传一次实时温度
  - 特征帧：每 5 秒上传一个特征帧（不含温度）
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
import threading
from datetime import datetime


# ============================================================
#  配置
# ============================================================

BASE_URL = "http://localhost"
TOTAL_DURATION = 180       # 总时长 3 分钟
FRAME_INTERVAL = 5         # 每 5 秒一个特征帧
TEMP_INTERVAL = 0.1        # 每 100ms 上传一次温度
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
    "base_temp": 25.0,    # 基准温度（℃）
    "target_temp": 25.0,  # 目标温度（℃）
}

# 周期 2：轻微扰动
CYCLE_2_BASE = {
    "kp": 2.8, "ti": 55.0, "td": 12.0,
    "iae_60s": 2.0, "var_power": 0.8,
    "zero_cross_count": 5, "avg_disturbance": 0.8,
    "current_power": 55.0, "rpm_equivalent": 1800.0,
    "status_flag": 0,
    "noise_level": 0.10,
    "base_temp": 26.5,
    "target_temp": 25.0,
}

# 周期 3：显著扰动（模拟异常）
CYCLE_3_BASE = {
    "kp": 1.2, "ti": 80.0, "td": 5.0,
    "iae_60s": 8.0, "var_power": 3.5,
    "zero_cross_count": 15, "avg_disturbance": 2.5,
    "current_power": 80.0, "rpm_equivalent": 2500.0,
    "status_flag": 1,
    "noise_level": 0.20,
    "base_temp": 30.0,
    "target_temp": 25.0,
}

CYCLES = [CYCLE_1_BASE, CYCLE_2_BASE, CYCLE_3_BASE]


# ============================================================
#  温度生成（100ms 间隔）
# ============================================================

class TemperatureSimulator:
    """
    模拟设备实时温度
    每 100ms 更新一次，温度变化平滑
    """

    def __init__(self):
        self.current_temp = 25.0
        self.target_temp = 25.0
        self.cycle_index = 0
        self.elapsed = 0.0
        self._lock = threading.Lock()

    def update(self, elapsed):
        """根据当前时间更新温度"""
        self.elapsed = elapsed
        cycle_index = min(int(elapsed // CYCLE_DURATION), 2)
        base = CYCLES[cycle_index]
        in_disturbance = (elapsed % CYCLE_DURATION) >= STEADY_DURATION

        with self._lock:
            self.cycle_index = cycle_index
            self.target_temp = base["target_temp"]

            # 计算目标温度
            if in_disturbance:
                # 扰动阶段：温度上升
                target = base["base_temp"] * random.uniform(1.02, 1.08)
            else:
                # 稳态阶段：接近目标温度
                target = base["target_temp"] + random.uniform(-0.3, 0.3)

            # 平滑过渡（低通滤波效果）
            alpha = 0.3  # 平滑系数
            self.current_temp = round(
                self.current_temp * (1 - alpha) + target * alpha, 2
            )

    def get_temperature(self):
        """获取当前温度"""
        with self._lock:
            return self.current_temp, self.target_temp


# ============================================================
#  特征帧生成（5 秒间隔）
# ============================================================

def generate_frame(cycle_index, frame_in_cycle, elapsed):
    """
    根据当前周期和帧位置生成特征帧（不含温度数据）
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
#  上传函数
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


def upload_temperature(timestamp, temperature, target_temp):
    """上传单条温度记录"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/upload_temperature",
            json={
                "timestamp": timestamp,
                "temperature": temperature,
                "target_temperature": target_temp
            },
            timeout=2
        )
        return resp.status_code == 200
    except Exception:
        return False


def upload_temperatures_batch(records):
    """批量上传温度记录"""
    try:
        resp = requests.post(
            f"{BASE_URL}/api/upload_temperatures",
            json={"records": records},
            timeout=5
        )
        return resp.status_code == 200
    except Exception:
        return False


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
#  温度上传线程
# ============================================================

def temperature_worker(temp_sim, stop_event):
    """
    温度上传线程
    每 100ms 采集并上传一次温度数据
    """
    batch_buffer = []
    last_upload = time.time()

    while not stop_event.is_set():
        now_ms = int(time.time() * 1000)
        temp, target = temp_sim.get_temperature()

        batch_buffer.append({
            "timestamp": now_ms,
            "temperature": temp,
            "target_temperature": target
        })

        # 每 1 秒批量上传一次（10 条记录）
        if time.time() - last_upload >= 1.0 and batch_buffer:
            upload_temperatures_batch(batch_buffer)
            batch_buffer.clear()
            last_upload = time.time()

        # 等待 100ms
        time.sleep(TEMP_INTERVAL)

    # 退出前上传剩余数据
    if batch_buffer:
        upload_temperatures_batch(batch_buffer)


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
    print(f"  温度采集:    每 {int(TEMP_INTERVAL*1000)}ms 一次")
    print(f"  特征帧间隔:  {FRAME_INTERVAL} 秒")
    print(f"  总帧数:      {TOTAL_FRAMES} 帧")
    print(f"  周期模式:    每 {CYCLE_DURATION} 秒 = {STEADY_DURATION}s 稳态 + {DISTURB_DURATION}s 扰动")
    print("-" * 70)
    print(f"  周期 1: 稳态运行")
    print(f"  周期 2: 轻微扰动")
    print(f"  周期 3: 显著扰动（异常）")
    print("-" * 70)

    # 初始化温度模拟器
    temp_sim = TemperatureSimulator()
    stop_event = threading.Event()

    # 启动温度上传线程
    temp_thread = threading.Thread(
        target=temperature_worker,
        args=(temp_sim, stop_event),
        daemon=True
    )
    temp_thread.start()

    frame_count = 0
    success_count = 0
    start_time = time.time()
    last_cmd_check = 0
    last_frame_time = 0

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= TOTAL_DURATION:
                print("\n" + "=" * 70)
                print(f"  ✅ 模拟完成！共上传 {frame_count} 帧，成功 {success_count} 帧")
                print("=" * 70)
                break

            # 更新温度模拟器
            temp_sim.update(elapsed)

            # 每 5 秒上传一个特征帧
            if elapsed - last_frame_time >= FRAME_INTERVAL:
                last_frame_time = elapsed

                # 计算当前周期和帧位置
                cycle_index = min(int(elapsed // CYCLE_DURATION), 2)
                frame_in_cycle = int((elapsed % CYCLE_DURATION) // FRAME_INTERVAL)
                in_disturbance = (elapsed % CYCLE_DURATION) >= STEADY_DURATION

                # 生成并上传特征帧（不含温度）
                frame = generate_frame(cycle_index, frame_in_cycle, elapsed)
                frame_count += 1

                ok, result = upload_frame(frame)
                if ok:
                    success_count += 1
                    status = f"✓ frame_id={result}"
                else:
                    status = f"✗ {result}"

                # 获取当前温度用于显示
                temp, target = temp_sim.get_temperature()

                # 打印进度
                progress = f"{elapsed:3.0f}s/{TOTAL_DURATION}s"
                cycle_label = f"周期{cycle_index + 1}"
                phase = PHASE_TEXT[in_disturbance]
                status_text = STATUS_TEXT.get(frame["status_flag"], "未知")
                print(f"  [{frame_count:02d}/{TOTAL_FRAMES}] {progress} | "
                      f"{cycle_label} {phase} | "
                      f"KP={frame['kp']:.2f} TI={frame['ti']:.1f} TD={frame['td']:.1f} | "
                      f"IAE={frame['iae_60s']:.2f} Pwr={frame['current_power']:.1f} | "
                      f"温度={temp:.1f}℃/{target:.0f}℃ | "
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

            # 短等待，保持循环响应
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n" + "-" * 70)
        print(f"  模拟器已手动停止 | 已上传 {frame_count} 帧，成功 {success_count} 帧")
        print("=" * 70)
    finally:
        stop_event.set()
        temp_thread.join(timeout=2)
        sys.exit(0)


if __name__ == "__main__":
    main()
