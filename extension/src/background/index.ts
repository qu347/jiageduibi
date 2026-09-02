import type { BackgroundMessage } from '../shared/types'


chrome.runtime.onMessage.addListener((message: BackgroundMessage, _sender, sendResponse) => {
  if (message.type === 'PING') {
    sendResponse({ ok: true })
    return false
  }
  if (message.type === 'CAPTURE_ACTIVE_TAB') {
    sendResponse({ ok: false, status: 'capture_not_implemented' })
    return false
  }
  return false
})
