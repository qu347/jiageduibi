import type { ApiErrorBody } from './offers'

export type PriceSheetBatchStatus =
  | 'reviewing' | 'queued' | 'running' | 'paused' | 'waiting_user'
  | 'completed' | 'completed_partial' | 'stopped' | 'failed'

export interface PriceSheetBatchView {
  id: number
  file_name: string
  price_date: string
  date_inferred: boolean
  status: PriceSheetBatchStatus
  recognized_count: number
  selected_count: number
  completed_item_count: number
  partial_item_count: number
  failed_item_count: number
  lower_price_count: number
  current_item_id: number | null
  pause_requested: boolean
  stop_requested: boolean
  last_error_code: string | null
  last_error_summary: string | null
  created_at: string
  updated_at: string
  started_at: string | null
  finished_at: string | null
}

export interface PriceSheetItemView {
  id: number
  batch_id: number
  sequence: number
  selected: boolean
  brand: string
  model_name: string
  storage: string
  color: string
  today_price_cents: number
  raw_text: string
  confidence: number
  review_required: boolean
  status: string
  candidate_count: number
  total_region_count: number
  completed_region_count: number
  failed_region_count: number
  lowest_price_cents: number | null
  last_error_code: string | null
  last_error_summary: string | null
  started_at: string | null
  finished_at: string | null
}

export interface PriceSheetRegionTaskView {
  id: number
  price_sheet_item_id: number
  region_code: string
  province: string
  city: string
  district: string
  street: string
  sequence: number
  status: string
  attempts: number
  verified_candidate_count: number
  lowest_result_cents: number | null
  error_code: string | null
  error_summary: string | null
  started_at: string | null
  finished_at: string | null
}

export interface PriceSheetCheckoutCurrentView {
  platform_sku_id: string
  region_code: string
  address: string
  entry_mode: string | null
}

export interface PriceSheetCheckoutProgressView {
  stage: string
  candidate_count: number
  task_total: number
  task_finished: number
  verified_count: number
  conditional_count: number
  address_required_count: number
  unavailable_count: number
  failed_count: number
  skipped_count: number
  cart_attention_required: boolean
  current: PriceSheetCheckoutCurrentView | null
}

export interface PriceSheetBatchDetail {
  batch: PriceSheetBatchView
  items: PriceSheetItemView[]
  tasks: PriceSheetRegionTaskView[]
  checkout_progress: PriceSheetCheckoutProgressView
}

export interface PriceSheetResultView {
  item_id: number
  model_name: string
  storage: string
  color: string
  today_price_cents: number
  status: string
  coverage: string
  region_code: string | null
  address: string | null
  platform_sku_id: string | null
  title: string | null
  product_url: string | null
  shop_name: string | null
  entry_mode: string | null
  price_status: string | null
  quantity: number | null
  target_only: boolean | null
  line_original_price_cents: number | null
  line_sale_price_cents: number | null
  merchant_discount_cents: number | null
  ordinary_coupon_cents: number | null
  subsidy_amount_cents: number | null
  shipping_fee_cents: number | null
  payable_price_cents: number | null
  discount_summary: string | null
  conditional_reason: string | null
  cart_restored: boolean | null
  failed_count: number
  captured_at: string | null
}

export interface PriceSheetResultsView {
  lower_results: PriceSheetResultView[]
  not_lower_items: PriceSheetResultView[]
  partial_items: PriceSheetResultView[]
}

export type PriceSheetError = ApiErrorBody
