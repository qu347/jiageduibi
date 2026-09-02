import type {
  ExtensionStorage,
  IngestionSummary,
  SearchSessionView,
} from './types'


export const SEARCH_SESSION_STORAGE_KEY = 'searchSessionId'


export async function saveSearchSessionId(
  value: number,
  storage: ExtensionStorage,
): Promise<void> {
  if (!Number.isInteger(value) || value <= 0) throw new Error('采集会话 ID 必须是正整数')
  await storage.set(SEARCH_SESSION_STORAGE_KEY, String(value))
}


export async function loadSearchSessionId(storage: ExtensionStorage): Promise<number | null> {
  const stored = await storage.get(SEARCH_SESSION_STORAGE_KEY)
  if (!stored) return null
  const value = Number(stored)
  return Number.isInteger(value) && value > 0 ? value : null
}


export async function validateCollectionSession(
  id: number,
  backendUrl: string,
  fetcher: typeof fetch = fetch,
): Promise<SearchSessionView> {
  let response: Response
  try {
    response = await fetcher(`${backendUrl}/api/search-sessions/${id}`)
  } catch {
    throw new Error('无法连接本地服务，请先启动个人国补比价工具')
  }
  if (response.status === 404) throw new Error('采集会话不存在，请从工作台复制新的会话 ID')
  if (!response.ok) throw new Error(`本地服务无法校验采集会话（${response.status}）`)
  const session = await response.json() as SearchSessionView
  if (session.status !== 'collecting') throw new Error('采集会话已经完成，请在工作台新建会话')
  if (session.comparison_scope !== 'national') throw new Error('浏览器扩展仅支持全国采集会话')
  return session
}


export function formatIngestionSummary(summary: IngestionSummary, sessionId: number): string {
  const reasons = Object.entries(summary.exclusions)
    .map(([reason, count]) => `${reason}：${count}`)
    .join('，')
  if (summary.accepted_count === 0 && summary.excluded_count > 0) {
    return `会话 ${sessionId}：全部 ${summary.excluded_count} 条候选报价均被排除${reasons ? `（${reasons}）` : ''}`
  }
  return `会话 ${sessionId}：已接收 ${summary.accepted_count} 条，排除 ${summary.excluded_count} 条${reasons ? `（${reasons}）` : ''}`
}
