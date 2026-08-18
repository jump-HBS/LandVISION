<template>
  <div class="dashboard">
    <!-- 顶部：项目工作台（项目信息 + 流程进度 + 范围管理） -->
    <el-card shadow="hover" class="panel-card mb">
      <div class="project-head">
        <div class="project-info">
          <el-icon color="#2e86ab" :size="22"><OfficeBuilding /></el-icon>
          <div>
            <div class="project-name">
              {{ summary.project?.name || '未选择分析项目（全量数据）' }}
              <el-tag v-if="summary.project?.name" size="small" type="success" effect="plain" style="margin-left:8px">
                范围：{{ summary.scope.label }}
              </el-tag>
              <el-tag v-if="summary.scope?.strict" size="small" type="warning" effect="plain" style="margin-left:6px">
                已按此范围聚合
              </el-tag>
            </div>
            <div class="project-meta">
              <template v-if="summary.project?.name">
                基期 {{ summary.project.base_year }} 年 → 末期 {{ summary.project.current_year }} 年
                · 结果持久化关联项目，各分析模块自动继承范围与期次
              </template>
              <template v-else>在顶栏选择或新建项目后，各分析模块将共享项目范围与期次设置</template>
            </div>
          </div>
        </div>
        <div class="project-actions">
          <el-button size="small" type="primary" plain @click="openScopeDialog">划定/变更项目范围</el-button>
          <el-button size="small" :loading="loading" @click="loadSummary">刷新数据</el-button>
        </div>
      </div>

      <!-- 分析流程进度条（推荐顺序） -->
      <div class="mt">
        <el-steps :active="progressActive" finish-status="success" simple style="max-width:760px">
          <el-step title="① 地块管理" />
          <el-step title="② 转移矩阵" :status="stepStatus(summary.progress?.transition)" />
          <el-step title="③ 三区三线体检" :status="stepStatus(summary.progress?.planning)" />
          <el-step title="④ 适宜性评价" :status="stepStatus(summary.progress?.suitability)" />
          <el-step title="⑤ 设施可达性" :status="stepStatus(summary.progress?.accessibility)" />
          <el-step title="⑥ 报告生成" />
        </el-steps>
        <div v-if="summary.progress?.missing?.length" class="scope-hint mt">
          流程提示：尚未执行
          <b>{{ summary.progress.missing.map(labelOfStep).join('、') }}</b>
          ，报告中会标注缺失并给出补全建议（允许跳过）。
        </div>
      </div>
    </el-card>

    <!-- 关键结论摘要卡片（点击下钻到对应模块） -->
    <el-row :gutter="16">
      <el-col :span="6">
        <div class="drill-card" @click="goto('/planning')">
          <StatsCard label="三区三线冲突地块" :value="summary.planning_review?.conflict_count || 0" unit="宗"
                     icon="Stamp" group-tag="体检类" icon-color="#ef476f" icon-bg="rgba(239,71,111,.14)"
                     sub="点击下钻到三区三线体检" />
        </div>
      </el-col>
      <el-col :span="6">
        <div class="drill-card" @click="goto('/accessibility')">
          <StatsCard label="设施盲区地块" :value="summary.accessibility?.gap_count || 0" unit="宗"
                     icon="Position" group-tag="分析类" icon-color="#e6a23c" icon-bg="rgba(230,162,60,.14)"
                     sub="点击下钻到设施可达性" />
        </div>
      </el-col>
      <el-col :span="6">
        <div class="drill-card" @click="goto('/transition')">
          <StatsCard label="耕地净减少" :value="farmlandDeltaHa" unit="公顷" icon="Sort" group-tag="变化类"
                     icon-color="#dc2626" icon-bg="rgba(220,38,38,.12)" :precision="2"
                     sub="点击下钻到转移矩阵" />
        </div>
      </el-col>
      <el-col :span="6">
        <div class="drill-card" @click="goto('/suitability')">
          <StatsCard label="高度适宜占比" :value="highSuitabilityPct" unit="%" icon="Histogram" group-tag="评价类"
                     icon-color="#16a34a" icon-bg="rgba(22,163,74,.12)" :precision="1"
                     sub="点击下钻到适宜性评价" />
        </div>
      </el-col>
    </el-row>

    <!-- 问题识别 + 规划建议 -->
    <el-row :gutter="16" class="mt">
      <el-col :span="12">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">问题识别（{{ summary.problem_total ?? summary.problems?.length }} 条）</div>
          </template>
          <div v-if="summary.problems?.length" class="problem-list">
            <div v-for="(p, i) in summary.problems.slice(0, 12)" :key="i" class="problem-item"
                 :class="'sev-' + p.severity" @click="problemDrill(p)">
              <el-tag size="small" :type="p.severity === 'high' ? 'danger' : p.severity === 'medium' ? 'warning' : 'info'">
                {{ p.type }}
              </el-tag>
              <div class="problem-title">{{ p.title }}</div>
              <div class="problem-detail">{{ p.detail }}</div>
            </div>
          </div>
          <el-empty v-else description="暂未发现问题" :image-size="60" />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">规划建议（自动生成）</div>
          </template>
          <div v-if="summary.suggestions?.length" class="suggest-list">
            <div v-for="(s, i) in summary.suggestions" :key="i" class="suggest-item">
              <div class="suggest-title">💡 {{ s.title }}</div>
              <div class="suggest-detail">{{ s.detail }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无建议" :image-size="60" />
        </el-card>
      </el-col>
    </el-row>

    <!-- 用地结构 -->
    <el-row :gutter="16" class="mt">
      <el-col :span="16">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">用地性质分布（GB/T 21010-2017 一级类，范围内 {{ summary.overview?.parcel_total }} 宗）</div>
          </template>
          <div ref="pieEl" class="chart chart-pie" v-loading="loading"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">各用地类型面积（公顷）</div>
          </template>
          <div ref="areaBarEl" class="chart chart-area" v-loading="loading"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 体检 + 适宜性 -->
    <el-row :gutter="16" class="mt">
      <el-col :span="16">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">三区三线体检 · 各控制线占用面积（公顷）</div>
          </template>
          <div ref="reviewBarEl" class="chart" v-loading="loading"></div>
        </el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">适宜性评价（格网单元）</div>
          </template>
          <div ref="suitBarEl" class="chart" v-loading="loading"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 转移矩阵概览 -->
    <el-row :gutter="16" class="mt">
      <el-col :span="24">
        <el-card shadow="hover" class="panel-card">
          <template #header>
            <div class="panel-title">用地变化转移矩阵概览（模块一）</div>
          </template>
          <el-alert v-if="!summary.transition_analysis?.has_data" type="info" :closable="false"
            :title="summary.transition_analysis?.hint || '尚未导入两期地块数据：请在“用地转移矩阵”页导入基期/末期 SHP 或一键生成演示基期'" />
          <template v-else>
            <div class="matrix-sum">
              <div class="matrix-card">基期地块<b>{{ summary.transition_analysis.base_count }}</b>宗</div>
              <div class="matrix-card">末期地块<b>{{ summary.transition_analysis.current_count }}</b>宗</div>
              <div class="matrix-card">变化图斑<b>{{ summary.transition_analysis.change_count }}</b>个</div>
              <div class="matrix-card">冲突图斑<b>{{ summary.transition_analysis.conflict_patch_count }}</b>个</div>
              <div class="matrix-card">变化总面积<b>{{ (summary.transition_analysis.change_area_sqm / 10000).toFixed(1) }}</b>公顷</div>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 范围划定对话框 -->
    <el-dialog v-model="scopeDialogVisible" title="划定 / 变更项目分析范围" width="560px">
      <el-alert v-if="scopeChangedHint" type="warning" :closable="false" class="mb"
        :title="scopeChangedHint" />
      <div class="section-title">方式一：行政区（省/市/县任意层级）</div>
      <el-cascader
        v-model="regionPath"
        :props="cascaderProps"
        placeholder="选择省 / 市 / 县（任意层级）"
        size="small" clearable filterable style="width:100%"
        @change="onRegionChange" />
      <div class="section-title mt">方式二：导入 SHP 范围</div>
      <div class="flex-row">
        <el-upload :auto-upload="false" :limit="1" accept=".zip" :show-file-list="false"
                   :on-change="(f) => (scopeFile = f.raw)">
          <el-button size="small" type="primary" plain>选择 SHP zip</el-button>
        </el-upload>
        <el-button size="small" :loading="scopeImporting" :disabled="!scopeFile" @click="importScopeShp">导入</el-button>
      </div>
      <div class="section-title mt">保存设置</div>
      <div class="flex-row">
        <el-checkbox v-model="confirmScopeChange">确认范围变更（已有分析结果可能失效）</el-checkbox>
      </div>
      <div class="flex-row mt">
        <el-tag v-if="pendingScopeLabel" type="success">待保存范围：{{ pendingScopeLabel }}</el-tag>
        <el-button size="small" type="danger" plain :disabled="pendingScope === undefined" @click="clearPendingScope">清空为全量</el-button>
      </div>
      <template #footer>
        <el-button @click="scopeDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingScope" :disabled="!confirmScopeChange || pendingScope === undefined"
                   @click="saveScope">保存项目范围</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * DashboardView —— 数据驾驶舱（v2.0 项目工作台）
 * 项目信息 + 流程进度 + 关键结论摘要（点击下钻）+ 问题识别/规划建议 + 范围管理。
 * 数据来自 /api/dashboard/summary（持久化结果优先，与报告生成同源）。
 */
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { useParcelStore } from '../stores/parcel'
import { useUiStore } from '../stores/ui'
import {
  getRegions, getRegionChildren, getRegion, getRegionLocate,
  parseScopeShp, dashboardSummary, updateProject,
} from '../api'
import { LAND_USE_COLORS, LAND_USE_ORDER, ZONE_TYPE_LABELS, ZONE_TYPE_COLORS } from '../utils/colors'
import StatsCard from '../components/StatsCard.vue'

const store = useParcelStore()
const ui = useUiStore()
const router = useRouter()

const pieEl = ref(null)
const areaBarEl = ref(null)
const reviewBarEl = ref(null)
const suitBarEl = ref(null)
let charts = []

const loading = ref(true)
const summary = ref({})
const scopeDialogVisible = ref(false)
const regionPath = ref([])
const scopeFile = ref(null)
const scopeImporting = ref(false)
const pendingScope = ref(undefined)
const pendingScopeLabel = ref(null)
const confirmScopeChange = ref(false)
const savingScope = ref(false)
const scopeChangedHint = ref('')

const STEP_LABELS = { transition: '转移矩阵', planning: '三区三线体检', suitability: '适宜性评价', accessibility: '设施可达性' }
const labelOfStep = (k) => STEP_LABELS[k] || k
const stepStatus = (done) => (done ? 'success' : 'wait')
const progressActive = computed(() => {
  const p = summary.value.progress || {}
  const order = ['transition', 'planning', 'suitability', 'accessibility']
  return order.filter((k) => p[k]).length + 1
})

const farmlandDeltaHa = computed(() => {
  const s = (summary.value.transition_analysis?.summary || []).find((x) => x.land_use === '耕地')
  return s ? s.delta_sqm / 10000 : 0
})
const highSuitabilityPct = computed(() => {
  const stats = summary.value.suitability?.stats || []
  const total = summary.value.suitability?.cell_total || 0
  const high = stats.find((s) => s.level === '高度适宜')?.count || 0
  return total ? (high / total) * 100 : 0
})

// 行政区级联（任意层级可选）
const cascaderProps = {
  lazy: true,
  checkStrictly: true,
  value: 'code',
  label: 'name',
  lazyLoad: async (node, resolve) => {
    try {
      if (!node || node.level === 0) {
        const data = await getRegions({ level: 'province', page_size: 100 })
        resolve(data.items.map((p) => ({ code: p.code, name: p.name })))
      } else {
        const children = await getRegionChildren(node.value)
        resolve(children.map((c) => ({ code: c.code, name: c.name, leaf: c.level === 'county' })))
      }
    } catch (e) {
      resolve([])
    }
  },
}

function goto(path) {
  router.push(path)
}

function problemDrill(problem) {
  const map = { 三区三线冲突: '/planning', 三区三线警告: '/planning', 设施盲区: '/accessibility', 违规变化: '/planning' }
  const path = map[problem.type]
  if (path) router.push(path)
}

async function loadSummary() {
  loading.value = true
  try {
    summary.value = await dashboardSummary({
      project_id: ui.currentProjectId || null,
      scope: null,
      scope_label: null,
    })
    await nextTick()
    renderAll()
  } catch (e) {
    ElMessage.error('统筹汇总失败：' + (e?.message || '未知原因'))
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadSummary(), store.fetchParcelsGeojson()])
})

