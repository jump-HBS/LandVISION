<template>
  <div class="page-fullmap">
    <!-- 全屏地图：评价格网 + 行政区范围 -->
    <MapView
      ref="mapRef"
      :cells="cellsFc"
      :region-boundary="boundaryGeojson"
      enable-selection
      @selection="onMapDraw"
      @region-select="onRegionSelect"
      @region-locate="onRegionLocate"
    />

    <!-- 左侧：图标栏 -->
    <button class="page-icon-btn icon-left1" :class="{ active: panel === 'setup' }" title="评价设置"
            @click="panel = panel === 'setup' ? null : 'setup'">
      <el-icon :size="18"><Setting /></el-icon>
    </button>
    <button class="page-icon-btn icon-left2" :class="{ active: panel === 'result' }" title="评价结果"
            @click="panel = panel === 'result' ? null : 'result'">
      <el-icon :size="18"><Histogram /></el-icon>
    </button>

    <!-- 左侧面板一：评价设置 -->
    <div v-if="panel === 'setup'" class="page-panel panel-left glass-panel">
      <div class="panel-title">土地适宜性评价设置（多因子加权叠加）</div>

      <div class="section-title">① 评价目标</div>
      <el-radio-group v-model="target" size="small" class="mb" @change="onTargetChange">
        <el-radio-button v-for="t in targetKeys" :key="t" :label="t">{{ t }}</el-radio-button>
      </el-radio-group>
      <div class="scope-hint">
        {{ target === '建设用地适宜性' ? '面向开发建设选址，考虑交通、配套、生态约束与建成区邻近度。' : '面向耕地保护与质量提升，考虑水源、地形、耕作服务与生态约束。' }}
      </div>

      <div class="section-title">② 因子权重（提交时自动归一化）</div>
      <div v-for="f in factors" :key="f.key" class="factor-row">
        <div class="factor-head">
          <span class="factor-name">{{ f.name }}</span>
          <span class="factor-value">{{ normWeight(f.key).toFixed(1) }}%</span>
        </div>
        <el-slider v-model="weights[f.key]" :min="5" :max="60" :step="5" size="small" />
      </div>
      <div class="flex-row">
        <span class="scope-hint">权重合计：{{ weightSum.toFixed(0) }}%（系统按比例归一化为 100%）</span>
        <el-button size="small" style="margin-left:auto" @click="resetWeights">恢复默认权重</el-button>
      </div>

      <el-divider />

      <div class="section-title">③ 评价范围（必填，三种方式任选）</div>
      <el-radio-group v-model="scopeMode" size="small" class="mb">
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
        <el-tag size="small" type="success" closable @close="clearScope">已划定评价范围</el-tag>
      </div>

      <div class="flex-row mt">
        <span class="scope-hint">格网法：范围内生成 40×40 格网，逐格计算因子得分（0~100）后加权叠加分级。</span>
        <el-button type="primary" style="margin-left:auto" :loading="evaluating" @click="runEvaluate">
          执行评价
        </el-button>
      </div>
    </div>

    <!-- 左侧面板二：评价结果 -->
    <div v-if="panel === 'result'" class="page-panel panel-left glass-panel">
      <div class="panel-title">适宜性评价结果（{{ result?.target || target }}）</div>
      <el-skeleton v-if="evaluating" :rows="10" animated />
      <template v-else-if="result">
        <el-row :gutter="8" class="mb">
          <el-col :span="5"><div class="sum-card">格网单元<b>{{ cellTotal }}</b></div></el-col>
          <el-col :span="19">
            <el-row :gutter="8">
              <el-col v-for="lv in levelOrder" :key="lv" :span="6">
                <div class="sum-card" :style="{ borderBottom: `3px solid ${LEVEL_COLORS[lv]}` }">
                  {{ lv }}<b>{{ statOf(lv)?.count || 0 }}</b><i>{{ percentOf(lv).toFixed(1) }}%</i>
                </div>
              </el-col>
            </el-row>
          </el-col>
        </el-row>

        <!-- v3.0 联动：适宜性矛盾提示（高度/中等适宜 ∩ 体检冲突） -->
        <el-alert v-if="conflictHint" class="mb" type="warning" :closable="false"
                  :title="conflictHint" />
        <div v-if="conflictParcels.length" class="mb">
          <el-tag v-for="c in conflictParcels" :key="c.parcel_id" size="small" type="danger" class="conflict-tag">
            {{ c.name }}（{{ c.parcel_code }}）
          </el-tag>
        </div>

        <div class="section-title">适宜等级分布（格网单元数）</div>
        <div ref="levelBarEl" class="chart-md"></div>

        <div class="section-title">因子权重（已归一化）</div>
        <el-table :data="weightRows" size="small" border max-height="180">
          <el-table-column prop="name" label="评价因子" min-width="120" />
          <el-table-column prop="key" label="因子键" width="90" show-overflow-tooltip />
          <el-table-column label="权重" align="right" width="90">
            <template #default="{ row }">{{ (row.weight * 100).toFixed(1) }}%</template>
          </el-table-column>
        </el-table>

        <div class="scope-hint mt">
          分级标准：综合得分 ≥80 高度适宜 / 60~80 中等适宜 / 40~60 勉强适宜 / ＜40 不适宜。
          点击地图格网可查看该单元综合得分与适宜等级。
          刚性约束：永久基本农田 / 生态保护红线内格网强制标记为「不适宜建设」。
        </div>
        <!-- v2.0 联动：反向校验体检结论 -->
        <div class="mt">
          <el-button size="small" type="primary" plain @click="gotoPlanning">
            查看体检结论（反向校验适宜性矛盾）
          </el-button>
        </div>
      </template>
      <el-empty v-else description="完成评价设置并划定范围后，点击“执行评价”" />
    </div>
  </div>
