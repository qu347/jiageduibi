<script setup lang="ts">
defineProps<{
  includeConditional: boolean
}>()

const emit = defineEmits<{
  'update:includeConditional': [value: boolean]
}>()
</script>

<template>
  <aside class="filters" aria-labelledby="filter-title">
    <span class="step">步骤 2</span>
    <h2 id="filter-title">比价条件</h2>
    <label>比较范围</label>
    <div class="nationwide-scope" data-testid="nationwide-scope">
      <strong>全国比价</strong>
      <span>汇总不同地区可用报价</span>
    </div>
    <p class="hint">按报价适用地区分别估算补贴；最低价会标明所在地区。</p>

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
