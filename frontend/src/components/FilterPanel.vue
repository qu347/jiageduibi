<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  regionCode: string
  includeConditional: boolean
}>()

const emit = defineEmits<{
  'update:regionCode': [value: string]
  'update:includeConditional': [value: boolean]
}>()

const selectedRegion = computed({
  get: () => props.regionCode,
  set: (value: string) => emit('update:regionCode', value),
})
</script>

<template>
  <aside class="filters" aria-labelledby="filter-title">
    <span class="step">步骤 2</span>
    <h2 id="filter-title">比价条件</h2>
    <label for="region">补贴地区</label>
    <select id="region" v-model="selectedRegion">
      <option value="">暂不选择（只看普通价）</option>
      <option value="110100">北京市</option>
      <option value="310100">上海市</option>
      <option value="440100">广东省广州市</option>
      <option value="440300">广东省深圳市</option>
    </select>
    <p class="hint">补贴按省市规则估算；没有规则时会标记“未知”。</p>

    <label class="check-row">
      <input
        type="checkbox"
        :checked="includeConditional"
        @change="emit('update:includeConditional', ($event.target as HTMLInputElement).checked)"
      />
      <span>显示会员、支付或以旧换新等条件价</span>
    </label>
    <div class="privacy-note">
      <strong>本地优先</strong>
      <p>数据库与规则保存在本机。登录、验证码由你在浏览器里完成。</p>
    </div>
  </aside>
</template>
