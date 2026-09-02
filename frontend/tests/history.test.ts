import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'

import PriceTrend from '../src/components/PriceTrend.vue'


it('shows the historical minimum and an empty state', () => {
  const populated = mount(PriceTrend, { props: { points: [
    { offer_id: 1, platform: 'jd', comparable_price_cents: 519900, subsidy_status: 'unknown', captured_at: '2026-09-01T00:00:00Z', source_type: 'fixture' },
    { offer_id: 2, platform: 'taobao', comparable_price_cents: 499900, subsidy_status: 'confirmed', captured_at: '2026-09-02T00:00:00Z', source_type: 'fixture' },
  ] } })
  expect(populated.text()).toContain('历史最低价')
  expect(populated.text()).toContain('¥4,999.00')

  const empty = mount(PriceTrend, { props: { points: [] } })
  expect(empty.text()).toContain('暂无历史价格')
})
