<template>
  <div class="map-wrap">
    <div ref="mapContainer" class="map-canvas"></div>

    <!-- 工具条：选择工具 + 测量工具（可拖拽移动） -->
    <div v-if="showControls" class="map-widget map-tools" :class="{ compact: layout === 'compact' }" v-drag>
      <template v-if="enableSelection">
        <el-tooltip content="框选统计" placement="bottom">
          <button class="tool-btn" :class="{ active: activeTool === 'box' }" @click="setTool('box')">
            <el-icon><FullScreen /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="圈选统计" placement="bottom">
          <button class="tool-btn" :class="{ active: activeTool === 'circle' }" @click="setTool('circle')">
            <el-icon><Aim /></el-icon>
          </button>
        </el-tooltip>
        <el-tooltip content="多边形选择" placement="bottom">
          <button class="tool-btn" :class="{ active: activeTool === 'polygon' }" @click="setTool('polygon')">
            <el-icon><Crop /></el-icon>
          </button>
        </el-tooltip>
        <span class="tool-divider"></span>
      </template>
      <el-tooltip content="距离测量" placement="bottom">
        <button class="tool-btn" :class="{ active: activeTool === 'distance' }" @click="setTool('distance')">
          <el-icon><Sort /></el-icon>
        </button>
      </el-tooltip>
      <el-tooltip content="面积测量" placement="bottom">
        <button class="tool-btn" :class="{ active: activeTool === 'area' }" @click="setTool('area')">
          <el-icon><PieChart /></el-icon>
        </button>
      </el-tooltip>
      <span class="tool-divider"></span>
      <el-tooltip content="清除绘制" placement="bottom">
        <button class="tool-btn" @click="clearDrawing">
          <el-icon><Delete /></el-icon>
        </button>
      </el-tooltip>
    </div>

    <!-- 右侧：图标栏（行政区 / 图层 / 图例）→ 点击展开面板（可拖拽移动） -->
    <div v-if="showControls" class="map-widget right-icon-bar" v-drag>
      <div v-if="showRegionSelector" class="icon-stack-item">
        <RegionSelector @select="(r) => emit('region-select', r)" @locate="(r) => emit('region-locate', r)" />
      </div>
      <div class="icon-stack-item">
        <button class="icon-btn" :class="{ active: panelOpen === 'layers' }" title="图层控制"
                @click="panelOpen = panelOpen === 'layers' ? null : 'layers'">
          <el-icon :size="16"><Collection /></el-icon>
        </button>
      </div>
      <div class="icon-stack-item">
        <button class="icon-btn" :class="{ active: panelOpen === 'legend' }" title="图例"
                @click="panelOpen = panelOpen === 'legend' ? null : 'legend'">
          <el-icon :size="16"><Menu /></el-icon>
        </button>
      </div>

      <!-- 图层面板（展开，内嵌于图标栏内 → 随拖拽一起移动） -->
      <div v-if="panelOpen === 'layers'" class="right-panel-inner map-widget">
        <div class="layer-title">图层控制</div>
        <label v-for="item in layerItems" :key="item.name" class="layer-item">
          <input type="checkbox" :checked="ui.layerVisibility[item.name]" @change="toggleLayer(item.name)" />
          <span class="layer-swatch" :style="{ background: item.color }"></span>
          <span>{{ item.label }}</span>
        </label>
      </div>

      <!-- 图例面板（展开，随图标栏移动） -->
      <div v-if="panelOpen === 'legend' && legendGroups.length" class="right-panel-inner map-widget">
        <div class="layer-title">图例（GB/T 21010-2017）</div>
        <div v-for="g in legendGroups" :key="g.title" class="legend-group">
          <div class="legend-group-title">{{ g.title }}</div>
          <div v-for="item in g.items" :key="item.label" class="legend-item">
            <span class="layer-swatch" :style="{ background: item.color }"></span>
            <span>{{ item.label }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 测量结果显示 -->
    <div v-if="measureText" class="map-widget measure-result">{{ measureText }}</div>

    <!-- v2.0：批量选择栏（点击地块/POI/控制线进入批量选中） -->
    <div v-if="batchSelect && batchTotal > 0" class="map-widget batch-bar">
      <span class="batch-title">已选中</span>
      <span v-if="batchSel.parcel_ids.length">地块 <b>{{ batchSel.parcel_ids.length }}</b></span>
      <span v-if="batchSel.poi_ids.length">POI <b>{{ batchSel.poi_ids.length }}</b></span>
      <span v-if="batchSel.zone_ids.length">控制线 <b>{{ batchSel.zone_ids.length }}</b></span>
      <el-button size="small" text type="danger" @click="clearBatchSelection">清空</el-button>
    </div>

    <!-- v2.0：保存绘制（地图上绘制的点/线/面入库 map_features） -->
    <div v-if="showSaveDrawing && lastDrawing" class="map-widget save-drawing-bar">
      <el-button size="small" type="primary" @click="emit('save-drawing', lastDrawing)">
        保存当前绘制
      </el-button>
    </div>

    <!-- 框选统计结果 -->
    <div v-if="selection && showSelectionPanel && showControls" class="map-widget selection-panel">
      <div class="selection-title">区域统计</div>
      <div>地块数：<b>{{ selection.count }}</b></div>
      <div>总面积：<b>{{ (selection.areaSqm / 10000).toFixed(2) }}</b> 公顷</div>
      <div v-for="(v, k) in selection.byLandUse" :key="k" class="selection-row">
        <span class="layer-swatch" :style="{ background: LAND_USE_COLORS[k] || '#999' }"></span>
        <span>{{ k }}：{{ v }} 宗</span>
      </div>
      <el-button size="small" text type="danger" @click="clearSelection">清除</el-button>
      <el-button v-if="selectionDelete" size="small" type="danger" @click="emit('selection-delete', selection)">
        删除选中地块
      </el-button>
    </div>

    <!-- 坐标拾取读数 -->
    <div v-if="showControls && showCoords" class="map-widget coord-readout">
      经度 {{ coord.lng.toFixed(5) }} 纬度 {{ coord.lat.toFixed(5) }} ｜ 缩放 {{ zoom }}
    </div>
  </div>
</template>

<script setup>
/**
 * MapView —— LandVISION 企业级地图组件（MapLibre GL JS 封装）
 *
 * 能力清单：
 *  - 底图：OpenFreeMap 矢量（免费）+ Esri 卫星影像（可开关）
 *  - 控件：导航（含指南针）/ 比例尺 / 全屏 / 坐标拾取 / 图层控制 / 图例
 *  - 工具：框选、圈选、多边形选择（自动统计地块数/面积/用地构成）+ 距离/面积测量
 *  - 交互：悬停高亮（feature-state）、选中描边、点击弹窗（定位缩放/查看档案）
 *
 * 组件契约：
 *  props:  parcels/pois/zones/changes/buffer（GeoJSON）、highlightId、center/zoom、
 *          autoFit、showControls、enableSelection、enablePopup
 *  emits:  parcel-click(feature)、parcel-detail(feature)、moveend(bbox)、
 *          map-ready(map)、selection({count, areaSqm, byLandUse, features})
 *  expose: flyTo(feature)、jumpTo({center, zoom})、getMap()、clearSelection()、ready
 */
import { onMounted, onBeforeUnmount, ref, watch, computed, reactive } from 'vue'
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { useUiStore } from '../stores/ui'
import { LAND_USE_COLORS, POI_COLORS, CHANGE_COLORS,
         LAND_USE_LEGEND, POI_LEGEND, CHANGE_LEGEND, ZONE_LEGEND } from '../utils/colors'
import { lineLengthM, polygonAreaSqm, featureInShape } from '../utils/geo'
import RegionSelector from './RegionSelector.vue'

const props = defineProps({
  parcels: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  pois: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  zones: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  changes: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  // 空间分析模块叠加图层：适宜性评价格网（cells）与设施可达性覆盖（coverage）
  cells: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  coverage: { type: Object, default: () => ({ type: 'FeatureCollection', features: [] }) },
  buffer: { type: Object, default: null },
  highlightId: { type: [Number, String], default: null },
  center: { type: Array, default: () => [116.4, 39.896] },
  zoom: { type: Number, default: 12.5 },
  autoFit: { type: Boolean, default: false },
  showControls: { type: Boolean, default: true },
  enableSelection: { type: Boolean, default: false },
  enablePopup: { type: Boolean, default: true },
  // 布局模式：default 全控件 / compact 精简（供驾驶舱整屏底图使用）
  layout: { type: String, default: 'default' },
  showLayerPanel: { type: Boolean, default: true },
  showLegend: { type: Boolean, default: true },
  showScale: { type: Boolean, default: true },
  showCoords: { type: Boolean, default: true },
  showSelectionPanel: { type: Boolean, default: true },
  // 右上角行政区选择器（国家→省→市→县查找定位）
  showRegionSelector: { type: Boolean, default: true },
  // 行政区边界（GeoJSON，检索定位后高亮显示，可在图层面板隐藏）
  regionBoundary: { type: Object, default: null },
  // v2.0：批量选择模式（点击地块/POI/控制线进入批量选中，供批量删除/锁定）
  batchSelect: { type: Boolean, default: false },
  // v2.0：显示"保存绘制"按钮（把地图上绘制的点/线/面保存到 map_features 表）
  showSaveDrawing: { type: Boolean, default: false },
  // v3.0：选择统计面板中显示「删除选中地块」按钮（框选删除，emit selection-delete）
  selectionDelete: { type: Boolean, default: false },
})

const emit = defineEmits(['parcel-click', 'parcel-detail', 'moveend', 'map-ready',
                          'selection', 'region-select', 'region-locate',
                          'cells-click', 'coverage-click',
                          'batch-selection', 'save-drawing', 'selection-delete'])

const ui = useUiStore()
const mapContainer = ref(null)
let map = null
let fitted = false
let hoveredFeatureId = null

const coord = ref({ lng: props.center[0], lat: props.center[1] })
const zoom = ref(props.zoom)
const measureText = ref('')
const activeTool = ref(null) // null | box | circle | polygon | distance | area
const selection = ref(null)
const showSelectionPanel = ref(true)
const panelOpen = ref(null) // null | layers | legend

const EMPTY_FC = () => ({ type: 'FeatureCollection', features: [] })

// 图层控制项
const layerItems = [
  { name: 'parcels', label: '地块', color: LAND_USE_COLORS['住宅用地'] },
  { name: 'pois', label: '兴趣点', color: POI_COLORS['交通'] },
  { name: 'zones', label: '三区三线控制线', color: '#E53935' },
  { name: 'changes', label: '变化图斑（转移矩阵）', color: CHANGE_COLORS['新增建设'] },
  { name: 'cells', label: '适宜性评价格网', color: '#91cf60' },
  { name: 'coverage', label: '设施可达性覆盖', color: '#16a34a' },
  { name: 'regionBoundary', label: '行政区范围', color: '#0ea5e9' },
  { name: 'satellite', label: '卫星影像底图', color: '#475569' },
]

const legendGroups = computed(() => {
  const groups = []
  if (ui.layerVisibility.parcels) groups.push({ title: '用地类型（12 大类）', items: LAND_USE_LEGEND })
  if (ui.layerVisibility.pois) groups.push({ title: '兴趣点类型', items: POI_LEGEND })
  if (ui.layerVisibility.changes) groups.push({ title: '变化类型', items: CHANGE_LEGEND })
  if (ui.layerVisibility.zones) groups.push({ title: '规划控制区', items: ZONE_LEGEND })
  return groups
})

// 绘制状态
const drawState = {
  box: null,          // { start: [lng,lat] }
  circle: null,       // { center: [lng,lat] }
  polygon: [],        // 顶点列表
  line: [],           // 距离测量点列表
  area: [],           // 面积测量顶点列表
}

// 地图视图状态持久化：切换页面/刷新后回到用户上次停留的位置
const VIEW_KEY = 'landvision-map-view'

function loadSavedView() {
  try {
    const saved = JSON.parse(localStorage.getItem(VIEW_KEY) || 'null')
    if (saved && Array.isArray(saved.center) && saved.center.length === 2
        && typeof saved.zoom === 'number') {
      return saved
    }
  } catch (e) { /* 忽略损坏数据 */ }
  return null
}

function saveCurrentView() {
  if (!map) return
  const c = map.getCenter()
  localStorage.setItem(VIEW_KEY, JSON.stringify({
    center: [c.lng, c.lat],
    zoom: map.getZoom(),
  }))
}

// 底图样式：OpenFreeMap（免费、清晰，浏览器访问正常）
// 注：此前误判 403 系诊断脚本缺少浏览器标识所致，现已恢复
const BASE_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

onMounted(() => {
  // 有用户上次停留位置 → 用其初始化；否则用 props 默认（首次进入由 autoFit 定位数据）
  const saved = loadSavedView()
  map = new maplibregl.Map({
    container: mapContainer.value,
    style: BASE_STYLE,
    center: saved ? saved.center : props.center,
    zoom: saved ? saved.zoom : props.zoom,
    attributionControl: true,
  })
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
  if (props.showScale) {
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 140 }), 'bottom-right')
  }
  map.addControl(new maplibregl.FullscreenControl(), 'top-right')

  map.on('load', () => {
    ensureAllLayers()
    highlight(props.highlightId)
    emit('map-ready', map)
    fitIfNeeded()
  })

  // ---------- 悬停 / 点击 / 视野 / 坐标 ----------
  map.on('mousemove', 'parcels-fill', onParcelHover)
  map.on('mouseleave', 'parcels-fill', onParcelHoverOut)
  map.on('click', 'parcels-fill', onParcelClick)
  map.on('click', 'cells-fill', onCellsClick)
  map.on('click', 'coverage-fill', onCoverageClick)
  map.on('click', 'pois-circle', onPoiClick)
  map.on('click', 'zones-line', onZoneClick)
  map.on('moveend', () => {
    const b = map.getBounds()
    emit('moveend', [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]
      .map((v) => v.toFixed(5)).join(','))
    zoom.value = map.getZoom()
    saveCurrentView() // 记住用户停留位置
  })
  map.on('mousemove', (e) => { coord.value = { lng: e.lngLat.lng, lat: e.lngLat.lat } })
  map.on('contextmenu', (e) => { if (activeTool.value === 'polygon' || activeTool.value === 'area') { e.preventDefault(); finishPolygonTool() } })

  // ---------- 工具交互 ----------
  map.on('mousedown', onMapMouseDown)
  map.on('mouseup', onMapMouseUp)
  map.on('click', onMapClick)
  map.on('dblclick', () => { if (activeTool.value === 'distance') finishLineTool() })

  watchAll()
})

