import { defineStore } from 'pinia'

import { ApiError, apiGet, apiPost, apiPut, apiUpload } from '../api/client'
import { normalizeApiError } from './comparison'
import type {
  PriceSheetBatchDetail,
  PriceSheetBatchStatus,
  PriceSheetItemView,
  PriceSheetResultsView,
} from '../types/price-sheets'
import type { ApiErrorBody } from '../types/offers'


const ALLOWED_TYPES = new Set(['image/jpeg', 'image/png', 'image/webp'])
const MAX_BYTES = 10 * 1024 * 1024
const ACTIVE = new Set<PriceSheetBatchStatus>(['queued', 'running', 'waiting_user'])

export function validatePriceSheetFile(file: File): string | null {
  if (!ALLOWED_TYPES.has(file.type)) return '只支持 JPG、PNG 或 WebP 图片'
  if (file.size > MAX_BYTES) return '图片不能超过 10 MiB'
  return null
}

function editableItem(item: PriceSheetItemView) {
  return {
    selected: item.selected,
    brand: item.brand,
    model_name: item.model_name,
    storage: item.storage,
    color: item.color,
    today_price_cents: item.today_price_cents,
    raw_text: item.raw_text,
    confidence: item.confidence,
    review_required: item.review_required,
  }
}

export const usePriceSheetStore = defineStore('price-sheets', {
  state: () => ({
    detail: null as PriceSheetBatchDetail | null,
    results: null as PriceSheetResultsView | null,
    loading: false,
    error: null as ApiErrorBody | null,
    pollingTimer: null as number | null,
    refreshInFlight: false,
  }),
  actions: {
    remember(detail: PriceSheetBatchDetail) {
      this.detail = detail
      localStorage.setItem('lastPriceSheetBatchId', String(detail.batch.id))
    },
    async recognize(file: File) {
      const validation = validatePriceSheetFile(file)
      if (validation) throw new Error(validation)
      this.loading = true
      this.error = null
      try {
        this.remember(await apiUpload('/api/price-sheet-batches/recognize', file))
        this.results = null
      } catch (error) {
        this.error = normalizeApiError(error)
        throw error
      } finally {
        this.loading = false
      }
    },
    async saveItems() {
      if (!this.detail) return
      this.loading = true
      this.error = null
      try {
        this.remember(await apiPut(`/api/price-sheet-batches/${this.detail.batch.id}/items`, {
          price_date: this.detail.batch.price_date,
          items: this.detail.items.map(editableItem),
        }))
      } catch (error) {
        this.error = normalizeApiError(error)
        throw error
      } finally {
        this.loading = false
      }
    },
    async start() {
      if (!this.detail) return
      this.loading = true
      try {
        this.remember(await apiPost(`/api/price-sheet-batches/${this.detail.batch.id}/start`, {}))
        this.startPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
        throw error
      } finally {
        this.loading = false
      }
    },
    async refresh() {
      const batchId = this.detail?.batch.id ?? Number(localStorage.getItem('lastPriceSheetBatchId'))
      if (!Number.isSafeInteger(batchId) || batchId <= 0 || this.refreshInFlight) return
      this.refreshInFlight = true
      try {
        this.remember(await apiGet(`/api/price-sheet-batches/${batchId}`))
        this.results = await apiGet(`/api/price-sheet-batches/${batchId}/results`)
        if (!ACTIVE.has(this.detail!.batch.status)) this.stopPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
        this.stopPolling()
      } finally {
        this.refreshInFlight = false
      }
    },
    async control(action: 'pause' | 'resume' | 'stop' | 'retry-failed') {
      if (!this.detail) return
      try {
        this.remember(await apiPost(`/api/price-sheet-batches/${this.detail.batch.id}/${action}`, {}))
        if (action === 'resume' || action === 'retry-failed') this.startPolling()
      } catch (error) {
        this.error = normalizeApiError(error)
      }
    },
    async restore() {
      const raw = localStorage.getItem('lastPriceSheetBatchId')
      if (!raw) return
      const batchId = Number(raw)
      if (!Number.isSafeInteger(batchId) || batchId <= 0) {
        localStorage.removeItem('lastPriceSheetBatchId')
        return
      }
      try {
        this.remember(await apiGet(`/api/price-sheet-batches/${batchId}`))
        this.results = await apiGet(`/api/price-sheet-batches/${batchId}/results`)
        this.startPolling()
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          localStorage.removeItem('lastPriceSheetBatchId')
          this.detail = null
          this.results = null
        } else {
          this.error = normalizeApiError(error)
        }
      }
    },
    reset() {
      this.stopPolling()
      this.detail = null
      this.results = null
      this.error = null
      localStorage.removeItem('lastPriceSheetBatchId')
    },
    startPolling() {
      this.stopPolling()
      if (!this.detail || !ACTIVE.has(this.detail.batch.status)) return
      this.pollingTimer = window.setInterval(() => void this.refresh(), 1500)
    },
    stopPolling() {
      if (this.pollingTimer !== null) window.clearInterval(this.pollingTimer)
      this.pollingTimer = null
    },
  },
})
