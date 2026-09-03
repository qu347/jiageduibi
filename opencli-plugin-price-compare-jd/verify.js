import { AuthRequiredError, CommandExecutionError, EmptyResultError } from '@jackwener/opencli/errors'
import { cli, Strategy } from '@jackwener/opencli/registry'

import {
  extractVerifiedOffer,
  extractSearchRows,
  normalizeSearchRows,
  normalizeVerifiedOffer,
  pageFailureCode,
  regionLabelCandidates,
  regionListLoading,
  regionOpenerSelector,
  regionSelectionConfirmed,
  regionSelectionPath,
  searchCandidatesToVerifiedOffers,
  waitForSearchResults,
} from './lib/jd-page.js'


async function exactTextSelector(page, wantedText) {
  return page.evaluate((wantedValues) => {
    const normalize = (value) => String(value || '').replace(/\s+/g, '').trim()
    const wanted = new Set(wantedValues.map(normalize))
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const panels = Array.from(document.querySelectorAll(
      '#area-selector, .ui-area-content-wrap, [class*="jd_area_wrap_"]',
    )).filter(visible)
    const nodes = panels.flatMap((panel) => Array.from(panel.querySelectorAll(
      '[data-value], [data-id], [data-code], a, button, li, span',
    ))).filter((node) => visible(node) && wanted.has(normalize(node.textContent)))
    const element = nodes[0]
    if (!element) return null
    if (element.id) return `#${CSS.escape(element.id)}`
    for (const attribute of ['data-value', 'data-id', 'data-code']) {
      const value = element.getAttribute(attribute)
      if (value) return `${element.tagName.toLowerCase()}[${attribute}="${CSS.escape(value)}"]`
    }
    const path = []
    let current = element
    while (current && current !== document.body) {
      const siblings = Array.from(current.parentElement?.children || []).filter(
        (sibling) => sibling.tagName === current.tagName,
      )
      const position = siblings.indexOf(current) + 1
      path.unshift(`${current.tagName.toLowerCase()}:nth-of-type(${position})`)
      current = current.parentElement
    }
    return `body > ${path.join(' > ')}`
  }, Array.isArray(wantedText) ? wantedText : [wantedText])
}


async function pageMarkers(page) {
  return page.evaluate(() => ({
    title: document.title,
    bodyText: (document.body?.innerText || '').slice(0, 20000),
  }))
}


function raisePageFailure(code) {
  if (code === 'AUTH_REQUIRED') throw new AuthRequiredError('jd.com', '请先在 Chrome 登录京东')
  if (code === 'CAPTCHA') throw new CommandExecutionError('CAPTCHA: 请在 Chrome 完成京东安全验证')
  if (code === 'NETWORK_ERROR') throw new CommandExecutionError('NETWORK_ERROR: 京东商品请求失败，请检查网络或稍后重试')
  if (code === 'RATE_LIMITED') throw new CommandExecutionError('RATE_LIMITED: 京东访问频繁，请稍后恢复采集')
  if (code === 'PAGE_CHANGED') throw new CommandExecutionError('PAGE_CHANGED: 京东商品页当前不可读取')
}


async function waitForRegionOption(page, part) {
  const labels = regionLabelCandidates(part)
  for (let attempt = 0; attempt < 16; attempt += 1) {
    const selector = await exactTextSelector(page, labels)
    if (selector) return selector
    await page.wait(0.5)
  }
  if (await page.evaluate(regionListLoading)) {
    throw new CommandExecutionError('NETWORK_ERROR: 京东地区列表加载失败，可能受代理或网络限制')
  }
  throw new CommandExecutionError(`UNSUPPORTED_REGION: 无法选择 ${part}`)
}


async function chooseRegion(page, province, city, district, street) {
  const opener = await page.evaluate(regionOpenerSelector)
  if (!opener) throw new CommandExecutionError('UNSUPPORTED_REGION: 找不到京东地区选择器')
  await page.click(opener)
  await page.wait(0.4)

  const newAddressTab = await exactTextSelector(page, '选择新地址')
  if (newAddressTab) {
    await page.click(newAddressTab)
    await page.wait(0.4)
    const firstRegionTab = await page.evaluate(() => {
      const tab = document.querySelector('[class*="jd_area_wrap_"] a[data-id]')
      return tab?.getAttribute('data-id')
        ? `[class*="jd_area_wrap_"] a[data-id="${tab.getAttribute('data-id')}"]`
        : null
    })
    if (firstRegionTab) {
      await page.click(firstRegionTab)
      await page.wait(0.4)
    }
  }

  for (const part of regionSelectionPath(province, city, district, street)) {
    const selector = await waitForRegionOption(page, part)
    await page.click(selector)
    await page.wait(0.4)
  }

  await page.wait(1)

  const state = await page.evaluate((openerSelector) => {
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const panels = Array.from(document.querySelectorAll(
      '#area-selector, .ui-area-content-wrap, [class*="jd_area_wrap_"]',
    )).filter(visible)
    const selectedArea = document.querySelector(openerSelector)?.textContent || ''
    const pending = panels.some((panel) => /请选择/.test(panel.textContent || ''))
    return { selectedArea, pending }
  }, opener)
  if (!regionSelectionConfirmed({ district, street }, state)) {
    throw new CommandExecutionError('PAGE_CHANGED: 页面未确认目标区县和街道')
  }
}


