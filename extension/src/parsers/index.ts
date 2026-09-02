import { jdParser } from './jd'
import { pddParser } from './pdd'
import { taobaoParser } from './taobao'
import type { ParseResult, PlatformParser } from './base'


const parsers: PlatformParser[] = [jdParser, taobaoParser, pddParser]

export function selectParser(url: URL): PlatformParser | undefined {
  return parsers.find((parser) => parser.canHandle(url))
}

export function captureCurrentDocument(document: Document, url: URL): ParseResult {
  const parser = selectParser(url)
  return parser?.parse(document, url) ?? { status: 'unsupported', message: '当前网站不在支持范围内' }
}

export type { ParseResult, PlatformParser, RawOfferCandidate } from './base'
