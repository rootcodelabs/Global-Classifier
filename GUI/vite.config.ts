import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import svgr from 'vite-plugin-svgr';
import path from 'path';
import { removeHiddenMenuItems } from './vitePlugin';

export default defineConfig(({ mode }) => ({
  envPrefix: 'REACT_APP_',
  plugins: [
    react(),
    tsconfigPaths(),
    svgr(),
    {
      name: 'removeHiddenMenuItemsPlugin',
      transform: (str, id) => {
        if(!id.endsWith('/menu-structure.json'))
          return str;
        return removeHiddenMenuItems(str);
      },
    },
  ],
  base: '/',
  build: {
    outDir: './build',
    target: 'es2015',
    emptyOutDir: true,
    sourcemap: mode === 'development',
  },
  server: {
    host: '0.0.0.0',
    port: 3001,
    strictPort: false,
    allowedHosts: [
      'global-classifier-dev.rootcode.software',
      'localhost',
      '127.0.0.1',
      '.rootcode.software',
    ],
    headers: {
      ...(process.env.REACT_APP_CSP && {
        'Content-Security-Policy': process.env.REACT_APP_CSP,
      }),
    },
    // Disable HMR in production
    hmr: mode === 'development' ? {
      port: 3001,
      host: 'localhost',
    } : false,
  },
  resolve: {
    alias: {
      '~@fontsource': path.resolve(__dirname, 'node_modules/@fontsource'),
      '@': `${path.resolve(__dirname, './src')}`,
    },
  },
}));