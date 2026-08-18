<template>
  <div class="stat-card glass-panel">
    <div class="stat-head">
      <div class="stat-icon" :style="{ background: iconBg, color: iconColor }">
        <el-icon :size="22"><component :is="icon" /></el-icon>
      </div>
      <div class="stat-meta">
        <div class="stat-label">{{ label }}</div>
        <div class="stat-value">
          {{ formattedValue }}<span v-if="unit" class="stat-unit">{{ unit }}</span>
        </div>
      </div>
      <el-tag v-if="groupTag" size="small" effect="plain" class="stat-group">{{ groupTag }}</el-tag>
    </div>

    <div class="stat-foot">
      <div v-if="delta !== null && delta !== undefined" class="stat-delta">
        <span class="delta-badge" :class="deltaClass">
          <el-icon :size="12"><component :is="deltaIcon" /></el-icon>
          {{ Math.abs(delta) }}%
        </span>
        <span class="delta-desc">{{ deltaDesc || '较上月' }}</span>
      </div>
      <span v-else-if="sub" class="stat-sub">{{ sub }}</span>
      <!-- 迷你趋势折线 -->
      <div v-if="spark && spark.length" ref="sparkEl" class="stat-spark"></div>
    </div>
  </div>
</template>

<script setup>
/**
 * StatsCard —— 企业级统计指标卡
 * props:
 *  label 指标名 / value 数值 / unit 单位 / icon 图标 / iconColor / iconBg
 *  delta 环比变化率(%)，正绿负红 / deltaDesc 变化说明
 *  sub 副文本（无 delta 时显示）/ groupTag 分组标签（总量类/监测类/业务类）
 *  spark 迷你趋势数据 [n1, n2, ...]（自动渲染折线）
 */
import { ref, computed, onMounted, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  unit: { type: String, default: '' },
  icon: { type: String, default: 'DataLine' },
  iconColor: { type: String, default: '#2e86ab' },
  iconBg: { type: String, default: 'rgba(46,134,171,.12)' },
  delta: { type: Number, default: null },
  deltaDesc: { type: String, default: '较上月' },
  sub: { type: String, default: '' },
  groupTag: { type: String, default: '' },
  spark: { type: Array, default: null },
  precision: { type: Number, default: 0 },
})

const sparkEl = ref(null)
let sparkChart = null

const formattedValue = computed(() => {
  if (typeof props.value === 'number') {
    return props.value.toLocaleString('zh-CN', { maximumFractionDigits: props.precision })
  }
  return props.value
})

const deltaClass = computed(() => (props.delta >= 0 ? 'delta-up' : 'delta-down'))
const deltaIcon = computed(() => (props.delta >= 0 ? 'Top' : 'Bottom'))

function renderSpark() {
  if (!sparkEl.value || !props.spark?.length) return
  if (!sparkChart) sparkChart = echarts.init(sparkEl.value)
  const color = props.delta >= 0 ? '#43aa8b' : '#ef476f'
  sparkChart.setOption({
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    xAxis: { type: 'category', show: false, data: props.spark.map((_, i) => i) },
    yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
    series: [{
      type: 'line', data: props.spark, smooth: true, symbol: 'none',
      lineStyle: { width: 2, color }, areaStyle: { opacity: 0.12, color },
    }],
  })
}

onMounted(renderSpark)
watch(() => props.spark, renderSpark, { deep: true })
</script>

<style scoped>
.stat-card {
  padding: 14px 16px;
  min-height: 108px;
}
.stat-head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.stat-meta {
  flex: 1;
  min-width: 0;
}
.stat-label {
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--lv-text);
  line-height: 1.25;
  font-variant-numeric: tabular-nums;
}
.stat-unit {
  font-size: 12px;
  font-weight: 400;
  color: var(--lv-text-tertiary);
  margin-left: 4px;
}
.stat-group {
  align-self: flex-start;
  border: none;
  background: var(--lv-primary-light);
  color: var(--lv-primary);
}
.stat-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  min-height: 22px;
}
.stat-delta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.delta-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  font-size: 12px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 6px;
}
.delta-up {
  color: #43aa8b;
  background: rgba(67, 170, 139, 0.12);
}
.delta-down {
  color: #ef476f;
  background: rgba(239, 71, 111, 0.12);
}
.delta-desc,
.stat-sub {
  font-size: 11px;
  color: var(--lv-text-tertiary);
}
.stat-spark {
  width: 90px;
  height: 26px;
}
</style>