onBeforeUnmount(() => {
  charts.forEach((c) => c.dispose())
  charts = []
})

// ---------- 项目范围管理 ----------
function openScopeDialog() {
  if (!ui.currentProjectId) {
    ElMessage.warning('请先在顶栏选择或新建分析项目')
    return
  }
  scopeChangedHint.value = '范围变更会提示已有分析结果可能失效（转移矩阵/体检/适宜性/可达性），确认后需重新执行对应分析。'
  pendingScope.value = undefined
  pendingScopeLabel.value = null
  confirmScopeChange.value = false
  scopeDialogVisible.value = true
}

async function onRegionChange(path) {
  if (!path?.length) return
  const code = path[path.length - 1]
  const region = await getRegion(code)
  if (!region?.geometry) {
    ElMessage.warning(`「${region?.name || code}」暂无边界几何数据`)
    regionPath.value = []
    return
  }
  pendingScope.value = region.geometry
  pendingScopeLabel.value = `${region.name}（${region.level === 'province' ? '省级' : region.level === 'city' ? '市级' : '县级'}）`
  const locate = await getRegionLocate(code)
  if (locate?.bbox) ElMessage.success(`已选定范围：${pendingScopeLabel.value}`)
}

async function importScopeShp() {
  if (!scopeFile.value) return
  scopeImporting.value = true
  try {
    const fd = new FormData()
    fd.append('file', scopeFile.value)
    const r = await parseScopeShp(fd)
    pendingScope.value = r.scope
    pendingScopeLabel.value = `SHP 范围（${r.feature_count} 个要素）`
    ElMessage.success(`SHP 范围已导入（${r.feature_count} 个要素）`)
  } finally {
    scopeImporting.value = false
  }
}

