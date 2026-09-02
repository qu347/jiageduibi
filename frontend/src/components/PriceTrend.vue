<script setup lang="ts">
import { computed } from 'vue'

import type { HistoryPoint } from '../types/offers'

const props = defineProps<{ points: HistoryPoint[] }>()
const pricedPoints = computed(() => props.points.filter(
  (point): point is HistoryPoint & { comparable_price_cents: number } => point.comparable_price_cents !== null,
))
const minimum = computed(() => pricedPoints.value.length
  ? Math.min(...pricedPoints.value.map((point) => point.comparable_price_cents))
  : null)
const polyline = computed(() => {
  if (!pricedPoints.value.length) return ''
  const values = pricedPoints.value.map((point) => point.comparable_price_cents)
  const low = Math.min(...values)
  const high = Math.max(...values)
  const spread = Math.max(1, high - low)
  return values.map((value, index) => {
    const x = values.length === 1 ? 50 : 6 + (index / (values.length - 1)) * 88
    const y = 82 - ((value - low) / spread) * 64
    return `${x},${y}`
  }).join(' ')
})

function formatMoney(value: number | null): string {
  return value === null ? '—' : `¥${(value / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
}
</script>

<template>
  <section class="trend-card">
    <div v-if="pricedPoints.length">
      <div class="trend-summary">
        <div><span>历史最低价</span><strong>{{ formatMoney(minimum) }}</strong></div>
        <div><span>记录数</span><strong>{{ pricedPoints.length }}</strong></div>
      </div>
      <svg viewBox="0 0 100 100" role="img" aria-label="价格变化趋势">
        <line x1="6" y1="82" x2="94" y2="82" class="axis" />
        <polyline :points="polyline" fill="none" class="trend-line" />
      </svg>
      <div class="trend-labels">
        <span>首次 {{ formatMoney(pricedPoints[0]?.comparable_price_cents ?? null) }}</span>
        <span>最新 {{ formatMoney(pricedPoints.at(-1)?.comparable_price_cents ?? null) }}</span>
      </div>
    </div>
    <div v-else class="trend-empty">暂无历史价格</div>
  </section>
</template>