onBeforeUnmount(() => { if (map) { map.remove(); map = null } })

// ===========================================================================
// 图层管理
// ===========================================================================

const LAYER_PAINTS = {
  parcels: {
    fillColor: ['match', ['get', 'land_use'],
      '耕地', LAND_USE_COLORS['耕地'], '园地', LAND_USE_COLORS['园地'],
      '林地', LAND_USE_COLORS['林地'], '草地', LAND_USE_COLORS['草地'],
      '商服用地', LAND_USE_COLORS['商服用地'], '工矿仓储用地', LAND_USE_COLORS['工矿仓储用地'],
      '住宅用地', LAND_USE_COLORS['住宅用地'],
      '公共管理与公共服务用地', LAND_USE_COLORS['公共管理与公共服务用地'],
      '特殊用地', LAND_USE_COLORS['特殊用地'], '交通运输用地', LAND_USE_COLORS['交通运输用地'],
      '水域及水利设施用地', LAND_USE_COLORS['水域及水利设施用地'],
      '其他土地', LAND_USE_COLORS['其他土地'], '#94a3b8'],
    outline: '#334155',
  },
  pois: { circleColor: ['match', ['get', 'poi_type'],
    '交通', POI_COLORS['交通'], '商业', POI_COLORS['商业'], '教育', POI_COLORS['教育'],
    '医疗', POI_COLORS['医疗'], '休闲', POI_COLORS['休闲'], '#64748b'] },
  // 三区三线（v2.0 标准三线：颜色鲜明、线型区分、无填充）
  zones: {
    lineColor: ['match', ['get', 'zone_type'],
      'ecological_red_line', '#E53935',
      'permanent_basic_farmland', '#FFB300',
      'urban_growth_boundary', '#1E88E5', '#E53935'],
    lineWidth: ['match', ['get', 'zone_type'],
      'ecological_red_line', 3,
      'permanent_basic_farmland', 2.5,
      'urban_growth_boundary', 2, 1.6],
    lineDash: ['match', ['get', 'zone_type'],
      'urban_growth_boundary', ['literal', [8, 4]],
      ['literal', [1, 0]]],
  },
  changes: { fillColor: ['match', ['get', 'change_type'],
    '新增建设', CHANGE_COLORS['新增建设'], '拆除', CHANGE_COLORS['拆除'],
    '植被变化', CHANGE_COLORS['植被变化'], '水域变化', CHANGE_COLORS['水域变化'], '#f59e0b'],
    outline: '#7f1d1d' },
  // 适宜性评价四级配色（绿→黄→红，专题制图惯例）
  cells: { fillColor: ['match', ['get', 'level'],
    '高度适宜', '#1a9850', '中等适宜', '#91cf60',
    '勉强适宜', '#fee08b', '不适宜', '#d73027', '#94a3b8'],
    outline: '#334155' },
  // 设施可达性：覆盖=绿 / 盲区=红
  coverage: { fillColor: ['match', ['get', 'covered'], true, '#16a34a', '#ef4444', '#94a3b8'],
    outline: '#166534' },
}