function clearPendingScope() {
  pendingScope.value = null
  pendingScopeLabel.value = '全量数据（无范围）'
  regionPath.value = []
}

async function saveScope() {
  savingScope.value = true
  try {
    const project = await updateProject(ui.currentProjectId, {
      scope: pendingScope.value || null,
      confirm_scope_change: true,
    })
    ui.setProject({ ...ui.currentProject, scope_geojson: pendingScope.value || null })
    if (project.scope_changed) {
      ElMessage.warning('范围已变更：已有分析结果可能失效，请重新执行各模块分析')
    } else {
      ElMessage.success('项目范围已保存')
    }
    scopeDialogVisible.value = false
    await loadSummary()
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知原因'))
  } finally {
    savingScope.value = false
  }
}

// ---------- 图表 ----------
function initChart(el) {
  const chart = echarts.init(el.value)
  charts.push(chart)
  return chart
}

function renderPie() {
  if (!pieEl.value) return
  const entries = LAND_USE_ORDER
    .filter((t) => (summary.value.land_use_distribution || []).some((d) => d.land_use === t && d.count > 0))
    .map((t) => {
      const d = summary.value.land_use_distribution.find((x) => x.land_use === t)
      return { name: t, value: d.count }
    })
  const chart = initChart(pieEl)
  chart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}：{c} 宗（{d}%）' },
    legend: { bottom: 0, type: 'scroll', orient: 'horizontal', textStyle: { fontSize: 11 }, itemWidth: 12, itemHeight: 10 },
    color: entries.map((e) => LAND_USE_COLORS[e.name]),
    series: [{
      type: 'pie', radius: ['38%', '62%'], center: ['50%', '42%'],
      label: { formatter: '{b}\n{d}%', fontSize: 11 }, data: entries,
    }],
  })
}

