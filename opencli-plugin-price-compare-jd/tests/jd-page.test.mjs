import test from 'node:test'
import assert from 'node:assert/strict'
import { parseHTML } from 'linkedom'

import * as jdPage from '../lib/jd-page.js'


const {
  cents,
  normalizeSearchRows,
  normalizeVerifiedOffer,
  pageFailureCode,
  searchCandidatesToVerifiedOffers,
} = jdPage


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
    { sku: '4', title: '【准新机】Apple iPhone 17 256GB', price: '4999', url: '//item.jd.com/4.html' },
  ], 30)

  assert.deepEqual(rows.map((row) => row.platform_sku_id), ['1'])
  assert.equal(rows[0].initial_price_cents, 519900)
  assert.equal(rows[0].product_url, 'https://item.jd.com/1.html')
  assert.equal(rows[0].shop_type, 'self_operated')
})


test('extracts product rows from the current JD React search cards', () => {
  const { document } = parseHTML(`
    <div class="plugin_goodsContainer">
      <div class="plugin_goodsCardWrapper" data-sku="100209267857">
        <div class="_goods_title_container_ab12">
          <span title="Apple/苹果 iPhone 17 256GB 白色">Apple/苹果 iPhone 17 256GB 白色</span>
        </div>
        <div class="_container_cd34">
          <span class="_price_cd34"><i>¥</i><span>5,419</span></span>
          <span>国补领后价</span>
          <span>¥5,919</span>
        </div>
        <div class="_name_ef56"><span class="_limit_ef56">Apple产品京东自营旗舰店</span></div>
      </div>
    </div>
  `)

  const extracted = jdPage.extractSearchRows?.(3, document) ?? []
  const rows = normalizeSearchRows(extracted, 3)

  assert.deepEqual(rows, [{
    platform_sku_id: '100209267857',
    title: 'Apple/苹果 iPhone 17 256GB 白色',
    product_url: 'https://item.jd.com/100209267857.html',
    shop_name: 'Apple产品京东自营旗舰店',
    platform_shop_id: null,
    shop_type: 'self_operated',
    initial_price_cents: 541900,
  }])
})


test('finds the unique current JD region opener', () => {
  const { document } = parseHTML(`
    <div class="shipping-address"></div>
    <div class="billing-address"></div>
    <div id="area-2026"></div>
  `)

  assert.equal(jdPage.regionOpenerSelector?.(document), '#area-2026')
})


test('matches official region names to JD short labels', () => {
  assert.deepEqual(jdPage.regionLabelCandidates?.('北京市'), ['北京市', '北京'])
  assert.deepEqual(jdPage.regionLabelCandidates?.('新疆维吾尔自治区'), ['新疆维吾尔自治区', '新疆'])
  assert.deepEqual(jdPage.regionLabelCandidates?.('朝阳区'), ['朝阳区', '朝阳'])
})


test('builds four-level paths and collapses municipality duplicates', () => {
  assert.deepEqual(
    jdPage.regionSelectionPath?.('广东省', '广州市', '天河区', '天河南街道'),
    ['广东省', '广州市', '天河区', '天河南街道'],
  )
  assert.deepEqual(
    jdPage.regionSelectionPath?.('北京市', '北京市', '朝阳区', '奥运村街道'),
    ['北京市', '朝阳区', '奥运村街道'],
  )
})


test('requires both district and street with no pending selector', () => {
  const target = { district: '朝阳区', street: '奥运村街道' }
  assert.equal(jdPage.regionSelectionConfirmed?.(target, {
    selectedArea: '配送至 北京朝阳区奥运村街道',
    pending: false,
  }), true)
  assert.equal(jdPage.regionSelectionConfirmed?.(target, {
    selectedArea: '配送至 北京朝阳区',
    pending: true,
  }), false)
})


test('detects a stalled current JD region list', () => {
  const { document } = parseHTML('<div class="jd_area_wrap_hash"><i class="jd_loading_hash"></i></div>')
  assert.equal(jdPage.regionListLoading?.(document), true)
})


test('waits for JD results through the OpenCLI page contract', async () => {
  const calls = []
  const page = {
    wait(options) {
      calls.push(options)
      return Promise.resolve()
    },
  }

  await jdPage.waitForSearchResults?.(page, 12)

  assert.deepEqual(calls, [{
    selector: '#J_goodsList .gl-item, .plugin_goodsCardWrapper[data-sku]',
    timeout: 12,
  }])
})


