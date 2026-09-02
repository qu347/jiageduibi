import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useCatalogStore } from '../src/stores/catalog'
import { useComparisonStore } from '../src/stores/comparison'


const session = {
  id: 123,
  variant_id: 7,
  region_code: null,
  comparison_scope: 'national' as const,
  include_conditional: false,
  status: 'collecting',
  created_at: '2026-09-02T00:00:00Z',
  finalized_at: null,
}

const variant = {
  id: 7,
  sku_code: 'APPLE_IPHONE_17_256_CN_NEW_ANY',
  storage: '256GB',
  memory: null,
  color: '不限',
  region_version: '中国大陆国行',
  condition: '全新',
}

const preview = {
  id: 123,
  comparison_scope: 'national' as const,
  status: 'collecting',
  offers: [],
  excluded_count: 0,
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}


describe('collection session store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('creates, previews and finalizes a national session while saving both ids', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/search-sessions' && init?.method === 'POST') return jsonResponse(session, 201)
      if (url === '/api/search-sessions/123/result') return jsonResponse(preview)
      if (url === '/api/search-sessions/123/finalize') {
        return jsonResponse({ ...preview, status: 'completed' })
      }
      throw new Error(`unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const store = useComparisonStore()

    await store.createCollectionSession(7, false)
    expect(JSON.parse(String(fetchMock.mock.calls[0][1]?.body))).toEqual({
      variant_id: 7,
      region_code: null,
      comparison_scope: 'national',
      include_conditional: false,
    })
    expect(localStorage.getItem('lastSessionId')).toBe('123')
    expect(localStorage.getItem('lastVariantId')).toBe('7')

    await store.refreshCollectionSession()
    expect(fetchMock).toHaveBeenCalledWith('/api/search-sessions/123/result')
    await store.finalizeCollectionSession()
    expect(store.session?.status).toBe('completed')
    expect(fetchMock).toHaveBeenCalledWith('/api/search-sessions/123/finalize', expect.objectContaining({ method: 'POST' }))
  })

  it('restores session, variant and preview in order', async () => {
    localStorage.setItem('lastSessionId', '123')
    localStorage.setItem('lastVariantId', '7')
    const requested: string[] = []
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      requested.push(url)
      if (url === '/api/search-sessions/123') return jsonResponse(session)
      if (url === '/api/catalog/variants/7') return jsonResponse(variant)
      if (url === '/api/search-sessions/123/result') return jsonResponse(preview)
      throw new Error(`unexpected request: ${url}`)
    }))

    const store = useComparisonStore()
    await store.restoreCollectionSession()

    expect(requested).toEqual([
      '/api/search-sessions/123',
      '/api/catalog/variants/7',
      '/api/search-sessions/123/result',
    ])
    expect(store.session?.id).toBe(123)
    expect(useCatalogStore().confirmedVariant).toEqual(variant)
  })

  it('clears stale ids on 404 but keeps them on a network error', async () => {
    localStorage.setItem('lastSessionId', '123')
    localStorage.setItem('lastVariantId', '7')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(jsonResponse({ detail: 'missing' }, 404)))
    const store = useComparisonStore()

    await store.restoreCollectionSession()
    expect(localStorage.getItem('lastSessionId')).toBeNull()
    expect(localStorage.getItem('lastVariantId')).toBeNull()

    localStorage.setItem('lastSessionId', '123')
    localStorage.setItem('lastVariantId', '7')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch')))
    await store.restoreCollectionSession()
    expect(localStorage.getItem('lastSessionId')).toBe('123')
    expect(localStorage.getItem('lastVariantId')).toBe('7')
  })
})
