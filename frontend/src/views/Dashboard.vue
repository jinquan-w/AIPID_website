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
            <p>特征帧总数: {{ frameCount }}</p>
            <p>已下发指令: {{ commandCount }}</p>
          </div>
        </div>
      </section>

      <!-- 特征帧列表 -->
      <section class="data-section">
        <div class="section-header">
          <h2>特征帧记录</h2>
          <span class="badge">最近 {{ frames.length }} 条</span>
        </div>

        <div class="table-wrapper">
          <table v-if="frames.length > 0">
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
              <tr v-for="frame in frames" :key="frame.id">
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
          <div v-else class="empty-state">
            暂无特征帧数据，请等待边缘侧设备上传
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  data() {
    return {
      user: null,
      latestFrame: null,
      frames: [],
      pendingCmd: {},
      frameCount: 0,
      commandCount: 0,
      refreshTimer: null
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
        const [framesRes, latestRes, pendingRes] = await Promise.all([
          axios.get('/api/frames?limit=50'),
          axios.get('/api/frames/latest'),
          axios.get('/api/pending_command')
        ])

        this.frames = framesRes.data || []
        this.latestFrame = latestRes.data || null
        this.pendingCmd = pendingRes.data || {}
        this.frameCount = this.frames.length
        this.commandCount = this.pendingCmd.action_batch_id ? 1 : 0
      } catch (err) {
        console.error('[Dashboard] 数据加载失败:', err)
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

/* 数据表格 */
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

.table-wrapper {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

thead th {
  background: #fafafa;
  padding: 10px 12px;
  text-align: left;
  font-weight: 600;
  color: #666;
  border-bottom: 2px solid #f0f0f0;
  white-space: nowrap;
}

tbody td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  color: #333;
  white-space: nowrap;
}

tbody tr:hover {
  background: #fafafa;
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
</style>
