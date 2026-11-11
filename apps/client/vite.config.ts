import { fileURLToPath } from 'node:url';
import legacy from '@vitejs/plugin-legacy';
import react from '@vitejs/plugin-react';
import { defineConfig, loadEnv } from 'vite';

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, '.', '');
  const apiProxy = {
    target: env.VITE_API_TARGET || 'http://127.0.0.1:8001',
    changeOrigin: false,
    ws: true,
  };
  return {
    plugins: [
      react(),
      legacy({
        targets: ['Chrome >= 53', 'Safari >= 10'],
        modernPolyfills: true,
        additionalLegacyPolyfills: ['regenerator-runtime/runtime'],
      }),
    ],
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
    base: command === 'build' ? '/static/' : '/',
    server: {
      host: '0.0.0.0',
      port: 5173,
      strictPort: true,
      watch: { usePolling: env.VITE_USE_POLLING === '1' },
      proxy: { '/api': apiProxy, '/media': apiProxy },
    },
  };
});
