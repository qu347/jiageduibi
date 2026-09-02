import { defineStore } from 'pinia'

import { ApiError, apiGet, apiPost, automaticCollectionApi } from '../api/client'
import { useCatalogStore } from './catalog'
import type {
  ApiErrorBody,
  AutomationEnvironment,
  CollectionRegionTaskView,
  CollectionRunStatus,
  CollectionRunView,
  ComparisonResult,
  CreateSearchCommand,
  OfferView,
  PlatformOfferBatch,
  SearchSessionView,
} from '../types/offers'


const ACTIVE_AUTOMATIC_STATUSES = new Set<CollectionRunStatus>(['queued', 'running', 'waiting_user'])


export function selectVisibleOffers(
  offers: OfferView[],
  _options: { includeConditional: boolean },
): OfferView[] {
  return offers
}


export function offerRegionLabel(offer: OfferView): string {
  return offer.region_name ?? offer.region_code ?? '地区未确认'
}


export function lowestOfferSummary(offers: OfferView[]): { price: number | null; regions: string[] } {
  const reliablePrices = offers
    .map((offer) => offer.comparable_price_cents)
    .filter((price): price is number => price !== null)
  if (reliablePrices.length === 0) return { price: null, regions: [] }
  const price = Math.min(...reliablePrices)
  const regions = [...new Set(
    offers
      .filter((offer) => offer.comparable_price_cents === price)
      .map(offerRegionLabel),
  )]
  return { price, regions }
}


export function normalizeApiError(error: unknown): ApiErrorBody {
  const fallback: ApiErrorBody = {
    what_happened: '比价请求失败',
    possible_cause: error instanceof Error ? error.message : '本地服务暂时无法处理请求',
    partial_saved: false,
    next_action: '确认本地服务正在运行后重试',
  }
  if (!(error instanceof ApiError) || typeof error.detail !== 'object' || error.detail === null) return fallback
  const outer = error.detail as { detail?: unknown }
  const detail = (outer.detail ?? outer) as Partial<ApiErrorBody>
  if (!detail.what_happened) return fallback
  return {
    what_happened: detail.what_happened,
    possible_cause: detail.possible_cause ?? fallback.possible_cause,
    partial_saved: detail.partial_saved ?? false,
    next_action: detail.next_action ?? fallback.next_action,
  }
}


