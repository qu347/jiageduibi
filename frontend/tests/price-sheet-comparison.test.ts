import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import PriceSheetComparison from '../src/components/PriceSheetComparison.vue'
import { usePriceSheetStore } from '../src/stores/price-sheets'


describe('price sheet comparison', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
  })

  it('shows editable color-level OCR rows and starts with the reviewed table', async () => {
    const store = usePriceSheetStore()
    store.detail = {
      batch: {
        id: 12, file_name: 'sheet.png', price_date: '2026-09-03', date_inferred: true,
        status: 'reviewing', recognized_count: 1, selected_count: 1, completed_item_count: 0,
        partial_item_count: 0, failed_item_count: 0, lower_price_count: 0, current_item_id: null,
        pause_requested: false, stop_requested: false, last_error_code: null, last_error_summary: null,
        created_at: '', updated_at: '', started_at: null, finished_at: null,
      },
      items: [{
        id: 1, batch_id: 12, sequence: 1, selected: true, brand: 'Apple', model_name: 'iPhone 17',
        storage: '256GB', color: '黑色', today_price_cents: 590000, raw_text: '17-256G 黑5900',
        confidence: 0.72, review_required: true, status: 'reviewing', candidate_count: 0,
        total_region_count: 0, completed_region_count: 0, failed_region_count: 0,
        lowest_price_cents: null, last_error_code: null, last_error_summary: null,
        started_at: null, finished_at: null,
      }],
      tasks: [],
    }
    const save = vi.spyOn(store, 'saveItems').mockResolvedValue()
    const start = vi.spyOn(store, 'start').mockResolvedValue()
    const wrapper = mount(PriceSheetComparison)

    expect(wrapper.text()).toContain('核对识别结果')
    expect(wrapper.text()).toContain('黑色')
    expect(wrapper.text()).toContain('低置信度')
    await wrapper.get('[data-testid="start-price-sheet"]').trigger('click')

    expect(save).toHaveBeenCalledOnce()
    expect(start).toHaveBeenCalledOnce()
  })

  it('shows only one nationwide low result with color, street and price breakdown', () => {
    const store = usePriceSheetStore()
    store.detail = {
      batch: {
        id: 12, file_name: 'sheet.png', price_date: '2026-09-03', date_inferred: false,
        status: 'completed', recognized_count: 1, selected_count: 1, completed_item_count: 1,
        partial_item_count: 0, failed_item_count: 0, lower_price_count: 1, current_item_id: null,
        pause_requested: false, stop_requested: false, last_error_code: null, last_error_summary: null,
        created_at: '', updated_at: '', started_at: '', finished_at: '',
      },
      items: [], tasks: [],
    }
    store.results = {
      lower_results: [{
        item_id: 1, model_name: 'iPhone 17', storage: '256GB', color: '黑色',
        today_price_cents: 590000, status: 'lower', coverage: '31/31', region_code: '110100',
        address: '北京市 / 朝阳区 / 奥运村街道', platform_sku_id: '1', title: 'Apple iPhone 17',
        product_url: 'https://item.jd.com/1.html', shop_name: '京东自营', sale_price_cents: 550000,
        platform_coupon_cents: 10000, subsidy_amount_cents: 40000, shipping_fee_cents: 0,
        trusted_price_cents: 500000, sale_price_includes_coupon: false,
        sale_price_includes_subsidy: false, captured_at: '2026-09-03T00:00:00Z',
      }],
      not_lower_items: [], partial_items: [],
    }

    const wrapper = mount(PriceSheetComparison)

    expect(wrapper.findAll('[data-testid="price-sheet-low-result"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('黑色')
    expect(wrapper.text()).toContain('奥运村街道')
    expect(wrapper.text()).toContain('31/31')
    expect(wrapper.text()).toContain('普通优惠券')
    expect(wrapper.text()).toContain('¥5,000')
  })
})
