import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 生产环境构建时，API 请求通过 Nginx 反向代理转发
// 开发环境通过 proxy 配置转发到 Flask 后端
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',  // 开发时 Flask 地址
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  }
})
