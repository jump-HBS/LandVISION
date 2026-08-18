<template>
  <div class="page-fullmap">
    <!-- 全屏地图：地块 + 变化图斑 -->
    <MapView
      ref="mapRef"
      :parcels="store.parcelsGeojson"
      :changes="changesFc"
      :region-boundary="boundaryGeojson"
      enable-selection
      @selection="onMapDraw"
      @region-select="onRegionSelect"
      @region-locate="onRegionLocate"
    />

    <!-- 左侧：图标栏 -->
    <button class="page-icon-btn icon-left1" :class="{ active: panel === 'setup' }" title="数据准备"
            @click="panel = panel === 'setup' ? null : 'setup'">
      <el-icon :size="18"><Upload /></el-icon>
    </button>
    <button class="page-icon-btn icon-left2" :class="{ active: panel === 'result' }" title="转移矩阵"
            @click="panel = panel === 'result' ? null : 'result'">
      <el-icon :size="18"><DataAnalysis /></el-icon>
    </button>

    <!-- 左侧面板一：数据准备 -->
    <div v-if="panel === 'setup'" class="page-panel panel-left glass-panel">
      <div class="panel-title">两期用地数据准备（转移矩阵）</div>

      <div class="section-title">① 方法说明</div>
      <el-alert class="mb" type="info" :closable="false"
        title="转移矩阵 = 基期（base，变化前）与末期（current，变化后）两期地块叠加求交，按地类组合统计转换面积；同时识别消失图斑（基期未保留）与新增图斑（末期新出现）。" />

      <div class="section-title">② 期次地块数据</div>
      <div class="flex-row mb">
        <el-radio-group v-model="importPeriod" size="small">
          <el-radio-button label="base">基期（变化前）</el-radio-button>
          <el-radio-button label="current">末期（变化后）</el-radio-button>
        </el-radio-group>
      </div>
      <div class="flex-row mb">
        <el-upload :auto-upload="false" :limit="1" accept=".zip" :show-file-list="false"
                   :on-change="(f) => (importFile = f.raw)">
          <el-button size="small" type="primary">选择 SHP zip（WGS84 面要素）</el-button>
        </el-upload>
        <el-button size="small" :loading="importing" :disabled="!importFile" @click="doImport">
          导入为{{ importPeriod === 'base' ? '基期' : '末期' }}
        </el-button>
      </div>
      <div class="flex-row mb">
        <el-button size="small" type="warning" plain :loading="demoGenerating" @click="generateDemo">
          一键生成演示基期（模拟 1 转换 + 1 消失 + 1 新增）
        </el-button>
      </div>
      <div class="scope-hint">期次数据状态：{{ periodStatus }}</div>

      <el-divider />

      <div class="section-title">③ 分析范围（可选，三种方式任选）</div>
      <el-radio-group v-model="scopeMode" size="small" class="mb">
        <el-radio-button label="none">不限定范围</el-radio-button>
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
        <el-button type="primary" style="margin-left:auto" :loading="running" @click="runMatrix">
          计算转移矩阵
        </el-button>
      </div>
    </div>

    <!-- 左侧面板二：转移矩阵结果 -->
    <div v-if="panel === 'result'" class="page-panel panel-left glass-panel">
      <div class="panel-title">用地变化转移矩阵（单位：公顷）</div>
      <el-skeleton v-if="running" :rows="10" animated />
      <template v-else-if="result">
        <el-alert v-if="result.hint && !result.rows.length" class="mb" type="warning" :closable="false"
                  :title="result.hint" />

        <el-row :gutter="8" class="mb">
          <el-col :span="6"><div class="sum-card">基期地块<b>{{ result.base_count }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">末期地块<b>{{ result.current_count }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">变化图斑<b>{{ changesFc.features.length }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">变化总面积<b>{{ (changeArea / 10000).toFixed(1) }}<i>公顷</i></b></div></el-col>
        </el-row>

        <div v-if="matrixData.fromUses.length" class="mb">
          <div class="section-title">转移矩阵（行 = 基期地类 → 列 = 末期地类，色深 = 面积占比）</div>
          <el-table :data="matrixRows" size="small" border max-height="230">
            <el-table-column label="基期 \ 末期" width="132" fixed>
              <template #default="{ row }">
                <span class="legend-dot" :style="{ background: landUseColor(row.use) }"></span>
                <span class="cell-use">{{ row.use }}</span>
              </template>
            </el-table-column>
            <el-table-column v-for="t in matrixData.toUses" :key="t" :label="t" width="92" align="right">
              <template #default="{ row }">
                <div class="cell-heat" :style="cellStyle(row.use, t)">
                  {{ fmtHa(matrixData.val(row.use, t)) }}
                </div>
              </template>
            </el-table-column>
            <el-table-column label="基期合计" width="92" align="right" fixed="right">
              <template #default="{ row }">
                <b>{{ fmtHa(matrixData.rowTotals[useIndex(row.use)]) }}</b>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="vanishAdded.length" class="change-chips mb">
          <el-tag v-for="c in vanishAdded" :key="c.label" size="small" effect="dark"
                  :type="c.label === '新增' ? 'success' : 'danger'">
            {{ c.label }}图斑（{{ c.label === '新增' ? '末期新出现' : '基期未保留' }}）：{{ (c.area / 10000).toFixed(2) }} 公顷
          </el-tag>
        </div>

        <!-- v2.0 模块联动：变化图斑 → 体检 / 适宜性 / 可达性 -->
        <div v-if="changesFc.features.length" class="mt mb">
          <div class="section-title">模块联动（基于变化图斑）</div>
          <div class="flex-row">
            <el-button size="small" type="danger" plain :disabled="!patchIds.length" @click="linkToPlanning">
              对变化图斑进行合规检查（{{ patchIds.length }}）
            </el-button>
            <el-button size="small" type="success" plain :disabled="!addedGeom" @click="linkToSuitability">
              评估新增用地适宜性
            </el-button>
            <el-button size="small" type="primary" plain :disabled="!addedGeom" @click="linkToAccessibility">
              分析新增用地设施可达性
            </el-button>
          </div>
          <div class="scope-hint mt">
            联动说明：合规检查 → 图斑体检（模块四）；适宜性/可达性 → 以「新增」图斑并集范围作为分析对象（需先选择分析项目，结果按项目持久化）。
          </div>
        </div>

        <div v-if="result.summary.length">
          <div class="section-title">各地类面积增减（公顷，基期 vs 末期）</div>
          <div ref="summaryBarEl" class="chart-lg"></div>
          <el-table :data="result.summary" size="small" border max-height="200">
            <el-table-column label="地类" min-width="110">
              <template #default="{ row }">
                <span class="legend-dot" :style="{ background: landUseColor(row.land_use) }"></span>
                {{ row.land_use }}
              </template>
            </el-table-column>
            <el-table-column label="基期(公顷)" align="right" width="96">
              <template #default="{ row }">{{ (row.base_area_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="末期(公顷)" align="right" width="96">
              <template #default="{ row }">{{ (row.current_area_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
            <el-table-column label="增减(公顷)" align="right" width="96">
              <template #default="{ row }">
                <span :class="row.delta_sqm >= 0 ? 'delta-up' : 'delta-down'">
                  {{ (row.delta_sqm / 10000).toFixed(2) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
      <el-empty v-else description="先导入两期地块数据（或一键生成演示基期），再点击“计算转移矩阵”" />
    </div>
  </div>
</template>

<script setup>
/**
 * TransferMatrixView —— 模块一：用地变化转移矩阵
 * 流程：导入基期/末期 SHP（或一键生成演示基期）→ 划定可选范围 → 计算矩阵
 *       → 矩阵表 + 面积增减图 + 变化图斑上图。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts'
import { useParcelStore } from '../stores/parcel'
import { useUiStore } from '../stores/ui'
import { useRouter } from 'vue-router'
import {
  getRegion, importTransitionShp, generateDemoBase, transitionMatrix, parseScopeShp,
} from '../api'
import { LAND_USE_ORDER, LAND_USE_COLORS } from '../utils/colors'
import MapView from '../components/MapView.vue'

const store = useParcelStore()
const ui = useUiStore()
const router = useRouter()

// ---------- v2.0 联动参数 ----------
const patchIds = computed(() =>
  (changesFc.value.features || []).map((f) => f.properties.patch_id).filter(Boolean)
)
const addedGeom = computed(() => {
  const geoms = (changesFc.value.features || [])
    .filter((f) => f.properties.kind === '新增' || f.properties.change_type === '新增建设')
    .map((f) => f.geometry)
  return geoms.length ? { type: 'GeometryCollection', geometries: geoms } : null
})

function requireProject() {
  if (!ui.currentProjectId) {
    ElMessage.warning('请先在顶栏选择分析项目（联动结果按项目持久化）')
    return false
  }
  return true
}

function linkToPlanning() {
  if (!requireProject()) return
  ui.setLinkedPatches(patchIds.value, null, '转移矩阵变化图斑')
  router.push('/planning')
}

function linkToSuitability() {
  if (!requireProject() || !addedGeom.value) return
  ui.setLinkedPatches(null, addedGeom.value, '新增建设用地图斑')
  router.push('/suitability')
}

function linkToAccessibility() {
  if (!requireProject() || !addedGeom.value) return
  ui.setLinkedPatches(null, addedGeom.value, '新增建设用地图斑')
  router.push('/accessibility')
}

const mapRef = ref(null)
const panel = ref(null)
const boundaryGeojson = ref(null)

// 期次数据
const importPeriod = ref('base')
const importFile = ref(null)
const importing = ref(false)
const demoGenerating = ref(false)

// 分析范围
const scopeMode = ref('none')
const currentRegion = ref(null)
const scopeGeojson = ref(null)
const scopeFile = ref(null)
const scopeImporting = ref(false)

// 结果
const running = ref(false)
const result = ref(null)
const summaryBarEl = ref(null)
let charts = []

const landUseColor = (use) => LAND_USE_COLORS[use] || '#94a3b8'
const useIndex = (use) => {
  const i = LAND_USE_ORDER.indexOf(use)
  return i >= 0 ? i : 99
}
const fmtHa = (sqm) => (sqm > 0 ? (sqm / 10000).toFixed(2) : '-')

/** 变化图斑：把后端 kind 归一化为 MapView changes 图层认识的 change_type */
const changesFc = computed(() => {
  const fc = result.value?.changes_geojson || { type: 'FeatureCollection', features: [] }
  const features = (fc.features || []).map((f) => {
    const p = { ...f.properties }
    if (p.kind === '新增' && p.change_type === '新增') p.change_type = '新增建设'
    if (p.kind === '消失' && p.change_type === '拆除') p.change_type = '拆除'
    return { ...f, properties: p }
  })
  return { type: 'FeatureCollection', features }
})

/** 矩阵透视：行 = 基期地类，列 = 末期地类 */
const matrixData = computed(() => {
  const r = result.value
  if (!r) return { fromUses: [], toUses: [], vanish: [], added: [], val: () => 0, rowTotals: [], colTotals: [], maxCell: 1 }
  const rows = r.rows || []
  const vanish = rows.filter((x) => x.from_use === '（消失）')
  const added = rows.filter((x) => x.to_use === '（新增）')
  const real = rows.filter((x) => x.from_use !== '（消失）' && !x.to_use.includes('—'))
  const fromUses = [...new Set(real.map((x) => x.from_use))].sort((a, b) => useIndex(a) - useIndex(b))
  const toUses = [...new Set(real.map((x) => x.to_use))].sort((a, b) => useIndex(a) - useIndex(b))
  const val = (f, t) => real.find((x) => x.from_use === f && x.to_use === t)?.area_sqm || 0
  const rowTotals = fromUses.map((f) => real.filter((x) => x.from_use === f).reduce((s, x) => s + x.area_sqm, 0))
  const colTotals = toUses.map((t) => real.filter((x) => x.to_use === t).reduce((s, x) => s + x.area_sqm, 0))
  const maxCell = Math.max(1, ...real.map((x) => x.area_sqm))
  return { fromUses, toUses, vanish, added, val, rowTotals, colTotals, maxCell }
})

const matrixRows = computed(() => matrixData.value.fromUses.map((use) => ({ use })))

const vanishAdded = computed(() => {
  const m = matrixData.value
  const chips = []
  m.vanish.forEach((v) => chips.push({ label: '消失', area: v.area_sqm }))
  m.added.forEach((a) => chips.push({ label: '新增', area: a.area_sqm }))
  return chips
})

/** 变化总面积 = 消失 + 新增 + 非对角转换 */
const changeArea = computed(() => {
  const r = result.value
  if (!r) return 0
  const m = matrixData.value
  let s = m.vanish.reduce((a, x) => a + x.area_sqm, 0) + m.added.reduce((a, x) => a + x.area_sqm, 0)
  for (const row of r.rows || []) {
    if (row.from_use !== '（消失）' && !row.to_use.includes('—') && row.from_use !== row.to_use) {
      s += row.area_sqm
    }
  }
  return s
})

const periodStatus = computed(() => {
  const r = result.value
  return r ? `基期 ${r.base_count} 宗 / 末期 ${r.current_count} 宗` : '尚未计算（导入数据后点击“计算转移矩阵”）'
})

function cellStyle(f, t) {
  const a = matrixData.value.val(f, t)
  if (a <= 0) return {}
  const alpha = 0.06 + 0.6 * (a / matrixData.value.maxCell)
  return { background: `rgba(229, 87, 46, ${alpha.toFixed(3)})` }
}

onMounted(async () => {
  await store.fetchParcelsGeojson()
})

onBeforeUnmount(() => {
  charts.forEach((c) => c.dispose())
  charts = []
})

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

// ---------- 期次数据导入 ----------
async function doImport() {
  if (!importFile.value) return
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    fd.append('period', importPeriod.value)
    if (ui.currentProjectId) fd.append('project_id', ui.currentProjectId)
    const r = await importTransitionShp(fd)
    ElMessage.success(`已导入 ${r.imported} 宗地块，标记为「${importPeriod.value === 'base' ? '基期' : '末期'}」，跳过 ${r.skipped.length} 条`)
    await store.fetchParcelsGeojson()
  } finally {
    importing.value = false
  }
}

async function generateDemo() {
  try {
    await ElMessageBox.confirm(
      '将生成 BASE-* 演示基期地块（模拟 1 宗类型转换 + 1 宗消失 + 1 宗新增），并把现有地块标记为末期（current）。是否继续？',
      '生成演示基期', { type: 'warning', confirmButtonText: '生成', cancelButtonText: '取消' }
    )
  } catch (e) {
    return
  }
  demoGenerating.value = true
  try {
    const r = await generateDemoBase({ project_id: ui.currentProjectId || null })
    ElMessage.success(r.message || `演示基期已生成（${r.created} 宗）`)
    await store.fetchParcelsGeojson()
  } finally {
    demoGenerating.value = false
  }
}

// ---------- 计算 ----------
async function runMatrix() {
  running.value = true
  panel.value = 'result'
  try {
    result.value = await transitionMatrix({
      scope: scopeGeojson.value || null,
      project_id: ui.currentProjectId || null,
    })
  } catch (e) {
    ElMessage.error('计算失败：' + (e?.message || '未知原因'))
  } finally {
    running.value = false
  }
  await nextTick()
  renderCharts()
  fitToResult()
  setTimeout(() => charts.forEach((c) => c.resize()), 80)
}

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
  const summary = result.value?.summary || []
  if (summaryBarEl.value && summary.length) {
    const bar = echarts.init(summaryBarEl.value)
    const names = [...summary].reverse().map((s) => s.land_use)
    const baseData = [...summary].reverse().map((s) => +(s.base_area_sqm / 10000).toFixed(2))
    const curData = [...summary].reverse().map((s) => +(s.current_area_sqm / 10000).toFixed(2))
    bar.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 10, right: 50, top: 10, bottom: 40, containLabel: true },
      xAxis: { type: 'value', name: '公顷' },
      yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11, width: 110, overflow: 'truncate' } },
      series: [
        { name: '基期面积', type: 'bar', barMaxWidth: 12, itemStyle: { color: '#94a3b8' }, data: baseData },
        { name: '末期面积', type: 'bar', barMaxWidth: 12, itemStyle: { color: '#2e86ab' }, data: curData },
      ],
    })
    charts.push(bar)
  }
}

// ---------- 视野定位 ----------
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

function fitToResult() {
  const changes = changesFc.value.features || []
  const first = changes[0]?.geometry
  const target = first ? bboxOfGeom(first) : (scopeGeojson.value ? bboxOfGeom(scopeGeojson.value) : null)
  if (target) mapRef.value?.fitBounds(target)
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
  width: 720px;
  max-width: 52vw;
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
.chart-lg {
  height: 260px;
}
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  margin-right: 6px;
}
.cell-use {
  font-size: 12px;
}
.cell-heat {
  padding: 2px 4px;
  border-radius: 4px;
  font-variant-numeric: tabular-nums;
}
.change-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.delta-up {
  color: #16a34a;
  font-weight: 600;
}
.delta-down {
  color: #dc2626;
  font-weight: 600;
}
</style>
