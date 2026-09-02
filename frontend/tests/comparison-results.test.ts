import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterPanel from '../src/components/FilterPanel.vue'
import OfferTable from '../src/components/OfferTable.vue'
import { selectVisibleOffers } from '../src/stores/comparison'
import type { OfferView } from '../src/types/offers'


function offer(changes: Partial<OfferView>): OfferView {
  return {
    id: 1,
    search_session_id: 1,
    platform: 'jd',
    platform_sku_id: 'sku-1',
    title: 'Apple iPhone 17 256GB 全新国行',
    product_url: 'https://example.invalid/item',
    shop_name: '测试店铺',
    shop_type: 'self_operated',
    comparable_price_cents: 500000,
    confirmed_final_price_cents: 500000,
    estimated_final_price_cents: null,
    conditional_price_cents: null,
    subsidy_status: 'unknown',
    region_code: null,
    region_name: null,
    match_confidence: 100,
    excluded_reason: null,
    captured_at: '2026-09-02T00:00:00Z',
    source_type: 'fixture',
    ...changes,
  }
}


describe('comparison results', () => {
  it('renders confirmed and estimated subsidies as different states', () => {
    const wrapper = mount(OfferTable, { props: { offers: [
      offer({ id: 1, subsidy_status: 'confirmed', comparable_price_cents: 499900 }),
      offer({ id: 2, subsidy_status: 'estimated', comparable_price_cents: 509900, estimated_final_price_cents: 459900 }),
    ] } })

    expect(wrapper.text()).toContain('已确认国补')
    expect(wrapper.text()).toContain('预计国补')
    expect(wrapper.text()).toContain('¥5,099.00')
    expect(wrapper.text()).toContain('估算 ¥4,599.00')
  })

  it('does not mix conditional price into ordinary ranking by default', () => {
    const visible = selectVisibleOffers([
      offer({ id: 1, comparable_price_cents: 510000 }),
      offer({ id: 2, comparable_price_cents: 520000, conditional_price_cents: 480000 }),
    ], { includeConditional: false })

    expect(visible.map((item) => item.id)).toEqual([1, 2])
  })

  it('shows nationwide scope instead of a city selector', () => {
    const wrapper = mount(FilterPanel, {
      props: { includeConditional: false },
    })

    expect(wrapper.text()).toContain('全国比价')
    expect(wrapper.find('select').exists()).toBe(false)
  })

  it('shows the applicable region on the cheapest offer only', () => {
    const cheapest = offer({
      id: 1,
      comparable_price_cents: 499900,
      region_code: '310100',
      region_name: '上海市',
    })
    const runnerUp = offer({
      id: 2,
      comparable_price_cents: 504900,
      region_code: '440300',
      region_name: '广东省深圳市',
    })

    const wrapper = mount(OfferTable, { props: { offers: [cheapest, runnerUp] } })

    expect(wrapper.text()).toContain('最低价地区：上海市')
    expect(wrapper.text()).not.toContain('广东省深圳市')
  })
})
