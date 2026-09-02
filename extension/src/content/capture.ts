import { captureCurrentDocument, type ParseResult } from '../parsers'


export const CAPTURE_LISTENER_MARKER = '__personalSubsidyPriceCaptureInstalledV1'

interface CaptureRuntime {
  onMessage: {
    addListener(listener: (
      message: { type?: string },
      sender: unknown,
      sendResponse: (response: unknown) => void,
    ) => boolean): void
  }
}

type CaptureTarget = Record<string, unknown>


export function installCaptureListener(
  runtime: CaptureRuntime,
  capture: () => ParseResult,
  target: CaptureTarget,
): void {
  if (target[CAPTURE_LISTENER_MARKER]) return
  target[CAPTURE_LISTENER_MARKER] = true
  runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.type !== 'CAPTURE_PAGE') return false
    sendResponse(capture())
    return false
  })
}


if (typeof chrome !== 'undefined' && chrome.runtime?.onMessage) {
  installCaptureListener(
    chrome.runtime,
    () => captureCurrentDocument(document, new URL(window.location.href)),
    globalThis as unknown as CaptureTarget,
  )
}
