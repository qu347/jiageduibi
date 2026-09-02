<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { apiGet } from '../api/client'
import PriceTrend from '../components/PriceTrend.vue'
import type { HistoryPoint, HistoryResponse } from '../types/offers'

const points = ref<HistoryPoint[]>([])
const loading = ref(true)
const message = ref('')

onMounted(async () => {
  const variantId = localStorage.getItem('lastVariantId')
  if (!variantId) {
    message.value = '请先在比价工作台完成一次比价。'
    loading.value = false
    return
  }
  try {
    points.value = (await apiGet<HistoryResponse>(`/api/price-history?variant_id=${variantId}`)).points
  } catch (error) {
    message.value = error instanceof Error ? error.message : '历史价格读取失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="simple-page history-page">
    <span class="eyebrow">价格档案</span>
    <h1>历史价格</h1>
    <p>只记录默认可比价；预计补贴不会被当作确认价格。</p>
    <p v-if="loading" class="page-message">正在读取本地价格快照…</p>
    <p v-else-if="message" class="page-message">{{ message }}</p>
    <PriceTrend v-else :points="points" />
  </main>
</template>
