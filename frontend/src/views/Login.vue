<template>
  <div class="login-container">
    <div class="login-card">
      <h2>AIPID 温控系统</h2>
      <p class="subtitle">请登录以访问仪表板</p>

      <form @submit.prevent="handleLogin">
        <div class="input-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            required
          />
        </div>

        <div class="input-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            required
          />
        </div>

        <button type="submit" :disabled="loading">
          {{ loading ? '登录中...' : '登 录' }}
        </button>

        <div v-if="errorMsg" class="error-message">{{ errorMsg }}</div>
      </form>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  data() {
    return {
      username: '',
      password: '',
      errorMsg: '',
      loading: false
    }
  },
  methods: {
    async handleLogin() {
      this.errorMsg = ''
      this.loading = true

      try {
        const res = await axios.post('/api/login', {
          username: this.username,
          password: this.password
        }, { withCredentials: true })

        if (res.data.status === 'success') {
          this.$router.push('/dashboard')
        } else {
          this.errorMsg = res.data.message || '登录失败'
        }
      } catch (err) {
        if (err.response && err.response.data && err.response.data.message) {
          this.errorMsg = err.response.data.message
        } else {
          this.errorMsg = '无法连接到服务器，请检查网络或联系管理员'
        }
        console.error('[Login Error]', err)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.login-card {
  background: white;
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}

h2 {
  text-align: center;
  color: #333;
  margin-bottom: 8px;
  font-size: 24px;
}

.subtitle {
  text-align: center;
  color: #888;
  margin-bottom: 30px;
  font-size: 14px;
}

.input-group {
  margin-bottom: 20px;
}

label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  font-size: 14px;
  color: #555;
}

input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.3s;
  outline: none;
}

input:focus {
  border-color: #667eea;
  box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2);
}

button {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.3s;
}

button:hover:not(:disabled) {
  opacity: 0.9;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error-message {
  color: #ff4d4f;
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
  padding: 8px;
  background: #fff2f0;
  border-radius: 4px;
}
</style>
