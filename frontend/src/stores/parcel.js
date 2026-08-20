import { defineStore } from 'pinia'
import {
  getParcels,
  getParcelsGeoJSON,
  getPoisGeoJSON,
  getZonesGeoJSON,
} from '../api'

// ---------------------------------------------------------------------------
// v4.0.3 海量数据可视化保护（模块级缓存，不进入 Pinia 状态）
// ---------------------------------------------------------------------------
const MAX_BBOX_AREA = 1.0   // 视野面积上限（平方度），超过直接跳过加载（保护后端与渲染）
const CACHE_MAX = 8         // 已加载视野缓存数量（LRU）

/** 视野缓存：每个元素 = {key, bbox:[minx,miny,maxx,maxy], entries:[{feat, bb}]} */
const bboxCache = []
let inflightController = null

function featBbox(feature) {
  const flat = feature?.geometry?.coordinates?.flat(Infinity) || []
  if (!flat.length) return null
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity
  for (let i = 0; i + 1 < flat.length; i += 2) {
    minx = Math.min(minx, flat[i]); maxx = Math.max(maxx, flat[i])
    miny = Math.min(miny, flat[i + 1]); maxy = Math.max(maxy, flat[i + 1])
  }
  return [minx, miny, maxx, maxy]
}

function bboxIntersects(bb, bbox) {
  return bb && bb[0] <= bbox[2] && bb[2] >= bbox[0] && bb[1] <= bbox[3] && bb[3] >= bbox[1]
}

const EMPTY_FC = { type: 'FeatureCollection', features: [], total: 0, truncated: false }

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
     * v4.0.3：按视野 bbox 智能加载指定期次地块 GeoJSON。
     *
     * 稳定性保障：
     *  1. 缩放/平移风暴防抖由调用方负责，这里再做三道防线 ——
     *     视野面积超限直接跳过（保护后端与渲染）；
     *     新视野完全落在已加载范围内时直接复用缓存（放大缩小不再重复请求）；
     *     新请求自动中止上一个在途请求（避免响应堆积）。
     *  2. 后端已对单次返回要素封顶（truncated/total），前端据此提示用户。
     *
     * bbox 兼容两种形态：MapView moveend 已拼接的字符串 "minx,miny,maxx,maxy"
     * 或数组 [minx, miny, maxx, maxy]；periods: ['base','current']。
     * 返回 FeatureCollection + {total, truncated, skipped, reason}。
     */
    async fetchParcelsGeojsonBbox(periods, bbox) {
      const bboxStr = Array.isArray(bbox)
        ? `${bbox[0]},${bbox[1]},${bbox[2]},${bbox[3]}`
        : bbox || null
      if (!bboxStr) return { ...EMPTY_FC }

      const parts = bboxStr.split(',').map(Number)
      if (parts.length !== 4 || parts.some(Number.isNaN)) {
        // 防御非法 bbox：静默跳过，不打断地图交互
        return { ...EMPTY_FC, skipped: true, reason: 'bad-bbox' }
      }
      const [minx, miny, maxx, maxy] = parts
      const area = (maxx - minx) * (maxy - miny)
      if (area <= 0 || area > MAX_BBOX_AREA) {
        // 视野过大（如全国视角）：跳过地块加载，提示用户放大后自动恢复
        return { ...EMPTY_FC, skipped: true, reason: 'area' }
      }

      const key = [...periods].sort().join('+') || 'all'

      // 1) 缓存命中：新视野完全位于已加载范围之内 → 本地裁剪复用，零网络请求
      for (let i = 0; i < bboxCache.length; i++) {
        const c = bboxCache[i]
        if (c.key !== key) continue
        if (minx >= c.bbox[0] && miny >= c.bbox[1] && maxx <= c.bbox[2] && maxy <= c.bbox[3]) {
          bboxCache.splice(i, 1)
          bboxCache.push(c) // LRU：移到队尾
          const feats = c.entries
            .filter((e) => bboxIntersects(e.bb, parts))
            .map((e) => e.feat)
          return { type: 'FeatureCollection', features: feats,
                   total: feats.length, truncated: false, cached: true }
        }
      }

      // 2) 网络加载：先中止上一个在途请求，避免缩放风暴造成响应堆积
      if (inflightController) {
        try { inflightController.abort() } catch (e) { /* 忽略 */ }
      }
      inflightController = new AbortController()
      try {
        const fcs = await Promise.all(periods.map((p) =>
          getParcelsGeoJSON({ period: p, bbox: bboxStr }, { signal: inflightController.signal })))
        const features = fcs.flatMap((fc) => fc.features || [])
        const total = fcs.reduce((s, fc) => s + (fc.total || 0), 0)
        const truncated = fcs.some((fc) => fc.truncated)
        // 写入缓存（记录每个要素包围盒，供放大复用时本地裁剪）
        bboxCache.push({
          key,
          bbox: parts,
          entries: features.map((f) => ({ feat: f, bb: featBbox(f) })),
        })
        while (bboxCache.length > CACHE_MAX) bboxCache.shift()
        return { type: 'FeatureCollection', features, total, truncated }
      } catch (e) {
        if (e?.code === 'ERR_CANCELED' || e?.name === 'CanceledError' || e?.__CANCEL__) {
          return { ...EMPTY_FC, skipped: true, reason: 'canceled' }
        }
        throw e
      } finally {
        inflightController = null
      }
    },
    async fetchPoisGeojson() {
      this.poisGeojson = await getPoisGeoJSON()
    },
    async fetchZonesGeojson() {
      this.zonesGeojson = await getZonesGeoJSON()
    },
    /** v4.0.3：删除/导入地块后清空视野缓存，强制下次加载走最新数据 */
    invalidateParcelsGeojsonCache() {
      bboxCache.length = 0
      if (inflightController) {
        try { inflightController.abort() } catch (e) { /* 忽略 */ }
        inflightController = null
      }
    },
    selectParcel(parcel) {
      this.selectedParcel = parcel
    },
  },
})
