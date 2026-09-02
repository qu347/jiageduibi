<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiGet } from '../api/client'
import type { PlatformStatus } from '../types/offers'

const statuses = ref<PlatformStatus[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    statuses.value = (await apiGet<{ items: PlatformStatus[] }>('/api/platforms/status')).items
  } finally {
    loading.value = false
  }
})

const names: Record<string, string> = { jd: '京东', taobao: '淘宝', pdd: '拼多多' }
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
  </main>
</template>
