<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { useCatalogStore } from '../stores/catalog'

const store = useCatalogStore()
const { models, confirmedVariant, loading, error } = storeToRefs(store)
const keyword = ref('')
const selectedModelCode = ref('')
const selectedStorage = ref('')
const selectedRegion = ref('')
const selectedCondition = ref('')

const selectedModel = computed(() => models.value.find((model) => model.model_code === selectedModelCode.value))
const variants = computed(() => selectedModel.value?.variants ?? [])
const storageOptions = computed(() => [...new Set(variants.value.map((variant) => variant.storage))])
const regionOptions = computed(() => [...new Set(
  variants.value.filter((variant) => !selectedStorage.value || variant.storage === selectedStorage.value)
    .map((variant) => variant.region_version),
)])
const conditionOptions = computed(() => [...new Set(
  variants.value.filter((variant) =>
    (!selectedStorage.value || variant.storage === selectedStorage.value)
    && (!selectedRegion.value || variant.region_version === selectedRegion.value),
  ).map((variant) => variant.condition),
)])
const candidate = computed(() => variants.value.find((variant) =>
  variant.storage === selectedStorage.value
  && variant.region_version === selectedRegion.value
  && variant.condition === selectedCondition.value,
))

async function searchModels() {
  if (!keyword.value.trim()) return
  await store.search(keyword.value.trim())
  selectedModelCode.value = ''
  selectedStorage.value = ''
  selectedRegion.value = ''
  selectedCondition.value = ''
}

function chooseModel(modelCode: string) {
  selectedModelCode.value = modelCode
  selectedStorage.value = ''
  selectedRegion.value = ''
  selectedCondition.value = ''
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
      <button
        v-for="model in models"
        :key="model.model_code"
        type="button"
        class="model-card model-choice"
        :class="{ selected: selectedModelCode === model.model_code }"
        @click="chooseModel(model.model_code)"
      >
        <div>
          <strong>{{ model.model_name }}</strong>
          <small>{{ model.model_code }}</small>
        </div>
        <span>{{ model.variants.length ? `${model.variants.length} 个可比 SKU` : '暂无可比 SKU' }}</span>
      </button>
    </div>

    <div v-if="selectedModel" class="variant-configurator">
      <div class="variant-option">
        <span>容量</span>
        <button
          v-for="storage in storageOptions"
          :key="storage"
          type="button"
          :class="{ selected: selectedStorage === storage }"
          @click="selectedStorage = storage"
        >{{ storage }}</button>
      </div>
      <div v-if="selectedStorage" class="variant-option">
        <span>版本</span>
        <button
          v-for="region in regionOptions"
          :key="region"
          type="button"
          :class="{ selected: selectedRegion === region }"
          @click="selectedRegion = region"
        >{{ region }}</button>
      </div>
      <div v-if="selectedRegion" class="variant-option">
        <span>成色</span>
        <button
          v-for="condition in conditionOptions"
          :key="condition"
          type="button"
          :class="{ selected: selectedCondition === condition }"
          @click="selectedCondition = condition"
        >{{ condition }}</button>
      </div>
      <button
        class="confirm-variant"
        data-testid="confirm-variant"
        type="button"
        :disabled="!candidate"
        @click="candidate && store.confirmVariant(candidate)"
      >
        {{ confirmedVariant?.id === candidate?.id ? '已确认此 SKU' : '确认标准 SKU' }}
      </button>
    </div>
  </section>
</template>
