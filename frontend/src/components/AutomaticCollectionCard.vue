<script setup lang="ts">
import { computed } from 'vue'

import type {
  AutomationEnvironment,
  CollectionRegionTaskView,
  CollectionRunStatus,
  CollectionRunView,
} from '../types/offers'

const props = defineProps<{
  run: CollectionRunView | null
  tasks: CollectionRegionTaskView[]
  environment: AutomationEnvironment | null
  canStart: boolean
  loading: boolean
}>()

defineEmits<{
  start: []
  pause: []
  resume: []
  stop: []
  retry: []
}>()

const environmentReady = computed(() => Boolean(
  props.environment?.agent_reach_available
  && props.environment.opencli_available
  && props.environment.browser_bridge_ready
  && props.environment.plugin_ready,
))

const currentRegion = computed(() => {
  const code = props.run?.current_region_code
  if (!code) return null
  return props.tasks.find((task) => task.region_code === code)?.province ?? code
})

const progressPercent = computed(() => {
  if (!props.run || props.run.total_region_count === 0) return 0
  return Math.round((props.run.completed_region_count / props.run.total_region_count) * 100)
})

const waitingInstruction = computed(() => {
  if (props.run?.status !== 'waiting_user') return null
  if (props.run.last_error_code === 'captcha') return '请在浏览器完成验证，然后点击继续采集'
  if (props.run.last_error_code === 'login_required') return '请先在浏览器登录京东，然后点击继续采集'
  return props.run.last_error_summary ?? '浏览器需要你处理后才能继续'
})

const statusLabels: Record<CollectionRunStatus, string> = {
  queued: '排队中',
  running: '采集中',
  paused: '已暂停',
  waiting_user: '等待操作',
  completed: '已完成',
  completed_partial: '部分完成',
  stopped: '已停止',
  failed: '运行失败',
}

const canPause = computed(() => Boolean(
  props.run
  && ['queued', 'running'].includes(props.run.status)
  && !props.run.pause_requested,
))
const canResume = computed(() => Boolean(
  props.run && ['paused', 'waiting_user'].includes(props.run.status),
))
const canStop = computed(() => Boolean(
  props.run && !['completed', 'completed_partial', 'stopped', 'failed'].includes(props.run.status),
))
const canRestart = computed(() => Boolean(
  props.run && ['completed', 'completed_partial', 'stopped', 'failed'].includes(props.run.status),
))
</script>

<template>
  <section class="automatic-collection-card" aria-labelledby="automatic-collection-title">
    <div class="automatic-collection-heading">
      <div>
        <span class="step">推荐 · 一键自动采集</span>
        <h3 id="automatic-collection-title">京东全国 31 省代表地区比价</h3>
      </div>
      <span v-if="run" class="session-status" :class="run.status">{{ statusLabels[run.status] }}</span>
    </div>

    <template v-if="!run">
      <p class="automation-intro">使用本机已登录浏览器自动搜索候选商品，再逐省核验售价、库存和补贴信息。</p>
      <p class="automation-environment" :class="{ ready: environmentReady }">
        {{ environment?.safe_message ?? '正在检查本机自动采集环境…' }}
      </p>
      <button
        class="automatic-primary"
        data-testid="start-automatic-collection"
        type="button"
        :disabled="!canStart || !environmentReady || loading"
        @click="$emit('start')"
      >{{ loading ? '正在启动…' : '开始全国自动比价' }}</button>
    </template>

    <template v-else>
      <div class="automatic-metrics">
        <div><span>平台</span><strong>京东</strong></div>
        <div><span>阶段</span><strong>{{ run.stage === 'discovering' ? '搜索候选' : run.stage === 'verifying' ? '逐省核验' : '采集完成' }}</strong></div>
        <div><span>商品筛选</span><strong>候选 {{ run.selected_candidate_count }}/{{ run.candidate_count }}</strong></div>
      </div>
      <div class="automatic-progress" data-testid="automatic-progress">
        <div><strong>已核验 {{ run.completed_region_count }}/{{ run.total_region_count }}</strong><span>{{ progressPercent }}%</span></div>
        <div class="progress-track"><span :style="{ width: `${progressPercent}%` }"></span></div>
        <p v-if="currentRegion">当前地区：{{ currentRegion }}</p>
        <p v-else-if="run.failed_region_count || run.skipped_region_count">
          失败 {{ run.failed_region_count }} · 跳过 {{ run.skipped_region_count }}
        </p>
      </div>
      <p class="automation-note">系统会自动分批采集并留出冷却时间，减少触发京东访问频繁。</p>
      <p v-if="waitingInstruction" class="automation-user-action">{{ waitingInstruction }}</p>
      <p v-else-if="run.last_error_summary" class="automation-warning">{{ run.last_error_summary }}</p>
      <p v-else-if="run.pause_requested" class="automation-note">暂停请求已提交，将在当前浏览器操作完成后暂停。</p>
      <p v-else-if="run.stop_requested" class="automation-note">停止请求已提交，将保留已经采集的报价。</p>

      <div class="automatic-actions">
        <button
          v-if="canRestart"
          class="automatic-primary"
          data-testid="restart-automatic-collection"
          type="button"
          :disabled="!canStart || !environmentReady || loading"
          @click="$emit('start')"
        >重新开始全国比价</button>
        <button
          v-if="canPause"
          data-testid="pause-automatic-collection"
          type="button"
          :disabled="loading"
          @click="$emit('pause')"
        >暂停</button>
        <button
          v-if="canResume"
          data-testid="resume-automatic-collection"
          type="button"
          :disabled="loading"
          @click="$emit('resume')"
        >继续采集</button>
        <button
          v-if="canStop"
          data-testid="stop-automatic-collection"
          type="button"
          :disabled="loading || run.stop_requested"
          @click="$emit('stop')"
        >停止</button>
        <button
          v-if="run.failed_region_count > 0"
          data-testid="retry-automatic-collection"
          type="button"
          :disabled="loading"
          @click="$emit('retry')"
        >重试失败地区</button>
      </div>
    </template>
  </section>
</template>
