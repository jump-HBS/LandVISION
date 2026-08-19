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
    /**
     * v4.0.1：按视野 bbox 加载指定期次地块 GeoJSON（GiST 索引毫秒级返回，
     * 替代海量数据下 40~60 秒的全量拉取）。
     * bbox: [minx, miny, maxx, maxy]；periods: ['base','current']。
     */
    async fetchParcelsGeojsonBbox(periods, bbox) {
      const bboxStr = bbox ? `${bbox[0]},${bbox[1]},${bbox[2]},${bbox[3]}` : null
      const tasks = periods.map((p) =>
        getParcelsGeoJSON(bboxStr ? { period: p, bbox: bboxStr } : { period: p }))
      const fcs = await Promise.all(tasks)
      return {
        type: 'FeatureCollection',
        features: fcs.flatMap((fc) => fc.features || []),
      }
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
