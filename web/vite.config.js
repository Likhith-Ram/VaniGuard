import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  build: {
    // Minify with esbuild (default) — fast and effective
    minify: 'esbuild',

    // Raise the inline asset limit so very small SVGs get inlined as data URIs
    assetsInlineLimit: 4096, // 4 KB

    // Enable CSS code-splitting
    cssCodeSplit: true,

    rollupOptions: {
      output: {
        // Split vendor chunks for better caching
        manualChunks: {
          react: ['react', 'react-dom'],
          router: ['react-router-dom'],
          chartjs: ['chart.js', 'react-chartjs-2'],
        },
      },
    },
  },

  // Enable Brotli / gzip compression reporting in build output
  // (actual Brotli serving is handled by the server/CDN)
});
