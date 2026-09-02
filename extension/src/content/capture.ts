import { captureCurrentDocument, type ParseResult } from '../parsers'


chrome.runtime.onMessage.addListener((message: { type?: string }, _sender, sendResponse) => {
  if (message.type !== 'CAPTURE_PAGE') return false
  const result: ParseResult = captureCurrentDocument(document, new URL(window.location.href))
  sendResponse(result)
  return false
})
