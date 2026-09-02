import { expect, it } from 'vitest'

import { selectParser } from '../src/parsers'


it.each([
  ['https://search.jd.com/Search?keyword=iphone17', 'jd'],
  ['https://s.taobao.com/search?q=iphone17', 'taobao'],
  ['https://mobile.yangkeduo.com/search_result.html?search_key=iphone17', 'pdd'],
])('routes %s to %s', (value, platform) => {
  expect(selectParser(new URL(value))?.platform).toBe(platform)
})


it('does not route unrelated sites', () => {
  expect(selectParser(new URL('https://example.com/search'))).toBeUndefined()
})
