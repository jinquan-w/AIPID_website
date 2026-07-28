<template>
  <div class="dashboard">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <h1>AIPID 温控系统</h1>
      </div>
      <div class="header-right">
        <!-- 系统状态（顶边偏右） -->
        <div class="status-bar" @mouseenter="showStatusPopover = true" @mouseleave="showStatusPopover = false">
          <div class="status-bar-item" @click="toggleStatusCard">
            <span class="status-dot" :class="'dot-' + (deviceStatus || 'offline')"></span>
            <span>服务器</span>
            <span class="status-label status-ok">● 运行中</span>
          </div>
          <div class="status-bar-item" @click="toggleStatusCard">
            <span class="status-dot" :class="'dot-' + (deviceStatus || 'offline')"></span>
            <span>恒温箱</span>
            <span :class="'status-label device-' + (deviceStatus || 'offline')">● {{ deviceLabel || '未连接' }}</span>
          </div>
          <!-- 悬浮/点击时显示的完整状态卡片 -->
          <div v-if="showStatusCard || showStatusPopover" class="status-popover" @click.stop>
            <div class="status-popover-header">系统状态详情</div>
            <div class="status-popover-body">
              <div class="status-row">
                <span class="status-key">后端服务</span>
                <span class="status-val status-ok">● 运行中</span>
              </div>
              <div class="status-row">
                <span class="status-key">数据库</span>
                <span class="status-val status-ok">● 已连接</span>
              </div>
              <div class="status-row">
                <span class="status-key">恒温箱</span>
                <span :class="'status-val device-' + (deviceStatus || 'offline')">● {{ deviceLabel || '未连接' }}</span>
              </div>
              <div class="status-row" v-if="lastSeenAgo !== null">
                <span class="status-key">最后通信</span>
                <span class="status-val">{{ lastSeenAgo }} 秒前</span>
              </div>
              <div class="status-row">
                <span class="status-key">特征帧总数</span>
                <span class="status-val">{{ totalFrames }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">运行批次</span>
                <span class="status-val">{{ totalBatches }}</span>
              </div>
              <div class="status-row">
                <span class="status-key">已下发指令</span>
                <span class="status-val">{{ commandCount }}</span>
              </div>
            </div>
          </div>
        </div>
        <span class="user-info" v-if="user">
          {{ user.username }} ({{ user.role }})
        </span>
        <button class="btn-logout" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <!-- 主要内容 -->
    <main class="main-content">
      <!-- 概览卡片 - 第一行 -->
      <section class="overview">
        <div class="card">
          <h3>最新特征帧</h3>
          <div v-if="latestFrame" class="card-content">
            <p>时间: {{ formatTime(latestFrame.timestamp) }}</p>
            <p>KP: {{ latestFrame.kp?.toFixed(3) }}</p>
            <p>TI: {{ latestFrame.ti?.toFixed(1) }}</p>
            <p>TD: {{ latestFrame.td?.toFixed(3) }}</p>
            <p>IAE(60s): {{ latestFrame.iae_60s?.toFixed(2) }}</p>
            <p>状态: {{ statusText(latestFrame.status_flag) }}</p>
          </div>
          <div v-else class="card-content empty">
            暂无数据
          </div>
        </div>

        <div class="card">
          <h3>待处理指令</h3>
          <div v-if="pendingCmd && pendingCmd.action_batch_id" class="card-content">
            <p>批次 ID: {{ pendingCmd.action_batch_id }}</p>
            <p>ΔKP: {{ pendingCmd.delta_kp?.toFixed(3) }}</p>
            <p>ΔTI: {{ pendingCmd.delta_ti?.toFixed(1) }}</p>
            <p>ΔTD: {{ pendingCmd.delta_td?.toFixed(3) }}</p>
            <p>置信度: {{ (pendingCmd.confidence * 100).toFixed(0) }}%</p>
          </div>
          <div v-else class="card-content empty">
            暂无待处理指令
          </div>
        </div>

        <!-- 温度曲线卡片 -->
        <div class="card chart-card">
          <h3>温度曲线</h3>
          <div class="card-content">
            <div v-if="chartData.labels.length > 0" class="chart-container">
              <canvas ref="tempChartCanvas"></canvas>
              <div class="chart-info">
                <span class="chart-legend">
                  <span class="legend-line legend-temp"></span> 实际温度
                </span>
                <span class="chart-legend">
                  <span class="legend-line legend-target"></span> 设定温度
                </span>
                <span class="chart-batch-label" v-if="focusedBatch !== null">
                  批次 #{{ focusedBatch }}
                </span>
              </div>
            </div>
            <div v-else class="empty">
              <p>暂无温度数据</p>
              <p class="chart-hint">请展开一个批次查看温度曲线</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 下发指令 - 第二行 -->
      <section class="cmd-row">
        <!-- 下发 PID 指令卡片 -->
        <div class="card cmd-card">
          <h3>下发 PID 指令</h3>
          <div class="card-content cmd-content">
            <p class="cmd-desc">手动填写 PID 参数调整量，下发到边缘侧设备</p>
            <button class="btn-issue" @click="showCmdModal = true">
              + 下发 PID 指令
            </button>
          </div>
        </div>

        <!-- 下发风扇功率卡片 -->
        <div class="card fan-card">
          <h3>下发风扇功率</h3>
          <div class="card-content cmd-content">
            <p class="cmd-desc">手动设定内外空气交换风扇功率（0~100%），立即下发到边缘侧设备</p>
            <button class="btn-issue btn-fan" @click="showFanModal = true">
              + 设定风扇功率
            </button>
          </div>
        </div>
      </section>

      <!-- 特征帧批次列表 -->
      <section class="data-section">
        <div class="section-header">
          <h2>运行批次</h2>
          <span class="badge">共 {{ totalBatches }} 批次 / {{ totalFrames }} 帧</span>
        </div>

        <div v-if="batches.length > 0" class="batch-list">
          <div
            v-for="batch in batches"
            :key="batch.batch_index"
            class="batch-card"
            :class="{ 'batch-active': batch.batch_index === 0, 'batch-focused': focusedBatch === batch.batch_index }"
          >
            <!-- 批次摘要头 -->
            <div class="batch-header" @click="toggleBatch(batch.batch_index)">
              <div class="batch-info">
                <span class="batch-label" :class="'batch-label-' + batch.max_status">
                  {{ batch.batch_index === 0 ? '🟢 当前运行' : '⏹ 历史批次' }}
                </span>
                <span class="batch-time">
                  {{ formatTime(batch.start_time) }}
                  <template v-if="batch.frame_count > 1">
                    ~ {{ formatTime(batch.end_time) }}
                  </template>
                </span>
              </div>
              <div class="batch-stats">
                <span class="batch-stat">{{ batch.frame_count }} 帧</span>
                <span class="batch-stat">{{ batch.duration_sec }}s</span>
                <span class="batch-stat">IAE: {{ batch.avg_iae_60s.toFixed(2) }}</span>
              </div>
              <span class="batch-toggle">{{ expandedBatches[batch.batch_index] ? '▲' : '▼' }}</span>
            </div>

            <!-- 批次详情（展开时显示） -->
            <div v-if="expandedBatches[batch.batch_index]" class="batch-detail">
              <!-- 最新批次直接显示帧数据 -->
              <div v-if="batch.batch_index === 0">
                <div v-if="batch.frames && batch.frames.length > 0" class="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>KP</th>
                        <th>TI</th>
                        <th>TD</th>
                        <th>IAE(60s)</th>
                        <th>功率方差</th>
                        <th>过零计数</th>
                        <th>平均扰动</th>
                        <th>当前功率</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="frame in batch.frames" :key="frame.id">
                        <td>{{ formatTime(frame.timestamp) }}</td>
                        <td>{{ frame.kp?.toFixed(3) }}</td>
                        <td>{{ frame.ti?.toFixed(1) }}</td>
                        <td>{{ frame.td?.toFixed(3) }}</td>
                        <td>{{ frame.iae_60s?.toFixed(2) }}</td>
                        <td>{{ frame.var_power?.toFixed(2) }}</td>
                        <td>{{ frame.zero_cross_count }}</td>
                        <td>{{ frame.avg_disturbance?.toFixed(2) }}</td>
                        <td>{{ frame.current_power?.toFixed(1) }}</td>
                        <td>
                          <span :class="'status-tag status-' + (frame.status_flag || 0)">
                            {{ statusText(frame.status_flag) }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="batch-loading">暂无帧数据</div>
              </div>
              <!-- 历史批次：点击加载帧数据 -->
              <div v-else-if="batch.batch_index > 0">
                <div v-if="batch.loading" class="batch-loading">加载中...</div>
                <div v-else-if="batch.loadedFrames && batch.loadedFrames.length > 0" class="table-wrapper">
                  <table>
                    <thead>
                      <tr>
                        <th>时间</th>
                        <th>KP</th>
                        <th>TI</th>
                        <th>TD</th>
                        <th>IAE(60s)</th>
                        <th>功率方差</th>
                        <th>过零计数</th>
                        <th>平均扰动</th>
                        <th>当前功率</th>
                        <th>状态</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="frame in batch.loadedFrames" :key="frame.id">
                        <td>{{ formatTime(frame.timestamp) }}</td>
                        <td>{{ frame.kp?.toFixed(3) }}</td>
                        <td>{{ frame.ti?.toFixed(1) }}</td>
                        <td>{{ frame.td?.toFixed(3) }}</td>
                        <td>{{ frame.iae_60s?.toFixed(2) }}</td>
                        <td>{{ frame.var_power?.toFixed(2) }}</td>
                        <td>{{ frame.zero_cross_count }}</td>
                        <td>{{ frame.avg_disturbance?.toFixed(2) }}</td>
                        <td>{{ frame.current_power?.toFixed(1) }}</td>
                        <td>
                          <span :class="'status-tag status-' + (frame.status_flag || 0)">
                            {{ statusText(frame.status_flag) }}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
                <div v-else class="batch-loading">点击加载帧数据...</div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-state">
          暂无特征帧数据，请等待边缘侧设备上传
        </div>
      </section>
    </main>

    <!-- 下发风扇功率弹窗 -->
    <div class="modal-overlay" v-if="showFanModal" @click.self="showFanModal = false">
      <div class="modal modal-sm">
        <div class="modal-header">
          <h3>设定风扇功率</h3>
          <button class="modal-close" @click="showFanModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>风扇功率（0~100%）</label>
            <input v-model.number="fanForm.power" type="number" step="1" min="0" max="100" placeholder="例如: 60" />
          </div>
          <div class="form-group">
            <label>有效期（秒）</label>
            <input v-model.number="fanForm.valid_time" type="number" min="10" placeholder="例如: 60" />
          </div>
          <div class="form-group">
            <label>置信度 (0~1)</label>
            <input v-model.number="fanForm.confidence" type="number" step="0.05" min="0" max="1" placeholder="例如: 0.95" />
          </div>
        </div>
        <div class="modal-footer">
          <span class="modal-msg" :class="fanMsgType">{{ fanMsg }}</span>
          <button class="btn-cancel" @click="showFanModal = false">取消</button>
          <button class="btn-confirm btn-fan-confirm" @click="handleIssueFanPower" :disabled="issuingFan">
            {{ issuingFan ? '下发中...' : '确认下发' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 下发 PID 指令弹窗 -->
    <div class="modal-overlay" v-if="showCmdModal" @click.self="showCmdModal = false">
      <div class="modal">
        <div class="modal-header">
          <h3>下发 PID 参数调整指令</h3>
          <button class="modal-close" @click="showCmdModal = false">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>ΔKP（比例系数调整量）</label>
            <input v-model.number="cmdForm.delta_kp" type="number" step="0.001" placeholder="例如: 0.5" />
          </div>
          <div class="form-group">
            <label>ΔTI（积分时间调整量）</label>
            <input v-model.number="cmdForm.delta_ti" type="number" step="0.1" placeholder="例如: -5.0" />
          </div>
          <div class="form-group">
            <label>ΔTD（微分时间调整量）</label>
            <input v-model.number="cmdForm.delta_td" type="number" step="0.001" placeholder="例如: 2.0" />
          </div>
          <div class="form-group">
            <label>ΔK_FF（前馈系数调整量）</label>
            <input v-model.number="cmdForm.delta_k_ff" type="number" step="0.001" placeholder="例如: 0.0" />
          </div>
          <div class="form-group">
            <label>置信度 (0~1)</label>
            <input v-model.number="cmdForm.confidence" type="number" step="0.05" min="0" max="1" placeholder="例如: 0.85" />
          </div>
          <div class="form-group">
            <label>有效期（秒）</label>
            <input v-model.number="cmdForm.valid_time" type="number" min="10" placeholder="例如: 60" />
          </div>
          <div class="form-divider"></div>
          <div class="form-group">
            <label>风扇功率（0~100%，留空=沿用当前）</label>
            <input v-model.number="cmdForm.fan_power" type="number" step="1" min="0" max="100" placeholder="留空表示沿用当前功率" />
          </div>
        </div>
        <div class="modal-footer">
          <span class="modal-msg" :class="modalMsgType">{{ modalMsg }}</span>
          <button class="btn-cancel" @click="showCmdModal = false">取消</button>
          <button class="btn-confirm" @click="handleIssueCommand" :disabled="issuing">
            {{ issuing ? '下发中...' : '确认下发' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  data() {
    return {
      user: null,
      latestFrame: null,
      batches: [],
      totalFrames: 0,
      totalBatches: 0,
      pendingCmd: {},
      commandCount: 0,
      refreshTimer: null,
      // 设备状态
      deviceStatus: 'offline',
      deviceLabel: '未连接',
      lastSeenAgo: null,
      // 系统状态卡片
      showStatusCard: false,
      showStatusPopover: false,
      // 批次展开状态
      expandedBatches: {},
      // 当前聚焦的批次索引（用于温度曲线）
      focusedBatch: null,
      // 温度曲线数据
      chartData: {
        labels: [],
        temperatures: [],
        targetTemps: []
      },
      chartInstance: null,
      // 强制刷新计数器
      refreshKey: 0,
      // 是否已完成首次自动展开（登录后只自动展开一次）
      _initialExpandDone: false,
      // 下发 PID 指令弹窗
      showCmdModal: false,
      issuing: false,
      modalMsg: '',
      modalMsgType: '',
      cmdForm: {
        delta_kp: 0,
        delta_ti: 0,
        delta_td: 0,
        delta_k_ff: 0,
        confidence: 0.85,
        valid_time: 60,
        fan_power: null
      },
      // 下发风扇功率弹窗
      showFanModal: false,
      issuingFan: false,
      fanMsg: '',
      fanMsgType: '',
      fanForm: {
        power: 60,
        valid_time: 60,
        confidence: 0.95
      }
    }
  },
  async mounted() {
    await this.checkAuth()
    if (this.user) {
      await this.loadData()
      // 每 5 秒自动刷新
      this.refreshTimer = setInterval(() => this.loadData(), 5000)
    }
  },
  beforeUnmount() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
    }
    if (this.chartInstance) {
      this.chartInstance.destroy()
    }
  },
  methods: {
    async checkAuth() {
      try {
        const res = await axios.get('/api/me', { withCredentials: true })
        if (res.data.status === 'success') {
          this.user = res.data
        } else {
          this.$router.push('/login')
        }
      } catch {
        this.$router.push('/login')
      }
    },

    async loadData() {
      try {
        const [batchesRes, latestRes, pendingRes, deviceRes] = await Promise.all([
          axios.get('/api/frames/batches?limit=500'),
          axios.get('/api/frames/latest'),
          axios.get('/api/pending_command'),
          axios.get('/api/device/status')
        ])

        // 处理批次数据
        const batchData = batchesRes.data
        const newBatches = batchData.batches || []
        this.totalFrames = batchData.total_frames || 0
        this.totalBatches = batchData.total_batches || 0

        // 保留已展开的历史批次加载的帧数据
        if (newBatches.length > 0) {
          const loadedData = {}
          this.batches.forEach(b => {
            if (b.batch_index > 0 && b.loadedFrames) {
              loadedData[b.batch_index] = b.loadedFrames
            }
          })
          newBatches.forEach(b => {
            if (b.batch_index > 0 && loadedData[b.batch_index]) {
              b.loadedFrames = loadedData[b.batch_index]
              b.loading = false
            }
          })
          this.batches = newBatches

          // 保留已展开的批次状态（不重置 expandedBatches）
          // 首次加载时自动展开最新批次，之后保持用户手动状态
          if (!this._initialExpandDone) {
            this._initialExpandDone = true
            const hasAnyExpanded = Object.values(this.expandedBatches).some(v => v === true)
            if (!hasAnyExpanded) {
              this.expandedBatches[0] = true
            }
            // 首次加载时设置聚焦批次
            if (this.focusedBatch === null) {
              this.focusedBatch = 0
            }
          }
        } else {
          this.batches = []
        }

        this.latestFrame = latestRes.data || null
        this.pendingCmd = pendingRes.data || {}
        this.commandCount = this.pendingCmd.action_batch_id ? 1 : 0

        // 设备状态
        if (deviceRes.data) {
          this.deviceStatus = deviceRes.data.status || 'offline'
          this.deviceLabel = deviceRes.data.label || '未连接'
          this.lastSeenAgo = deviceRes.data.last_seen_ago ?? null
        }

        // 更新温度曲线
        this.updateChartData()
      } catch (err) {
        console.error('[Dashboard] 数据加载失败:', err)
      }
    },

    // 获取指定批次的帧数据（从已加载的数据中获取）
    getBatchFrames(batchIndex) {
      const batch = this.batches.find(b => b.batch_index === batchIndex)
      if (!batch) return []
      if (batchIndex === 0) {
        return batch.frames || []
      } else {
        return batch.loadedFrames || []
      }
    },

    // 更新温度曲线数据（从温度记录表获取 100ms 精度的数据）
    async updateChartData() {
      if (this.focusedBatch === null) return

      // 获取聚焦批次的起止时间
      const batch = this.batches.find(b => b.batch_index === this.focusedBatch)
      if (!batch) return

      const start = batch.start_time
      const end = batch.end_time || (Date.now() + 5000)

      try {
        const res = await axios.get('/api/temperatures/range', {
          params: { start, end, max_points: 1000 }
        })
        const records = res.data || []

        if (records.length === 0) {
          this.chartData = { labels: [], temperatures: [], targetTemps: [] }
          return
        }

        const labels = []
        const temperatures = []
        const targetTemps = []

        records.forEach(r => {
          const d = new Date(r.timestamp)
          labels.push(d.toLocaleTimeString('zh-CN'))
          temperatures.push(r.temperature)
          targetTemps.push(r.target_temperature !== null && r.target_temperature !== undefined ? r.target_temperature : null)
        })

        this.chartData = { labels, temperatures, targetTemps }

        // 重新绘制图表
        this.$nextTick(() => {
          this.renderChart()
        })
      } catch (err) {
        console.error('[Dashboard] 温度数据加载失败:', err)
      }
    },

    // 渲染温度曲线（使用 Canvas 2D API，无需额外依赖）
    renderChart() {
      const canvas = this.$refs.tempChartCanvas
      if (!canvas) return
      if (this.chartData.labels.length === 0) return

      const ctx = canvas.getContext('2d')
      const dpr = window.devicePixelRatio || 1
      const rect = canvas.parentElement.getBoundingClientRect()
      const width = rect.width - 20
      const height = 220

      canvas.width = width * dpr
      canvas.height = height * dpr
      canvas.style.width = width + 'px'
      canvas.style.height = height + 'px'
      ctx.scale(dpr, dpr)

      const padding = { top: 20, right: 20, bottom: 35, left: 50 }
      const chartW = width - padding.left - padding.right
      const chartH = height - padding.top - padding.bottom

      // 清空
      ctx.clearRect(0, 0, width, height)

      const temps = this.chartData.temperatures
      const targets = this.chartData.targetTemps

      // 计算 Y 轴范围
      let minY = Math.min(...temps)
      let maxY = Math.max(...temps)
      // 如果有目标温度，也纳入范围
      const validTargets = targets.filter(t => t !== null)
      if (validTargets.length > 0) {
        minY = Math.min(minY, ...validTargets)
        maxY = Math.max(maxY, ...validTargets)
      }
      const yPadding = Math.max((maxY - minY) * 0.15, 1)
      minY = Math.floor((minY - yPadding) * 10) / 10
      maxY = Math.ceil((maxY + yPadding) * 10) / 10
      if (minY === maxY) {
        minY -= 1
        maxY += 1
      }

      const xScale = (i) => padding.left + (i / (temps.length - 1 || 1)) * chartW
      const yScale = (v) => padding.top + chartH - ((v - minY) / (maxY - minY)) * chartH

      // 绘制网格
      ctx.strokeStyle = '#f0f0f0'
      ctx.lineWidth = 1
      const gridLines = 5
      for (let i = 0; i <= gridLines; i++) {
        const y = padding.top + (i / gridLines) * chartH
        ctx.beginPath()
        ctx.moveTo(padding.left, y)
        ctx.lineTo(width - padding.right, y)
        ctx.stroke()
      }

      // 绘制 Y 轴标签
      ctx.fillStyle = '#999'
      ctx.font = '11px sans-serif'
      ctx.textAlign = 'right'
      for (let i = 0; i <= gridLines; i++) {
        const val = maxY - (i / gridLines) * (maxY - minY)
        const y = padding.top + (i / gridLines) * chartH
        ctx.fillText(val.toFixed(1) + '℃', padding.left - 8, y + 4)
      }

      // 绘制 X 轴标签（显示首尾和中间几个）
      ctx.textAlign = 'center'
      const labelCount = Math.min(temps.length, 6)
      const step = Math.max(1, Math.floor(temps.length / labelCount))
      for (let i = 0; i < temps.length; i += step) {
        const x = xScale(i)
        ctx.fillText(this.chartData.labels[i], x, height - padding.bottom + 18)
      }
      // 最后一个标签
      if ((temps.length - 1) % step !== 0) {
        ctx.fillText(this.chartData.labels[temps.length - 1], xScale(temps.length - 1), height - padding.bottom + 18)
      }

      // 绘制温度曲线
      ctx.beginPath()
      ctx.strokeStyle = '#2196F3'
      ctx.lineWidth = 2
      temps.forEach((t, i) => {
        const x = xScale(i)
        const y = yScale(t)
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      })
      ctx.stroke()

      // 绘制温度数据点（极小圆点，避免密集时重叠）
      temps.forEach((t, i) => {
        const x = xScale(i)
        const y = yScale(t)
        ctx.beginPath()
        ctx.arc(x, y, 1, 0, Math.PI * 2)
        ctx.fillStyle = '#2196F3'
        ctx.fill()
      })

      // 绘制设定温度线（如果有）
      const firstTarget = targets.find(t => t !== null)
      if (firstTarget !== null && firstTarget !== undefined) {
        const targetY = yScale(firstTarget)
        ctx.beginPath()
        ctx.setLineDash([6, 4])
        ctx.strokeStyle = '#ff5722'
        ctx.lineWidth = 2
        ctx.moveTo(padding.left, targetY)
        ctx.lineTo(width - padding.right, targetY)
        ctx.stroke()
        ctx.setLineDash([])

        // 标注设定温度值
        ctx.fillStyle = '#ff5722'
        ctx.font = '12px sans-serif'
        ctx.textAlign = 'left'
        ctx.fillText('设定: ' + firstTarget.toFixed(1) + '℃', width - padding.right - 100, targetY - 6)
      }
    },

    toggleStatusCard() {
      this.showStatusCard = !this.showStatusCard
      if (this.showStatusCard) {
        this.showStatusPopover = false
      }
    },

    toggleBatch(batchIndex) {
      const isCurrentlyExpanded = this.expandedBatches[batchIndex]
      if (isCurrentlyExpanded) {
        delete this.expandedBatches[batchIndex]
      } else {
        this.expandedBatches[batchIndex] = true
      }

      // 设置聚焦批次
      this.focusedBatch = batchIndex

      // 如果是展开历史批次且尚未加载数据，则加载
      if (!isCurrentlyExpanded && batchIndex > 0) {
        const batch = this.batches.find(b => b.batch_index === batchIndex)
        if (batch && !batch.loadedFrames) {
          batch.loading = true
          axios.get(`/api/frames/batch/${batchIndex}?limit=500`).then(res => {
            batch.loadedFrames = res.data.frames || []
            // 加载完成后更新温度曲线
            this.updateChartData()
          }).catch(err => {
            console.error(`[Dashboard] 加载批次 ${batchIndex} 失败:`, err)
            batch.loadedFrames = []
          }).finally(() => {
            batch.loading = false
          })
        } else if (batch && batch.loadedFrames) {
          // 已有数据，直接更新曲线
          this.updateChartData()
        }
      } else {
        // 收起或展开最新批次，更新曲线
        this.updateChartData()
      }
    },

    async handleLogout() {
      try {
        await axios.post('/api/logout', {}, { withCredentials: true })
      } catch {
        // ignore
      }
      this.$router.push('/login')
    },

    formatTime(ts) {
      if (!ts) return '-'
      const d = new Date(ts)
      return d.toLocaleString('zh-CN')
    },

    statusText(flag) {
      const map = {
        0: '正常',
        1: '警告',
        2: '过载',
        3: '异常'
      }
      return map[flag] || `未知(${flag})`
    },

    async handleIssueCommand() {
      this.issuing = true
      this.modalMsg = ''
      this.modalMsgType = ''
      const payload = { ...this.cmdForm }
      if (payload.fan_power === null || payload.fan_power === '' || isNaN(payload.fan_power)) {
        delete payload.fan_power
      }
      try {
        const res = await axios.post('/api/issue_command', payload, {
          withCredentials: true
        })
        if (res.data.status === 'ok') {
          this.modalMsg = `✅ 指令已下发（批次 #${res.data.action_batch_id}，置信度 ${(res.data.confidence * 100).toFixed(0)}%）`
          this.modalMsgType = 'success'
          this.cmdForm = {
            delta_kp: 0,
            delta_ti: 0,
            delta_td: 0,
            delta_k_ff: 0,
            confidence: 0.85,
            valid_time: 60,
            fan_power: null
          }
          await this.loadData()
        } else {
          this.modalMsg = '❌ 下发失败：' + (res.data.message || '未知错误')
          this.modalMsgType = 'error'
        }
      } catch (err) {
        const msg = err.response?.data?.message || err.message || '网络错误'
        this.modalMsg = '❌ 下发失败：' + msg
        this.modalMsgType = 'error'
      } finally {
        this.issuing = false
      }
    },

    async handleIssueFanPower() {
      this.issuingFan = true
      this.fanMsg = ''
      this.fanMsgType = ''
      const power = this.fanForm.power
      if (power === null || power === '' || isNaN(power)) {
        this.fanMsg = '❌ 请填写有效的风扇功率值'
        this.fanMsgType = 'error'
        this.issuingFan = false
        return
      }
      if (power < 0 || power > 100) {
        this.fanMsg = '❌ 风扇功率必须在 0~100 之间'
        this.fanMsgType = 'error'
        this.issuingFan = false
        return
      }
      try {
        const res = await axios.post('/api/issue_command', {
          delta_kp: 0,
          delta_ti: 0,
          delta_td: 0,
          delta_k_ff: 0,
          confidence: this.fanForm.confidence,
          valid_time: this.fanForm.valid_time,
          fan_power: power
        }, {
          withCredentials: true
        })
        if (res.data.status === 'ok') {
          this.fanMsg = `✅ 风扇功率已设定为 ${power}%（批次 #${res.data.action_batch_id}）`
          this.fanMsgType = 'success'
          await this.loadData()
        } else {
          this.fanMsg = '❌ 下发失败：' + (res.data.message || '未知错误')
          this.fanMsgType = 'error'
        }
      } catch (err) {
        const msg = err.response?.data?.message || err.message || '网络错误'
        this.fanMsg = '❌ 下发失败：' + msg
        this.fanMsgType = 'error'
      } finally {
        this.issuingFan = false
      }
    }
  }
}
</script>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: #f0f2f5;
}

/* 顶部导航 */
.header {
  background: #fff;
  padding: 0 24px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left h1 {
  font-size: 18px;
  color: #333;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.user-info {
  font-size: 14px;
  color: #666;
}

.btn-logout {
  padding: 6px 16px;
  background: #fff;
  color: #ff4d4f;
  border: 1px solid #ff4d4f;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-logout:hover {
  background: #fff1f0;
}

/* 系统状态栏 */
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  position: relative;
  cursor: pointer;
}

.status-bar-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #666;
  padding: 4px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.status-bar-item:hover {
  background: #f5f5f5;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.dot-running {
  background: #52c41a;
}

.dot-stopped {
  background: #faad14;
}

.dot-offline {
  background: #d9d9d9;
}

.status-label {
  font-size: 12px;
  font-weight: 500;
}

.status-ok {
  color: #52c41a;
}

.device-running {
  color: #52c41a;
}

.device-stopped {
  color: #faad14;
}

.device-offline {
  color: #d9d9d9;
}

/* 状态弹出卡片 */
.status-popover {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 8px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  width: 240px;
  z-index: 200;
  overflow: hidden;
}

.status-popover-header {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}

.status-popover-body {
  padding: 8px 14px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-size: 13px;
}

.status-key {
  color: #999;
}

.status-val {
  font-weight: 500;
}

/* 主要内容 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px 24px;
}

/* 概览卡片网格 - 第一行：最新特征帧、待处理指令、温度曲线 */
.overview {
  display: grid;
  grid-template-columns: 1fr 1fr 2fr;
  gap: 16px;
  margin-bottom: 16px;
}

/* 下发指令行 - 第二行：PID指令、风扇功率 */
.cmd-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.card {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.card h3 {
  font-size: 14px;
  color: #999;
  margin-bottom: 12px;
  font-weight: 500;
}

.card-content {
  font-size: 13px;
  line-height: 1.8;
  color: #333;
}

.card-content.empty {
  color: #bbb;
  font-size: 14px;
  padding: 20px 0;
  text-align: center;
}

/* 温度曲线卡片 */

.chart-container {
  width: 100%;
}

.chart-info {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 8px;
  font-size: 12px;
  color: #666;
}

.chart-legend {
  display: flex;
  align-items: center;
  gap: 6px;
}

.legend-line {
  width: 20px;
  height: 3px;
  border-radius: 2px;
  display: inline-block;
}

.legend-temp {
  background: #2196F3;
}

.legend-target {
  background: #ff5722;
}

.chart-batch-label {
  margin-left: auto;
  font-weight: 500;
  color: #333;
}

.chart-hint {
  font-size: 12px;
  color: #bbb;
  margin-top: 4px;
}

/* 下发指令卡片 - 不同背景配色 */
.cmd-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

.cmd-card h3 {
  color: rgba(255, 255, 255, 0.85);
}

.cmd-card .cmd-desc {
  color: rgba(255, 255, 255, 0.7);
}

.fan-card {
  background: linear-gradient(135deg, #18b44c 0%, #19c5a5 100%);
  color: #fff;
}

.fan-card h3 {
  color: rgba(255, 255, 255, 0.85);
}

.fan-card .cmd-desc {
  color: rgba(255, 255, 255, 0.7);
}

.cmd-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cmd-desc {
  font-size: 12px;
  line-height: 1.5;
}

.btn-issue {
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-issue:hover {
  background: rgba(255, 255, 255, 0.4);
}

.btn-fan {
  background: rgba(255, 255, 255, 0.25);
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.btn-fan:hover {
  background: rgba(255, 255, 255, 0.4);
}

/* 数据区域 */
.data-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-header h2 {
  font-size: 16px;
  color: #333;
}

.badge {
  font-size: 12px;
  color: #999;
  background: #f5f5f5;
  padding: 4px 10px;
  border-radius: 12px;
}

/* 批次列表 */
.batch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.batch-card {
  border: 1px solid #f0f0f0;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.batch-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.batch-active {
  border-color: #b7eb8f;
  background: #f6ffed;
}

.batch-focused {
  box-shadow: 0 0 0 2px #667eea40;
}

.batch-header {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  gap: 16px;
  user-select: none;
}

.batch-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.batch-label {
  font-size: 13px;
  font-weight: 600;
}

.batch-label-0 {
  color: #52c41a;
}

.batch-label-1 {
  color: #faad14;
}

.batch-label-2 {
  color: #ff7a45;
}

.batch-label-3 {
  color: #ff4d4f;
}

.batch-time {
  font-size: 12px;
  color: #999;
}

.batch-stats {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #666;
}

.batch-stat {
  white-space: nowrap;
}

.batch-toggle {
  font-size: 12px;
  color: #bbb;
  width: 20px;
  text-align: center;
}

/* 批次详情 */
.batch-detail {
  border-top: 1px solid #f0f0f0;
  padding: 12px 16px;
}

.batch-loading {
  text-align: center;
  padding: 20px;
  color: #999;
  font-size: 13px;
}

/* 表格 */
.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th {
  background: #fafafa;
  padding: 8px 10px;
  text-align: left;
  font-weight: 500;
  color: #666;
  white-space: nowrap;
  border-bottom: 1px solid #f0f0f0;
}

td {
  padding: 6px 10px;
  border-bottom: 1px solid #f5f5f5;
  color: #333;
  white-space: nowrap;
}

tr:hover td {
  background: #fafafa;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.status-0 {
  background: #f6ffed;
  color: #52c41a;
}

.status-1 {
  background: #fffbe6;
  color: #faad14;
}

.status-2 {
  background: #fff2e8;
  color: #ff7a45;
}

.status-3 {
  background: #fff1f0;
  color: #ff4d4f;
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #bbb;
  font-size: 14px;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #fff;
  border-radius: 12px;
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

.modal-sm {
  width: 400px;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
}

.modal-header h3 {
  font-size: 16px;
  color: #333;
  margin: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 22px;
  color: #999;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.modal-close:hover {
  color: #333;
}

.modal-body {
  padding: 20px;
}

.form-group {
  margin-bottom: 14px;
}

.form-group label {
  display: block;
  font-size: 13px;
  color: #666;
  margin-bottom: 6px;
  font-weight: 500;
}

.form-group input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  color: #333;
  outline: none;
  transition: border-color 0.3s;
  box-sizing: border-box;
}

.form-group input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.15);
}

.form-divider {
  height: 1px;
  background: #f0f0f0;
  margin: 16px 0;
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 20px;
  border-top: 1px solid #f0f0f0;
}

.modal-msg {
  flex: 1;
  font-size: 13px;
  text-align: left;
}

.modal-msg.success {
  color: #52c41a;
}

.modal-msg.error {
  color: #ff4d4f;
}

.btn-cancel {
  padding: 8px 20px;
  background: #fff;
  color: #666;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-cancel:hover {
  color: #333;
  border-color: #bbb;
}

.btn-confirm {
  padding: 8px 20px;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-confirm:hover {
  background: #5a6fd6;
}

.btn-confirm:disabled {
  background: #a0aeea;
  cursor: not-allowed;
}

.btn-fan-confirm {
  background: #52c41a;
}

.btn-fan-confirm:hover {
  background: #45a818;
}

.btn-fan-confirm:disabled {
  background: #95de64;
}
</style>
