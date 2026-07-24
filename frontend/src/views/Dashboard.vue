<template>
  <div class="dashboard">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <h1>AIPID 温控系统</h1>
      </div>
      <div class="header-right">
        <span class="user-info" v-if="user">
          {{ user.username }} ({{ user.role }})
        </span>
        <button class="btn-logout" @click="handleLogout">退出登录</button>
      </div>
    </header>

    <!-- 主要内容 -->
    <main class="main-content">
      <!-- 概览卡片 -->
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

        <div class="card">
          <h3>系统状态</h3>
          <div class="card-content">
            <p>后端: <span class="status-ok">● 运行中</span></p>
            <p>数据库: <span class="status-ok">● 已连接</span></p>
            <p>恒温箱: <span :class="'device-status device-' + (deviceStatus || 'offline')">● {{ deviceLabel || '未连接' }}</span></p>
            <p v-if="lastSeenAgo !== null">最后通信: {{ lastSeenAgo }} 秒前</p>
            <p>特征帧总数: {{ totalFrames }}</p>
            <p>运行批次: {{ totalBatches }}</p>
            <p>已下发指令: {{ commandCount }}</p>
          </div>
        </div>

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
            :class="{ 'batch-active': batch.batch_index === 0 }"
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
              <div v-if="batch.batch_index === 0 && batch.frames && batch.frames.length > 0">
                <div class="table-wrapper">
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
      // 批次展开状态
      expandedBatches: {},
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
      // 每 10 秒自动刷新
      this.refreshTimer = setInterval(() => this.loadData(), 10000)
    }
  },
  beforeUnmount() {
    if (this.refreshTimer) {
      clearInterval(this.refreshTimer)
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
          axios.get('/api/frames/batches?limit=100'),
          axios.get('/api/frames/latest'),
          axios.get('/api/pending_command'),
          axios.get('/api/device/status')
        ])

        // 处理批次数据
        const batchData = batchesRes.data
        this.batches = batchData.batches || []
        this.totalFrames = batchData.total_frames || 0
        this.totalBatches = batchData.total_batches || 0

        // 为每个历史批次添加 loadedFrames 和 loading 状态
        this.batches.forEach(b => {
          if (b.batch_index > 0) {
            if (!('loadedFrames' in b)) {
              this.$set(b, 'loadedFrames', null)
            }
            if (!('loading' in b)) {
              this.$set(b, 'loading', false)
            }
          }
        })

        // 默认展开最新批次
        if (this.batches.length > 0) {
          this.$set(this.expandedBatches, 0, true)
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
      } catch (err) {
        console.error('[Dashboard] 数据加载失败:', err)
      }
    },

    async toggleBatch(batchIndex) {
      const isExpanded = this.expandedBatches[batchIndex]
      this.$set(this.expandedBatches, batchIndex, !isExpanded)

      // 如果是展开历史批次且尚未加载数据，则加载
      if (!isExpanded && batchIndex > 0) {
        const batch = this.batches.find(b => b.batch_index === batchIndex)
        if (batch && !batch.loadedFrames) {
          batch.loading = true
          try {
            const res = await axios.get(`/api/frames/batch/${batchIndex}?limit=500`)
            batch.loadedFrames = res.data.frames || []
          } catch (err) {
            console.error(`[Dashboard] 加载批次 ${batchIndex} 失败:`, err)
            batch.loadedFrames = []
          } finally {
            batch.loading = false
          }
        }
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
      // 处理 fan_power：NaN 转为 null（沿用当前）
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
          // 重置表单
          this.cmdForm = {
            delta_kp: 0,
            delta_ti: 0,
            delta_td: 0,
            delta_k_ff: 0,
            confidence: 0.85,
            valid_time: 60,
            fan_power: null
          }
          // 刷新数据
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
          // 刷新数据
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
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s;
}

.btn-logout:hover {
  background: #ff4d4f;
  color: #fff;
}

/* 主要内容 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 24px;
}

/* 概览卡片 */
.overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.card h3 {
  font-size: 15px;
  color: #666;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f0f0f0;
}

.card-content p {
  font-size: 14px;
  color: #333;
  margin-bottom: 6px;
  line-height: 1.6;
}

.card-content.empty {
  color: #999;
  text-align: center;
  padding: 20px 0;
}

.status-ok {
  color: #52c41a;
}

/* 设备状态 */
.device-status {
  font-weight: 600;
}

.device-running {
  color: #52c41a;
}

.device-stopped {
  color: #fa8c16;
}

.device-offline {
  color: #999;
}

/* 批次列表 */
.data-section {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
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
  background: #667eea;
  color: #fff;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
}

.batch-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.batch-card {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.3s;
}

.batch-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.batch-active {
  border-color: #52c41a;
  background: #f6ffed;
}

.batch-header {
  display: flex;
  align-items: center;
  padding: 14px 16px;
  cursor: pointer;
  gap: 16px;
  user-select: none;
}

.batch-header:hover {
  background: rgba(0, 0, 0, 0.02);
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

.batch-label-0 { color: #52c41a; }
.batch-label-1 { color: #fa8c16; }
.batch-label-2 { color: #ff4d4f; }
.batch-label-3 { color: #999; }

.batch-time {
  font-size: 12px;
  color: #999;
}

.batch-stats {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #666;
}

.batch-stat {
  white-space: nowrap;
}

.batch-toggle {
  font-size: 12px;
  color: #999;
  width: 20px;
  text-align: center;
}

.batch-detail {
  border-top: 1px solid #e8e8e8;
  padding: 12px 16px;
  background: #fafafa;
}

.batch-loading {
  text-align: center;
  padding: 20px;
  color: #999;
  font-size: 13px;
}

/* 数据表格 */
.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead th {
  background: #f0f0f0;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  color: #666;
  border-bottom: 2px solid #e0e0e0;
  white-space: nowrap;
}

tbody td {
  padding: 8px 10px;
  border-bottom: 1px solid #f0f0f0;
  color: #333;
  white-space: nowrap;
}

tbody tr:hover {
  background: #f5f5f5;
}

.status-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.status-0 { background: #f6ffed; color: #52c41a; }
.status-1 { background: #fff7e6; color: #fa8c16; }
.status-2 { background: #fff1f0; color: #ff4d4f; }
.status-3 { background: #f0f0f0; color: #999; }

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #999;
  font-size: 14px;
}

/* 下发指令卡片 */
.cmd-card {
  border: 1px dashed #667eea;
  background: #f8f9ff;
}

.cmd-desc {
  font-size: 13px !important;
  color: #888 !important;
  margin-bottom: 12px !important;
}

.btn-issue {
  width: 100%;
  padding: 10px 0;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-issue:hover {
  background: #5a6fd6;
}

/* 下发风扇功率卡片 */
.fan-card {
  border: 1px dashed #52c41a;
  background: #f6ffed;
}

.btn-fan {
  background: #52c41a;
}

.btn-fan:hover {
  background: #45a818;
}

.btn-fan-confirm {
  background: #52c41a;
}

.btn-fan-confirm:hover {
  background: #45a818;
}

.btn-fan-confirm:disabled {
  background: #95d475;
  cursor: not-allowed;
}

/* 弹窗遮罩 */
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
  border-radius: 10px;
  width: 480px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.15);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 24px;
  border-bottom: 1px solid #f0f0f0;
}

.modal-header h3 {
  font-size: 16px;
  color: #333;
  margin: 0;
  border: none;
  padding: 0;
}

.modal-close {
  background: none;
  border: none;
  font-size: 24px;
  color: #999;
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
}

.modal-close:hover {
  color: #333;
}

.modal-body {
  padding: 20px 24px;
}

.form-group {
  margin-bottom: 16px;
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
  padding: 16px 24px;
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
</style>
