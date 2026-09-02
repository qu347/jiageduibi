import { DEFAULT_BACKEND_URL } from '../shared/api'
import { formatIngestionSummary, validateCollectionSession } from '../shared/collection-session'
import type { ParseResult } from '../parsers'
import type { BackgroundMessage, IngestionSummary } from '../shared/types'


chrome.runtime.onMessage.addListener((message: BackgroundMessage, _sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ ok: true })
    return false
  }
  if (message.type === 'CAPTURE_ACTIVE_TAB') {
    void captureAndSubmit(message.searchSessionId).then(sendResponse).catch((error: unknown) => {
      sendResponse({
        status: 'unsupported',
        message: error instanceof Error ? error.message : '采集当前标签页失败',
      })
    })
    return true
  }
  return false
})


async function captureAndSubmit(searchSessionId: number): Promise<ParseResult | { status: 'submitted'; message: string }> {
  const stored = await chrome.storage.local.get(['extensionToken', 'backendUrl'])
  const token = typeof stored.extensionToken === 'string' ? stored.extensionToken : ''
  const backendUrl = typeof stored.backendUrl === 'string' ? stored.backendUrl : DEFAULT_BACKEND_URL
  if (!token) return { status: 'unsupported', message: '扩展尚未配对' }
  await validateCollectionSession(searchSessionId, backendUrl)

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  if (!tab?.id || !tab.url) return { status: 'unsupported', message: '当前标签页无法采集' }

  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['capture.js'] })
  const result = await chrome.tabs.sendMessage(tab.id, { type: 'CAPTURE_PAGE' }) as ParseResult
  if (result.status !== 'ok') return result

  const platform = result.items[0]?.platform
  if (!platform) return { status: 'unsupported', message: '页面没有可提交的商品' }

  const response = await fetch(`${backendUrl}/api/extension/offers`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      search_session_id: searchSessionId,
      platform,
      adapter_version: 'capture-v1',
      items: result.items,
    }),
  })
  if (!response.ok) return { status: 'unsupported', message: `本地服务拒绝报价（${response.status}）` }
  const summary = await response.json() as IngestionSummary
  return { status: 'submitted', message: formatIngestionSummary(summary, searchSessionId) }
}
