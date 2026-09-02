<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'

import FilterPanel from '../components/FilterPanel.vue'
import ModelSelector from '../components/ModelSelector.vue'
import { useCatalogStore } from '../stores/catalog'

const catalog = useCatalogStore()
const { confirmedVariant } = storeToRefs(catalog)
const regionCode = ref('')
const includeConditional = ref(false)
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

    <ModelSelector />

    <div class="workbench-grid">
      <FilterPanel v-model:region-code="regionCode" v-model:include-conditional="includeConditional" />
      <section class="results-placeholder">
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
        <div v-else class="empty-state">
          <div class="empty-icon">¥</div>
          <h3>等待确认标准 SKU</h3>
          <p>确认后才能创建比价会话，避免不同型号和容量混排。</p>
        </div>
        <button
          class="primary-action"
          data-test="create-search"
          type="button"
          :disabled="!confirmedVariant"
        >
          创建比价会话
        </button>
      </section>
    </div>
  </main>
</template>
