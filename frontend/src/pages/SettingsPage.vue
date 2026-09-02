<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiGet, apiPost } from '../api/client'
import type { PlatformStatus } from '../types/offers'

const statuses = ref<PlatformStatus[]>([])
const loading = ref(true)
const pairingCode = ref('')

onMounted(async () => {
  try {
    statuses.value = (await apiGet<{ items: PlatformStatus[] }>('/api/platforms/status')).items
  } finally {
    loading.value = false
  }
})

const names: Record<string, string> = { jd: '京东', taobao: '淘宝', pdd: '拼多多' }

async function generatePairingCode() {
  pairingCode.value = (await apiPost<{ code: string }>('/api/extension/pairing-code', {})).code
}
</script>

<template>
  <main class="simple-page settings-page">
    <span class="eyebrow">本地配置</span>
    <h1>设置与平台状态</h1>
    <p>夹具验证只说明离线解析流程通过，不代表真实网站已完成验收。</p>
    <section class="status-grid" aria-label="平台适配状态">
      <p v-if="loading">正在读取状态…</p>
      <article v-for="item in statuses" :key="item.platform">
        <strong>{{ names[item.platform] ?? item.platform }}</strong>
        <span class="fixture-pass">夹具：{{ item.fixture_status === 'passing' ? '通过' : '未通过' }}</span>
        <span>真实网站：尚未验证</span>
      </article>
    </section>
    <section class="pairing-card">
      <div><strong>浏览器扩展配对</strong><p>配对码只能使用一次，有效内容不会写入日志。</p></div>
      <code v-if="pairingCode">{{ pairingCode }}</code>
      <button type="button" @click="generatePairingCode">{{ pairingCode ? '重新生成' : '生成 6 位配对码' }}</button>
    </section>
  </main>
</template>
