import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: { baseURL: 'http://127.0.0.1:8765', channel: 'msedge' },
  webServer: {
    command: 'powershell -NoProfile -ExecutionPolicy Bypass -File ..\\scripts\\demo.ps1 -NoOpen',
    url: 'http://127.0.0.1:8765/api/health',
    reuseExistingServer: false,
    timeout: 120_000,
  },
})
