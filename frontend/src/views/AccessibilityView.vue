<template>
  <div class="page-fullmap">
    <!-- 全屏地图：地块 + 设施 POI + 覆盖/盲区专题 -->
    <MapView
      ref="mapRef"
      :parcels="store.parcelsGeojson"
      :pois="filteredPois"
      :coverage="coverageFc"
      :buffer="sitesFc.features.length ? sitesFc : null"
      :region-boundary="boundaryGeojson"
      enable-selection
      @selection="onMapDraw"
      @region-select="onRegionSelect"
      @region-locate="onRegionLocate"
    />

    <!-- 左侧：图标栏 -->
    <button class="page-icon-btn icon-left1" :class="{ active: panel === 'setup' }" title="分析设置"
            @click="panel = panel === 'setup' ? null : 'setup'">
      <el-icon :size="18"><Setting /></el-icon>
    </button>
    <button class="page-icon-btn icon-left2" :class="{ active: panel === 'result' }" title="分析结果"
            @click="panel = panel === 'result' ? null : 'result'">
      <el-icon :size="18"><DataAnalysis /></el-icon>
    </button>

    <!-- 左侧面板一：分析设置 -->
    <div v-if="panel === 'setup'" class="page-panel panel-left glass-panel">
      <div class="panel-title">服务设施可达性分析设置（生活圈覆盖）</div>

      <div class="section-title">① 方法说明</div>
      <el-alert class="mb" type="info" :closable="false"
        title="以地块几何中心为起点，计算到所选设施（POI）的直线距离；距离 ≤ 服务半径即判定覆盖（达标），否则列入盲区清单。参照《城市居住区规划设计标准》15 分钟生活圈理念，默认半径 800 m。" />

      <div class="section-title">② 设施类型（不勾选 = 全部设施）</div>
      <el-alert v-if="linkedFacilityHint" class="mb" type="success" :closable="false" :title="linkedFacilityHint" />
      <el-checkbox-group v-model="facilityTypes" size="small" class="mb">
        <el-checkbox v-for="t in POI_TYPES" :key="t" :label="t">
          <span class="legend-dot" :style="{ background: POI_COLORS[t] }"></span>{{ t }}
        </el-checkbox>
      </el-checkbox-group>

      <div class="section-title">③ 服务半径</div>
      <div class="flex-row mb">
        <el-slider v-model="radius" :min="100" :max="3000" :step="100" style="flex:1" />
        <el-input-number v-model="radius" :min="100" :max="10000" :step="100" size="small" style="width:110px" />
        <span class="scope-hint">米</span>
      </div>
      <div class="flex-row mb">
        <el-radio-group v-model="radius" size="small">
          <el-radio-button :label="300">300m</el-radio-button>
          <el-radio-button :label="500">500m</el-radio-button>
          <el-radio-button :label="800">800m</el-radio-button>
          <el-radio-button :label="1000">1000m</el-radio-button>
          <el-radio-button :label="1500">1500m</el-radio-button>
        </el-radio-group>
      </div>

      <el-divider />

      <div class="section-title">④ 分析范围（可选，四种方式任选）</div>
      <el-radio-group v-model="scopeMode" size="small" class="mb">
        <el-radio-button label="none">全部地块</el-radio-button>
        <el-radio-button label="region">当前行政区</el-radio-button>
        <el-radio-button label="shp">导入 SHP 范围</el-radio-button>
        <el-radio-button label="manual">手动划定</el-radio-button>
      </el-radio-group>
      <div v-if="scopeMode === 'region'" class="scope-hint">
        <template v-if="currentRegion">
          当前行政区：<el-tag size="small">{{ currentRegion.name }}（{{ currentRegion.code }}）</el-tag>
        </template>
        <template v-else>请先在地图右上角行政区选择器逐级选到区县</template>
      </div>
      <div v-if="scopeMode === 'shp'" class="flex-row">
        <el-upload :auto-upload="false" :limit="1" accept=".zip" :show-file-list="false"
                   :on-change="(f) => (scopeFile = f.raw)">
          <el-button size="small" type="primary">选择 SHP zip</el-button>
        </el-upload>
        <el-button size="small" :loading="scopeImporting" :disabled="!scopeFile" @click="importScopeShp">导入为范围</el-button>
      </div>
      <div v-if="scopeMode === 'manual'" class="scope-hint">
        使用地图左侧工具（多边形/框选/圈选）在图上划定范围，划定后自动生效
      </div>
      <div v-if="scopeGeojson" class="scope-status">
        <el-tag size="small" type="success" closable @close="clearScope">已划定分析范围</el-tag>
      </div>

      <div class="flex-row mt">
        <el-button type="primary" style="margin-left:auto" :loading="running" @click="runAnalyze">
          执行可达性分析
        </el-button>
      </div>
    </div>

    <!-- 左侧面板二：分析结果 -->
    <div v-if="panel === 'result'" class="page-panel panel-left glass-panel">
      <div class="panel-title">设施可达性分析结果（服务半径 {{ result?.radius_m || radius }} m）</div>
      <el-skeleton v-if="running" :rows="10" animated />
      <template v-else-if="result">
        <el-row :gutter="8" class="mb">
          <el-col :span="6"><div class="sum-card">覆盖地块<b>{{ result.covered_count }} / {{ result.parcel_total }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">覆盖率<b>{{ (result.coverage_rate * 100).toFixed(1) }}<i>%</i></b></div></el-col>
          <el-col :span="6"><div class="sum-card">盲区地块<b>{{ result.gap_count }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">服务半径<b>{{ result.radius_m }}<i>米</i></b></div></el-col>
        </el-row>

        <el-alert v-if="!result.parcel_total" class="mb" type="warning" :closable="false"
                  title="范围内没有地块。请检查分析范围是否覆盖了地块图层。" />

        <el-row :gutter="8">
          <el-col :span="11">
            <div class="section-title">覆盖 / 盲区构成</div>
            <div ref="pieEl" class="chart-md"></div>
          </el-col>
          <el-col :span="13">
            <div class="section-title">盲区清单（按地块）</div>
            <el-table v-if="result.gaps.length" :data="result.gaps" size="small" border max-height="210">
              <el-table-column prop="parcel_code" label="编号" width="76" fixed />
              <el-table-column prop="name" label="地块" min-width="92" show-overflow-tooltip />
              <el-table-column prop="land_use" label="用地类型" width="88" show-overflow-tooltip />
              <el-table-column label="操作" width="52" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" link type="primary" @click="locateGap(row)">定位</el-button>
                </template>
              </el-table-column>
            </el-table>
            <el-empty v-else description="无盲区，所有地块均在服务半径内" :image-size="56" />
          </el-col>
        </el-row>

        <div class="scope-hint mt">
          地图绿色 = 已覆盖地块，红色 = 盲区地块；点击覆盖图斑可查看最近设施（名称/距离）。
        </div>
        <!-- v2.0 联动：盲区 × 适宜性 → 推荐设施选址 -->
        <div class="mt">
          <el-button size="small" type="warning" plain :loading="sitesLoading" @click="recommendSites">
            推荐设施选址（盲区 ∩ 适宜布局区）
          </el-button>
          <span v-if="sitesFc.count" class="scope-hint">已找到 {{ sitesFc.count }} 个候选区域（地图蓝色虚线）</span>
        </div>
      </template>
      <el-empty v-else description="完成左侧设置后，点击“执行可达性分析”" />
    </div>
  </div>
</template>

<script setup>
/**
 * AccessibilityView —— 模块三：服务设施可达性分析
 * 地块质心 → 所选 POI 的直线距离 ≤ 服务半径 = 覆盖；输出覆盖率 + 盲区清单 + 覆盖专题图。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { useParcelStore } from '../stores/parcel'
import { useUiStore } from '../stores/ui'
import {
  getRegion, getPoisGeoJSON, accessibilityAnalyze, parseScopeShp, getFacilitySites,
} from '../api'
import { POI_COLORS } from '../utils/colors'
import MapView from '../components/MapView.vue'

const POI_TYPES = Object.keys(POI_COLORS)

const store = useParcelStore()
const ui = useUiStore()

const mapRef = ref(null)
const panel = ref(null)
const boundaryGeojson = ref(null)

// 分析设置
const facilityTypes = ref([])
const radius = ref(800)
const scopeMode = ref('none')
const currentRegion = ref(null)
const scopeGeojson = ref(null)
const scopeFile = ref(null)
const scopeImporting = ref(false)
// v3.0 联动：转移矩阵预置的设施类型提示
const linkedFacilityHint = ref('')

// 结果
const running = ref(false)
const result = ref(null)
const pieEl = ref(null)
let charts = []

const poisGeojson = ref({ type: 'FeatureCollection', features: [] })
const coverageFc = computed(() => result.value?.parcels_geojson || { type: 'FeatureCollection', features: [] })

/** 地图上只显示所选类型的设施（不选 = 全部） */
const filteredPois = computed(() => {
  const set = new Set(facilityTypes.value)
  if (!set.size) return poisGeojson.value
  return {
    type: 'FeatureCollection',
    features: (poisGeojson.value.features || []).filter((f) => set.has(f.properties?.poi_type)),
  }
})

onMounted(async () => {
  await Promise.all([
    store.fetchParcelsGeojson(),
    loadPois(),
  ])
  // v3.0 联动：转移矩阵 → 预置设施类型（先于范围继承处理，均消费后清除）
  if (ui.linkedFacilityTypes?.length) {
    facilityTypes.value = [...ui.linkedFacilityTypes]
    linkedFacilityHint.value = `已按转移矩阵结果预置设施类型：${ui.linkedFacilityTypes.join('、')}`
    ui.setLinkedFacilityTypes([])
    ElMessage.info(`已接收联动预置设施类型：${facilityTypes.value.join('、')}`)
  }
  // v2.0 范围统一继承：转移矩阵联动范围 ＞ 当前项目范围
  if (ui.linkedScope) {
    scopeGeojson.value = ui.linkedScope
    scopeMode.value = 'manual'
    ui.setLinkedPatches(null, null, null)
    ElMessage.info('已接收联动范围（新增建设用地图斑），可直接执行可达性分析')
  } else if (ui.currentProject?.scope_geojson) {
    scopeGeojson.value = ui.currentProject.scope_geojson
    scopeMode.value = 'region'
  }
})

onBeforeUnmount(() => {
  charts.forEach((c) => c.dispose())
  charts = []
})

async function loadPois() {
  try {
    poisGeojson.value = await getPoisGeoJSON()
  } catch (e) {
    ElMessage.error('加载 POI 失败：' + (e?.message || '未知原因'))
  }
}

// ---------- 行政区联动 ----------
function onRegionSelect(region) {
  currentRegion.value = region?.level === 'county' ? region : null
}

async function onRegionLocate(locate) {
  if (mapRef.value && locate.bbox) mapRef.value.fitBounds(locate.bbox)
  try {
    const r = await getRegion(locate.code)
    boundaryGeojson.value = r?.geometry
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: r.geometry, properties: {} }] }
      : null
  } catch (e) {
    boundaryGeojson.value = null
  }
  if (scopeMode.value === 'region' && locate.level === 'county') {
    scopeGeojson.value = boundaryGeojson.value?.features?.[0]?.geometry || null
  }
}

