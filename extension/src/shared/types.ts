export interface ExtensionStorage {
  get(key: string): Promise<string | undefined>
  set(key: string, value: string): Promise<void>
  remove(key: string): Promise<void>
}

export interface PairingApi {
  pair(code: string): Promise<{ token: string }>
}

export type BackgroundMessage =
  | { type: 'PING' }
  | { type: 'CAPTURE_ACTIVE_TAB'; searchSessionId: number }