export const useComparisonStore = defineStore('comparison', {
  state: () => ({
    offers: [] as OfferView[],
    excludedCount: 0,
    loading: false,
    error: null as ApiErrorBody | null,
    lastSessionId: null as number | null,
    session: null as SearchSessionView | null,
    restoreMessage: '',
    automationEnvironment: null as AutomationEnvironment | null,
    automaticRun: null as CollectionRunView | null,
    automaticTasks: [] as CollectionRegionTaskView[],
    lastAutomaticRunId: null as number | null,
    automaticLoading: false,
    automaticRefreshInFlight: false,
    automaticPollingTimer: null as number | null,
  }),
  actions: {
    saveSessionIdentity(session: SearchSessionView) {
      this.session = session
      this.lastSessionId = session.id
      localStorage.setItem('lastSessionId', String(session.id))
      localStorage.setItem('lastVariantId', String(session.variant_id))
    },
    applyResult(result: ComparisonResult) {
      this.offers = result.offers
      this.excludedCount = result.excluded_count
    },
    async loadAutomationEnvironment() {
      try {
        this.automationEnvironment = await automaticCollectionApi.environment()
      } catch (error) {
        this.automationEnvironment = {
          agent_reach_available: false,
          opencli_available: false,
          browser_bridge_ready: false,
          plugin_ready: false,
          safe_message: normalizeApiError(error).next_action,
        }
      }
    },
    saveAutomaticRun(run: CollectionRunView) {
      this.automaticRun = run
      this.lastAutomaticRunId = run.id
      localStorage.setItem('lastAutomaticRunId', String(run.id))
    },
    async startAutomaticCollection(variantId: number, includeConditional: boolean) {
      this.automaticLoading = true
      this.error = null
      try {
        let session = this.session
        if (
          !session
          || session.variant_id !== variantId
          || session.status !== 'collecting'
          || this.automaticRun !== null
        ) {
          session = await apiPost<SearchSessionView>('/api/search-sessions', {
            variant_id: variantId,
            region_code: null,
            comparison_scope: 'national',
            include_conditional: includeConditional,
          } satisfies CreateSearchCommand)
          this.saveSessionIdentity(session)
        }
        const run = await automaticCollectionApi.create(session.id)
        this.saveAutomaticRun(run)
        this.automaticTasks = await automaticCollectionApi.tasks(run.id)
        this.applyResult(await apiGet<ComparisonResult>(`/api/search-sessions/${session.id}/result`))
        this.startAutomaticPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.automaticLoading = false
      }
    },
    async refreshAutomaticCollection() {
      const runId = this.automaticRun?.id ?? this.lastAutomaticRunId
      if (runId === null || this.automaticRefreshInFlight) return
      this.automaticRefreshInFlight = true
      try {
        const run = await automaticCollectionApi.get(runId)
        this.saveAutomaticRun(run)
        this.automaticTasks = await automaticCollectionApi.tasks(runId)
        this.applyResult(await apiGet<ComparisonResult>(`/api/search-sessions/${run.search_session_id}/result`))
        if (!ACTIVE_AUTOMATIC_STATUSES.has(run.status)) this.stopAutomaticPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
        this.stopAutomaticPolling()
      } finally {
        this.automaticRefreshInFlight = false
      }
    },
    async pauseAutomaticCollection() {
      if (!this.automaticRun) return
      try {
        this.saveAutomaticRun(await automaticCollectionApi.pause(this.automaticRun.id))
      } catch (error) {
        this.error = normalizeApiError(error)
      }
    },
    async resumeAutomaticCollection() {
      if (!this.automaticRun) return
      try {
        this.saveAutomaticRun(await automaticCollectionApi.resume(this.automaticRun.id))
        this.startAutomaticPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
      }
    },
    async stopAutomaticCollection() {
      if (!this.automaticRun) return
      try {
        this.saveAutomaticRun(await automaticCollectionApi.stop(this.automaticRun.id))
      } catch (error) {
        this.error = normalizeApiError(error)
      }
    },
    async retryFailedRegions() {
      if (!this.automaticRun) return
      try {
        this.saveAutomaticRun(await automaticCollectionApi.retryFailed(this.automaticRun.id))
        this.startAutomaticPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
      }
    },
    async restoreAutomaticCollection() {
      const storedRunId = localStorage.getItem('lastAutomaticRunId')
      if (!storedRunId) return
      const runId = Number(storedRunId)
      if (!Number.isSafeInteger(runId) || runId <= 0) {
        localStorage.removeItem('lastAutomaticRunId')
        return
      }
      try {
        const run = await automaticCollectionApi.get(runId)
        this.saveAutomaticRun(run)
        this.automaticTasks = await automaticCollectionApi.tasks(runId)
        this.applyResult(await apiGet<ComparisonResult>(`/api/search-sessions/${run.search_session_id}/result`))
        this.startAutomaticPolling()
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          localStorage.removeItem('lastAutomaticRunId')
          this.lastAutomaticRunId = null
          this.automaticRun = null
          this.automaticTasks = []
        } else {
          this.error = normalizeApiError(error)
        }
      }
    },
    startAutomaticPolling() {
      this.stopAutomaticPolling()
      if (!this.automaticRun || !ACTIVE_AUTOMATIC_STATUSES.has(this.automaticRun.status)) return
      this.automaticPollingTimer = window.setInterval(() => {
        void this.refreshAutomaticCollection()
      }, 1500)
    },
    stopAutomaticPolling() {
      if (this.automaticPollingTimer !== null) {
        window.clearInterval(this.automaticPollingTimer)
        this.automaticPollingTimer = null
      }
    },
    async createCollectionSession(variantId: number, includeConditional: boolean) {
      this.loading = true
      this.error = null
      this.restoreMessage = ''
      try {
        const session = await apiPost<SearchSessionView>('/api/search-sessions', {
          variant_id: variantId,
          region_code: null,
          comparison_scope: 'national',
          include_conditional: includeConditional,
        } satisfies CreateSearchCommand)
        this.saveSessionIdentity(session)
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.loading = false
      }
    },
    async refreshCollectionSession() {
      const sessionId = this.session?.id ?? this.lastSessionId
      if (sessionId === null) return
      this.loading = true
      this.error = null
      try {
        this.applyResult(await apiGet<ComparisonResult>(`/api/search-sessions/${sessionId}/result`))
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.loading = false
      }
    },
    async finalizeCollectionSession() {
      const sessionId = this.session?.id ?? this.lastSessionId
      if (sessionId === null) return
      this.loading = true
      this.error = null
      try {
        const result = await apiPost<ComparisonResult>(`/api/search-sessions/${sessionId}/finalize`, {})
        this.applyResult(result)
        if (this.session) {
          this.session = { ...this.session, status: result.status }
        }
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.loading = false
      }
    },
    async restoreCollectionSession() {
      const storedSessionId = localStorage.getItem('lastSessionId')
      if (!storedSessionId) return
      this.loading = true
      this.error = null
      this.restoreMessage = ''
      try {
        const session = await apiGet<SearchSessionView>(`/api/search-sessions/${storedSessionId}`)
        const variant = await apiGet<import('../types/catalog').ProductVariant>(
          `/api/catalog/variants/${session.variant_id}`,
        )
        const result = await apiGet<ComparisonResult>(`/api/search-sessions/${session.id}/result`)
        this.saveSessionIdentity(session)
        useCatalogStore().confirmVariant(variant)
        this.applyResult(result)
        this.restoreMessage = '已恢复上次采集会话'
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          localStorage.removeItem('lastSessionId')
          localStorage.removeItem('lastVariantId')
          this.lastSessionId = null
          this.session = null
          this.offers = []
          this.excludedCount = 0
          useCatalogStore().confirmedVariant = null
          this.restoreMessage = '上次采集会话已失效，请重新创建'
        } else {
          this.restoreMessage = '暂时无法恢复上次会话，本地记录已保留'
        }
      } finally {
        this.loading = false
      }
    },
    async createAndFinalizeSearch(command: CreateSearchCommand, fixtureBatches: PlatformOfferBatch[]) {
      this.loading = true
      this.error = null
      this.offers = []
      this.excludedCount = 0
      try {
        const session = await apiPost<SearchSessionView>('/api/search-sessions', command)
        this.saveSessionIdentity(session)
        for (const batch of fixtureBatches) {
          await apiPost(`/api/search-sessions/${session.id}/offers`, batch)
        }
        const result = await apiPost<ComparisonResult>(`/api/search-sessions/${session.id}/finalize`, {})
        this.offers = result.offers
        this.excludedCount = result.excluded_count
        this.session = { ...session, status: result.status }
      } catch (error) {
        this.error = normalizeApiError(error)
      } finally {
        this.loading = false
      }
    },
  },
})


export async function loadFixtureBatches(): Promise<PlatformOfferBatch[]> {
  return Promise.all(
    ['jd', 'taobao', 'pdd'].map(async (platform) => {
      const response = await fetch(`/${platform}/search-results.json`)
      if (!response.ok) throw await ApiError.fromResponse(response)
      return response.json() as Promise<PlatformOfferBatch>
    }),
  )
}
