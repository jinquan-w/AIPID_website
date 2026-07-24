<template>
  <div class="register-container">
    <div class="register-card">
      <h2>AIPID 温控系统</h2>
      <p class="subtitle">创建新账号</p>

      <form @submit.prevent="handleRegister">
        <div class="input-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名（2-50个字符）"
            required
          />
        </div>

        <div class="input-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码（至少6位）"
            required
          />
        </div>

        <div class="input-group">
          <label for="confirmPassword">确认密码</label>
          <input
            id="confirmPassword"
            v-model="confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            required
          />
        </div>

        <button type="submit" :disabled="loading">
          {{ loading ? '注册中...' : '注 册' }}
        </button>

        <div v-if="errorMsg" class="error-message">{{ errorMsg }}</div>
        <div v-if="successMsg" class="success-message">{{ successMsg }}</div>
      </form>

      <div class="login-link">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
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
      confirmPassword: '',
      errorMsg: '',
      successMsg: '',
      loading: false
    }
  },
  methods: {
    async handleRegister() {
      this.errorMsg = ''
      this.successMsg = ''
      this.loading = true

      if (this.password !== this.confirmPassword) {
        this.errorMsg = '两次输入的密码不一致'
        this.loading = false
        return
      }

      if (this.password.length < 6) {
        this.errorMsg = '密码长度不能少于 6 位'
        this.loading = false
        return
      }

      try {
        const res = await axios.post('/api/register', {
          username: this.username,
          password: this.password
        })

        if (res.data.status === 'success') {
          this.successMsg = res.data.message || '注册成功！即将跳转到登录页...'
          setTimeout(() => {
            this.$router.push('/login')
          }, 1500)
        } else {
          this.errorMsg = res.data.message || '注册失败'
        }
      } catch (err) {
        if (err.response && err.response.data && err.response.data.message) {
          this.errorMsg = err.response.data.message
        } else {
          this.errorMsg = '无法连接到服务器，请检查网络或联系管理员'
        }
        console.error('[Register Error]', err)
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.register-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.register-card {
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
  box-sizing: border-box;
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

.success-message {
  color: #52c41a;
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
  padding: 8px;
  background: #f6ffed;
  border-radius: 4px;
}

.login-link {
  text-align: center;
  margin-top: 20px;
  font-size: 14px;
  color: #888;
}

.login-link a {
  color: #667eea;
  text-decoration: none;
  font-weight: 600;
}

.login-link a:hover {
  text-decoration: underline;
}
</style>
