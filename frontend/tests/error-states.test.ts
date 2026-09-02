import { mount } from '@vue/test-utils'
import { expect, it } from 'vitest'

import ErrorNotice from '../src/components/ErrorNotice.vue'


it('renders the complete structured error', () => {
  const wrapper = mount(ErrorNotice, { props: { error: {
    what_happened: '平台报价导入失败',
    possible_cause: '搜索会话已结束',
    partial_saved: false,
    next_action: '新建会话后重试',
  } } })

  expect(wrapper.text()).toContain('平台报价导入失败')
  expect(wrapper.text()).toContain('搜索会话已结束')
  expect(wrapper.text()).toContain('没有保存部分数据')
  expect(wrapper.text()).toContain('新建会话后重试')
})
