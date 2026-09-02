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
  comparison_scope: 'national' | 'regional'
  include_conditional: boolean
  status: string
  created_at: string
  finalized_at: string | null
}

export interface ComparisonResult {
  id: number
  comparison_scope: 'national' | 'regional'
  status: string
  offers: OfferView[]
  excluded_count: number
}

export interface CreateSearchCommand {
  variant_id: number
  region_code: string | null
  comparison_scope: 'national'
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

export type CollectionRunStatus =
  | 'queued'
  | 'running'
  | 'paused'
  | 'waiting_user'
  | 'completed'
  | 'completed_partial'
  | 'stopped'
  | 'failed'

export type CollectionRegionTaskStatus =
  | 'queued'
  | 'running'
  | 'waiting_user'
  | 'completed'
  | 'failed'
  | 'skipped'

export interface CollectionRunView {
  id: number
  search_session_id: number
  platform: 'jd'
  status: CollectionRunStatus
  stage: string
  candidate_source: string
  candidate_count: number
  selected_candidate_count: number
  total_region_count: number
  completed_region_count: number
  failed_region_count: number
  skipped_region_count: number
  current_region_code: string | null
  pause_requested: boolean
  stop_requested: boolean
  last_error_code: string | null
  last_error_summary: string | null
  started_at: string | null
  updated_at: string
  finished_at: string | null
}

export interface CollectionRegionTaskView {
  id: number
  collection_run_id: number
  region_code: string
  province: string
  city: string
  district: string
  sequence: number
  status: CollectionRegionTaskStatus
  attempts: number
  verified_candidate_count: number
  accepted_offer_count: number
  error_code: string | null
  error_summary: string | null
  started_at: string | null
  finished_at: string | null
}

export interface AutomationEnvironment {
  agent_reach_available: boolean
  opencli_available: boolean
  browser_bridge_ready: boolean
  plugin_ready: boolean
  safe_message: string
}
