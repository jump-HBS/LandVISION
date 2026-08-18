<template>
  <div ref="rootEl" class="region-selector">
    <!-- 图标按钮：点击展开/收起（悬浮面板不会遮挡按钮） -->
    <button class="rs-icon" :class="{ active: open }" @click="open = !open" title="行政区选择（国家-省-市-县）">
      <el-icon :size="16"><LocationInformation /></el-icon>
    </button>

    <!-- 展开面板：绝对定位悬浮，点击外部自动关闭 -->
    <div v-show="open" class="rs-panel map-widget">
      <div class="rs-title">行政区选择（逐级检索）</div>

      <el-select :model-value="COUNTRY.code" placeholder="国家" size="small"
                 class="rs-select" disabled>
        <el-option :label="COUNTRY.name" :value="COUNTRY.code" />
      </el-select>

      <el-select v-model="provinceCode" placeholder="省 / 直辖市" size="small"
                 filterable class="rs-select" @change="onProvinceChange">
        <el-option v-for="p in provinces" :key="p.code" :label="p.name" :value="p.code" />
      </el-select>

      <el-select v-model="cityCode" placeholder="市 / 州" size="small" filterable clearable
                 class="rs-select" :disabled="!provinceCode" @change="onCityChange">
        <el-option v-for="c in cities" :key="c.code" :label="c.name" :value="c.code" />
      </el-select>

      <el-select v-model="countyCode" placeholder="区 / 县" size="small" filterable clearable
                 class="rs-select" :disabled="!cityCode" @change="onCountyChange">
        <el-option v-for="c in counties" :key="c.code" :label="c.name" :value="c.code" />
      </el-select>

      <div class="rs-actions">
        <el-button size="small" type="primary" :loading="locating" @click="locate">定位</el-button>
        <el-button size="small" :disabled="!countyCode && !cityCode && !provinceCode" @click="clear">清除</el-button>
      </div>
      <div v-if="hint" class="rs-hint">{{ hint }}</div>
    </div>
  </div>
</template>

<script setup>
/**
 * RegionSelector —— 行政区选择器（固定在地图右上角）
 * 国家 → 省 → 市 → 县 四级逐级检索；点击"定位"飞行至该行政区完整范围。
 *
 * emits:
 *  select({code, name, level})  选中行政区（县级优先，用于地块过滤）
 *  locate({code, name, center, bbox})  定位（父页面 fitBounds + 显示边界）
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { getRegions, getRegionChildren, getRegionLocate } from '../api'

const emit = defineEmits(['select', 'locate'])

const COUNTRY = { code: '100000', name: '中国', level: 'country' }

const rootEl = ref(null)
const open = ref(false)
const provinces = ref([])
const cities = ref([])
const counties = ref([])
const provinceCode = ref(null)
const cityCode = ref(null)
const countyCode = ref(null)
const locating = ref(false)
const hint = ref('')

onMounted(() => {
  loadProvinces()
  // 点击组件外部 → 关闭面板
  document.addEventListener('mousedown', onOutsideClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('mousedown', onOutsideClick)
})

function onOutsideClick(e) {
  if (!open.value) return
  // Element Plus 的下拉选项（el-select/el-option）渲染在 body 的 popper 层，
  // 必须排除，否则点击下拉选项会被误判为"点击面板外部"导致面板熄灭
  if (e.target.closest('.el-popper, .el-select-dropdown, .el-picker__popper, .el-message-box')) {
    return
  }
  if (rootEl.value && !rootEl.value.contains(e.target)) {
    open.value = false
  }
}

async function loadProvinces() {
  const data = await getRegions({ level: 'province', page_size: 100 })
  provinces.value = data.items
}

async function onProvinceChange(code) {
  cityCode.value = null
  countyCode.value = null
  counties.value = []
  hint.value = ''
  if (!code) { cities.value = []; emit('select', null); return }
  cities.value = await getRegionChildren(code)
  if (!cities.value.length) hint.value = '该省级行政区暂无市级数据'
  emit('select', { code, name: provinceName(code), level: 'province' })
}

async function onCityChange(code) {
  countyCode.value = null
  counties.value = []
  hint.value = ''
  if (!code) { emit('select', null); return }
  counties.value = await getRegionChildren(code)
  if (!counties.value.length) hint.value = '该市级行政区暂无县级数据'
  emit('select', { code, name: cityName(code), level: 'city' })
}

async function onCountyChange(code) {
  if (!code) { emit('select', null); return }
  emit('select', { code, name: countyName(code), level: 'county' })
}

function provinceName(code) {
  return provinces.value.find((p) => p.code === code)?.name || code
}
function cityName(code) {
  return cities.value.find((c) => c.code === code)?.name || code
}
function countyName(code) {
  return counties.value.find((c) => c.code === code)?.name || code
}

async function locate() {
  const code = countyCode.value || cityCode.value || provinceCode.value
  if (!code) {
    ElMessage.warning('请先逐级选择行政区')
    return
  }
  locating.value = true
  try {
    const data = await getRegionLocate(code)
    if (!data.center || !data.bbox) {
      ElMessage.warning('该行政区没有边界几何数据')
      return
    }
    emit('locate', data)
  } finally {
    locating.value = false
  }
}

function clear() {
  provinceCode.value = null
  cityCode.value = null
  countyCode.value = null
  cities.value = []
  counties.value = []
  hint.value = ''
  emit('select', null)
}

defineExpose({ openPanel: () => (open.value = true), clear })
</script>

<style scoped>
.region-selector {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}
.rs-icon {
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
  position: relative;
  z-index: 30; /* 按钮始终在面板上层，随时可点击关闭 */
}
.rs-icon:hover,
.rs-icon.active {
  background: var(--lv-primary);
  color: #fff;
}
/* 悬浮面板：绝对定位在图标下方，不遮挡图标，不占用布局流 */
.rs-panel {
  position: absolute;
  right: 0;
  top: 42px;
  z-index: 25;
  width: 210px;
  padding: 10px;
  max-height: min(60vh, 420px);
  overflow-y: auto;
}
.rs-title {
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 8px;
  color: var(--lv-text);
}
.rs-select {
  width: 100%;
  margin-bottom: 6px;
}
.rs-actions {
  display: flex;
  gap: 6px;
  margin-top: 4px;
}
.rs-hint {
  font-size: 11px;
  color: var(--lv-text-tertiary);
  margin-top: 6px;
  line-height: 1.5;
}
</style>