function renderAreaBar() {
  if (!areaBarEl.value) return
  const entries = LAND_USE_ORDER
    .filter((t) => (summary.value.land_use_distribution || []).some((d) => d.land_use === t && d.area_sqm > 0))
    .map((t) => {
      const d = summary.value.land_use_distribution.find((x) => x.land_use === t)
      return { name: t, value: +(d.area_sqm / 10000).toFixed(2) }
    })
  const chart = initChart(areaBarEl)
  chart.setOption({
    tooltip: { trigger: 'axis', formatter: '{b}：{c} 公顷' },
    grid: { left: 10, right: 30, top: 10, bottom: 10, containLabel: true },
    xAxis: { type: 'value', name: '公顷' },
    yAxis: { type: 'category', data: entries.map((e) => e.name).reverse(), axisLabel: { fontSize: 11 } },
    series: [{
      type: 'bar', barMaxWidth: 14,
      data: entries.map((e) => ({ value: e.value, itemStyle: { color: LAND_USE_COLORS[e.name], borderRadius: [0, 4, 4, 0] } })).reverse(),
    }],
  })
}

function renderReviewBar() {
  if (!reviewBarEl.value) return
  const totals = summary.value.planning_review?.review_totals || []
  const sorted = [...totals].sort((a, b) => b.total_area_sqm - a.total_area_sqm)
  const chart = initChart(reviewBarEl)
  if (sorted.length) {
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}：{c} 公顷' },
      grid: { left: 10, right: 30, top: 20, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: sorted.map((t) => ZONE_TYPE_LABELS[t.zone_type] || t.zone_type), axisLabel: { fontSize: 11, interval: 0 } },
      yAxis: { type: 'value', name: '公顷' },
      series: [{
        type: 'bar', barMaxWidth: 40,
        label: { show: true, position: 'top', fontSize: 10, formatter: '{c}' },
        data: sorted.map((t) => ({ value: +(t.total_area_sqm / 10000).toFixed(2), itemStyle: { color: ZONE_TYPE_COLORS[t.zone_type] || '#999', borderRadius: [4, 4, 0, 0] } })),
      }],
    })
  } else {
    chart.setOption({ title: { text: '范围内暂无占用数据', left: 'center', top: 'middle', textStyle: { fontSize: 12, color: '#999' } } })
  }
}

