import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: Number(env.VITE_DEV_PORT) || 5173,
      // default 0.0.0.0 = listen on all interfaces so it's reachable on the network
      host: env.VITE_DEV_HOST || '0.0.0.0',
    },
  }
})
