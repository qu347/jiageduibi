import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { describe, expect, it } from 'vitest'

import { jdParser } from '../src/parsers/jd'
import { pddParser } from '../src/parsers/pdd'
import { taobaoParser } from '../src/parsers/taobao'


function fixtureDocument(path: string): Document {
  const html = readFileSync(resolve(import.meta.dirname, '../../fixtures', path), 'utf8')
  return new DOMParser().parseFromString(html, 'text/html')
}


describe('fixture parsers', () => {
  it.each([
    [jdParser, 'jd/search-page.html', 'https://search.jd.com/Search', 549900],
    [taobaoParser, 'taobao/search-page.html', 'https://s.taobao.com/search', 504900],
    [pddParser, 'pdd/search-page.html', 'https://mobile.yangkeduo.com/search_result.html', 509900],
  ] as const)('parses %s fixture', (parser, path, url, expectedPrice) => {
    const result = parser.parse(fixtureDocument(path), new URL(url))
    expect(result.status).toBe('ok')
    if (result.status === 'ok') {
      expect(result.items).toHaveLength(1)
      expect(result.items[0]?.sale_price_cents).toBe(expectedPrice)
      expect(result.items[0]?.platform).toBe(parser.platform)
    }
  })

  it('returns missing_price instead of guessing', () => {
    const document = fixtureDocument('jd/search-page-missing-price.html')
    expect(jdParser.parse(document, new URL('https://search.jd.com/Search')).status).toBe('missing_price')
  })
})
