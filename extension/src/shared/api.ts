import type { ExtensionStorage, PairingApi } from './types'


export const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8765'


export async function pairExtension(
  code: string,
  storage: ExtensionStorage,
  api: PairingApi,
): Promise<void> {
  const result = await api.pair(code)
  await storage.set('extensionToken', result.token)
  await storage.remove('pairingCode')
}


export function localPairingApi(backendUrl = DEFAULT_BACKEND_URL): PairingApi {
  return {
    async pair(code: string) {
      const response = await fetch(`${backendUrl}/api/extension/pair`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      })
      if (!response.ok) throw new Error(`配对失败（${response.status}）`)
      return response.json() as Promise<{ token: string }>
    },
  }
}


export const chromeStorage: ExtensionStorage = {
  async get(key) {
    const result = await chrome.storage.local.get(key)
    return typeof result[key] === 'string' ? result[key] : undefined
  },
  async set(key, value) {
    await chrome.storage.local.set({ [key]: value })
  },
  async remove(key) {
    await chrome.storage.local.remove(key)
  },
}
