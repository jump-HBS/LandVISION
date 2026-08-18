import { defineStore } from 'pinia'
import {
  getParcels,
  getParcelsGeoJSON,
  getPoisGeoJSON,
  getZonesGeoJSON,
} from '../api'

/**
 * 全局地块状态（Pinia）：
 *  - 地块列表（表格，分页后的 items）、地块 GeoJSON（地图）、当前选中地块
 *  - 各页面共享，一处更新、处处联动
 */
export const useParcelStore = defineStore('parcel', {
  state: () => ({
    parcels: [],          // 当前页表格数据
    parcelsGeojson: { type: 'FeatureCollection', features: [] },
    poisGeojson: { type: 'FeatureCollection', features: [] },
    zonesGeojson: { type: 'FeatureCollection', features: [] },
    selectedParcel: null, // 当前选中的地块（详情）
    loading: false,
  }),

  getters: {
    totalArea: (state) =>
      state.parcels.reduce((sum, p) => sum + (p.area_sqm || 0), 0),
  },

  actions: {
    async fetchParcels(params) {
      this.loading = true
      try {
        const data = await getParcels(params)
        this.parcels = data.items
        return data // 返回 {items,total,page,page_size,pages} 供页面分页
      } finally {
        this.loading = false
      }
    },
    async fetchParcelsGeojson(params) {
      this.parcelsGeojson = await getParcelsGeoJSON(params)
    },
    async fetchPoisGeojson() {
      this.poisGeojson = await getPoisGeoJSON()
    },
    async fetchZonesGeojson() {
      this.zonesGeojson = await getZonesGeoJSON()
    },
    selectParcel(parcel) {
      this.selectedParcel = parcel
    },
  },
})
