<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'

import { usePriceSheetStore, validatePriceSheetFile } from '../stores/price-sheets'
import type { PriceSheetItemView } from '../types/price-sheets'

const store = usePriceSheetStore()
const { detail, results, loading, error } = storeToRefs(store)
const uploadError = ref('')
const resultTab = ref<'lower' | 'other'>('lower')

const statusLabels: Record<string, string> = {
  queued: '排队中', running: '正在比价', paused: '已暂停', waiting_user: '等待操作',
  completed: '已完成', completed_partial: '部分完成', stopped: '已停止', failed: '失败',
}
const isReviewing = computed(() => detail.value?.batch.status === 'reviewing')
const isFinished = computed(() => Boolean(detail.value && ['completed', 'completed_partial', 'stopped', 'failed'].includes(detail.value.batch.status)))
const isProgress = computed(() => Boolean(detail.value && !isReviewing.value && !isFinished.value))
const currentItem = computed(() => detail.value?.items.find((item) => item.id === detail.value?.batch.current_item_id) ?? null)
const currentTask = computed(() => {
  if (!currentItem.value) return null
  return detail.value?.tasks.find((task) => task.price_sheet_item_id === currentItem.value?.id && ['running', 'waiting_user'].includes(task.status)) ?? null
})
const otherResults = computed(() => [
  ...(results.value?.not_lower_items ?? []),
  ...(results.value?.partial_items ?? []),
])

function money(cents: number | null): string {
  if (cents === null) return '—'
  return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY', maximumFractionDigits: 0 }).format(cents / 100)
}

async function selectFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  uploadError.value = validatePriceSheetFile(file) ?? ''
  if (uploadError.value) return
  try {
    await store.recognize(file)
  } catch {
    // The store exposes the structured error below.
  }
}

function removeItem(index: number) {
  detail.value?.items.splice(index, 1)
}

function addItem() {
  if (!detail.value) return
  const sequence = detail.value.items.length + 1
  detail.value.items.push({
    id: -sequence, batch_id: detail.value.batch.id, sequence, selected: true, brand: 'Apple',
    model_name: '', storage: '', color: '', today_price_cents: 0, raw_text: '', confidence: 1,
    review_required: false, status: 'reviewing', candidate_count: 0, total_region_count: 0,
    completed_region_count: 0, failed_region_count: 0, lowest_price_cents: null,
    last_error_code: null, last_error_summary: null, started_at: null, finished_at: null,
  })
}

function updatePrice(item: PriceSheetItemView, event: Event) {
  item.today_price_cents = Math.round(Number((event.target as HTMLInputElement).value || 0) * 100)
}

async function saveAndStart() {
  try {
    await store.saveItems()
    await store.start()
  } catch {
    // The store exposes the structured error below.
  }
}
</script>

