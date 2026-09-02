<script setup lang="ts">
import type { ProductVariant } from '../types/catalog'
import type { SearchSessionView } from '../types/offers'

const props = defineProps<{
  session: SearchSessionView | null
  sku: ProductVariant | null
  loading: boolean
}>()

defineEmits<{
  create: []
  refresh: []
  finalize: []
  recreate: []
  copy: []
}>()

function statusLabel(status: string): string {
  return status === 'collecting' ? '采集中' : status === 'completed' ? '已完成' : status
}
</script>

<template>
  <section class="collection-session-card" aria-labelledby="collection-session-title">
    <div class="collection-session-heading">
      <div>
        <span class="step">全国采集会话</span>
        <h3 id="collection-session-title">连接浏览器扩展与多地区报价</h3>
      </div>
      <span v-if="session" class="session-status" :class="session.status">
        {{ statusLabel(session.status) }}
      </span>
    </div>

    <div v-if="session" class="session-identity">
      <div>
        <span>会话 ID</span>
        <code data-testid="collection-session-id">{{ session.id }}</code>
      </div>
      <div><span>比较范围</span><strong>全国</strong></div>
      <div><span>标准 SKU</span><strong>{{ sku?.sku_code ?? session.variant_id }}</strong></div>
    </div>
    <p v-else class="session-empty">创建后，把会话 ID 填入浏览器扩展，再逐地区主动采集报价。</p>

    <div class="collection-session-actions">
      <button
        data-testid="create-collection-session"
        type="button"
        :disabled="!sku || loading"
        @click="session ? $emit('recreate') : $emit('create')"
      >{{ session ? '新建采集会话' : '创建采集会话' }}</button>
      <button
        v-if="session"
        data-testid="copy-session-id"
        type="button"
        :disabled="loading"
        @click="$emit('copy')"
      >复制 ID</button>
      <button
        v-if="session"
        data-testid="refresh-session"
        type="button"
        :disabled="loading"
        @click="$emit('refresh')"
      >刷新报价</button>
      <button
        v-if="session"
        data-testid="finalize-session"
        type="button"
        :disabled="loading || props.session?.status !== 'collecting'"
        @click="$emit('finalize')"
      >完成采集</button>
    </div>
  </section>
</template>
