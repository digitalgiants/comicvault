import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  return {
    plugins: [react()],
    server: {
      allowedHosts: env.VITE_ALLOWED_HOST ? [env.VITE_ALLOWED_HOST] : [],
      proxy: {
        '/api': {
          target: 'http://backend:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
