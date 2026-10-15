import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 开发期把 /api/* 代理到本地后端，前端只认相对路径，绕开跨域。
    // 后端路由在根路径（/chat、/plan...），所以 rewrite 把 /api 前缀去掉。
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