<template>
  <section class="price-sheet-workflow" aria-labelledby="price-sheet-title">
    <div class="price-sheet-heading">
      <div>
        <span class="eyebrow">仅京东 · 精确到颜色</span>
        <h2 id="price-sheet-title">上传价目表，找全国最低价</h2>
        <p>本机识别图片，逐个规格核验 31 个代表街道；原图识别后立即删除。</p>
      </div>
      <button v-if="detail" class="secondary-action" type="button" @click="store.reset()">新建批次</button>
    </div>

    <ol class="price-sheet-steps" aria-label="处理步骤">
      <li :class="{ active: !detail }">1 上传图片</li>
      <li :class="{ active: isReviewing }">2 核对识别结果</li>
      <li :class="{ active: isProgress }">3 全国比价</li>
      <li :class="{ active: isFinished }">4 查看结果</li>
    </ol>

    <div v-if="!detail" class="price-sheet-upload">
      <div class="upload-icon">图片</div>
      <h3>上传竖版手机价目表</h3>
      <p>支持 JPG、PNG、WebP，最大 10 MiB / 2000 万像素。</p>
      <label class="primary-action upload-button">
        {{ loading ? '正在本机识别…' : '选择图片' }}
        <input data-testid="price-sheet-file" type="file" accept="image/jpeg,image/png,image/webp" :disabled="loading" @change="selectFile">
      </label>
      <small>隐私提示：图片不会保存到数据库，也不会上传到云端 OCR。</small>
    </div>

    <div v-else-if="isReviewing" class="price-sheet-review">
      <div class="review-toolbar">
        <div><span>文件</span><strong>{{ detail.batch.file_name }}</strong></div>
        <label>价目日期 <input v-model="detail.batch.price_date" type="date"></label>
        <span v-if="detail.batch.date_inferred" class="review-badge warning">日期需确认</span>
      </div>
      <div class="price-sheet-table">
        <article v-for="(item, index) in detail.items" :key="item.id" class="price-sheet-row">
          <div class="price-sheet-row-title">
            <label><input v-model="item.selected" type="checkbox"> 查询</label>
            <strong>{{ item.model_name }} · {{ item.storage }} · {{ item.color }}</strong>
            <span v-if="item.review_required" class="review-badge warning">请核对 · 识别置信度 {{ Math.round(item.confidence * 100) }}%</span>
          </div>
          <div class="price-sheet-fields">
            <label>机型<input v-model="item.model_name"></label>
            <label>容量<input v-model="item.storage"></label>
            <label>颜色<input v-model="item.color"></label>
            <label>今日价（元）<input type="number" min="1000" max="30000" :value="item.today_price_cents / 100" @input="updatePrice(item, $event)"></label>
            <button type="button" @click="removeItem(index)">删除</button>
          </div>
        </article>
      </div>
      <div class="review-actions">
        <button type="button" class="secondary-action" @click="addItem">新增一行</button>
        <button data-testid="start-price-sheet" type="button" class="primary-action" :disabled="loading || !detail.items.some((item) => item.selected)" @click="saveAndStart">
          {{ loading ? '正在保存…' : '确认并开始京东全国比价' }}
        </button>
      </div>
    </div>

    <div v-else-if="isProgress" class="price-sheet-progress">
      <div class="progress-summary">
        <div><span>批次状态</span><strong>{{ statusLabels[detail.batch.status] }}</strong></div>
        <div><span>商品进度</span><strong>{{ detail.batch.completed_item_count }}/{{ detail.batch.selected_count }}</strong></div>
        <div><span>当前规格</span><strong>{{ currentItem ? `${currentItem.model_name} ${currentItem.storage} ${currentItem.color}` : '等待调度' }}</strong></div>
        <div><span>地区进度</span><strong>{{ currentItem?.completed_region_count ?? 0 }}/31</strong></div>
      </div>
      <p v-if="currentTask">当前地址：{{ [currentTask.province, currentTask.city, currentTask.district, currentTask.street].filter((part, index, all) => index === 0 || part !== all[index - 1]).join(' / ') }}</p>
      <p v-if="detail.batch.last_error_summary" class="automation-warning">{{ detail.batch.last_error_summary }}</p>
      <div class="automatic-actions">
        <button v-if="detail.batch.status === 'running' || detail.batch.status === 'queued'" type="button" @click="store.control('pause')">暂停</button>
        <button v-if="detail.batch.status === 'paused' || detail.batch.status === 'waiting_user'" type="button" @click="store.control('resume')">继续</button>
        <button type="button" @click="store.control('stop')">停止</button>
        <button v-if="detail.batch.failed_item_count" type="button" @click="store.control('retry-failed')">重试失败地区</button>
      </div>
    </div>

    <div v-else class="price-sheet-results">
      <div class="result-tabs">
        <button :class="{ active: resultTab === 'lower' }" type="button" @click="resultTab = 'lower'">低于今日价（{{ results?.lower_results.length ?? 0 }}）</button>
        <button :class="{ active: resultTab === 'other' }" type="button" @click="resultTab = 'other'">未发现更低价 / 待处理（{{ otherResults.length }}）</button>
      </div>
      <div v-if="resultTab === 'lower'" class="price-sheet-result-list">
        <article v-for="result in results?.lower_results" :key="result.item_id" data-testid="price-sheet-low-result" class="price-sheet-result-card">
          <div><span>全国最低</span><h3>{{ result.model_name }} · {{ result.storage }} · {{ result.color }}</h3><p>{{ result.address }} · {{ result.coverage }}</p></div>
          <div class="result-prices"><small>今日价 {{ money(result.today_price_cents) }}</small><strong>{{ money(result.trusted_price_cents) }}</strong><span>节省 {{ money(result.today_price_cents - (result.trusted_price_cents ?? result.today_price_cents)) }}</span></div>
          <dl>
            <div><dt>页面价</dt><dd>{{ money(result.sale_price_cents) }}</dd></div>
            <div><dt>普通优惠券</dt><dd>-{{ money(result.platform_coupon_cents) }}</dd></div>
            <div><dt>确认国补</dt><dd>-{{ money(result.subsidy_amount_cents) }}</dd></div>
            <div><dt>运费</dt><dd>+{{ money(result.shipping_fee_cents) }}</dd></div>
          </dl>
          <a v-if="result.product_url" :href="result.product_url" target="_blank" rel="noopener">在京东查看 · {{ result.shop_name }}</a>
        </article>
        <p v-if="!results?.lower_results.length" class="empty-state">没有满足“31/31 且低于今日价”的结果。</p>
      </div>
      <div v-else class="price-sheet-result-list">
        <article v-for="result in otherResults" :key="result.item_id" class="price-sheet-result-card muted-card">
          <h3>{{ result.model_name }} · {{ result.storage }} · {{ result.color }}</h3>
          <p>{{ result.status === 'partial' ? `仅完成 ${result.coverage}，不能称为全国最低` : result.status === 'no_comparable' ? '未发现可比较商品' : '未发现低于今日价的商品' }}</p>
        </article>
      </div>
    </div>

    <p v-if="uploadError" class="automation-warning">{{ uploadError }}</p>
    <div v-if="error" class="error-notice"><strong>{{ error.what_happened }}</strong><p>{{ error.possible_cause }}</p><p>{{ error.next_action }}</p></div>
  </section>
</template>
