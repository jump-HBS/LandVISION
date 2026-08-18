<template>
  <div class="page-fullmap">
    <!-- 全屏地图 -->
    <MapView
      ref="mapRef"
      :parcels="store.parcelsGeojson"
      :zones="zonesGeojson"
      :region-boundary="boundaryGeojson"
      :highlight-id="highlightZoneId"
      enable-selection
      @parcel-click="onParcelClick"
      @parcel-detail="onParcelClick"
      @selection="onMapDraw"
      @region-select="onRegionSelect"
      @region-locate="onRegionLocate"
    />

    <!-- 左侧：图标栏 -->
    <button class="page-icon-btn icon-left1" :class="{ active: panel === 'setup' }" title="体检设置"
            @click="panel = panel === 'setup' ? null : 'setup'">
      <el-icon :size="18"><Setting /></el-icon>
    </button>
    <button class="page-icon-btn icon-left2" :class="{ active: panel === 'result' }" title="体检结果"
            @click="panel = panel === 'result' ? null : 'result'">
      <el-icon :size="18"><DataAnalysis /></el-icon>
    </button>
    <button class="page-icon-btn icon-left3" title="查看判定规则矩阵" @click="rulesVisible = true">
      <el-icon :size="18"><Notebook /></el-icon>
    </button>

    <!-- 左侧面板一：体检设置 -->
    <div v-if="panel === 'setup'" class="page-panel panel-left glass-panel">
      <div class="panel-title">三区三线体检设置（范围与要素）</div>

      <el-alert v-if="patchLinkHint" class="mb" type="warning" :closable="false"
        :title="patchLinkHint" />

      <div class="section-title">① 体检范围（默认继承当前项目范围）</div>
      <div class="scope-hint mb">
        <template v-if="currentProject">当前项目：<el-tag size="small">{{ currentProject.name }}</el-tag>（范围自动继承，无需重复划定）</template>
        <template v-else>未选择项目 —— 可手动划定范围或全量体检</template>
      </div>
      <el-radio-group v-model="scopeMode" size="small" class="mb">
        <el-radio-button label="project">项目范围</el-radio-button>
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
        <el-tag size="small" type="success" closable @close="clearScope">已划定体检范围</el-tag>
      </div>

      <el-divider />

      <div class="section-title">② 三区三线控制线（由用户导入：SHP 选择约束类型）</div>
      <div class="flex-row mb">
        <el-button size="small" type="primary" @click="openZoneImport">SHP 导入（选类型）</el-button>
        <el-select v-model="zoneForm.zone_type" size="small" style="width:170px">
          <el-option v-for="(label, code) in ZONE_TYPE_LABELS" :key="code" :label="label" :value="code" />
        </el-select>
        <el-input v-model="zoneForm.zone_name" size="small" style="width:150px" placeholder="名称（可选）" />
        <el-tooltip content="点击后在地图上用多边形工具绘制" placement="top">
          <el-button size="small" @click="startDrawZone">图上绘制</el-button>
        </el-tooltip>
      </div>
      <el-table :data="zones" size="small" max-height="150" @selection-change="(rows) => (selectedZones = rows)">
        <el-table-column type="selection" width="34" />
        <el-table-column prop="zone_name" label="名称" min-width="100" show-overflow-tooltip />
        <el-table-column label="类型" width="104">
          <template #default="{ row }">
            <el-tag size="small" :style="zoneTagStyle(row.zone_type)">{{ ZONE_TYPE_LABELS[row.zone_type] || row.zone_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="锁定" width="50" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.locked" size="small" type="danger">锁定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link :type="row.locked ? 'warning' : 'info'" @click="toggleZoneLock(row)">
              {{ row.locked ? '解锁' : '锁定' }}
            </el-button>
            <el-button size="small" link type="danger" @click="removeZone(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="flex-row mt">
        <el-button size="small" type="danger" plain :disabled="!selectedZones.length" @click="batchDeleteZonesSel">
          批量删除选中控制线
        </el-button>
      </div>

      <el-divider />

      <div class="section-title">③ 选择被体检地块（按用地类型筛选 + 勾选）</div>
      <div class="flex-row mb">
        <el-select v-model="parcelLandUses" multiple collapse-tags placeholder="按用地类型筛选"
                   size="small" style="width:280px" @change="loadParcels">
          <el-option v-for="lu in LAND_USE_ORDER" :key="lu" :label="lu" :value="lu" />
        </el-select>
        <el-button size="small" @click="selectAllParcels">全选</el-button>
        <el-button size="small" @click="clearParcelSelection">清空</el-button>
      </div>
      <el-table :data="parcelOptions" size="small" max-height="170" ref="parcelTableRef"
                @selection-change="(rows) => (selectedParcelIds = rows.map((r) => r.id))">
        <el-table-column type="selection" width="34" />
        <el-table-column prop="parcel_code" label="编号" width="78" />
        <el-table-column prop="name" label="名称" min-width="96" show-overflow-tooltip />
        <el-table-column prop="land_use" label="用地类型" width="88" show-overflow-tooltip />
      </el-table>
      <div class="flex-row mt">
        <span class="scope-hint">已选 {{ selectedParcelIds.length }} 宗地块</span>
        <el-button type="primary" size="small" style="margin-left:auto" :loading="reviewing" @click="runReview">
          执行三区三线体检
        </el-button>
      </div>
    </div>

    <!-- 左侧面板二：体检结果与台账 -->
    <div v-if="panel === 'result'" class="page-panel panel-left glass-panel">
      <div class="panel-title">{{ patchReviewMode ? '变化图斑体检结果' : '体检结果与问题台账' }}</div>
      <el-skeleton v-if="reviewing" :rows="10" animated />
      <template v-else-if="reviewResult">
        <div class="flex-row mb">
          <span class="scope-hint">
            判定依据：规则矩阵（12 地类 × 三线）→
            <el-tag size="small" type="danger">冲突</el-tag> /
            <el-tag size="small" type="warning">警告</el-tag> /
            <el-tag size="small" type="success">通过</el-tag>
            <template v-if="conflictCount">（冲突 <b>{{ conflictCount }}</b> 条）</template>
          </span>
          <el-button v-if="!patchReviewMode" size="small" type="primary" plain style="margin-left:auto"
                     :loading="exporting" :disabled="!reviewResult?.rows?.length" @click="exportLedger">
            <el-icon :size="13"><Download /></el-icon>&nbsp;导出问题台账 CSV
          </el-button>
        </div>

        <el-row :gutter="8" class="mb">
          <el-col :span="6"><div class="sum-card">参与地块<b>{{ reviewResult.parcel_count }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">审查要素<b>{{ reviewResult.zone_count }}</b></div></el-col>
          <el-col :span="6"><div class="sum-card">占用总面积<b>{{ (totalOccupied / 10000).toFixed(1) }}<i>公顷</i></b></div></el-col>
          <el-col :span="6"><div class="sum-card">涉及地块<b>{{ affectedCount }}</b></div></el-col>
        </el-row>

        <el-alert
          v-if="!reviewResult.totals?.length"
          class="mb"
          type="warning"
          :closable="false"
          title="所选范围内地块与三区三线没有重叠，未产生占用数据。请检查范围与控制线数据。" />

        <div class="section-title">各类型控制线占用汇总</div>
        <el-table :data="reviewResult.totals" size="small" border max-height="130">
          <el-table-column label="控制线类型" min-width="120">
            <template #default="{ row }">
              <span class="legend-dot" :style="{ background: ZONE_TYPE_COLORS[row.zone_type] || '#999' }"></span>
              {{ ZONE_TYPE_LABELS[row.zone_type] || row.zone_type }}
            </template>
          </el-table-column>
          <el-table-column label="占用面积(公顷)" align="right" width="110">
            <template #default="{ row }">{{ (row.total_area_sqm / 10000).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="冲突/警告" align="right" width="86">
            <template #default="{ row }">{{ row.conflict_count || 0 }} / {{ row.warning_count || 0 }}</template>
          </el-table-column>
        </el-table>

        <div class="section-title mt">问题台账（按占用面积降序，含判定依据）</div>
        <el-table :data="sortedRows" size="small" border max-height="240" @row-click="locateParcelRow">
          <el-table-column prop="parcel_code" label="编号" width="80" fixed />
          <el-table-column prop="name" label="地块" min-width="92" show-overflow-tooltip />
          <el-table-column prop="land_use" label="用地类型" width="86" show-overflow-tooltip />
          <el-table-column label="涉及控制线" min-width="120">
            <template #default="{ row }">
              <span v-for="o in row.overlaps" :key="o.zone_id">
                <el-tag size="small" :type="o.level === '冲突' ? 'danger' : o.level === '警告' ? 'warning' : 'success'"
                        effect="plain" style="margin:0 2px 2px 0">
                  {{ o.zone_type_label }}({{ (o.overlap_area_sqm / 10000).toFixed(1) }}ha)
                </el-tag>
              </span>
            </template>
          </el-table-column>
          <el-table-column label="结论" width="64" align="center" fixed="right">
            <template #default="{ row }">
              <el-tag size="small" :type="verdictOf(row).type">{{ verdictOf(row).text }}</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div class="section-title mt">判定依据（冲突/警告明细）</div>
        <el-table v-if="reasonRows.length" :data="reasonRows" size="small" border max-height="180">
          <el-table-column prop="parcel" label="地块" min-width="110" show-overflow-tooltip />
          <el-table-column prop="zone_label" label="控制线" width="96" />
          <el-table-column prop="mu" label="重叠(亩)" width="76" align="right" />
          <el-table-column prop="level" label="结论" width="60" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.level === '冲突' ? 'danger' : 'warning'">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="message" label="判定依据" min-width="200" show-overflow-tooltip />
        </el-table>
        <el-empty v-else description="范围内无冲突/警告，全部通过" :image-size="50" />
      </template>
      <el-empty v-else description="完成左侧设置后点击“执行三区三线体检”" />
    </div>

    <!-- 规则矩阵对话框 -->
    <el-dialog v-model="rulesVisible" title="体检规则矩阵（12 用地大类 × 三区三线）" width="680px">
      <el-alert type="info" :closable="false" class="mb"
        title="规则参考国土空间规划管控逻辑（可配置：GET/PUT /api/planning/rules）。冲突=禁止占用，警告=需专项论证，通过=符合管控。" />
      <el-table :data="rulesRows" size="small" border max-height="420">
        <el-table-column prop="land_use" label="用地类型" width="150" fixed />
        <el-table-column v-for="zt in rulesZoneTypes" :key="zt.code" :label="zt.label" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="ruleTagType(row[zt.code])">{{ row[zt.code] }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- SHP 导入控制线对话框 -->
    <el-dialog v-model="zoneImportVisible" title="SHP 导入三区三线控制线" width="520px">
      <el-alert type="info" :closable="false" class="mb"
        title="三区三线边界由用户自行导入：请上传 SHP 边界并选定本包属于哪一类约束（永久基本农田 / 生态保护红线 / 城镇开发边界），导入后在地图上以规范线型显示。" />
      <el-form label-width="100px">
        <el-form-item label="约束类型">
          <el-radio-group v-model="zoneImportForm.zone_type">
            <el-radio-button v-for="(label, code) in ZONE_TYPE_LABELS" :key="code" :label="code">{{ label }}</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属项目（必选）">
          <el-select v-model="zoneImportForm.project_id" style="width:240px" placeholder="选择分析项目（必选，v3.0 上传数据必须关联项目）">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="SHP 压缩包">
          <el-upload :auto-upload="false" :limit="1" accept=".zip"
                     :on-change="(f) => (zoneImportFile = f.raw)"
                     :on-remove="() => (zoneImportFile = null)">
            <el-button size="small">选择 zip（.shp/.shx/.dbf/.prj）</el-button>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="zoneImportVisible = false">取消</el-button>
        <el-button type="primary" :loading="zoneImporting" :disabled="!zoneImportFile" @click="importZonesShpFile">
          开始导入
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * PlanningCheckView —— 模块四：三区三线合规性批量体检（v2.0）
 * 标准三线术语（英文代码+中文标签）/ 规则矩阵判定（判定依据含亩数）/
 * 结果持久化（planning_check_results）/ 转移矩阵图斑联动体检 / 台账 CSV 导出。
 */
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute } from 'vue-router'
import { useParcelStore } from '../stores/parcel'
import { useUiStore } from '../stores/ui'
import {
  getParcels, getZones, getZonesGeoJSON, getRegion, parseScopeShp,
  createZone, deleteZone, importZonesShp, reviewPlanning, exportReviewCsv,
  lockZone, batchDeleteZones, getPlanningRules, reviewPatches, getProjects,
} from '../api'
import { LAND_USE_ORDER, ZONE_TYPE_LABELS, ZONE_TYPE_COLORS } from '../utils/colors'
import MapView from '../components/MapView.vue'

const store = useParcelStore()
const ui = useUiStore()
const route = useRoute()

const mapRef = ref(null)
const panel = ref(null)
const boundaryGeojson = ref(null)
const zones = ref([])
const zonesGeojson = ref({ type: 'FeatureCollection', features: [] })
const highlightZoneId = ref(null)
const projects = ref([])

// 体检范围
const scopeMode = ref('project')
const currentRegion = ref(null)
const scopeGeojson = ref(null)
const scopeFile = ref(null)
const scopeImporting = ref(false)
const currentProject = computed(() => ui.currentProject)

// 控制线表单
const zoneForm = ref({ zone_type: 'permanent_basic_farmland', zone_name: '' })
const drawingZone = ref(false)
const zoneImportVisible = ref(false)
const zoneImportForm = ref({ zone_type: 'permanent_basic_farmland', project_id: null })
const zoneImportFile = ref(null)
const zoneImporting = ref(false)
const selectedZones = ref([])

// 被体检地块
const parcelLandUses = ref([])
const parcelOptions = ref([])
const selectedParcelIds = ref([])
const parcelTableRef = ref(null)

// 结果
const reviewing = ref(false)
const exporting = ref(false)
const reviewResult = ref(null)
const lastReviewPayload = ref(null)
const patchReviewMode = ref(false)
const patchLinkHint = ref('')
const rulesVisible = ref(false)
const rulesRows = ref([])
const rulesZoneTypes = ref([])

const zoneTagStyle = (type) => {
  const color = ZONE_TYPE_COLORS[type] || '#999'
  return { borderColor: color, color, background: 'transparent' }
}
const ruleTagType = (level) =>
  ({ 冲突: 'danger', 警告: 'warning', 通过: 'success', 提示: 'info' })[level] || 'info'

const totalOccupied = computed(() =>
  (reviewResult.value?.totals || []).reduce((s, t) => s + t.total_area_sqm, 0)
)
const affectedCount = computed(() =>
  (reviewResult.value?.rows || []).filter((r) => r.total_occupied_sqm > 0).length
)
const conflictCount = computed(() =>
  (reviewResult.value?.rows || []).filter((r) =>
    (r.overlaps || []).some((o) => o.level === '冲突')).length
)
const sortedRows = computed(() =>
  [...(reviewResult.value?.rows || [])].sort((a, b) => b.total_occupied_sqm - a.total_occupied_sqm)
)
const reasonRows = computed(() => {
  const rows = []
  for (const r of sortedRows.value) {
    for (const o of r.overlaps || []) {
      if (o.level === '冲突' || o.level === '警告') {
        rows.push({
          parcel: `${r.name}（${r.parcel_code}）`, zone_label: o.zone_type_label,
          mu: o.overlap_mu, level: o.level, message: o.message,
        })
      }
    }
  }
  return rows
})

onMounted(async () => {
  await Promise.all([
    store.fetchParcels({ page: 1, page_size: 100 }),
    store.fetchParcelsGeojson(),
    loadProjects(),
    loadRules(),
  ])
  await loadZones()
  await loadParcels()
  // 项目范围自动继承
  if (currentProject.value?.scope_geojson) {
    scopeGeojson.value = currentProject.value.scope_geojson
    scopeMode.value = 'project'
  }
  // 图斑联动：来自转移矩阵的合规检查
  if (ui.linkedPatches?.length && ui.currentProjectId) {
    patchLinkHint.value = `已接收转移矩阵联动：对 ${ui.linkedPatches.length} 个变化图斑进行合规检查（项目 #${ui.currentProjectId}）`
    runPatchReview()
  }
  // 地块详情跳转：按 query 选中
  if (route.query.parcel) {
    const id = Number(route.query.parcel)
    selectParcelById(id)
  }
})

async function loadProjects() {
  projects.value = await getProjects()
}

async function loadRules() {
  const data = await getPlanningRules()
  rulesRows.value = data.rows
  rulesZoneTypes.value = data.zone_types
}

async function loadZones() {
  zones.value = await getZones()
  zonesGeojson.value = await getZonesGeoJSON()
}

async function loadParcels() {
  const data = await getParcels({ page: 1, page_size: 100 })
  const luSet = new Set(parcelLandUses.value)
  parcelOptions.value = luSet.size
    ? data.items.filter((p) => luSet.has(p.land_use))
    : data.items
  nextTick(() => {
    parcelTableRef.value?.clearSelection()
    selectedParcelIds.value = []
  })
}

function selectParcelById(id) {
  const row = parcelOptions.value.find((p) => p.id === id)
  if (!row) return
  parcelTableRef.value?.toggleRowSelection(row, true)
  ElMessage.info(`已选中地块 ${row.name}，点击「执行三区三线体检」查看结果`)
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

watch(scopeMode, (mode) => {
  if (mode === 'project' && currentProject.value?.scope_geojson) {
    scopeGeojson.value = currentProject.value.scope_geojson
  }
  if (mode === 'manual' && !scopeGeojson.value) {
    panel.value = null
    ElMessage.info('请使用地图左侧工具绘制体检范围，画完自动返回设置面板')
  }
})

function onMapDraw(selection) {
  if (!selection?.geometry) return
  if (drawingZone.value) {
    submitDrawZone(selection.geometry)
    return
  }
  if (scopeMode.value === 'manual') {
    scopeGeojson.value = selection.geometry
    ElMessage.success('手动体检范围已划定，已自动回到设置面板')
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

// ---------- 控制线 ----------
function startDrawZone() {
  drawingZone.value = true
  panel.value = null
  ElMessage.info('请在地图左侧工具条选择“多边形/框选/圈选”并绘制控制线范围')
}

async function submitDrawZone(geometry) {
  drawingZone.value = false
  try {
    await createZone({
      zone_name: zoneForm.value.zone_name || ZONE_TYPE_LABELS[zoneForm.value.zone_type],
      zone_type: zoneForm.value.zone_type,
      control_desc: `手动绘制（${ZONE_TYPE_LABELS[zoneForm.value.zone_type]}）`,
      project_id: ui.currentProjectId || null,
      geometry,
    })
    ElMessage.success('控制线已新增')
    await loadZones()
    panel.value = 'setup'
  } catch (e) {
    ElMessage.error('新增失败：' + (e?.message || '未知原因'))
  }
}

function openZoneImport() {
  zoneImportForm.value = { zone_type: 'permanent_basic_farmland', project_id: ui.currentProjectId || null }
  zoneImportFile.value = null
  zoneImportVisible.value = true
}

async function importZonesShpFile() {
  if (!zoneImportFile.value) return
  // v3.0：控制线导入强制关联分析项目
  if (!zoneImportForm.value.project_id) {
    ElMessage.warning('请先选择所属项目（v3.0 起上传数据必须关联分析项目；无项目请先在顶栏「项目工作台」创建）')
    return
  }
  zoneImporting.value = true
  try {
    const fd = new FormData()
    fd.append('file', zoneImportFile.value)
    fd.append('zone_type', zoneImportForm.value.zone_type)
    fd.append('project_id', zoneImportForm.value.project_id)
    const result = await importZonesShp(fd)
    ElMessage.success(`SHP 导入完成：成功 ${result.imported} 条（${ZONE_TYPE_LABELS[zoneImportForm.value.zone_type]}），跳过 ${result.skipped.length} 条`)
    await loadZones()
    zoneImportVisible.value = false
  } finally {
    zoneImporting.value = false
  }
}

async function toggleZoneLock(row) {
  await lockZone(row.id, !row.locked)
  ElMessage.success(row.locked ? '已解锁' : '已锁定（锁定后不可删除）')
  await loadZones()
}

async function batchDeleteZonesSel() {
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedZones.value.length} 条控制线吗？`,
    '批量删除确认', { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  const result = await batchDeleteZones(selectedZones.value.map((z) => z.id))
  ElMessage.success(`已删除 ${result.deleted.length} 条` + (result.locked.length ? `，${result.locked.length} 条已锁定跳过` : ''))
  await loadZones()
}

async function removeZone(row) {
  await ElMessageBox.confirm(`确定删除控制线 ${row.zone_name} 吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteZone(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.warning(e?.message || '删除失败（可能已锁定）')
  }
  await loadZones()
}

// ---------- 地块选择 ----------
function selectAllParcels() {
  if (!parcelOptions.value.length) return
  parcelTableRef.value?.clearSelection()
  parcelOptions.value.forEach((row) => parcelTableRef.value?.toggleRowSelection(row, true))
}

function clearParcelSelection() {
  parcelTableRef.value?.clearSelection()
  selectedParcelIds.value = []
}

// ---------- 体检计算 ----------
async function runReview() {
  if (!zones.value.length) {
    ElMessage.warning('当前没有任何三区三线控制线。请先通过 SHP 导入或图上绘制添加')
    panel.value = 'setup'
    return
  }
  reviewing.value = true
  patchReviewMode.value = false
  panel.value = 'result'
  try {
    lastReviewPayload.value = {
      scope: scopeGeojson.value || null,
      zone_ids: zones.value.map((z) => z.id),
      parcel_ids: selectedParcelIds.value.length ? selectedParcelIds.value : null,
      project_id: ui.currentProjectId || null,
    }
    reviewResult.value = await reviewPlanning(lastReviewPayload.value)
    ui.bumpAnalysisVersion()  // v3.0：通知驾驶舱自动刷新
  } finally {
    reviewing.value = false
  }
}

async function runPatchReview() {
  if (!ui.currentProjectId) {
    ElMessage.warning('请先在顶栏选择分析项目')
    return
  }
  reviewing.value = true
  patchReviewMode.value = true
  panel.value = 'result'
  try {
    reviewResult.value = await reviewPatches({
      project_id: ui.currentProjectId,
      patch_ids: ui.linkedPatches?.length ? ui.linkedPatches : null,
    })
    ui.setLinkedPatches(null, null, null)
    ui.bumpAnalysisVersion()  // v3.0：图斑体检结论变化 → 驾驶舱自动刷新
  } finally {
    reviewing.value = false
  }
}

function verdictOf(row) {
  const levels = new Set((row.overlaps || []).map((o) => o.level))
  if (levels.has('冲突')) return { text: '冲突', type: 'danger' }
  if (levels.has('警告')) return { text: '警告', type: 'warning' }
  if (levels.size) return { text: '提示', type: 'info' }
  return { text: '通过', type: 'success' }
}

function locateParcelRow(row) {
  const feature = store.parcelsGeojson?.features?.find(
    (f) => Number(f.properties?.id) === Number(row.parcel_id || row.patch_id)
  )
  if (feature) mapRef.value?.flyTo(feature)
  else ElMessage.warning('未在地图上找到该图斑')
}

function onParcelClick(feature) {
  const p = feature.properties
  mapRef.value?.flyTo(feature)
  ElMessage.info(`${p.name}（${p.parcel_code}）：可在“体检设置”勾选后参与批量体检`)
}

async function exportLedger() {
  if (!lastReviewPayload.value) {
    ElMessage.warning('请先执行体检计算')
    return
  }
  exporting.value = true
  try {
    const blob = await exportReviewCsv(lastReviewPayload.value)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `三区三线体检台账_${new Date().toISOString().slice(0, 10)}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('问题台账 CSV 已导出（含判定依据）')
  } catch (e) {
    ElMessage.error('导出失败：' + (e?.message || '未知原因'))
  } finally {
    exporting.value = false
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
  transform: translateY(calc(-50% - 48px));
}
.icon-left2 {
  left: 10px;
  top: 50%;
  transform: translateY(0);
}
.icon-left3 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% + 48px));
}
.page-panel {
  position: absolute;
  z-index: 6;
  width: 700px;
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
.legend-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 3px;
  margin-right: 6px;
}
</style>