function ensureAllLayers() {
  ensureLayer('parcels', props.parcels)
  ensureLayer('pois', props.pois)
  ensureLayer('zones', props.zones)
  ensureLayer('changes', props.changes)
  ensureLayer('buffer', props.buffer)
  ensureLayer('satellite', null)
  ensureLayer('regionBoundary', props.regionBoundary)
  ensureLayer('cells', props.cells)
  ensureLayer('coverage', props.coverage)
  ensureDrawLayers()
  ensureBatchLayer()
  applyVisibility()
}

function ensureLayer(key, geojson) {
  if (!map) return
  const src = `${key}-source`
  if (key === 'satellite') {
    if (!map.getSource(src)) {
      map.addSource(src, {
        type: 'raster',
        tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
        tileSize: 256,
        maxzoom: 18,
      })
      map.addLayer({ id: 'satellite-layer', type: 'raster', source: src, paint: { 'raster-opacity': 1 } })
    }
    return
  }
  if (!map.getSource(src)) {
    map.addSource(src, { type: 'geojson', data: geojson || EMPTY_FC(), promoteId: 'id' })
    addLayer(key, src)
  } else if (geojson) {
    map.getSource(src).setData(geojson)
  }
}

function addLayer(key, src) {
  const paint = LAYER_PAINTS[key]
  switch (key) {
    case 'parcels':
      map.addLayer({ id: 'parcels-fill', type: 'fill', source: src, paint: {
        'fill-color': paint.fillColor,
        'fill-opacity': ['case', ['boolean', ['feature-state', 'hover'], false], 0.85, 0.55],
      }})
      map.addLayer({ id: 'parcels-line', type: 'line', source: src, paint: {
        'line-color': paint.outline, 'line-width': 1.1,
        // v3.0：锁定地块虚线描边（锁定后不可删除的视觉提示）
        'line-dasharray': ['case', ['boolean', ['get', 'locked'], false],
          ['literal', [6, 3]], ['literal', [1, 0]]],
      } })
      break
    case 'pois':
      map.addLayer({ id: 'pois-circle', type: 'circle', source: src, paint: {
        'circle-color': paint.circleColor, 'circle-radius': 6,
        'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 } })
      break
    case 'zones':
      // 三区三线：刚性约束边界 —— 无填充、线型按类型区分（颜色/粗细/虚实）
      map.addLayer({ id: 'zones-fill', type: 'fill', source: src, paint: { 'fill-opacity': 0 } })
      map.addLayer({ id: 'zones-line', type: 'line', source: src, paint: {
        'line-color': paint.lineColor, 'line-width': paint.lineWidth,
        'line-dasharray': paint.lineDash } })
      break
    case 'changes':
      map.addLayer({ id: 'changes-fill', type: 'fill', source: src, paint: { 'fill-color': paint.fillColor, 'fill-opacity': 0.5 } })
      map.addLayer({ id: 'changes-line', type: 'line', source: src, paint: { 'line-color': paint.outline, 'line-width': 1 } })
      break
    case 'buffer':
      map.addLayer({ id: 'buffer-fill', type: 'fill', source: src, paint: { 'fill-color': '#6366f1', 'fill-opacity': 0.12 } })
      map.addLayer({ id: 'buffer-line', type: 'line', source: src, paint: { 'line-color': '#4f46e5', 'line-width': 2, 'line-dasharray': [3, 2] } })
      break
    case 'regionBoundary':
      // 行政区范围高亮：蓝色描边 + 淡蓝填充（可在图层控制中隐藏）
      map.addLayer({ id: 'region-fill', type: 'fill', source: src, paint: { 'fill-color': '#0ea5e9', 'fill-opacity': 0.06 } })
      map.addLayer({ id: 'region-line', type: 'line', source: src, paint: { 'line-color': '#0ea5e9', 'line-width': 2.5 } })
      map.addLayer({ id: 'region-line-outer', type: 'line', source: src, paint: { 'line-color': '#ffffff', 'line-width': 5.5, 'line-opacity': 0.5 } },
        'region-line')
      break
    case 'cells':
      map.addLayer({ id: 'cells-fill', type: 'fill', source: src, paint: { 'fill-color': paint.fillColor, 'fill-opacity': 0.55 } })
      map.addLayer({ id: 'cells-line', type: 'line', source: src, paint: { 'line-color': paint.outline, 'line-width': 0.6 } })
      break
    case 'coverage':
      map.addLayer({ id: 'coverage-fill', type: 'fill', source: src, paint: { 'fill-color': paint.fillColor, 'fill-opacity': 0.45 } })
      map.addLayer({ id: 'coverage-line', type: 'line', source: src, paint: { 'line-color': paint.outline, 'line-width': 0.8 } })
      break
  }
}

function ensureDrawLayers() {
  if (map.getSource('draw-source')) return
  map.addSource('draw-source', { type: 'geojson', data: EMPTY_FC() })
  map.addSource('measure-source', { type: 'geojson', data: EMPTY_FC() })
  map.addSource('selection-source', { type: 'geojson', data: EMPTY_FC() })
  map.addLayer({ id: 'draw-line', type: 'line', source: 'draw-source', paint: { 'line-color': '#2563eb', 'line-width': 2, 'line-dasharray': [2, 2] } })
  map.addLayer({ id: 'draw-fill', type: 'fill', source: 'draw-source', paint: { 'fill-color': '#3b82f6', 'fill-opacity': 0.15 } })
  map.addLayer({ id: 'measure-line', type: 'line', source: 'measure-source', paint: { 'line-color': '#f97316', 'line-width': 2.5 } })
  map.addLayer({ id: 'measure-fill', type: 'fill', source: 'measure-source', paint: { 'fill-color': '#fb923c', 'fill-opacity': 0.18 } })
  map.addLayer({ id: 'selection-line', type: 'line', source: 'selection-source', paint: { 'line-color': '#16a34a', 'line-width': 2.5 } })
  map.addLayer({ id: 'selection-fill', type: 'fill', source: 'selection-source', paint: { 'fill-color': '#22c55e', 'fill-opacity': 0.15 } })
}

function applyVisibility() {
  if (!map) return
  const vis = (layerId, on) => {
    if (map.getLayer(layerId)) map.setLayoutProperty(layerId, 'visibility', on ? 'visible' : 'none')
  }
  vis('parcels-fill', ui.layerVisibility.parcels)
  vis('parcels-line', ui.layerVisibility.parcels)
  vis('pois-circle', ui.layerVisibility.pois)
  vis('zones-fill', ui.layerVisibility.zones)
  vis('zones-line', ui.layerVisibility.zones)
  vis('changes-fill', ui.layerVisibility.changes)
  vis('changes-line', ui.layerVisibility.changes)
  vis('cells-fill', ui.layerVisibility.cells)
  vis('cells-line', ui.layerVisibility.cells)
  vis('coverage-fill', ui.layerVisibility.coverage)
  vis('coverage-line', ui.layerVisibility.coverage)
  vis('region-fill', ui.layerVisibility.regionBoundary)
  vis('region-line', ui.layerVisibility.regionBoundary)
  vis('region-line-outer', ui.layerVisibility.regionBoundary)
  vis('satellite-layer', ui.layerVisibility.satellite)
}

function toggleLayer(name) {
  ui.setLayerVisible(name, !ui.layerVisibility[name])
}

// ===========================================================================
// 交互
// ===========================================================================

function onParcelHover(e) {
  if (!e.features?.length) return
  const id = e.features[0].id
  if (hoveredFeatureId !== null && hoveredFeatureId !== id) {
    map.setFeatureState({ source: 'parcels-source', id: hoveredFeatureId }, { hover: false })
  }
  if (hoveredFeatureId !== id) {
    map.setFeatureState({ source: 'parcels-source', id }, { hover: true })
    hoveredFeatureId = id
  }
  map.getCanvas().style.cursor = 'pointer'
}

function onParcelHoverOut() {
  if (hoveredFeatureId !== null) {
    map.setFeatureState({ source: 'parcels-source', id: hoveredFeatureId }, { hover: false })
    hoveredFeatureId = null
  }
  map.getCanvas().style.cursor = ''
}

function onParcelClick(e) {
  if (activeTool.value) return // 绘制模式下不触发弹窗
  const feature = e.features?.[0]
  if (!feature) return
  emit('parcel-click', feature)
  if (props.batchSelect) {
    toggleBatch('parcel_ids', feature.id ?? feature.properties?.id, feature)
    return
  }
  if (!props.enablePopup) return

  const p = feature.properties
  const popupEl = document.createElement('div')
  popupEl.className = 'lv-popup'
  popupEl.innerHTML = `
    <div class="lv-popup-title">${p.name || p.parcel_code}</div>
    <div class="lv-popup-row"><span>编号</span><b>${p.parcel_code}</b></div>
    <div class="lv-popup-row"><span>用地性质</span><b>${p.land_use}</b></div>
    <div class="lv-popup-row"><span>面积</span><b>${((p.area_sqm || 0) / 10000).toFixed(2)} 公顷</b></div>
    <div class="lv-popup-actions">
      <button class="lv-popup-btn primary" data-act="zoom">定位缩放</button>
      <button class="lv-popup-btn" data-act="detail">查看档案</button>
    </div>`
  popupEl.querySelector('[data-act="zoom"]').onclick = () => { flyTo(feature); popup?.remove() }
  popupEl.querySelector('[data-act="detail"]').onclick = () => { emit('parcel-detail', feature); popup?.remove() }

  const popup = new maplibregl.Popup({ closeButton: true, offset: 10 })
    .setLngLat(e.lngLat).setDOMContent(popupEl).addTo(map)
  if (popupEl) popup.on('close', () => popupEl.remove())
}

/** POI 点击：批量选择模式下进入选中集 */
function onPoiClick(e) {
  if (activeTool.value || !props.batchSelect) return
  const feature = e.features?.[0]
  if (!feature) return
  toggleBatch('poi_ids', feature.id ?? feature.properties?.id, feature)
}

/** 三区三线控制线点击：批量选择模式下进入选中集 */
function onZoneClick(e) {
  if (activeTool.value || !props.batchSelect) return
  const feature = e.features?.[0]
  if (!feature) return
  toggleBatch('zone_ids', feature.id ?? feature.properties?.id, feature)
}

// ---------- v2.0 批量选择 ----------
const batchSel = reactive({ parcel_ids: [], poi_ids: [], zone_ids: [] })
const batchSelectedFeatures = ref([])
const batchTotal = computed(() =>
  batchSel.parcel_ids.length + batchSel.poi_ids.length + batchSel.zone_ids.length
)

function toggleBatch(key, id, feature) {
  if (id === null || id === undefined) return
  const arr = batchSel[key]
  const idx = arr.indexOf(id)
  if (idx >= 0) {
    arr.splice(idx, 1)
    batchSelectedFeatures.value = batchSelectedFeatures.value.filter((f) => f.__key !== `${key}:${id}`)
  } else {
    arr.push(id)
    batchSelectedFeatures.value.push({ ...feature, __key: `${key}:${id}` })
  }
  renderBatchSelected()
  emit('batch-selection', {
    parcel_ids: [...batchSel.parcel_ids],
    poi_ids: [...batchSel.poi_ids],
    zone_ids: [...batchSel.zone_ids],
  })
}

function renderBatchSelected() {
  if (!map || !map.getSource('batch-selected-source')) return
  map.getSource('batch-selected-source').setData({
    type: 'FeatureCollection',
    features: batchSelectedFeatures.value.map(({ __key, ...f }) => f),
  })
}

function ensureBatchLayer() {
  if (!map || map.getSource('batch-selected-source')) return
  map.addSource('batch-selected-source', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
  map.addLayer({
    id: 'batch-selected-line', type: 'line', source: 'batch-selected-source',
    paint: { 'line-color': '#facc15', 'line-width': 4, 'line-opacity': 0.95 },
  })
  map.addLayer({
    id: 'batch-selected-fill', type: 'fill', source: 'batch-selected-source',
    paint: { 'fill-color': '#facc15', 'fill-opacity': 0.18 },
  })
}

function clearBatchSelection() {
  batchSel.parcel_ids.splice(0)
  batchSel.poi_ids.splice(0)
  batchSel.zone_ids.splice(0)
  batchSelectedFeatures.value = []
  renderBatchSelected()
  emit('batch-selection', { parcel_ids: [], poi_ids: [], zone_ids: [] })
}

/** 适宜性评价单元点击：弹出得分与等级，并向页面抛出事件 */
function onCellsClick(e) {
  if (activeTool.value) return
  const feature = e.features?.[0]
  if (!feature) return
  emit('cells-click', feature)
  const p = feature.properties || {}
  const el = document.createElement('div')
  el.className = 'lv-popup'
  el.innerHTML = `
    <div class="lv-popup-title">适宜性评价单元</div>
    <div class="lv-popup-row"><span>综合得分</span><b>${p.score ?? '-'}</b></div>
    <div class="lv-popup-row"><span>适宜等级</span><b>${p.level ?? '-'}</b></div>`
  const popup = new maplibregl.Popup({ closeButton: true, offset: 6 })
    .setLngLat(e.lngLat).setDOMContent(el).addTo(map)
  popup.on('close', () => el.remove())
}

/** 可达性覆盖图斑点击：弹出覆盖情况，并向页面抛出事件 */
function onCoverageClick(e) {
  if (activeTool.value) return
  const feature = e.features?.[0]
  if (!feature) return
  emit('coverage-click', feature)
  const p = feature.properties || {}
  const near = (p.nearby || []).slice(0, 3)
    .map((n) => `${n.name}(${Math.round(n.distance_m)}m)`).join('、')
  const el = document.createElement('div')
  el.className = 'lv-popup'
  el.innerHTML = `
    <div class="lv-popup-title">${p.name || p.parcel_code}</div>
    <div class="lv-popup-row"><span>可达性</span><b>${p.covered ? '已覆盖' : '盲区'}</b></div>
    <div class="lv-popup-row"><span>覆盖设施数</span><b>${p.facility_count ?? 0}</b></div>
    <div class="lv-popup-row"><span>最近设施</span><b>${near || '无'}</b></div>`
  const popup = new maplibregl.Popup({ closeButton: true, offset: 8 })
    .setLngLat(e.lngLat).setDOMContent(el).addTo(map)
  popup.on('close', () => el.remove())
}

function highlight(id) {
  if (!map || !map.getLayer('parcels-line')) return
  const hl = 'parcels-selected'
  if (map.getLayer(hl)) map.removeLayer(hl)
  if (id !== null && id !== undefined) {
    map.addLayer({
      id: hl, type: 'line', source: 'parcels-source',
      filter: ['==', ['get', 'id'], Number(id)],
      paint: { 'line-color': '#facc15', 'line-width': 4 },
    })
  }
}

function fitIfNeeded() {
  if (!map || !props.autoFit || fitted) return
  // 有用户上次停留位置时不再自动缩放，尊重用户视图
  if (loadSavedView()) {
    fitted = true
    return
  }
  const all = [props.parcels, props.buffer, props.changes, props.cells, props.coverage].filter(Boolean)
  const features = all.flatMap((fc) => fc.features || [])
  if (features.length > 0) {
    const bounds = new maplibregl.LngLatBounds()
    features.forEach((f) => {
      if (f.geometry) extendBounds(bounds, f.geometry)
    })
    if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 50, duration: 800 })
  }
  fitted = true
}

// ===========================================================================
// 工具：选择与测量
// ===========================================================================

function setTool(tool) {
  activeTool.value = activeTool.value === tool ? null : tool
  map.getCanvas().style.cursor = activeTool.value ? 'crosshair' : ''
  if (activeTool.value !== 'box') map.dragPan.enable()
}

function onMapMouseDown(e) {
  if (activeTool.value !== 'box') return
  map.dragPan.disable()
  drawState.box = { start: [e.lngLat.lng, e.lngLat.lat] }
}

function onMapMouseUp(e) {
  if (activeTool.value !== 'box' || !drawState.box) return
  const end = [e.lngLat.lng, e.lngLat.lat]
  map.dragPan.enable()
  setDrawData(boxFeature(drawState.box.start, end))
  const bbox = [[Math.min(drawState.box.start[0], end[0]), Math.min(drawState.box.start[1], end[1])],
                [Math.max(drawState.box.start[0], end[0]), Math.max(drawState.box.start[1], end[1])]]
  drawState.box = null
  applySelection({ type: 'box', bbox }, boxFeature([bbox[0][0], bbox[0][1]], [bbox[1][0], bbox[1][1]]))
}

function onMapClick(e) {
  const lnglat = [e.lngLat.lng, e.lngLat.lat]
  switch (activeTool.value) {
    case 'circle':
      if (!drawState.circle) {
        drawState.circle = { center: lnglat }
        setDrawData(pointFeature(lnglat))
      } else {
        const { center } = drawState.circle
        drawState.circle = null
        const radiusM = lineLengthM([center, lnglat])
        applySelection({ type: 'circle', center, radiusM }, circleFeature(center, radiusM))
      }
      break
    case 'polygon':
      drawState.polygon.push(lnglat)
      updatePolygonDraw(drawState.polygon)
      break
    case 'distance':
      drawState.line.push(lnglat)
      updateLineDraw(drawState.line)
      measureText.value = `距离：${lineLengthM(drawState.line).toFixed(1)} m（双击结束）`
      break
    case 'area':
      drawState.area.push(lnglat)
      updateAreaDraw(drawState.area)
      measureText.value = `面积：${(polygonAreaSqm(drawState.area) / 10000).toFixed(2)} 公顷（右键结束）`
      break
  }
}

function finishPolygonTool() {
  const pts = activeTool.value === 'polygon' ? drawState.polygon : drawState.area
  if (pts.length >= 3) {
    const ring = [...pts, pts[0]]
    setDrawData(polygonFeature(ring))
    if (activeTool.value === 'polygon') {
      applySelection({ type: 'polygon', ring }, polygonFeature(ring))
    } else {
      // 面积测量 → 存入测量层
      pushToMeasure(polygonFeature(ring))
      measureText.value = `面积：${(polygonAreaSqm(ring) / 10000).toFixed(2)} 公顷`
    }
  }
  if (activeTool.value === 'polygon') drawState.polygon = []
  else drawState.area = []
  setTool(null)
}

function finishLineTool() {
  if (drawState.line.length >= 2) {
    pushToMeasure(lineFeature(drawState.line))
    measureText.value = `距离：${lineLengthM(drawState.line).toFixed(1)} m`
  }
  drawState.line = []
  setTool(null)
}

function applySelection(shape, shapeGeojson) {
  if (!props.enableSelection) return
  const features = (props.parcels.features || []).filter((f) => featureInShape(f, shape))
  const byLandUse = {}
  let areaSqm = 0
  features.forEach((f) => {
    const lu = f.properties.land_use || '未知'
    byLandUse[lu] = (byLandUse[lu] || 0) + 1
    areaSqm += f.properties.area_sqm || 0
  })
  selection.value = { count: features.length, areaSqm, byLandUse, features, geometry: shapeGeojson }
  ui.setSelection(selection.value)
  // 选择图形保留在地图
  map.getSource('selection-source').setData(shapeGeojson)
  emit('selection', selection.value)
}

function clearSelection() {
  selection.value = null
  ui.setSelection(null)
  if (map?.getSource('selection-source')) {
    map.getSource('selection-source').setData(EMPTY_FC())
  }
  emit('selection', null)
}

function clearDrawing() {
  setTool(null)
  drawState.polygon = []
  drawState.line = []
  drawState.area = []
  drawState.circle = null
  measureText.value = ''
  measureFeatures.value = []
  map.getSource('draw-source').setData(EMPTY_FC())
  map.getSource('measure-source').setData(EMPTY_FC())
  clearSelection()
}

// ---------- 绘制数据助手 ----------
const measureFeatures = ref([])
// v2.0：最近一次绘制（测量/勾绘的最后一个要素），供"保存绘制"入库
const lastDrawing = computed(() => {
  if (measureFeatures.value.length) return measureFeatures.value[measureFeatures.value.length - 1]
  return null
})
function setDrawData(feature) { map.getSource('draw-source').setData(fc(feature)) }
function pushToMeasure(feature) {
  measureFeatures.value = [...measureFeatures.value, feature]
  map.getSource('measure-source').setData({ type: 'FeatureCollection', features: measureFeatures.value })
  setDrawData(null)
}
function updateLineDraw(pts) { setDrawData(lineFeature(pts)) }
function updatePolygonDraw(pts) {
  if (pts.length < 2) { setDrawData(pointFeature(pts[0])); return }
  if (pts.length < 3) { setDrawData(lineFeature([...pts, pts[0]])); return }
  setDrawData(polygonFeature([...pts, pts[0]]))
}
function updateAreaDraw(pts) { updatePolygonDraw(pts) }

function fc(feature) { return { type: 'FeatureCollection', features: feature ? [feature] : [] } }
function pointFeature(c) { return { type: 'Feature', geometry: { type: 'Point', coordinates: c }, properties: {} } }
function lineFeature(pts) { return { type: 'Feature', geometry: { type: 'LineString', coordinates: pts }, properties: {} } }
function polygonFeature(ring) { return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} } }
function boxFeature(a, b) {
  const ring = [[a[0], a[1]], [b[0], a[1]], [b[0], b[1]], [a[0], b[1]], [a[0], a[1]]]
  return polygonFeature(ring)
}
function circleFeature(center, radiusM) {
  const ring = []
  const dLat = (radiusM / 111320) // 近似度
  const dLng = radiusM / (111320 * Math.cos((center[1] * Math.PI) / 180))
  for (let i = 0; i <= 48; i++) {
    const a = (i * 2 * Math.PI) / 48
    ring.push([center[0] + dLng * Math.cos(a), center[1] + dLat * Math.sin(a)])
  }
  return polygonFeature(ring)
}

