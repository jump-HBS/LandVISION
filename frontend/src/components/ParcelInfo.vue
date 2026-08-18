<template>
  <el-drawer v-model="visible" :title="title" size="440px" destroy-on-close>
    <template v-if="parcel">
      <!-- 基本信息 -->
      <el-descriptions title="基本信息" :column="2" border>
        <el-descriptions-item label="地块编号">{{ parcel.parcel_code }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ parcel.name }}</el-descriptions-item>
        <el-descriptions-item label="用地类型">
          <el-tag size="small" :color="LAND_USE_COLORS[parcel.land_use] || undefined" style="border:none;color:#fff">
            {{ parcel.land_use }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="面积">{{ fmtArea(parcel.area_sqm) }}</el-descriptions-item>
        <el-descriptions-item label="行政区">{{ parcel.district || '-' }}</el-descriptions-item>
        <el-descriptions-item label="区划代码">{{ parcel.region_code || '-' }}</el-descriptions-item>
        <el-descriptions-item label="期次">
          <el-tag size="small" :type="parcel.period === 'current' ? 'warning' : 'success'">
            {{ parcel.period === 'current' ? '末期（current）' : '基期（base）' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="所属项目">{{ projectName || '未关联' }}</el-descriptions-item>
        <el-descriptions-item label="锁定状态">
          <el-tag size="small" :type="parcel.locked ? 'danger' : 'info'">
            {{ parcel.locked ? '已锁定（不可删除）' : '未锁定' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="容积率上限">{{ parcel.far_limit ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="建筑限高">{{ parcel.height_limit ?? '-' }} m</el-descriptions-item>
      </el-descriptions>

      <!-- 三区三线体检结论（含判定依据） -->
      <div v-if="planning" class="mt">
        <el-divider content-position="left">三区三线体检</el-divider>
        <el-tag :type="planningTagType" size="large">{{ planning.overall }}</el-tag>
        <el-table :data="planning.details" size="small" class="mt" max-height="230">
          <el-table-column label="控制线" min-width="96">
            <template #default="{ row }">{{ row.zone_type_label || row.zone_name }}</template>
          </el-table-column>
          <el-table-column prop="overlap_mu" label="重叠(亩)" width="76" align="right" />
          <el-table-column prop="level" label="结论" width="64">
            <template #default="{ row }">
              <el-tag size="small" :type="levelTagType(row.level)">{{ row.level }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <!-- 判定依据：冲突/警告时展示具体原因 -->
        <el-alert
          v-for="(d, i) in conflictDetails" :key="i"
          class="mt" :type="d.level === '冲突' ? 'error' : 'warning'"
          :closable="false" :title="d.message" />
      </div>

      <!-- 操作：地图定位 + 模块跳转（自动携带地块 ID） -->
      <div class="mt" style="display:flex; gap:10px; flex-wrap:wrap">
        <el-button type="primary" @click="$emit('fly-to', parcel)">地图定位</el-button>
        <el-button @click="$emit('goto-planning', parcel)">查看体检结果</el-button>
        <el-button @click="$emit('goto-transition', parcel)">查看转移矩阵记录</el-button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup>
/**
 * ParcelInfo —— 地块详情抽屉（v2.0：期次/项目/锁定 + 三区三线判定依据 + 模块跳转）
 * props: modelValue(visible) / parcel / planning / projectName
 * emits: update:modelValue / fly-to / goto-planning / goto-transition
 */
import { computed } from 'vue'
import { LAND_USE_COLORS } from '../utils/colors'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  parcel: { type: Object, default: null },
  planning: { type: Object, default: null },
  projectName: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'fly-to', 'goto-planning', 'goto-transition'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const title = computed(() =>
  props.parcel ? `${props.parcel.name}（${props.parcel.parcel_code}）` : '地块详情'
)

const planningTagType = computed(() => {
  const map = { 冲突: 'danger', 警告: 'warning', 提示: 'info', 通过: 'success' }
  return map[props.planning?.overall] || 'info'
})

const levelTagType = (level) => {
  const map = { 冲突: 'danger', 警告: 'warning', 提示: 'info', 通过: 'success' }
  return map[level] || 'info'
}

const fmtArea = (v) => (v ? `${(v / 10000).toFixed(2)} 公顷` : '-')

// 判定依据：仅展示冲突/警告（增强系统可信度）
const conflictDetails = computed(() =>
  (props.planning?.details || []).filter((d) => d.level === '冲突' || d.level === '警告')
)
</script>

<style scoped>
.mt {
  margin-top: 16px;
}
</style>
