import { defineStore } from 'pinia'

/**
 * 全局 UI 状态：主题 / 侧边栏 / 图层可见性 / 驾驶舱联动筛选
 */
export const useUiStore = defineStore('ui', {
  state: () => ({
    // 主题：light / dark
    theme: localStorage.getItem('landvision-theme') || 'light',
    sidebarCollapsed: false,

    // 地图图层可见性（图层面板开关）
    layerVisibility: {
      parcels: true,
      pois: true,
      zones: true,
      changes: true,
      cells: true,         // 适宜性评价格网
      coverage: true,      // 设施可达性覆盖
      regionBoundary: true,  // 行政区范围高亮
      satellite: false,       // 卫星影像底图
    },

    // 驾驶舱联动筛选（图表点击 ↔ 地图过滤 ↔ 框选统计）
    activeLandUse: null,   // 用地类型筛选（null=全部）
    activeRegion: null,    // 行政区筛选 {code, name, level}（县域级）

    // 驾驶舱统筹分析范围（报告生成模块继承此范围）
    analysisScope: null,   // {geometry, label, kind: 'region'|'shp', code, level}（null=全量数据）

    // v2.0 分析项目上下文（业务上下文：范围 + 期次年份）
    currentProjectId: null,
    currentProject: null,  // {id, name, base_year, current_year, scope_geojson}

    // 模块联动参数（模块间跳转时传递）
    linkedPatches: null,   // 转移矩阵 → 体检：图斑 id 列表
    linkedScope: null,     // 转移矩阵 → 适宜性/可达性：图斑并集范围
    linkedScopeLabel: null,
    linkedFacilityTypes: [], // v3.0：转移矩阵 → 可达性：预置设施类型

    // v3.0：分析结果版本号（各视图完成分析后自增，驾驶舱据此自动刷新）
    analysisVersion: 0,

    // 地图框选结果（跨组件共享）
    selection: null,       // {count, areaSqm, byLandUse, features}

    // 通知（顶栏铃铛）
    notifications: [
      { id: 1, title: '三区三线体检预警', desc: '滨江住宅区与生态保护红线存在冲突', time: '10 分钟前', type: 'warning', read: false },
      { id: 2, title: '可达性分析完成', desc: '800m 生活圈覆盖率达 100%', time: '2 小时前', type: 'success', read: false },
      { id: 3, title: '系统提示', desc: '已切换至 Demo 数据模式', time: '1 天前', type: 'info', read: true },
    ],
  }),

  getters: {
    isDark: (state) => state.theme === 'dark',
    unreadCount: (state) => state.notifications.filter((n) => !n.read).length,
  },

  actions: {
    toggleTheme() {
      this.theme = this.theme === 'light' ? 'dark' : 'light'
      localStorage.setItem('landvision-theme', this.theme)
      document.documentElement.classList.toggle('dark', this.isDark)
    },
    applyTheme() {
      document.documentElement.classList.toggle('dark', this.isDark)
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed
    },
    setLayerVisible(name, visible) {
      this.layerVisibility[name] = visible
    },
    setLandUseFilter(landUse) {
      this.activeLandUse = landUse
    },
    setRegionFilter(region) {
      this.activeRegion = region
    },
    setAnalysisScope(scope) {
      this.analysisScope = scope
    },
    setProject(project) {
      this.currentProject = project
      this.currentProjectId = project?.id ?? null
    },
    setLinkedPatches(patchIds, scope, label) {
      this.linkedPatches = patchIds
      this.linkedScope = scope
      this.linkedScopeLabel = label
    },
    setLinkedFacilityTypes(types) {
      this.linkedFacilityTypes = types || []
    },
    bumpAnalysisVersion() {
      this.analysisVersion += 1
    },
    setSelection(selection) {
      this.selection = selection
    },
    markAllRead() {
      this.notifications.forEach((n) => (n.read = true))
    },
  },
})
