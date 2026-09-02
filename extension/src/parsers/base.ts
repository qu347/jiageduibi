export type PlatformCode = 'jd' | 'taobao' | 'pdd'

export interface RawOfferCandidate {
  platform: PlatformCode
  title: string
  platform_product_id: string
  platform_sku_id: string
  platform_shop_id: string
  shop_name: string
  shop_type: 'self_operated' | 'official_flagship' | 'authorized' | 'third_party'
  product_url: string
  sale_price_cents: number
  captured_at: string
}

export type ParseResult =
  | { status: 'ok'; items: RawOfferCandidate[] }
  | { status: 'login_required' | 'captcha' | 'unsupported' | 'missing_price'; message: string }

export interface PlatformParser {
  readonly platform: PlatformCode
  readonly adapterVersion: string
  canHandle(url: URL): boolean
  parse(document: Document, url: URL): ParseResult
}

export function parseCents(text: string): number | null {
  const match = text.replace(/,/g, '').match(/(?:¥|￥)\s*(\d+(?:\.\d{1,2})?)/)
  if (!match?.[1]) return null
  const [yuan, fraction = ''] = match[1].split('.')
  return Number(yuan) * 100 + Number(fraction.padEnd(2, '0'))
}

export function pageFailure(document: Document): ParseResult | null {
  const text = document.body?.textContent ?? ''
  if (/请登录|登录后查看/.test(text)) return { status: 'login_required', message: '请先在当前平台手动登录' }
  if (/验证码|安全验证|滑块验证/.test(text)) return { status: 'captcha', message: '请先在页面完成验证码' }
  return null
}

export function textOf(element: Element | null): string {
  return element?.textContent?.trim() ?? ''
}
