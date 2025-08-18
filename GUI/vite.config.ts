import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tsconfigPaths from 'vite-tsconfig-paths';
import svgr from 'vite-plugin-svgr';
import path from 'path';
import { removeHiddenMenuItems } from './vitePlugin';

// https://vitejs.dev/config/
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
    headers: {
      ...(process.env.REACT_APP_CSP && {
        'Content-Security-Policy': process.env.REACT_APP_CSP,
      }),
    },
    host: '0.0.0.0',
    port: 3001,
    // Use the environment variable approach for allowed hosts
    ...(process.env.VITE_ALLOWED_HOSTS && {
      allowedHosts: process.env.VITE_ALLOWED_HOSTS.split(',')
    }),
    // Fallback static configuration
    ...(!process.env.VITE_ALLOWED_HOSTS && {
      allowedHosts: [
        'global-classifier-dev.rootcode.software',
        'localhost',
        '127.0.0.1',
        '.rootcode.software'
      ]
    }),
  },
  resolve: {
    alias: {
      '~@fontsource': path.resolve(__dirname, 'node_modules/@fontsource'),
      '@': `${path.resolve(__dirname, './src')}`,
    },
  },
});
