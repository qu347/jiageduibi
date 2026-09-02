<script setup lang="ts">
import { computed } from 'vue'

import { lowestOfferSummary, offerRegionLabel, selectVisibleOffers } from '../stores/comparison'
import type { OfferView, SubsidyStatus } from '../types/offers'
import OfferDetails from './OfferDetails.vue'

const props = withDefaults(defineProps<{
  offers: OfferView[]
  includeConditional?: boolean
}>(), { includeConditional: false })

const visibleOffers = computed(() => selectVisibleOffers(props.offers, {
  includeConditional: props.includeConditional,
}))
const lowest = computed(() => lowestOfferSummary(visibleOffers.value))

function isLowest(offer: OfferView): boolean {
  return lowest.value.price !== null && offer.comparable_price_cents === lowest.value.price
}

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
    <p v-if="lowest.price !== null" class="lowest-region-summary" data-testid="lowest-region">
      最低价地区：{{ lowest.regions.join('、') }}
    </p>
    <p v-else class="no-reliable-price">暂无可靠可比价</p>
    <article
      v-for="(offer, index) in visibleOffers"
      :key="offer.id"
      class="offer-row"
      data-testid="offer-row"
      :data-offer-id="offer.id"
    >
      <div class="rank" :class="{ best: isLowest(offer) }">{{ isLowest(offer) ? '最低' : index + 1 }}</div>
      <div class="offer-main">
        <div class="offer-title-line">
          <strong>{{ platformNames[offer.platform] ?? offer.platform }}</strong>
          <span class="shop-name">{{ offer.shop_name }}</span>
          <span class="subsidy-badge" :class="offer.subsidy_status">
            {{ subsidyLabels[offer.subsidy_status] }}
          </span>
          <span class="region-badge" data-testid="offer-region">
            适用地区：{{ offerRegionLabel(offer) }}
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
