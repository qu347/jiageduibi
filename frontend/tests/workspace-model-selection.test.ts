import { createPinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import WorkspacePage from '../src/pages/WorkspacePage.vue'


describe('workspace model selection', () => {
  it('requires a standard variant before search creation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ items: [
        { model_code: 'APPLE_IPHONE_17', model_name: 'iPhone 17', variants: [
          { id: 1, sku_code: 'APPLE_IPHONE_17_256_CN_NEW_ANY', storage: '256GB', color: '不限', region_version: '中国大陆国行', condition: '全新' },
        ] },
        { model_code: 'APPLE_IPHONE_17_PRO', model_name: 'iPhone 17 Pro', variants: [] },
        { model_code: 'APPLE_IPHONE_17_PRO_MAX', model_name: 'iPhone 17 Pro Max', variants: [] },
      ] }),
    }))

    const wrapper = mount(WorkspacePage, { global: { plugins: [createPinia()] } })
    await wrapper.get('[data-test="keyword"]').setValue('苹果17')
    await wrapper.get('[data-test="search-models"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('iPhone 17 Pro Max')
    expect(wrapper.get('[data-test="create-search"]').attributes('disabled')).toBeDefined()
  })
})
