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
      checkout_progress: {
        stage: 'review', candidate_count: 0, task_total: 0, task_finished: 0,
        verified_count: 0, conditional_count: 0, address_required_count: 0,
        unavailable_count: 0, failed_count: 0, skipped_count: 0,
        cart_attention_required: false, current: null,
      },
    }
    const save = vi.spyOn(store, 'saveItems').mockResolvedValue()
    const start = vi.spyOn(store, 'start').mockResolvedValue()
    const wrapper = mount(PriceSheetComparison)

    expect(wrapper.text()).toContain('核对识别结果')
    expect(wrapper.text()).toContain('黑色')
    expect(wrapper.text()).toContain('请核对 · 识别置信度 72%')
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
      checkout_progress: {
        stage: 'checkout_verification', candidate_count: 20, task_total: 620, task_finished: 620,
        verified_count: 600, conditional_count: 10, address_required_count: 2,
        unavailable_count: 5, failed_count: 5, skipped_count: 5,
        cart_attention_required: false, current: null,
      },
    }
    store.results = {
      lower_results: [{
        item_id: 1, model_name: 'iPhone 17', storage: '256GB', color: '黑色',
        today_price_cents: 590000, status: 'lower', coverage: '31/31', region_code: '110100',
        address: '北京市 / 朝阳区 / 奥运村街道', platform_sku_id: '1', title: 'Apple iPhone 17',
        product_url: 'https://item.jd.com/1.html', shop_name: '京东自营', entry_mode: 'buy_now',
        price_status: 'verified', quantity: 1, target_only: true,
        line_original_price_cents: 590000, line_sale_price_cents: 550000,
        merchant_discount_cents: 10000, ordinary_coupon_cents: 10000,
        subsidy_amount_cents: 30000, shipping_fee_cents: 0, payable_price_cents: 500000,
        discount_summary: '店铺优惠 100 元；优惠券 100 元；国家补贴 300 元',
        conditional_reason: null, cart_restored: true, failed_count: 0,
        captured_at: '2026-09-03T00:00:00Z',
      }],
      not_lower_items: [], partial_items: [],
    }

    const wrapper = mount(PriceSheetComparison)

    expect(wrapper.findAll('[data-testid="price-sheet-low-result"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('黑色')
    expect(wrapper.text()).toContain('奥运村街道')
    expect(wrapper.text()).toContain('31/31')
    expect(wrapper.text()).toContain('普通优惠券')
    expect(wrapper.text()).toContain('结算应付')
    expect(wrapper.text()).toContain('¥5,000')
  })

  it('shows compact checkout progress, safety notice and sticky cart warning', () => {
    const store = usePriceSheetStore()
    store.detail = {
      batch: {
        id: 12, file_name: 'sheet.png', price_date: '2026-09-03', date_inferred: false,
        status: 'running', recognized_count: 1, selected_count: 1, completed_item_count: 0,
        partial_item_count: 0, failed_item_count: 0, lower_price_count: 0, current_item_id: 1,
        pause_requested: false, stop_requested: false, last_error_code: null, last_error_summary: null,
        created_at: '', updated_at: '', started_at: '', finished_at: null,
      },
      items: [{
        id: 1, batch_id: 12, sequence: 1, selected: true, brand: 'Apple', model_name: 'iPhone 17',
        storage: '256GB', color: '黑色', today_price_cents: 590000, raw_text: '', confidence: 1,
        review_required: false, status: 'running', candidate_count: 20, total_region_count: 31,
        completed_region_count: 4, failed_region_count: 8, lowest_price_cents: 500000,
        last_error_code: null, last_error_summary: null, started_at: '', finished_at: null,
      }],
      tasks: [],
      checkout_progress: {
        stage: 'checkout_verification', candidate_count: 20, task_total: 620, task_finished: 127,
        verified_count: 83, conditional_count: 11, address_required_count: 7,
        unavailable_count: 18, failed_count: 8, skipped_count: 25,
        cart_attention_required: true,
        current: {
          platform_sku_id: '100209267857', region_code: '110100',
          address: '北京市 / 朝阳区 / 奥运村街道', entry_mode: 'cart_fallback',
        },
      },
    }
    store.cartAttentionSeen = true

    const wrapper = mount(PriceSheetComparison)
    const text = wrapper.text()

    expect(text).toContain('结算页核价')
    expect(text).toContain('候选 20/20')
    expect(text).toContain('组合进度 127/620')
    expect(text).toContain('100209267857')
    expect(text).toContain('奥运村街道')
    expect(text).toContain('购物车回退')
    expect(text).toContain('已核验 83')
    expect(text).toContain('条件价 11')
    expect(text).toContain('需真实地址 7')
    expect(text).toContain('不可用 18')
    expect(text).toContain('失败 8')
    expect(text).toContain('跳过 25')
    expect(text).toContain('程序只读取结算预览，不会提交订单或付款')
    expect(text).toContain('购物车可能未完全恢复，请人工检查')
  })
})