test('detects login, captcha and unsupported page states', () => {
  assert.equal(pageFailureCode('京东登录', '请登录京东'), 'AUTH_REQUIRED')
  assert.equal(pageFailureCode('安全验证', '请完成滑块验证码'), 'CAPTCHA')
  assert.equal(pageFailureCode('商品页', '页面内容暂不可用'), 'PAGE_CHANGED')
  assert.equal(pageFailureCode('商品搜索', '抱歉由于网络异常导致无法搜索，请稍后再试'), 'NETWORK_ERROR')
  assert.equal(pageFailureCode('京东商品', 'Apple iPhone 17'), null)
  assert.equal(pageFailureCode('京东商品', '账户中心 退出登录 Apple iPhone 17'), null)
})


test('distinguishes JD rate limiting and unavailable item pages from missing region controls', () => {
  assert.equal(
    pageFailureCode('商品搜索', '抱歉由于访问频繁导致无法搜索，请稍后再试'),
    'RATE_LIMITED',
  )
  assert.equal(
    pageFailureCode('京东商品', '暂时无法展示该商品的信息，请稍后重试'),
    'PAGE_CHANGED',
  )
})


test('maps only allowed visible search candidates to region offers', () => {
  const candidates = normalizeSearchRows([
    {
      sku: '1001',
      title: 'Apple iPhone 17 256GB 全新国行',
      price: '¥5,199.00',
      url: '//item.jd.com/1001.html',
      shop_name: '京东自营',
      platform_shop_id: 'self',
    },
    {
      sku: '2002',
      title: '其他商品',
      price: '¥99.00',
      url: '//item.jd.com/2002.html',
      shop_name: '其他店铺',
      platform_shop_id: 'other',
    },
  ], 10)

  const offers = searchCandidatesToVerifiedOffers(
    candidates,
    ['1001'],
    '2026-09-03T06:30:00.000Z',
  )

  assert.deepEqual(offers, [{
    platform_sku_id: '1001',
    title: 'Apple iPhone 17 256GB 全新国行',
    product_url: 'https://item.jd.com/1001.html',
    shop_name: '京东自营',
    platform_shop_id: 'self',
    shop_type: 'self_operated',
    listed_price_cents: null,
    sale_price_cents: 519900,
    merchant_discount_cents: 0,
    platform_coupon_cents: 0,
    member_discount_cents: 0,
    payment_discount_cents: 0,
    subsidy_amount_cents: 0,
    subsidy_status: 'unknown',
    shipping_fee_cents: 0,
    installation_fee_cents: 0,
    conditional_price_cents: null,
    stock_status: 'in_stock',
    captured_at: '2026-09-03T06:30:00.000Z',
  }])
})


test('extracts and normalizes the current JD item offer with explicit subsidy', () => {
  const { document } = parseHTML(`
    <div class="top-name" title="Apple产品京东自营旗舰店"></div>
    <span class="sku-title-name">Apple/苹果 iPhone 17 256GB 白色</span>
    <div class="product-price-panel">
      <span class="product-price--value">5419</span>
      <span class="product-price--gray-line-through">¥5919</span>
    </div>
    <div class="floor-item">国家补贴｜领后减￥500</div>
    <div class="logistics-delivery-time">现货，预计明日送达</div>
    <div class="logistics-service">京东物流 59元免基础运费</div>
  `)

  const raw = jdPage.extractVerifiedOffer?.('100209267857', document)
  const offer = normalizeVerifiedOffer(raw, '2026-09-03T03:00:00.000Z')

  assert.equal(offer.title, 'Apple/苹果 iPhone 17 256GB 白色')
  assert.equal(offer.shop_name, 'Apple产品京东自营旗舰店')
  assert.equal(offer.sale_price_cents, 541900)
  assert.equal(offer.listed_price_cents, 591900)
  assert.equal(offer.subsidy_amount_cents, 50000)
  assert.equal(offer.subsidy_status, 'confirmed')
  assert.equal(offer.shipping_fee_cents, 0)
  assert.equal(offer.stock_status, 'in_stock')
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