// ---------- 分析范围 ----------
watch(scopeMode, (mode) => {
  if (mode === 'manual' && !scopeGeojson.value) {
    panel.value = null
    ElMessage.info('请使用地图左侧工具（多边形/框选/圈选）绘制分析范围，画完自动返回设置面板')
  }
})

function onMapDraw(selection) {
  if (!selection?.geometry) return
  if (scopeMode.value === 'manual') {
    scopeGeojson.value = selection.geometry
    ElMessage.success('手动分析范围已划定，已自动回到设置面板')
    panel.value = 'setup'
  }
}

function clearScope() {
  scopeGeojson.value = null
  scopeFile.value = null
}

async function importScopeShp() {
  if (!scopeFile.value) return
  scopeImporting.value = true
  try {
    const fd = new FormData()
    fd.append('file', scopeFile.value)
    const r = await parseScopeShp(fd)
    scopeGeojson.value = r.scope
    if (r.bbox) mapRef.value?.fitBounds(r.bbox)
    ElMessage.success(`SHP 范围已导入（合并 ${r.feature_count} 个要素）`)
  } finally {
    scopeImporting.value = false
  }
}

// ---------- 分析计算 ----------
async function runAnalyze() {
  running.value = true
  panel.value = 'result'
  try {
    result.value = await accessibilityAnalyze({
      facility_types: facilityTypes.value.length ? facilityTypes.value : [],
      radius_m: radius.value,
      scope: scopeGeojson.value || null,
      project_id: ui.currentProjectId || null,
    })
    ui.bumpAnalysisVersion()  // v3.0：通知驾驶舱自动刷新
  } catch (e) {
    ElMessage.error('分析失败：' + (e?.message || '未知原因'))
  } finally {
    running.value = false
  }
  await nextTick()
  renderCharts()
  fitToCoverage()
  setTimeout(() => charts.forEach((c) => c.resize()), 80)
}

