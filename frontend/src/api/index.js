/**
 * API 接口汇总（v2.0）：按后端 10 组路由分组。
 * 每个函数返回 Promise，直接拿到响应 data。
 */
import request from '../utils/request'

// ---------- 地块 parcels ----------
export const getParcels = (params) => request.get('/parcels', { params })
// v4.0.3：支持透传 config（AbortController signal 取消在途请求）
export const getParcelsGeoJSON = (params, config) => request.get('/parcels/geojson', { params, ...config })
export const getParcel = (id) => request.get(`/parcels/${id}`)
export const createParcel = (data) => request.post('/parcels', data)
export const updateParcel = (id, data) => request.put(`/parcels/${id}`, data)
export const deleteParcel = (id) => request.delete(`/parcels/${id}`)
export const lockParcel = (id, locked) => request.post(`/parcels/${id}/lock`, { locked })
export const batchDeleteParcels = (ids) => request.post('/parcels/batch-delete', { ids })
// v3.0：按几何范围批量删除（地图框选删除，跳过锁定项）
export const deleteParcelsByGeometry = (data) => request.post('/parcels/delete-by-geometry', data)
export const batchSetParcelPeriod = (period, ids) =>
  request.post('/parcels/batch-set-period', null, { params: { period, ids: ids?.join(',') } })
// SHP 批量导入（multipart：file + period + project_id + 字段）
export const importParcelsShp = (formData) =>
  request.post('/parcels/import-shp', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })

// ---------- 行政区划 regions ----------
export const getRegions = (params) => request.get('/regions', { params })
export const getRegionsGeoJSON = (params) => request.get('/regions/geojson', { params })
export const getRegion = (code) => request.get(`/regions/${code}`)
export const getRegionChildren = (code) => request.get(`/regions/${code}/children`)
export const getRegionLocate = (code) => request.get(`/regions/${code}/locate`)
export const importRegionsShp = (formData) =>
  request.post('/regions/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })

// ---------- 兴趣点 pois ----------
export const getPois = (params) => request.get('/pois', { params })
export const getPoisGeoJSON = (params) => request.get('/pois/geojson', { params })
export const createPoi = (data) => request.post('/pois', data)
export const deletePoi = (id) => request.delete(`/pois/${id}`)
export const lockPoi = (id, locked) => request.post(`/pois/${id}/lock`, { locked })
export const batchDeletePois = (ids) => request.post('/pois/batch-delete', { ids })
// SHP 点要素导入（multipart：file + period + project_id + 字段；v3.0 点面分离）
export const importPoisShp = (formData) =>
  request.post('/pois/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })

// ---------- 分析项目 projects（业务上下文） ----------
export const getProjects = () => request.get('/projects')
export const getProject = (id) => request.get(`/projects/${id}`)
export const createProject = (data) => request.post('/projects', data)
export const updateProject = (id, data) => request.put(`/projects/${id}`, data)
export const deleteProject = (id) => request.delete(`/projects/${id}`)

// ---------- 三区三线体检 planning（模块四） ----------
export const getZones = () => request.get('/planning/zones')
export const getZonesGeoJSON = () => request.get('/planning/zones/geojson')
export const checkParcel = (id) => request.get(`/planning/check/${id}`)
export const checkGeometry = (data) => request.post('/planning/check', data)
export const createZone = (data) => request.post('/planning/zones', data)
export const deleteZone = (id) => request.delete(`/planning/zones/${id}`)
export const lockZone = (id, locked) => request.post(`/planning/zones/${id}/lock`, { locked })
export const batchDeleteZones = (ids) => request.post('/planning/zones/batch-delete', { ids })
export const importZonesShp = (formData) =>
  request.post('/planning/zones/import-shp', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
export const reviewPlanning = (data) => request.post('/planning/review', data, { timeout: 120000 })
export const reviewPatches = (data) => request.post('/planning/review-patches', data, { timeout: 120000 })
export const getPlanningRules = () => request.get('/planning/rules')
export const updatePlanningRules = (data) => request.put('/planning/rules', data)
export const getPlanningResults = (params) => request.get('/planning/results', { params })
// 三区三线台账导出
export const exportReviewCsv = (data) =>
  request.post('/planning/review/export', data, { responseType: 'blob', timeout: 120000 })

// ---------- 空间分析 analysis（模块一~三） ----------
export const importTransitionShp = (formData) =>
  request.post('/analysis/transition/import-shp', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
export const generateDemoBase = (data = {}) => request.post('/analysis/transition/generate-demo-base', data)
export const transitionMatrix = (data) => request.post('/analysis/transition/matrix', data, { timeout: 120000 })
export const getTransitionPatches = (params) => request.get('/analysis/transition/patches', { params })
export const getSuitabilityTargets = () => request.get('/analysis/suitability/targets')
export const suitabilityEvaluate = (data) => request.post('/analysis/suitability/evaluate', data, { timeout: 120000 })
export const getSuitabilityGrids = (params) => request.get('/analysis/suitability/grids', { params })
// v3.0：适宜性矛盾提示（高度/中等适宜 ∩ 体检冲突地块）
export const getSuitabilityConflicts = (params) => request.get('/analysis/suitability/conflicts', { params })
export const accessibilityAnalyze = (data) => request.post('/analysis/accessibility/analyze', data, { timeout: 120000 })
export const getAccessibilityResults = (params) => request.get('/analysis/accessibility/results', { params })
export const getFacilitySites = (params) => request.get('/analysis/facility-sites', { params })
// SHP 范围解析（各分析页"导入 SHP 范围"共用，不落库）
export const parseScopeShp = (formData) =>
  request.post('/analysis/parse-scope', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })

// ---------- 地图标注 map-features（地图绘制持久化） ----------
export const getMapFeatures = (params) => request.get('/map-features', { params })
export const getMapFeaturesGeoJSON = (params) => request.get('/map-features/geojson', { params })
export const createMapFeature = (data) => request.post('/map-features', data)
export const deleteMapFeature = (id) => request.delete(`/map-features/${id}`)
export const lockMapFeature = (id, locked) => request.post(`/map-features/${id}/lock`, { locked })
export const batchDeleteMapFeatures = (ids) => request.post('/map-features/batch-delete', { ids })

// ---------- 数据驾驶舱 dashboard（项目工作台统筹汇总，与报告共用数据源） ----------
export const dashboardSummary = (data) => request.post('/dashboard/summary', data, { timeout: 120000 })

// ---------- 报告 report（继承驾驶舱项目与范围） ----------
export const generateReport = (data) => request.post('/report/generate', data)
export const getLatestReport = () => request.get('/report/latest')
export const downloadReport = () => request.get('/report/latest/download', { responseType: 'blob' })
