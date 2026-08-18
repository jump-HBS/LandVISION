<template>
  <el-row :gutter="16">
    <!-- 左侧：报告参数 -->
    <el-col :span="8">
      <el-card shadow="hover">
        <template #header>报告参数</template>
        <el-form :model="form" label-width="90px">
          <el-form-item label="项目名称">
            <el-input v-model="form.project_name" />
          </el-form-item>
          <el-form-item label="报告期">
            <el-input v-model="form.period" />
          </el-form-item>
          <el-form-item label="编制人">
            <el-input v-model="form.author" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="generating" @click="generate" style="width:100%">
              生成综合分析报告
            </el-button>
          </el-form-item>
          <el-form-item v-if="report">
            <el-button type="success" @click="download" style="width:100%">
              下载 Markdown
            </el-button>
          </el-form-item>
        </el-form>
        <el-alert
          title="报告继承数据驾驶舱的分析项目与范围；结合持久化结果自动生成问题清单与对策（项目概况 → 现状评价 → 问题识别 → 原因分析 → 规划建议 → 附录数据表）"
          type="info" :closable="false" />
        <el-divider content-position="left">当前分析范围</el-divider>
        <el-alert v-if="ui.currentProject" type="success" :closable="false" class="mb">
          <template #title>
            项目：<b>{{ ui.currentProject.name }}</b>（基期 {{ ui.currentProject.base_year }} → 末期 {{ ui.currentProject.current_year }}）
          </template>
        </el-alert>
        <el-alert v-else type="warning" :closable="false" class="mb"
          title="未选择分析项目 —— 将按全量数据生成。如需限定范围，请先在顶栏选择项目并在驾驶舱划定范围。" />
      </el-card>
    </el-col>

    <!-- 右侧：报告预览（综合分析） -->
    <el-col :span="16">
      <el-card shadow="hover" v-loading="generating">
        <template #header>报告预览</template>
        <el-skeleton v-if="generating && !report" :rows="12" animated />
        <template v-else-if="report">
          <h2 style="text-align:center">{{ report.meta.project_name }}</h2>
          <p style="text-align:center;color:var(--lv-text-tertiary);font-size:12px">
            {{ report.meta.period }} | 生成时间：{{ report.meta.generated_at }} | 数据模式：{{ report.meta.mode }}
          </p>

          <el-divider content-position="left">一、项目概况</el-divider>
          <el-descriptions :column="3" border size="small">
            <el-descriptions-item label="分析范围">
              {{ report.scope.label }}
              <el-tag v-if="report.scope?.strict" size="small" type="warning" effect="plain" style="margin-left:4px">
                已按此范围聚合
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="地块总数">{{ report.overview.parcel_total }} 宗</el-descriptions-item>
            <el-descriptions-item label="总面积">{{ (report.overview.area_total_sqm / 10000).toFixed(2) }} 公顷</el-descriptions-item>
            <el-descriptions-item label="兴趣点">{{ report.overview.poi_total }} 个</el-descriptions-item>
            <el-descriptions-item label="三区三线">{{ report.overview.planning_zone_total }} 条</el-descriptions-item>
            <el-descriptions-item label="可达覆盖率">{{ (report.overview.coverage_rate * 100).toFixed(1) }}%</el-descriptions-item>
          </el-descriptions>
          <div class="mt">
            <el-space wrap>
              <el-tag :type="report.progress.transition ? 'success' : 'info'">② 转移矩阵 {{ report.progress.transition ? '已完成' : '未执行' }}</el-tag>
              <el-tag :type="report.progress.planning ? 'success' : 'info'">③ 体检 {{ report.progress.planning ? '已完成' : '未执行' }}</el-tag>
              <el-tag :type="report.progress.suitability ? 'success' : 'info'">④ 适宜性 {{ report.progress.suitability ? '已完成' : '未执行' }}</el-tag>
              <el-tag :type="report.progress.accessibility ? 'success' : 'info'">⑤ 可达性 {{ report.progress.accessibility ? '已完成' : '未执行' }}</el-tag>
            </el-space>
          </div>

          <el-divider content-position="left">二、现状评价</el-divider>
          <el-table :data="landUseRows" size="small" border max-height="280">
            <el-table-column prop="land_use" label="用地类型（GB/T 21010-2017 一级类）" />
            <el-table-column prop="count" label="数量" align="right" width="70" />
            <el-table-column label="面积(公顷)" align="right" width="100">
              <template #default="{ row }">{{ (row.area_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
          </el-table>
          <div class="section-title">行政区分布</div>
          <el-table :data="report.district_distribution" size="small" border max-height="180">
            <el-table-column prop="district" label="行政区" />
            <el-table-column prop="count" label="地块数" align="right" width="70" />
            <el-table-column label="面积(公顷)" align="right" width="100">
              <template #default="{ row }">{{ (row.area_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
          </el-table>
          <div class="section-title">用地变化转移矩阵（模块一）</div>
          <template v-if="report.transition_analysis.has_data">
            <el-space wrap class="mb">
              <el-tag>基期 {{ report.transition_analysis.base_count }} 宗</el-tag>
              <el-tag type="success">末期 {{ report.transition_analysis.current_count }} 宗</el-tag>
              <el-tag type="warning">变化图斑 {{ report.transition_analysis.change_count }} 个</el-tag>
              <el-tag type="danger">冲突图斑 {{ report.transition_analysis.conflict_patch_count }} 个</el-tag>
            </el-space>
          </template>
          <el-alert v-else type="info" :closable="false" class="mb"
            :title="report.transition_analysis.hint || '尚未导入两期地块数据'" />
          <div class="section-title">适宜性评价（模块二）</div>
          <el-space v-if="report.suitability.stats.length" wrap class="mb">
            <el-tag v-for="s in report.suitability.stats" :key="s.level" size="small">
              {{ s.level }}：{{ s.count }} 个格网
            </el-tag>
          </el-space>
          <el-alert v-else type="info" :closable="false" class="mb" title="尚未执行适宜性评价" />

          <el-divider content-position="left">三、问题识别</el-divider>
          <div v-if="report.problems?.length" class="problem-list">
            <div v-for="(p, i) in report.problems.slice(0, 30)" :key="i" class="problem-item" @click="problemDrill(p)">
              <el-tag size="small" :type="p.severity === 'high' ? 'danger' : p.severity === 'medium' ? 'warning' : 'info'">
                {{ p.type }}
              </el-tag>
              <b style="margin-left:6px">{{ p.title }}</b>
              <div class="problem-detail">{{ p.detail }}</div>
            </div>
          </div>
          <el-empty v-else description="未发现问题" :image-size="60" />

          <el-divider content-position="left">四、原因分析</el-divider>
          <el-space wrap class="mb">
            <el-tag type="danger">冲突 {{ report.planning_review.by_level.冲突 || 0 }}</el-tag>
            <el-tag type="warning">警告 {{ report.planning_review.by_level.警告 || 0 }}</el-tag>
            <el-tag type="info">提示 {{ report.planning_review.by_level.提示 || 0 }}</el-tag>
            <el-tag type="success">通过 {{ report.planning_review.by_level.通过 || 0 }}</el-tag>
          </el-space>
          <el-alert type="info" :closable="false" class="mb"
            title="判定依据采用可配置规则矩阵（12 用地大类 × 三区三线，见三区三线体检页「规则矩阵」按钮）" />
          <el-table :data="conflictReasons" size="small" border max-height="220">
            <el-table-column prop="parcel" label="地块" min-width="110" show-overflow-tooltip />
            <el-table-column prop="zone_label" label="控制线" width="90" />
            <el-table-column prop="mu" label="重叠(亩)" width="72" align="right" />
            <el-table-column prop="message" label="判定依据" min-width="180" show-overflow-tooltip />
          </el-table>

          <el-divider content-position="left">五、规划建议</el-divider>
          <div v-if="report.suggestions?.length" class="suggest-list">
            <div v-for="(s, i) in report.suggestions" :key="i" class="suggest-item">
              <div class="suggest-title">💡 {{ s.title }}</div>
              <div class="suggest-detail">{{ s.detail }}</div>
            </div>
          </div>
          <el-empty v-else description="暂无建议" :image-size="60" />

          <el-divider content-position="left">六、附录数据表</el-divider>
          <div class="section-title">各类型控制线占用汇总</div>
          <el-table :data="report.planning_review.review_totals" size="small" border>
            <el-table-column label="控制线" min-width="110">
              <template #default="{ row }">{{ row.zone_type_label }}</template>
            </el-table-column>
            <el-table-column label="被占用总面积(公顷)" align="right">
              <template #default="{ row }">{{ (row.total_area_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
          </el-table>
          <div class="section-title">问题台账（前 15 条，点击行定位地块）</div>
          <el-table :data="topLedger" size="small" border max-height="220" @row-click="locateParcel">
            <el-table-column prop="parcel_code" label="编号" width="76" />
            <el-table-column prop="name" label="地块" min-width="96" show-overflow-tooltip />
            <el-table-column prop="land_use" label="用地类型" width="86" show-overflow-tooltip />
            <el-table-column label="占用(公顷)" align="right" width="86">
              <template #default="{ row }">{{ (row.total_occupied_sqm / 10000).toFixed(2) }}</template>
            </el-table-column>
          </el-table>
          <div class="section-title">设施可达性盲区清单</div>
          <el-table v-if="report.accessibility.gaps.length" :data="report.accessibility.gaps" size="small" border max-height="200">
            <el-table-column prop="parcel_code" label="编号" width="76" />
            <el-table-column prop="name" label="地块" min-width="96" show-overflow-tooltip />
            <el-table-column prop="land_use" label="用地类型" width="86" show-overflow-tooltip />
            <el-table-column prop="reason" label="原因" min-width="120" show-overflow-tooltip />
          </el-table>
          <el-empty v-else description="无盲区" :image-size="50" />
        </template>
        <el-empty v-else description="点击左侧“生成综合分析报告”查看预览" />
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup>
/**
 * ReportView —— 报告生成（v2.0 综合分析）
 * 继承驾驶舱的分析项目与范围；六章节：项目概况/现状评价/问题识别/原因分析/规划建议/附录。
 * 问题与台账行可点击跳转到对应模块/地块（钻取）。
 */
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useUiStore } from '../stores/ui'
import { generateReport, downloadReport, getLatestReport } from '../api'