// ---------- v2.0 联动：盲区 ∩ 适宜区 → 推荐设施选址 ----------
const sitesFc = ref({ type: 'FeatureCollection', features: [] })
const sitesLoading = ref(false)

async function recommendSites() {
  if (!ui.currentProjectId) {
    ElMessage.warning('请先在顶栏选择分析项目（推荐选址基于该项目持久化的可达性与适宜性结果）')
    return
  }
  sitesLoading.value = true
  try {
    const data = await getFacilitySites({ project_id: ui.currentProjectId })
    sitesFc.value = data
    if (data.count) {
      ElMessage.success(`推荐设施选址：找到 ${data.count} 个候选区域（盲区 ∩ 适宜布局区）`)
      fitToSites()
    } else {
      ElMessage.info(data.hint || '暂无候选区域：请先执行可达性分析与适宜性评价')
    }
  } finally {
    sitesLoading.value = false
  }
}

function fitToSites() {
  const first = sitesFc.value.features?.[0]?.geometry
  const bbox = first ? bboxOfGeom(first) : null
  if (bbox) mapRef.value?.fitBounds(bbox)
}

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
  const r = result.value
  if (pieEl.value && r && r.parcel_total > 0) {
    const pie = echarts.init(pieEl.value)
    pie.setOption({
      tooltip: { trigger: 'item', formatter: '{b}：{c} 宗（{d}%）' },
      series: [{
        type: 'pie',
        radius: ['38%', '62%'],
        label: { formatter: '{b}\n{d}%', fontSize: 10 },
        data: [
          { name: '已覆盖', value: r.covered_count, itemStyle: { color: '#16a34a' } },
          { name: '盲区', value: r.gap_count, itemStyle: { color: '#ef4444' } },
        ],
      }],
    })
    charts.push(pie)
  } else if (pieEl.value) {
    const pie = echarts.init(pieEl.value)
    pie.setOption({ title: { text: '范围内无地块', left: 'center', top: 'middle', textStyle: { fontSize: 12, color: '#999' } } })
    charts.push(pie)
  }
}

