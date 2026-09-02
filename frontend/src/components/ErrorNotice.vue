<script setup lang="ts">
import type { ApiErrorBody } from '../types/offers'

defineProps<{ error: ApiErrorBody }>()
</script>

<template>
  <section class="error-notice" role="alert">
    <strong>{{ error.what_happened }}</strong>
    <dl>
      <div><dt>可能原因</dt><dd>{{ error.possible_cause }}</dd></div>
      <div><dt>数据状态</dt><dd>{{ error.partial_saved ? '已保存部分数据' : '没有保存部分数据' }}</dd></div>
      <div><dt>下一步</dt><dd>{{ error.next_action }}</dd></div>
    </dl>
  </section>
</template>
