<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { storeToRefs } from 'pinia'

import FilterPanel from '../components/FilterPanel.vue'
import ModelSelector from '../components/ModelSelector.vue'
import OfferTable from '../components/OfferTable.vue'
import ErrorNotice from '../components/ErrorNotice.vue'
import CollectionSessionCard from '../components/CollectionSessionCard.vue'
import AutomaticCollectionCard from '../components/AutomaticCollectionCard.vue'
import PriceSheetComparison from '../components/PriceSheetComparison.vue'
import { useCatalogStore } from '../stores/catalog'
import { loadFixtureBatches, normalizeApiError, useComparisonStore } from '../stores/comparison'
import { usePriceSheetStore } from '../stores/price-sheets'

const catalog = useCatalogStore()
const { confirmedVariant } = storeToRefs(catalog)
const comparison = useComparisonStore()
const {
  offers,
  excludedCount,
  loading,
  error,
  session,
  restoreMessage,
  automationEnvironment,
  automaticRun,
  automaticTasks,
  automaticLoading,
} = storeToRefs(comparison)
const includeConditional = ref(false)
const workspaceMode = ref<'single' | 'price-sheet'>('single')
const priceSheets = usePriceSheetStore()

async function runFixtureComparison() {
  if (!confirmedVariant.value) return
  try {
    const batches = await loadFixtureBatches()
    await comparison.createAndFinalizeSearch({
      variant_id: confirmedVariant.value.id,
      region_code: null,
      comparison_scope: 'national',
      include_conditional: includeConditional.value,
    }, batches)
  } catch (caught) {
    comparison.error = normalizeApiError(caught)
  }
}

async function createCollectionSession() {
  if (!confirmedVariant.value) return
  await comparison.createCollectionSession(confirmedVariant.value.id, includeConditional.value)
}

async function startAutomaticCollection() {
  if (!confirmedVariant.value) return
  await comparison.startAutomaticCollection(confirmedVariant.value.id, includeConditional.value)
}

async function copySessionId() {
  if (!session.value) return
  await navigator.clipboard.writeText(String(session.value.id))
}

onMounted(() => {
  void comparison.loadAutomationEnvironment()
  void comparison.restoreCollectionSession().then(() => comparison.restoreAutomaticCollection())
  void priceSheets.restore()
})
onUnmounted(() => {
  comparison.stopAutomaticPolling()
  priceSheets.stopPolling()
})
</script>

<template>
  <main class="workspace">
    <header class="hero">
      <div>
        <span class="eyebrow">全国版 · 本地离线 MVP</span>
        <h1>先认准商品，再比较到手价</h1>
        <p>统一型号、容量和版本口径，把确认补贴与估算补贴分开显示。</p>
      </div>
      <div class="status-pill"><span></span> 本地服务</div>
    </header>

    <div class="workspace-tabs" role="tablist" aria-label="比价方式">
      <button data-testid="single-product-tab" :class="{ active: workspaceMode === 'single' }" type="button" @click="workspaceMode = 'single'">单品比价</button>
      <button data-testid="price-sheet-tab" :class="{ active: workspaceMode === 'price-sheet' }" type="button" @click="workspaceMode = 'price-sheet'">价目表批量比价</button>
    </div>

    <PriceSheetComparison v-if="workspaceMode === 'price-sheet'" />

    <template v-else>
    <ModelSelector />

    <div class="workbench-grid">
      <FilterPanel v-model:include-conditional="includeConditional" />
      <section class="results-placeholder" :class="{ 'has-results': offers.length }">
        <div class="section-heading">
          <div>
            <span class="step">步骤 3</span>
            <h2>开始比价</h2>
          </div>
        </div>
        <div v-if="confirmedVariant" class="confirmed-sku">
          <span>已确认 SKU</span>
          <strong>{{ confirmedVariant.storage }} · {{ confirmedVariant.region_version }} · {{ confirmedVariant.condition }}</strong>
          <small>{{ confirmedVariant.sku_code }}</small>
        </div>
        <p v-if="restoreMessage" class="message">{{ restoreMessage }}</p>
        <AutomaticCollectionCard
          :run="automaticRun"
          :tasks="automaticTasks"
          :environment="automationEnvironment"
          :can-start="Boolean(confirmedVariant)"
          :loading="automaticLoading"
          @start="startAutomaticCollection"
          @pause="comparison.pauseAutomaticCollection()"
          @resume="comparison.resumeAutomaticCollection()"
          @stop="comparison.stopAutomaticCollection()"
          @retry="comparison.retryFailedRegions()"
        />
        <details class="manual-collection-fallback">
          <summary>手动采集备用</summary>
          <CollectionSessionCard
            :session="session"
            :sku="confirmedVariant"
            :loading="loading"
            @create="createCollectionSession"
            @recreate="createCollectionSession"
            @copy="copySessionId"
            @refresh="comparison.refreshCollectionSession()"
            @finalize="comparison.finalizeCollectionSession()"
          />
        </details>
        <ErrorNotice v-if="error" :error="error" />
        <div v-else-if="!confirmedVariant" class="empty-state">
          <div class="empty-icon">¥</div>
          <h3>等待确认标准 SKU</h3>
          <p>确认后才能创建比价会话，避免不同型号和容量混排。</p>
        </div>
        <div v-else-if="!offers.length" class="ready-state">
          <div class="empty-icon">✓</div>
          <h3>标准 SKU 已确认</h3>
          <p>点击下方按钮，用本地三平台夹具验证完整比价流程。</p>
        </div>
        <div v-else class="comparison-results">
          <div class="result-summary">
            <strong>找到 {{ offers.length }} 条可比报价</strong>
            <span>已排除 {{ excludedCount }} 条干扰项</span>
          </div>
          <OfferTable :offers="offers" :include-conditional="includeConditional" />
        </div>
        <button
          class="primary-action"
          data-test="create-search"
          data-testid="run-fixture-comparison"
          type="button"
          :disabled="!confirmedVariant || loading"
          @click="runFixtureComparison"
        >
          {{ loading ? '正在汇总三平台报价…' : offers.length ? '重新运行离线比价' : '运行三平台离线比价' }}
        </button>
        <p class="fixture-disclaimer">固定夹具，不代表真实平台价格；用于离线验证完整流程。</p>
      </section>
    </div>
    </template>
  </main>
</template>
