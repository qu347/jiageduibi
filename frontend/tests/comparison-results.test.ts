import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import FilterPanel from '../src/components/FilterPanel.vue'
import OfferTable from '../src/components/OfferTable.vue'
import { lowestOfferSummary, selectVisibleOffers } from '../src/stores/comparison'
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

  it('does not mix conditional price into ordinary ranking when it is shown', () => {
    const offers = [
      offer({ id: 1, comparable_price_cents: 510000 }),
      offer({ id: 2, comparable_price_cents: 520000, conditional_price_cents: 480000 }),
    ]

    expect(selectVisibleOffers(offers, { includeConditional: false }).map((item) => item.id)).toEqual([1, 2])
    expect(selectVisibleOffers(offers, { includeConditional: true }).map((item) => item.id)).toEqual([1, 2])
  })

  it('shows nationwide scope instead of a city selector', () => {
    const wrapper = mount(FilterPanel, {
      props: { includeConditional: false },
    })

    expect(wrapper.text()).toContain('全国比价')
    expect(wrapper.find('select').exists()).toBe(false)
  })

  it('shows every applicable region and summarizes tied cheapest regions', () => {
    const cheapest = offer({
      id: 1,
      comparable_price_cents: 499900,
      region_code: '310100',
      region_name: '上海市',
    })
    const runnerUp = offer({
      id: 2,
      comparable_price_cents: 499900,
      region_code: '110100',
      region_name: '北京市',
    })

    const wrapper = mount(OfferTable, { props: { offers: [cheapest, runnerUp] } })

    expect(wrapper.text()).toContain('本次已采集范围最低价：上海市、北京市')
    expect(wrapper.findAll('[data-testid="offer-region"]').map((item) => item.text())).toEqual([
      '适用地区：上海市',
      '适用地区：北京市',
    ])
    expect(wrapper.findAll('.rank.best')).toHaveLength(2)
  })

  it('labels unknown regions and does not claim a minimum without a reliable price', () => {
    const offers = [
      offer({ id: 1, comparable_price_cents: null }),
      offer({ id: 2, comparable_price_cents: null, region_code: '310100' }),
    ]
    const wrapper = mount(OfferTable, { props: { offers } })

    expect(wrapper.text()).toContain('地区未确认')
    expect(wrapper.text()).toContain('暂无可靠可比价')
    expect(wrapper.text()).not.toContain('本次已采集范围最低价')
    expect(wrapper.findAll('.rank.best')).toHaveLength(0)
    expect(lowestOfferSummary(offers)).toEqual({ price: null, regions: [] })
  })

  it('shows five per platform-region and expands to ten without resorting', async () => {
    const offers = Array.from({ length: 10 }, (_value, index) => offer({
      id: index + 1,
      platform_sku_id: `sku-${index + 1}`,
      region_code: '110100',
      region_name: '北京市',
      comparable_price_cents: 500000 + index * 100,
      confirmed_final_price_cents: 500000 + index * 100,
      source_type: 'browser',
    }))
    const wrapper = mount(OfferTable, { props: { offers } })

    expect(wrapper.findAll('[data-testid="offer-row"]')).toHaveLength(5)
    await wrapper.get('[data-testid="expand-region-offers"]').trigger('click')
    expect(wrapper.findAll('[data-testid="offer-row"]')).toHaveLength(10)
    expect(wrapper.findAll('[data-testid="offer-row"]').map((row) => row.attributes('data-offer-id')))
      .toEqual(offers.map((item) => String(item.id)))
    expect(wrapper.text()).toContain('浏览器核验')
    expect(wrapper.text()).toContain('采集时间')
    expect(wrapper.text()).toContain('本次已采集范围最低价')
  })
})
