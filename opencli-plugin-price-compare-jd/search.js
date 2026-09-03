import { AuthRequiredError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors'
import { cli, Strategy } from '@jackwener/opencli/registry'

import {
  extractSearchRows,
  normalizeSearchRows,
  pageFailureCode,
  waitForSearchResults,
} from './lib/jd-page.js'


async function pageMarkers(page) {
  return page.evaluate(() => ({
    title: document.title,
    bodyText: (document.body?.innerText || '').slice(0, 20000),
  }))
}


function raisePageFailure(code) {
  if (code === 'AUTH_REQUIRED') throw new AuthRequiredError('jd.com', '请先在 Chrome 登录京东')
  if (code === 'CAPTCHA') throw new CommandExecutionError('CAPTCHA: 请在 Chrome 完成京东安全验证')
  if (code === 'NETWORK_ERROR') throw new CommandExecutionError('NETWORK_ERROR: 京东搜索请求失败，请检查网络或稍后重试')
  if (code === 'PAGE_CHANGED') throw new CommandExecutionError('PAGE_CHANGED: 京东搜索页面当前不可读取')
}


cli({
  site: 'price-compare-jd',
  name: 'search',
  description: 'Search JD product candidates without account mutations',
  domain: 'search.jd.com',
  strategy: Strategy.UI,
  access: 'read',
  browser: true,
  args: [
    { name: 'query', positional: true, required: true, help: 'Exact product model query' },
    { name: 'limit', type: 'int', default: 30, help: 'Maximum candidates, 1-50' },
  ],
  columns: [
    'platform_sku_id',
    'title',
    'product_url',
    'shop_name',
    'platform_shop_id',
    'shop_type',
    'initial_price_cents',
  ],
  func: async (page, { query, limit = 30 }) => {
    const maximum = Math.min(50, Math.max(1, Number(limit)))
    await page.goto(`https://search.jd.com/Search?keyword=${encodeURIComponent(String(query))}`)

    let markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
    try {
      await waitForSearchResults(page)
    } catch {
      markers = await pageMarkers(page)
      raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
      throw new CommandExecutionError('PAGE_CHANGED: 京东搜索结果结构未找到')
    }

    const rows = await page.evaluate(extractSearchRows, maximum)
    const normalized = normalizeSearchRows(rows, maximum)
    if (!normalized.length) throw new EmptyResultError('price-compare-jd search', '请使用更准确的商品型号')
    return normalized
  },
})
