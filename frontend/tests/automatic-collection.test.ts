import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import AutomaticCollectionCard from '../src/components/AutomaticCollectionCard.vue'
import type { CollectionRunView } from '../src/types/offers'


function run(changes: Partial<CollectionRunView> = {}): CollectionRunView {
  return {
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
    ...changes,
  }
}


describe('automatic collection card', () => {
  it('shows nationwide progress, current province and candidate counts', () => {
    const wrapper = mount(AutomaticCollectionCard, {
      props: {
        run: run(),
        tasks: [{
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
        }],
        environment: null,
        canStart: true,
        loading: false,
      },
    })

    expect(wrapper.get('[data-testid="automatic-progress"]').text()).toContain('已核验 3/31')
    expect(wrapper.text()).toContain('当前地区：上海市 / 浦东新区 / 陆家嘴街道')
    expect(wrapper.text()).toContain('候选 12/30')
    expect(wrapper.find('[data-testid="pause-automatic-collection"]').exists()).toBe(true)
  })

  it('renders login or captcha waiting as a user action instead of failure', () => {
    const wrapper = mount(AutomaticCollectionCard, {
      props: {
        run: run({ status: 'waiting_user', last_error_code: 'captcha' }),
        tasks: [],
        environment: null,
        canStart: true,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('请在浏览器完成验证')
    expect(wrapper.find('[data-testid="resume-automatic-collection"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="pause-automatic-collection"]').exists()).toBe(false)
  })

  it('explains that nationwide collection runs in low-frequency batches', () => {
    const wrapper = mount(AutomaticCollectionCard, {
      props: {
        run: run(),
        tasks: [],
        environment: null,
        canStart: true,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('自动分批采集并留出冷却时间')
  })

  it('requires a ready local browser environment before starting', () => {
    const wrapper = mount(AutomaticCollectionCard, {
      props: {
        run: null,
        tasks: [],
        environment: {
          agent_reach_available: true,
          opencli_available: true,
          browser_bridge_ready: false,
          plugin_ready: true,
          safe_message: '请连接 OpenCLI 浏览器扩展',
        },
        canStart: true,
        loading: false,
      },
    })

    expect(wrapper.text()).toContain('请连接 OpenCLI 浏览器扩展')
    expect(wrapper.get('[data-testid="start-automatic-collection"]').attributes('disabled')).toBeDefined()
  })
})
