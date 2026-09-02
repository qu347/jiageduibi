<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'

import { useCatalogStore } from '../stores/catalog'

const store = useCatalogStore()
const { models, confirmedVariant, loading, error } = storeToRefs(store)
const keyword = ref('')

async function searchModels() {
  if (!keyword.value.trim()) return
  await store.search(keyword.value.trim())
}
</script>

<template>
  <section class="selector" aria-labelledby="model-selector-title">
    <div class="section-heading">
      <div>
        <span class="step">步骤 1</span>
        <h2 id="model-selector-title">确认标准商品</h2>
      </div>
      <p>先选准型号与容量，再开始跨平台比价。</p>
    </div>

    <form class="keyword-row" @submit.prevent="searchModels">
      <label class="sr-only" for="keyword">商品关键词</label>
      <input
        id="keyword"
        v-model="keyword"
        data-test="keyword"
        placeholder="例如：苹果17"
        autocomplete="off"
      />
      <button
        data-test="search-models"
        type="button"
        :disabled="loading || !keyword.trim()"
        @click="searchModels"
      >
        {{ loading ? '正在查找…' : '查找标准型号' }}
      </button>
    </form>

    <p v-if="error" class="message error" role="alert">{{ error }}</p>
    <p v-else-if="!models.length" class="message">输入常用叫法，工具会映射到标准型号。</p>

    <div v-else class="model-list" aria-live="polite">
      <article v-for="model in models" :key="model.model_code" class="model-card">
        <div>
          <strong>{{ model.model_name }}</strong>
          <small>{{ model.model_code }}</small>
        </div>
        <div v-if="model.variants.length" class="variant-list">
          <button
            v-for="variant in model.variants"
            :key="variant.id"
            type="button"
            class="variant-button"
            :class="{ selected: confirmedVariant?.id === variant.id }"
            @click="store.confirmVariant(variant)"
          >
            {{ variant.storage }} · {{ variant.region_version }} · {{ variant.condition }}
          </button>
        </div>
        <span v-else class="no-variant">暂无可比 SKU</span>
      </article>
    </div>
  </section>
</template>
