export interface ProductVariant {
  id: number
  sku_code: string
  storage: string
  memory: string | null
  color: string
  region_version: string
  condition: string
}

export interface CatalogModel {
  id?: number
  model_code: string
  model_name: string
  series_name?: string
  brand?: string
  category?: string
  score?: number
  variants: ProductVariant[]
}

export interface CatalogSearchResponse {
  items: CatalogModel[]
}
