export type SubsidyStatus = 'confirmed' | 'estimated' | 'ineligible' | 'not_eligible' | 'unknown'

export interface OfferView {
  id: number
  search_session_id: number
  platform: string
  platform_sku_id: string
  title: string
  product_url: string
  shop_name: string
  shop_type: 'self_operated' | 'official_flagship' | 'authorized' | 'third_party'
  comparable_price_cents: number | null
  confirmed_final_price_cents: number | null
  estimated_final_price_cents: number | null
  conditional_price_cents: number | null
  subsidy_status: SubsidyStatus
  region_code: string | null
  region_name: string | null
  match_confidence: number
  excluded_reason: string | null
  captured_at: string
  source_type: string
}

export interface SearchSessionView {
  id: number
  variant_id: number
  region_code: string | null
  include_conditional: boolean
  status: string
  created_at: string
  finalized_at: string | null
}

export interface ComparisonResult {
  id: number
  status: string
  offers: OfferView[]
  excluded_count: number
}

export interface CreateSearchCommand {
  variant_id: number
  region_code: string | null
  include_conditional: boolean
}

export interface PlatformOfferBatch {
  platform: string
  platform_name: string
  adapter_version: string
  source_type: string
  items: Record<string, unknown>[]
}

export interface ApiErrorBody {
  what_happened: string
  possible_cause: string
  partial_saved: boolean
  next_action: string
}

export interface HistoryPoint {
  offer_id: number
  platform: string
  comparable_price_cents: number | null
  subsidy_status: string
  captured_at: string
  source_type: string
}

export interface HistoryResponse {
  points: HistoryPoint[]
}

export interface PlatformStatus {
  platform: string
  fixture_status: 'passing' | 'failing' | 'not_run'
  live_status: 'not_validated'
}
