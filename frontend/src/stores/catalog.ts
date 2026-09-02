import { defineStore } from 'pinia'

import { apiGet } from '../api/client'
import type { CatalogModel, CatalogSearchResponse, ProductVariant } from '../types/catalog'


export const useCatalogStore = defineStore('catalog', {
  state: () => ({
    models: [] as CatalogModel[],
    confirmedVariant: null as ProductVariant | null,
    loading: false,
    error: '',
  }),
  actions: {
    async search(query: string) {
      this.loading = true
      this.error = ''
      this.confirmedVariant = null
      try {
        const response = await apiGet<CatalogSearchResponse>(
          `/api/catalog/search?q=${encodeURIComponent(query)}`,
        )
        this.models = response.items
      } catch (error) {
        this.models = []
        this.error = error instanceof Error ? error.message : '型号检索失败'
      } finally {
        this.loading = false
      }
    },
    confirmVariant(variant: ProductVariant) {
      this.confirmedVariant = variant
    },
  },
})
