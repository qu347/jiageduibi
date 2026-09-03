import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors'
import { cli, Strategy } from '@jackwener/opencli/registry'

import {
  extractVerifiedOffer,
  normalizeVerifiedOffer,
  pageFailureCode,
  regionLabelCandidates,
  regionListLoading,
  regionOpenerSelector,
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
    const nodes = Array.from(document.querySelectorAll(
      '[data-value], [data-id], [data-code], a, button, li, span',
    )).filter((node) => visible(node) && wanted.has(normalize(node.textContent)))
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


async function chooseRegion(page, province, city, district) {
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

  for (const part of [province, city, district]) {
    const selector = await waitForRegionOption(page, part)
    await page.click(selector)
    await page.wait(0.4)
  }

  const selectedArea = await page.evaluate(() => {
    const selectors = [
      '#area-2026',
      '#area-selector',
      '.ui-area-text',
      '.delivery-address',
      '[class*="jd_area_wrap_"] [class*="jd_tab_item_"]',
    ]
    let combined = ''
    for (const selector of selectors) {
      const text = document.querySelector(selector)?.textContent?.replace(/\s+/g, '') || ''
      combined += text
    }
    return combined
  })
  if (!regionLabelCandidates(district).some((label) => selectedArea.includes(label))) {
    throw new CommandExecutionError('UNSUPPORTED_REGION: 页面未确认目标区县')
  }
}


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
  ],
  columns: [
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
  ],
  func: async (page, { sku, province, city, district }) => {
    const normalizedSku = String(sku)
    if (!/^\d{5,30}$/.test(normalizedSku)) {
      throw new CommandExecutionError('PAGE_CHANGED: 京东 SKU 格式无效')
    }
    await page.goto(`https://item.jd.com/${normalizedSku}.html`)
    let markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))

    await chooseRegion(page, String(province), String(city), String(district))
    markers = await pageMarkers(page)
    raisePageFailure(pageFailureCode(markers.title, markers.bodyText))

    const raw = await page.evaluate(extractVerifiedOffer, normalizedSku)
    const offer = normalizeVerifiedOffer(raw)
    if (!offer) throw new CommandExecutionError('PAGE_CHANGED: 京东商品价格结构未找到')
    return [offer]
  },
})
