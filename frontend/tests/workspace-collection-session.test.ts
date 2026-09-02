import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import WorkspacePage from '../src/pages/WorkspacePage.vue'
import { useCatalogStore } from '../src/stores/catalog'
import { useComparisonStore } from '../src/stores/comparison'


function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}


describe('workspace collection session', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('creates, copies and completes a national collection session', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const comparison = useComparisonStore()
    const restore = vi.spyOn(comparison, 'restoreCollectionSession')
    const clipboard = { writeText: vi.fn().mockResolvedValue(undefined) }
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: clipboard })
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/api/search-sessions') {
        return jsonResponse({
          id: 123,
          variant_id: 7,
          region_code: null,
          comparison_scope: 'national',
          include_conditional: false,
          status: 'collecting',
          created_at: '2026-09-02T00:00:00Z',
          finalized_at: null,
        }, 201)
      }
      if (url === '/api/search-sessions/123/finalize') {
        return jsonResponse({ id: 123, comparison_scope: 'national', status: 'completed', offers: [], excluded_count: 0 })
      }
      throw new Error(`unexpected request: ${url}`)
    }))
    const wrapper = mount(WorkspacePage, { global: { plugins: [pinia] } })

    expect(restore).toHaveBeenCalledOnce()
    expect(wrapper.get('[data-testid="create-collection-session"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="run-fixture-comparison"]').attributes('disabled')).toBeDefined()

    useCatalogStore().confirmedVariant = {
      id: 7,
      sku_code: 'APPLE_IPHONE_17_256_CN_NEW_ANY',
      storage: '256GB',
      memory: null,
      color: '不限',
      region_version: '中国大陆国行',
      condition: '全新',
    }
    await nextTick()
    await wrapper.get('[data-testid="create-collection-session"]').trigger('click')
    await flushPromises()

    expect(wrapper.get('[data-testid="collection-session-id"]').text()).toContain('123')
    expect(wrapper.text()).toContain('采集中')
    expect(wrapper.text()).toContain('全国')
    expect(wrapper.text()).toContain('APPLE_IPHONE_17_256_CN_NEW_ANY')
    await wrapper.get('[data-testid="copy-session-id"]').trigger('click')
    expect(clipboard.writeText).toHaveBeenCalledWith('123')

    await wrapper.get('[data-testid="finalize-session"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="finalize-session"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('固定夹具，不代表真实平台价格')
  })
})
