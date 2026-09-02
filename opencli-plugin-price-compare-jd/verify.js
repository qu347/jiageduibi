import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors'
import { cli, Strategy } from '@jackwener/opencli/registry'

import { normalizeVerifiedOffer, pageFailureCode } from './lib/jd-page.js'


async function visibleSelector(page, selectors) {
  return page.evaluate((candidates) => {
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    for (const selector of candidates) {
      const element = Array.from(document.querySelectorAll(selector)).find(visible)
      if (element) return selector
    }
    return null
  }, selectors)
}


async function exactTextSelector(page, wantedText) {
  return page.evaluate((wanted) => {
    const normalize = (value) => String(value || '').replace(/\s+/g, '').trim()
    const visible = (element) => {
      const style = window.getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0
    }
    const nodes = Array.from(document.querySelectorAll(
      '[data-value], [data-id], [data-code], a, button, li, span',
    )).filter((node) => visible(node) && normalize(node.textContent) === normalize(wanted))
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
  }, wantedText)
}


async function pageMarkers(page) {
  return page.evaluate(() => ({
    title: document.title,
    bodyText: (document.body?.innerText || '').slice(0, 20000),
  }))
}


function raisePageFailure(code) {
  if (code === 'AUTH_REQUIRED') throw new AuthRequiredError('请先在 Chrome 登录京东')
  if (code === 'CAPTCHA') throw new CommandExecutionError('CAPTCHA: 请在 Chrome 完成京东安全验证')
  if (code === 'PAGE_CHANGED') throw new CommandExecutionError('PAGE_CHANGED: 京东商品页当前不可读取')
}


async function chooseRegion(page, province, city, district) {
  const opener = await visibleSelector(page, [
    '#area-selector',
    '.ui-area-text',
    '.delivery-address',
    '[class*="address"]',
  ])
  if (!opener) throw new CommandExecutionError('UNSUPPORTED_REGION: 找不到京东地区选择器')
  await page.click(opener)
  await page.wait(0.4)

  for (const part of [province, city, district]) {
    const selector = await exactTextSelector(page, part)
    if (!selector) throw new CommandExecutionError(`UNSUPPORTED_REGION: 无法选择 ${part}`)
    await page.click(selector)
    await page.wait(0.4)
  }

  const selectedArea = await page.evaluate(() => {
    const selectors = ['#area-selector', '.ui-area-text', '.delivery-address', '[class*="address"]']
    for (const selector of selectors) {
      const text = document.querySelector(selector)?.textContent?.replace(/\s+/g, '') || ''
      if (text) return text
    }
    return ''
  })
  if (!selectedArea.includes(String(district).replace(/\s+/g, ''))) {
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

    const raw = await page.evaluate((itemSku) => {
      const text = (...selectors) => {
        for (const selector of selectors) {
          const value = document.querySelector(selector)?.textContent?.replace(/\s+/g, ' ').trim()
          if (value) return value
        }
        return ''
      }
      const shopLink = document.querySelector('.name a, .J-hove-wrap a, [class*="shop"] a')
      return {
        sku: itemSku,
        title: text('.sku-name', '.itemInfo-wrap h1', 'h1'),
        shopName: shopLink?.textContent?.replace(/\s+/g, ' ').trim() || '未知店铺',
        shopId: shopLink?.getAttribute('data-shopid') || shopLink?.getAttribute('data-id') || null,
        salePrice: text('.summary-price .p-price', '.p-price .price', '[class*="price"] .price'),
        listedPrice: text('.summary-price .del', '.origin-price', '[class*="market-price"]'),
        stockText: text('#store-prompt', '#J-stock', '.store-prompt', '[class*="stock"]'),
        shippingText: text('#summary-service', '.delivery', '[class*="freight"]'),
        memberPrice: text('.plus-price', '[class*="member-price"]'),
      }
    }, normalizedSku)
    const offer = normalizeVerifiedOffer(raw)
    if (!offer) throw new CommandExecutionError('PAGE_CHANGED: 京东商品价格结构未找到')
    return [offer]
  },
})
