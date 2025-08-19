import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import svgr from 'vite-plugin-svgr';
import path from 'path';
import { removeHiddenMenuItems } from './vitePlugin';

export default defineConfig({
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
  base: 'global-classifier',
  build: {
    outDir: './build',
    target: 'es2015',
    emptyOutDir: true,
  },
  server: {
    host: '0.0.0.0', // Accept connections from any host
    port: 3001,
    strictPort: false,
    headers: {
      ...(process.env.REACT_APP_CSP && {
        'Content-Security-Policy': process.env.REACT_APP_CSP,
      }),
    },
    // Ensure proper proxying
    proxy: {
      '/ruuter-public': {
        target: 'http://ruuter-public:8086',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ruuter-public/, ''),
      },
      '/ruuter-private': {
        target: 'http://ruuter-private:8088',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ruuter-private/, ''),
      },
    },
  },
  resolve: {
    alias: {
      '~@fontsource': path.resolve(__dirname, 'node_modules/@fontsource'),
      '@': `${path.resolve(__dirname, './src')}`,
    },
  },
});