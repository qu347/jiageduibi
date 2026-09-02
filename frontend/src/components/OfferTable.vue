<script setup lang="ts">
import { computed } from 'vue'

import { selectVisibleOffers } from '../stores/comparison'
import type { OfferView, SubsidyStatus } from '../types/offers'
import OfferDetails from './OfferDetails.vue'

const props = withDefaults(defineProps<{
  offers: OfferView[]
  includeConditional?: boolean
}>(), { includeConditional: false })

const visibleOffers = computed(() => selectVisibleOffers(props.offers, {
  includeConditional: props.includeConditional,
}))

const subsidyLabels: Record<SubsidyStatus, string> = {
  confirmed: '已确认国补',
  estimated: '预计国补',
  ineligible: '不符合',
  not_eligible: '不符合',
  unknown: '无法确认',
}

const platformNames: Record<string, string> = { jd: '京东', taobao: '淘宝', pdd: '拼多多' }

function formatMoney(value: number | null): string {
  return value === null ? '—' : `¥${(value / 100).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}
</script>

<template>
  <div class="offer-list" aria-live="polite">
    <article
      v-for="(offer, index) in visibleOffers"
      :key="offer.id"
      class="offer-row"
      data-testid="offer-row"
    >
      <div class="rank" :class="{ best: index === 0 }">{{ index === 0 ? '最低' : index + 1 }}</div>
      <div class="offer-main">
        <div class="offer-title-line">
          <strong>{{ platformNames[offer.platform] ?? offer.platform }}</strong>
          <span class="shop-name">{{ offer.shop_name }}</span>
          <span class="subsidy-badge" :class="offer.subsidy_status">
            {{ subsidyLabels[offer.subsidy_status] }}
          </span>
          <span v-if="index === 0" class="region-badge" data-testid="lowest-region">
            最低价地区：{{ offer.region_name ?? offer.region_code ?? '地区未知' }}
          </span>
        </div>
        <p>{{ offer.title }}</p>
        <OfferDetails :offer="offer" />
      </div>
      <div class="price-block">
        <small>默认可比价</small>
        <strong data-testid="comparable-price">{{ formatMoney(offer.comparable_price_cents) }}</strong>
        <span v-if="offer.estimated_final_price_cents !== null" class="estimated-price">
          估算 {{ formatMoney(offer.estimated_final_price_cents) }}
        </span>
        <span v-if="includeConditional && offer.conditional_price_cents !== null" class="conditional-price">
          条件价 {{ formatMoney(offer.conditional_price_cents) }}
        </span>
      </div>
    </article>
  </div>
</template>