const VERIFIED_COLUMNS = [
  'platform_sku_id',
  'title',
  'product_url',
  'shop_name',
  'platform_shop_id',
  'shop_type',
  'listed_price_cents',
  'sale_price_cents',
  'merchant_discount_cents',
  'platform_coupon_cents',
  'member_discount_cents',
  'payment_discount_cents',
  'subsidy_amount_cents',
  'subsidy_status',
  'shipping_fee_cents',
  'installation_fee_cents',
  'conditional_price_cents',
  'stock_status',
  'captured_at',
]


cli({
  site: 'price-compare-jd',
  name: 'verify',
  description: 'Read one JD item price and stock for a representative region',
  domain: 'item.jd.com',
  strategy: Strategy.UI,
  access: 'read',
  browser: true,
  args: [
    { name: 'sku', positional: true, required: true, help: 'JD SKU' },
    { name: 'province', required: true, help: 'Province display name' },
    { name: 'city', required: true, help: 'City display name' },
    { name: 'district', required: true, help: 'District display name' },
    { name: 'street', required: true, help: 'Street or town display name' },
  ],
  columns: VERIFIED_COLUMNS,
  func: async (page, { sku, province, city, district, street }) => {
    const normalizedSku = String(sku)
    if (!/^\d{5,30}$/.test(normalizedSku)) {
      throw new CommandExecutionError('PAGE_CHANGED: 京东 SKU 格式无效')
    }
    await page.goto(`https://item.jd.com/${normalizedSku}.html`)
    let markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))

    await chooseRegion(page, String(province), String(city), String(district), String(street))
    markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))

    const raw = await page.evaluate(extractVerifiedOffer, normalizedSku)
    const offer = normalizeVerifiedOffer(raw)
    if (!offer) throw new CommandExecutionError('PAGE_CHANGED: 京东商品价格结构未找到')
    return [offer]
  },
})


cli({
  site: 'price-compare-jd',
  name: 'verify-region',
  description: 'Read allowed JD candidate prices for one representative region',
  domain: 'search.jd.com',
  strategy: Strategy.UI,
  access: 'read',
  browser: true,
  args: [
    { name: 'query', positional: true, required: true, help: 'Exact product model query' },
    { name: 'skus', required: true, help: 'Comma-separated allowed JD SKUs' },
    { name: 'province', required: true, help: 'Province display name' },
    { name: 'city', required: true, help: 'City display name' },
    { name: 'district', required: true, help: 'District display name' },
    { name: 'street', required: true, help: 'Street or town display name' },
  ],
  columns: VERIFIED_COLUMNS,
  func: async (page, { query, skus, province, city, district, street }) => {
    const normalizedQuery = String(query).replace(/\s+/g, ' ').trim()
    const allowedSkus = [...new Set(String(skus).split(',').map((sku) => sku.trim()).filter(Boolean))]
    if (!normalizedQuery || normalizedQuery.length > 200 || !allowedSkus.length || allowedSkus.length > 50) {
      throw new CommandExecutionError('PAGE_CHANGED: 地区批量核验参数无效')
    }
    if (allowedSkus.some((sku) => !/^\d{5,30}$/.test(sku))) {
      throw new CommandExecutionError('PAGE_CHANGED: 京东 SKU 格式无效')
    }

    await page.goto(`https://search.jd.com/Search?keyword=${encodeURIComponent(normalizedQuery)}`)
    let markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
    try {
      await waitForSearchResults(page)
    } catch {
      markers = await pageMarkers(page)
      raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
      throw new CommandExecutionError('PAGE_CHANGED: 京东搜索结果结构未找到')
    }

    await chooseRegion(page, String(province), String(city), String(district), String(street))
    markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
    try {
      await waitForSearchResults(page)
    } catch {
      markers = await pageMarkers(page)
      raisePageFailure(pageFailureCode(markers.title, markers.bodyText))
      throw new CommandExecutionError('PAGE_CHANGED: 京东地区搜索结果结构未找到')
    }

    const rows = normalizeSearchRows(await page.evaluate(extractSearchRows, 50), 50)
    const offers = searchCandidatesToVerifiedOffers(rows, allowedSkus, new Date().toISOString())
    if (!offers.length) {
      throw new EmptyResultError('price-compare-jd verify-region', '该地区未显示候选白名单商品')
    }
    return offers
  },
})