function renderSuitBar() {
  if (!suitBarEl.value) return
  const stats = summary.value.suitability?.stats || []
  const chart = initChart(suitBarEl)
  if (stats.length) {
    const colors = { 高度适宜: '#1a9850', 中等适宜: '#91cf60', 勉强适宜: '#fee08b', 不适宜: '#d73027' }
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: '{b}：{c} 个格网' },
      grid: { left: 10, right: 20, top: 20, bottom: 10, containLabel: true },
      xAxis: { type: 'category', data: stats.map((s) => s.level), axisLabel: { fontSize: 11 } },
      yAxis: { type: 'value', name: '单元' },
      series: [{
        type: 'bar', barMaxWidth: 36,
        label: { show: true, position: 'top', fontSize: 10 },
        data: stats.map((s) => ({ value: s.count, itemStyle: { color: colors[s.level] || '#999', borderRadius: [4, 4, 0, 0] } })),
      }],
    })
  } else {
    chart.setOption({ title: { text: '尚未执行适宜性评价', left: 'center', top: 'middle', textStyle: { fontSize: 12, color: '#999' } } })
  }
}

function renderAll() {
  renderPie()
  renderAreaBar()
  renderReviewBar()
  renderSuitBar()
  setTimeout(() => charts.forEach((c) => c.resize()), 60)
}
</script>

<style scoped>
.dashboard {
  padding: 4px;
}
.project-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}
.project-info {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.project-name {
  font-size: 16px;
  font-weight: 700;
  color: var(--lv-text);
}
.project-meta {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-top: 4px;
}
.project-actions {
  display: flex;
  gap: 8px;
}
.mt {
  margin-top: 16px;
}
.mb {
  margin-bottom: 16px;
}
.panel-card {
  border: none;
  box-shadow: var(--lv-shadow);
  border-radius: var(--lv-radius);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--lv-text);
  display: flex;
  align-items: center;
  gap: 8px;
}
.panel-title::before {
  content: '';
  width: 4px;
  height: 14px;
  border-radius: 2px;
  background: var(--lv-primary);
}
.drill-card {
  cursor: pointer;
  border-radius: var(--lv-radius);
  transition: transform 0.15s ease;
}
.drill-card:hover {
  transform: translateY(-2px);
}
.problem-list,
.suggest-list {
  max-height: 320px;
  overflow-y: auto;
}
.problem-item {
  padding: 8px 10px;
  border-radius: 8px;
  margin-bottom: 8px;
  background: var(--lv-bg);
  cursor: pointer;
}
.problem-item:hover {
  outline: 1px solid var(--lv-primary-light);
}
.problem-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lv-text);
  margin-top: 4px;
}
.problem-detail {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-top: 2px;
}
.suggest-item {
  padding: 8px 10px;
  border-left: 3px solid var(--lv-primary);
  background: var(--lv-bg);
  border-radius: 0 8px 8px 0;
  margin-bottom: 8px;
}
.suggest-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lv-text);
}
.suggest-detail {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-top: 2px;
}
.chart {
  height: 300px;
}
.chart-pie {
  height: 380px;
}
.chart-area {
  height: 380px;
}
.matrix-sum {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.matrix-card {
  flex: 1;
  min-width: 130px;
  text-align: center;
  padding: 14px 8px;
  border-radius: 8px;
  background: var(--lv-bg);
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.matrix-card b {
  display: block;
  font-size: 20px;
  color: var(--lv-primary);
  margin-top: 2px;
}
.scope-hint {
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lv-text);
  margin: 6px 0 8px;
}
.flex-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
