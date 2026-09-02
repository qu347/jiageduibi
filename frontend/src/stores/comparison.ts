import { defineStore } from 'pinia'

import { ApiError, apiPost } from '../api/client'
import type {
  ApiErrorBody,
  ComparisonResult,
  CreateSearchCommand,
  OfferView,
  PlatformOfferBatch,
  SearchSessionView,
} from '../types/offers'


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
  }),
  actions: {
    async createAndFinalizeSearch(command: CreateSearchCommand, fixtureBatches: PlatformOfferBatch[]) {
      this.loading = true
      this.error = null
      this.offers = []
      this.excludedCount = 0
      try {
        const session = await apiPost<SearchSessionView>('/api/search-sessions', command)
        for (const batch of fixtureBatches) {
          await apiPost(`/api/search-sessions/${session.id}/offers`, batch)
        }
        const result = await apiPost<ComparisonResult>(`/api/search-sessions/${session.id}/finalize`, {})
        this.offers = result.offers
        this.excludedCount = result.excluded_count
        this.lastSessionId = session.id
        localStorage.setItem('lastVariantId', String(command.variant_id))
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