</template>

<script setup>
/**
 * SuitabilityView —— 模块二：土地适宜性评价
 * 格网法多因子加权叠加：评价目标 × 因子权重 × 评价范围 → 四级适宜性 + 格网专题图。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useUiStore } from '../stores/ui'
import {
  getRegion, getSuitabilityTargets, suitabilityEvaluate, parseScopeShp,
  getSuitabilityConflicts,
} from '../api'
import MapView from '../components/MapView.vue'

const ui = useUiStore()
const router = useRouter()

const LEVEL_COLORS = {
  高度适宜: '#1a9850',
  中等适宜: '#91cf60',
  勉强适宜: '#fee08b',
  不适宜: '#d73027',
}
const levelOrder = ['高度适宜', '中等适宜', '勉强适宜', '不适宜']

const mapRef = ref(null)
const panel = ref(null)
const boundaryGeojson = ref(null)

// 评价设置
const targets = ref({})
const target = ref('建设用地适宜性')
const weights = ref({})
const scopeMode = ref('region')
const currentRegion = ref(null)
const scopeGeojson = ref(null)
const scopeFile = ref(null)
const scopeImporting = ref(false)
// 项目范围继承（v2.0）：当前项目范围自动作为评价范围；转移矩阵联动范围优先
const projectScopeLabel = computed(() => {
  if (ui.linkedScopeLabel) return ui.linkedScopeLabel
  return ui.currentProject?.name ? `${ui.currentProject.name}（项目范围）` : null
})

// 结果
const evaluating = ref(false)
const result = ref(null)
const levelBarEl = ref(null)
let charts = []

// v3.0 联动：适宜性矛盾提示（高度/中等适宜 ∩ 体检冲突地块）
const conflictHint = ref('')
const conflictParcels = ref([])

const targetKeys = computed(() => Object.keys(targets.value).length ? Object.keys(targets.value) : ['建设用地适宜性', '耕地适宜性'])
const factors = computed(() => targets.value[target.value]?.factors || [])
const weightSum = computed(() => factors.value.reduce((s, f) => s + (weights.value[f.key] || 0), 0))
const cellsFc = computed(() => result.value?.cells_geojson || { type: 'FeatureCollection', features: [] })
const cellTotal = computed(() => cellsFc.value.features.length)
const weightRows = computed(() => {
  const w = result.value?.weights || {}
  const sum = Object.values(w).reduce((s, v) => s + v, 0) || 1
  return factors.value.map((f) => ({ ...f, weight: (w[f.key] || 0) / sum }))
})

const statOf = (lv) => (result.value?.stats || []).find((s) => s.level === lv)
const percentOf = (lv) => (cellTotal.value ? ((statOf(lv)?.count || 0) / cellTotal.value) * 100 : 0)
const normWeight = (key) => {
  const sum = weightSum.value
  return sum > 0 ? ((weights.value[key] || 0) / sum) * 100 : 0
}

onMounted(async () => {
  try {
    targets.value = await getSuitabilityTargets()
    if (!targets.value[target.value]) target.value = Object.keys(targets.value)[0] || '建设用地适宜性'
    resetWeights()
  } catch (e) {
    ElMessage.error('加载评价因子失败：' + (e?.message || '未知原因'))
  }
  // v2.0 范围统一继承：转移矩阵联动范围 ＞ 当前项目范围
  if (ui.linkedScope) {
    scopeGeojson.value = ui.linkedScope
    scopeMode.value = 'manual'
    ui.setLinkedPatches(null, null, null)
    ElMessage.info(`已接收联动范围：${projectScopeLabel.value}（可直接执行评价）`)
  } else if (ui.currentProject?.scope_geojson) {
    scopeGeojson.value = ui.currentProject.scope_geojson
  }
})

onBeforeUnmount(() => {
  charts.forEach((c) => c.dispose())
  charts = []
})

function onTargetChange() {
  resetWeights()
}

function resetWeights() {
  const map = {}
  factors.value.forEach((f) => (map[f.key] = Math.round(f.default * 100)))
  weights.value = map
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

// ---------- 评价范围 ----------
watch(scopeMode, (mode) => {
  if (mode === 'manual' && !scopeGeojson.value) {
    panel.value = null
    ElMessage.info('请使用地图左侧工具（多边形/框选/圈选）绘制评价范围，画完自动返回设置面板')
  }
})

function onMapDraw(selection) {
  if (!selection?.geometry) return
  if (scopeMode.value === 'manual') {
    scopeGeojson.value = selection.geometry
    ElMessage.success('手动评价范围已划定，已自动回到设置面板')
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

// ---------- 评价计算 ----------
async function runEvaluate() {
  if (!scopeGeojson.value) {
    ElMessage.warning('请先划定评价范围（行政区 / SHP / 手动绘制）')
    panel.value = 'setup'
    return
  }
  evaluating.value = true
  panel.value = 'result'
  try {
    result.value = await suitabilityEvaluate({
      target: target.value,
      weights: Object.fromEntries(factors.value.map((f) => [f.key, (weights.value[f.key] || 0) / 100])),
      scope: scopeGeojson.value,
      project_id: ui.currentProjectId || null,
    })
    ui.bumpAnalysisVersion()  // v3.0：通知驾驶舱自动刷新
    if (!cellTotal.value) ElMessage.warning('范围内未生成格网单元，请检查评价范围')
    await checkConflicts()
  } catch (e) {
    ElMessage.error('评价失败：' + (e?.message || '未知原因'))
  } finally {
    evaluating.value = false
  }
  await nextTick()
  renderCharts()
  fitToCells()
  setTimeout(() => charts.forEach((c) => c.resize()), 80)
}

// v3.0 联动：适宜性矛盾提示（高度/中等适宜格网 ∩ 体检冲突地块）
async function checkConflicts() {
  conflictHint.value = ''
  conflictParcels.value = []
  if (!ui.currentProjectId) return
  try {
    const data = await getSuitabilityConflicts({ project_id: ui.currentProjectId })
    conflictHint.value = data.hint || ''
    conflictParcels.value = data.conflicts || []
  } catch (e) {
    // 体检尚未执行等场景静默跳过
  }
}

function renderCharts() {
  charts.forEach((c) => c.dispose())
  charts = []
  const stats = result.value?.stats || []
  if (levelBarEl.value && stats.length) {
    const bar = echarts.init(levelBarEl.value)
    bar.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}：{c} 个格网单元' },
      grid: { left: 10, right: 20, top: 24, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: stats.map((s) => s.level), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '单元数' },
      series: [{
        type: 'bar',
        barMaxWidth: 40,
        label: { show: true, position: 'top', fontSize: 10 },
        data: stats.map((s) => ({ value: s.count, itemStyle: { color: LEVEL_COLORS[s.level] || '#999', borderRadius: [4, 4, 0, 0] } })),
      }],
    })
    charts.push(bar)
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

function fitToCells() {
  const first = cellsFc.value.features?.[0]?.geometry
  const target = first ? bboxOfGeom(first) : (scopeGeojson.value ? bboxOfGeom(scopeGeojson.value) : null)
  if (target) mapRef.value?.fitBounds(target)
}

// 联动：跳转三区三线体检（继承项目范围，反向校验适宜性矛盾）
function gotoPlanning() {
  router.push('/planning')
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
  width: 640px;
  max-width: 48vw;
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
.factor-row {
  margin-bottom: 2px;
}
.factor-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.factor-name {
  font-size: 12px;
  color: var(--lv-text);
}
.factor-value {
  font-size: 12px;
  color: var(--lv-primary);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.factor-row :deep(.el-slider) {
  --el-slider-main-bg-color: var(--lv-primary);
}
.sum-card {
  text-align: center;
  padding: 8px 2px;
  border-radius: 8px;
  background: var(--lv-bg);
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.sum-card b {
  display: block;
  font-size: 15px;
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
.conflict-tag {
  margin: 0 6px 4px 0;
}
.chart-md {
  height: 220px;
}
</style>