// ===========================================================================
// 对外暴露 + 响应式
// ===========================================================================

/** 把 GeoJSON 几何的全部坐标对加入 LngLatBounds（修复：坐标扁平数组必须成对迭代） */
function extendBounds(bounds, geometry) {
  if (!geometry) return bounds
  const flat = geometry.coordinates.flat(Infinity)
  for (let i = 0; i + 1 < flat.length; i += 2) {
    bounds.extend([flat[i], flat[i + 1]])
  }
  return bounds
}

defineExpose({
  flyTo(feature) {
    if (!map || !feature || !feature.geometry) return
    const bounds = extendBounds(new maplibregl.LngLatBounds(), feature.geometry)
    if (!bounds.isEmpty()) map.fitBounds(bounds, { padding: 80, duration: 600 })
  },
  jumpTo({ center, zoom: z }) {
    if (map && center) map.jumpTo({ center, zoom: z ?? map.getZoom() })
  },
  // 按包围盒缩放视野（行政区定位：显示完整区域范围，随数据自适应）
  fitBounds(bbox) {
    if (!map || !bbox) return
    const [minx, miny, maxx, maxy] = bbox
    map.fitBounds([[minx, miny], [maxx, maxy]], { padding: 60, duration: 700 })
  },
  getMap: () => map,
  clearSelection,
  clearBatchSelection,
  clearDrawing,
  ready: computed(() => !!map),
})