const ui = useUiStore()
const router = useRouter()

const form = ref({
  project_name: '武汉市洪山区国土空间数据管理报告',
  period: '2026 年第三季度',
  author: 'LandVISION 系统',
})
const report = ref(null)
const generating = ref(false)

const landUseRows = computed(() =>
  (report.value?.land_use_distribution || []).filter((r) => r.count > 0 || r.area_sqm > 0)
)
const topLedger = computed(() =>
  [...(report.value?.planning_review?.review_rows || [])]
    .sort((a, b) => b.total_occupied_sqm - a.total_occupied_sqm)
    .slice(0, 15)
)
const conflictReasons = computed(() => {
  const rows = []
  for (const r of report.value?.planning_review?.review_rows || []) {
    for (const o of r.overlaps || []) {
      if (o.level === '冲突' || o.level === '警告') {
        rows.push({
          parcel: `${r.name}（${r.parcel_code}）`, zone_label: o.zone_type_label,
          mu: o.overlap_mu, message: o.message,
        })
      }
    }
  }
  return rows.slice(0, 20)
})

onMounted(async () => {
  try {
    const r = await getLatestReport()
    if (r && !r.detail) report.value = r
  } catch (e) {
    /* 尚无报告，忽略 */
  }
})

async function generate() {
  generating.value = true
  try {
    report.value = await generateReport({
      ...form.value,
      project_id: ui.currentProjectId || null,
      scope: null,
      scope_label: null,
    })
  } finally {
    generating.value = false
  }
}

async function download() {
  const blob = await downloadReport()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'landvision_report.md'
  a.click()
  URL.revokeObjectURL(url)
}

// 钻取：问题/台账行 → 对应模块/地块
function problemDrill(problem) {
  const map = { 三区三线冲突: '/planning', 三区三线警告: '/planning', 设施盲区: '/accessibility', 违规变化: '/planning' }
  if (map[problem.type]) router.push(map[problem.type])
}

function locateParcel(row) {
  router.push({ path: '/parcels', query: { highlight: row.parcel_id } })
}
</script>

<style scoped>
.mb {
  margin-bottom: 12px;
}
.mt {
  margin-top: 12px;
}
.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--lv-text);
  margin: 10px 0 8px;
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
</style>
