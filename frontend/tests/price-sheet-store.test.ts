import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { usePriceSheetStore, validatePriceSheetFile } from '../src/stores/price-sheets'


const batch = {
  id: 12,
  file_name: 'sheet.png',
  price_date: '2026-09-03',
  date_inferred: false,
  status: 'reviewing' as const,
  recognized_count: 1,
  selected_count: 1,
  completed_item_count: 0,
  partial_item_count: 0,
  failed_item_count: 0,
  lower_price_count: 0,
  current_item_id: null,
  pause_requested: false,
  stop_requested: false,
  last_error_code: null,
  last_error_summary: null,
  created_at: '2026-09-03T00:00:00Z',
  updated_at: '2026-09-03T00:00:00Z',
  started_at: null,
  finished_at: null,
}

const item = {
  id: 1, batch_id: 12, sequence: 1, selected: true, brand: 'Apple',
  model_name: 'iPhone 17', storage: '256GB', color: '黑色', today_price_cents: 590000,
  raw_text: '17-256G 黑5900', confidence: 0.98, review_required: false, status: 'reviewing',
  candidate_count: 0, total_region_count: 0, completed_region_count: 0, failed_region_count: 0,
  lowest_price_cents: null, last_error_code: null, last_error_summary: null,
  started_at: null, finished_at: null,
}

const progress = {
  stage: 'review', candidate_count: 0, task_total: 0, task_finished: 0,
  verified_count: 0, conditional_count: 0, address_required_count: 0,
  unavailable_count: 0, failed_count: 0, skipped_count: 0,
  cart_attention_required: false, current: null,
}


describe('price sheet store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('validates supported image types and the 10 MiB limit', () => {
    expect(validatePriceSheetFile(new File(['x'], 'sheet.png', { type: 'image/png' }))).toBeNull()
    expect(validatePriceSheetFile(new File(['x'], 'sheet.txt', { type: 'text/plain' }))).toContain('JPG')
    const large = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.png', { type: 'image/png' })
    expect(validatePriceSheetFile(large)).toContain('10 MiB')
  })

  it('uploads raw image bytes and persists the returned batch identity', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ batch, items: [item], tasks: [], checkout_progress: progress }), {
      status: 201, headers: { 'Content-Type': 'application/json' },
    }))
    vi.stubGlobal('fetch', fetchMock)
    const store = usePriceSheetStore()
    const file = new File(['png'], '今日 9.3.png', { type: 'image/png' })

    await store.recognize(file)

    expect(fetchMock).toHaveBeenCalledWith('/api/price-sheet-batches/recognize', expect.objectContaining({
      method: 'POST',
      body: file,
      headers: expect.objectContaining({
        'Content-Type': 'image/png',
        'X-File-Name': encodeURIComponent('今日 9.3.png'),
      }),
    }))
    expect(localStorage.getItem('lastPriceSheetBatchId')).toBe('12')
    expect(store.detail?.items[0].color).toBe('黑色')
  })

  it('keeps cart attention visible across later refreshes until reset', () => {
    const store = usePriceSheetStore()
    const attention = { ...progress, cart_attention_required: true }

    store.remember({ batch, items: [item], tasks: [], checkout_progress: attention })
    store.remember({ batch, items: [item], tasks: [], checkout_progress: progress })

    expect(store.cartAttentionSeen).toBe(true)
    store.reset()
    expect(store.cartAttentionSeen).toBe(false)
  })
})