function watchAll() {
  watch(() => props.parcels, (v) => ensureLayer('parcels', v))
  watch(() => props.pois, (v) => ensureLayer('pois', v))
  watch(() => props.zones, (v) => ensureLayer('zones', v))
  watch(() => props.changes, (v) => ensureLayer('changes', v))
  watch(() => props.cells, (v) => ensureLayer('cells', v))
  watch(() => props.coverage, (v) => ensureLayer('coverage', v))
  watch(() => props.regionBoundary, (v) => {
    if (map && map.getSource('regionBoundary-source')) {
      map.getSource('regionBoundary-source').setData(v || EMPTY_FC())
    } else if (v) {
      ensureLayer('regionBoundary', v)
    }
  })
  watch(() => props.buffer, (v) => {
    if (map && map.getSource('buffer-source')) {
      map.getSource('buffer-source').setData(v || EMPTY_FC())
    } else if (v) {
      ensureLayer('buffer', v)
    }
  })
  watch(() => props.highlightId, (v) => highlight(v))
  watch(() => props.autoFit, (v) => { if (v) fitIfNeeded() })
  // 图层面板 → 可见性
  watch(
    () => ({ ...ui.layerVisibility }),
    () => applyVisibility(),
    { deep: true }
  )
}
</script>

<style scoped>
.map-wrap {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
  border-radius: var(--lv-radius);
  overflow: hidden;
}
.map-canvas {
  position: absolute;
  inset: 0;
}
.map-tools {
  top: 10px;
  left: 10px;
  display: flex;
  gap: 4px;
  padding: 6px;
  align-items: center;
}
.map-tools.compact {
  top: 50%;
  left: 10px;
  transform: translateY(-50%);
  flex-direction: column;
}
.map-tools.compact .tool-divider {
  width: 16px;
  height: 1px;
}
.tool-btn {
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--lv-text-secondary);
  cursor: pointer;
  font-size: 15px;
}
.tool-btn:hover {
  background: var(--lv-primary-light);
  color: var(--lv-primary);
}
.tool-btn.active {
  background: var(--lv-primary);
  color: #fff;
}
.tool-divider {
  width: 1px;
  height: 16px;
  background: var(--lv-border);
}
.right-icon-bar {
  top: 210px; /* 整体下移约 2cm，避开右上角导航控件 */
  right: 10px;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  padding: 0;
  background: transparent;
  border: none;
  box-shadow: none;
  z-index: 12;
}
.icon-stack-item {
  display: flex;
  justify-content: flex-end;
}
.icon-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--lv-radius-sm);
  background: var(--lv-surface-glass);
  backdrop-filter: blur(8px);
  box-shadow: var(--lv-shadow);
  color: var(--lv-text-secondary);
  cursor: pointer;
}
.icon-btn:hover,
.icon-btn.active {
  background: var(--lv-primary);
  color: #fff;
}
/* 展开面板：内嵌于图标栏，向左展开，随图标栏拖拽移动 */
.right-panel-inner {
  position: absolute;
  right: 44px;
  top: 0;
  width: 200px;
  max-height: min(60vh, 480px);
  overflow-y: auto;
  padding: 10px;
  z-index: 12;
}
.layer-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--lv-text);
}
.layer-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 3px 0;
  cursor: pointer;
  color: var(--lv-text);
}
.layer-item input {
  accent-color: var(--lv-primary);
}
.layer-swatch {
  width: 12px;
  height: 12px;
  border-radius: 3px;
  display: inline-block;
  flex-shrink: 0;
}
.legend-group-title {
  color: var(--lv-text-secondary);
  font-size: 11px;
  margin: 6px 0 2px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 1px 0;
  color: var(--lv-text);
}
.measure-result {
  left: 50%;
  top: 12px;
  transform: translateX(-50%);
  padding: 6px 14px;
  font-weight: 600;
  color: var(--lv-primary);
}
.selection-panel {
  bottom: 40px;
  left: 10px;
  width: 180px;
  padding: 10px;
}
.batch-bar {
  top: 56px;
  left: 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--lv-text);
}
.batch-bar .batch-title {
  font-weight: 600;
  color: var(--lv-primary);
}
.save-drawing-bar {
  top: 96px;
  left: 10px;
  padding: 6px 10px;
}
.selection-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--lv-text);
}
.selection-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 1px 0;
  color: var(--lv-text);
}
.coord-readout {
  bottom: 8px;
  left: 10px;
  padding: 4px 10px;
  color: var(--lv-text-secondary);
  font-variant-numeric: tabular-nums;
}
</style>

<style>
/* 弹窗样式（全局，MapLibre popup 在组件外渲染） */
.lv-popup {
  min-width: 190px;
  padding: 4px;
}
.lv-popup-title {
  font-size: 14px;
  font-weight: 700;
  color: #1f2937;
  margin-bottom: 6px;
}
.lv-popup-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #6b7280;
  padding: 2px 0;
}
.lv-popup-row b {
  color: #1f2937;
}
.lv-popup-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.lv-popup-btn {
  flex: 1;
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 6px;
  padding: 5px 0;
  font-size: 12px;
  cursor: pointer;
  color: #374151;
}
.lv-popup-btn.primary {
  background: #2e86ab;
  border-color: #2e86ab;
  color: #fff;
}
.lv-popup-btn:hover {
  opacity: 0.85;
}
</style>
