import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', 'CLOUDSERVE_')
  const apiPort = Number(env.CLOUDSERVE_API_PORT || 8001)
  return {
    base: './',
    plugins: [react()],
    server: { proxy: { '/api': { target: `http://127.0.0.1:${apiPort}`, rewrite: path => path.replace(/^\/api/, '') } } },
  }
})
