export interface ExtensionStorage {
  get(key: string): Promise<string | undefined>
  set(key: string, value: string): Promise<void>
  remove(key: string): Promise<void>
}

export interface PairingApi {
  pair(code: string): Promise<{ token: string }>
}

export interface SearchSessionView {
  id: number
  variant_id: number
  region_code: string | null
  comparison_scope: 'national' | 'regional'
  include_conditional: boolean
  status: string
  created_at: string
  finalized_at: string | null
}

export interface IngestionSummary {
  platform: string
  accepted_count: number
  excluded_count: number
  exclusions: Record<string, number>
}

export type BackgroundMessage =
  | { type: 'PING' }
  | { type: 'CAPTURE_ACTIVE_TAB'; searchSessionId: number }
