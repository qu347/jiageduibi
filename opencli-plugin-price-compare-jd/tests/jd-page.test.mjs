import test from 'node:test'
import assert from 'node:assert/strict'

import {
  cents,
  normalizeSearchRows,
  normalizeVerifiedOffer,
  pageFailureCode,
} from '../lib/jd-page.js'


test('converts visible RMB text to integer cents', () => {
  assert.equal(cents('￥5,199.00'), 519900)
  assert.equal(cents('到手价 ¥4,999'), 499900)
  assert.equal(cents('月供 ¥199'), null)
  assert.equal(cents('定金 ¥100'), null)
})


test('deduplicates search rows by sku and rejects non-total prices', () => {
  const rows = normalizeSearchRows([
    {
      sku: '1',
      title: 'Apple iPhone 17 256GB 全新国行',
      price: '5199',
      url: '//item.jd.com/1.html',
      shop_name: '京东自营',
      platform_shop_id: 'self',
    },
    { sku: '1', title: 'duplicate', price: '5099', url: '//item.jd.com/1.html' },
    { sku: '2', title: 'iPhone 17 定金', price: '100', url: '//item.jd.com/2.html' },
    { sku: '3', title: 'iPhone 17 手机壳', price: '59', url: '' },
  ], 30)

  assert.deepEqual(rows.map((row) => row.platform_sku_id), ['1'])
  assert.equal(rows[0].initial_price_cents, 519900)
  assert.equal(rows[0].product_url, 'https://item.jd.com/1.html')
  assert.equal(rows[0].shop_type, 'self_operated')
})


test('detects login, captcha and unsupported page states', () => {
  assert.equal(pageFailureCode('京东登录', '请登录京东'), 'AUTH_REQUIRED')
  assert.equal(pageFailureCode('安全验证', '请完成滑块验证码'), 'CAPTCHA')
  assert.equal(pageFailureCode('商品页', '页面内容暂不可用'), 'PAGE_CHANGED')
  assert.equal(pageFailureCode('京东商品', 'Apple iPhone 17'), null)
  assert.equal(pageFailureCode('京东商品', '账户中心 退出登录 Apple iPhone 17'), null)
})


test('normalizes a verified visible offer without inventing discounts', () => {
  const offer = normalizeVerifiedOffer({
    sku: '1',
    title: 'Apple iPhone 17 256GB 全新国行',
    shopName: 'Apple 产品京东自营旗舰店',
    shopId: 'self',
    salePrice: '¥5,199.00',
    listedPrice: '¥5,299.00',
    stockText: '现货，23:00前下单预计明日送达',
    shippingText: '免运费',
    memberPrice: 'PLUS会员价 ¥5,099.00',
  }, '2026-09-02T10:00:00.000Z')

  assert.equal(offer.sale_price_cents, 519900)
  assert.equal(offer.listed_price_cents, 529900)
  assert.equal(offer.conditional_price_cents, 509900)
  assert.equal(offer.merchant_discount_cents, 0)
  assert.equal(offer.platform_coupon_cents, 0)
  assert.equal(offer.subsidy_status, 'unknown')
  assert.equal(offer.stock_status, 'in_stock')
})
