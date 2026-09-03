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
      if (url === '/api/automation/environment') {
        return jsonResponse({
          agent_reach_available: true,
          opencli_available: true,
          browser_bridge_ready: true,
          plugin_ready: true,
          safe_message: '自动采集环境可用',
        })
      }
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
    wrapper.unmount()
  })

  it('starts a JD nationwide run with one click and shows coverage', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    useCatalogStore().confirmedVariant = {
      id: 7,
      sku_code: 'APPLE_IPHONE_17_256_CN_NEW_ANY',
      storage: '256GB',
      memory: null,
      color: '不限',
      region_version: '中国大陆国行',
      condition: '全新',
    }
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url === '/api/automation/environment') {
        return jsonResponse({
          agent_reach_available: true,
          opencli_available: true,
          browser_bridge_ready: true,
          plugin_ready: true,
          safe_message: '自动采集环境可用',
        })
      }
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
      if (url === '/api/search-sessions/123/collection-runs') {
        expect(init).toEqual(expect.objectContaining({ method: 'POST' }))
        return jsonResponse({
          id: 8,
          search_session_id: 123,
          platform: 'jd',
          status: 'running',
          stage: 'verifying',
          candidate_source: 'browser',
          candidate_count: 30,
          selected_candidate_count: 12,
          total_region_count: 31,
          completed_region_count: 3,
          failed_region_count: 0,
          skipped_region_count: 0,
          current_region_code: '310100',
          pause_requested: false,
          stop_requested: false,
          last_error_code: null,
          last_error_summary: null,
          started_at: '2026-09-02T00:00:00Z',
          updated_at: '2026-09-02T00:01:00Z',
          finished_at: null,
        }, 201)
      }
      if (url === '/api/collection-runs/8/tasks') {
        return jsonResponse([{
          id: 9,
          collection_run_id: 8,
          region_code: '310100',
          province: '上海市',
          city: '上海市',
          district: '浦东新区',
          street: '陆家嘴街道',
          sequence: 9,
          status: 'running',
          attempts: 1,
          verified_candidate_count: 2,
          accepted_offer_count: 2,
          error_code: null,
          error_summary: null,
          started_at: '2026-09-02T00:01:00Z',
          finished_at: null,
        }])
      }
      if (url === '/api/search-sessions/123/result') {
        return jsonResponse({ id: 123, comparison_scope: 'national', status: 'collecting', offers: [], excluded_count: 0 })
      }
      throw new Error(`unexpected request: ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    const wrapper = mount(WorkspacePage, { global: { plugins: [pinia] } })
    await flushPromises()

    await wrapper.get('[data-testid="start-automatic-collection"]').trigger('click')
    await flushPromises()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/search-sessions/123/collection-runs',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(wrapper.get('[data-testid="automatic-progress"]').text()).toContain('已核验 3/31')
    expect(wrapper.text()).toContain('当前地区：上海市 / 浦东新区 / 陆家嘴街道')
    expect(localStorage.getItem('lastAutomaticRunId')).toBe('8')
    wrapper.unmount()
  })
})
