import { networkInterfaces } from 'node:os';
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
  // The dev server runs on the host, so it can tell the page which LAN addresses a TV or phone can reach.
  // Built bundles run inside Docker, where the host's addresses are unknown, so they get none.
  const lanAddresses = command === 'serve'
    ? Object.entries(networkInterfaces()).flatMap(([name, entries]) => (entries ?? [])
      .filter((entry) => entry.family === 'IPv4' && !entry.internal && !/^vEthernet|^docker|^br-|^veth/i.test(name))
      .map((entry) => ({ name, address: entry.address })))
    : [];
  return {
    define: { __LAN_ADDRESSES__: JSON.stringify(lanAddresses) },
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
      allowedHosts: true,
      watch: { usePolling: env.VITE_USE_POLLING === '1' },
      proxy: { '/api': apiProxy, '/media': apiProxy },
    },
  };
});