function bboxOfGeom(geom) {
  if (!geom?.coordinates) return null
  const flat = geom.coordinates.flat(Infinity)
  if (!flat.length) return null
  let minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity
  for (let i = 0; i + 1 < flat.length; i += 2) {
    minx = Math.min(minx, flat[i]); maxx = Math.max(maxx, flat[i])
    miny = Math.min(miny, flat[i + 1]); maxy = Math.max(maxy, flat[i + 1])
  }
  return [minx, miny, maxx, maxy]
}

function fitToCoverage() {
  const first = coverageFc.value.features?.[0]?.geometry
  const target = first ? bboxOfGeom(first) : (scopeGeojson.value ? bboxOfGeom(scopeGeojson.value) : null)
  if (target) mapRef.value?.fitBounds(target)
}

function locateGap(row) {
  const feature = coverageFc.value.features?.find((f) => f.properties?.parcel_code === row.parcel_code)
  if (feature) {
    mapRef.value?.flyTo(feature)
  } else {
    ElMessage.warning('未在地图上找到该地块图斑')
  }
}
</script>

<style scoped>
.page-fullmap {
  position: relative;
  height: calc(100vh - 122px);
  min-height: 640px;
  border-radius: var(--lv-radius);
  overflow: hidden;
}
.page-fullmap :deep(.map-wrap) {
  border-radius: 0;
  position: absolute;
  inset: 0;
}
.page-icon-btn {
  position: absolute;
  z-index: 7;
  width: 36px;
  height: 36px;
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
.page-icon-btn:hover,
.page-icon-btn.active {
  background: var(--lv-primary);
  color: #fff;
}
.icon-left1 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% - 26px));
}
.icon-left2 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% + 26px));
}
.page-panel {
  position: absolute;
  z-index: 6;
  width: 680px;
  max-width: 50vw;
  max-height: calc(100% - 28px);
  overflow-y: auto;
}
.panel-left {
  left: 54px;
  top: 14px;
  bottom: 14px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lv-text);
  margin: 6px 0 8px;
}
.scope-hint {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-bottom: 8px;
}
.scope-status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0;
}
.sum-card {
  text-align: center;
  padding: 10px 4px;
  border-radius: 8px;
  background: var(--lv-bg);
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.sum-card b {
  display: block;
  font-size: 16px;
  color: var(--lv-primary);
  margin-top: 2px;
}
.sum-card i {
  font-style: normal;
  font-size: 11px;
  color: var(--lv-text-tertiary);
}
.flex-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.mb {
  margin-bottom: 10px;
}
.mt {
  margin-top: 12px;
}
.chart-md {
  height: 230px;
}
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  margin-right: 4px;
  vertical-align: -1px;
}
</style>
