import { resolve } from 'node:path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  root: resolve(import.meta.dirname, 'src'),
  publicDir: resolve(import.meta.dirname, 'public'),
  build: {
    outDir: resolve(import.meta.dirname, 'dist'),
    emptyOutDir: true,
    rollupOptions: {
      input: {
        background: resolve(import.meta.dirname, 'src/background/index.ts'),
        capture: resolve(import.meta.dirname, 'src/content/capture.ts'),
        popup: resolve(import.meta.dirname, 'src/popup/index.html'),
      },
      output: {
        entryFileNames: (chunk) => {
          if (chunk.name === 'background') return 'background.js'
          if (chunk.name === 'capture') return 'capture.js'
          return 'assets/[name]-[hash].js'
        },
      },
    },
  },
  test: { root: import.meta.dirname, environment: 'jsdom' },
})
