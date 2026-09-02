<script setup lang="ts">
import type { OfferView } from '../types/offers'

defineProps<{ offer: OfferView }>()

function formatMoney(value: number | null): string {
  return value === null ? '无法确认' : `¥${(value / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2 })}`
}
</script>

<template>
  <details class="offer-details">
    <summary>查看口径与来源</summary>
    <dl>
      <div><dt>商品标题</dt><dd>{{ offer.title }}</dd></div>
      <div><dt>店铺</dt><dd>{{ offer.shop_name }}</dd></div>
      <div><dt>确认后价格</dt><dd>{{ formatMoney(offer.confirmed_final_price_cents) }}</dd></div>
      <div><dt>匹配置信度</dt><dd>{{ offer.match_confidence }} / 100</dd></div>
      <div><dt>采集来源</dt><dd>{{ offer.source_type === 'fixture' ? '本地测试夹具' : offer.source_type }}</dd></div>
    </dl>
    <a :href="offer.product_url" target="_blank" rel="noreferrer">打开商品来源</a>
  </details>
</template>
