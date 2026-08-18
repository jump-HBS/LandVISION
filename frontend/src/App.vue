<template>
  <el-container class="app-layout">
    <!-- 侧边导航（可折叠 + 分组 + 推荐流程编号） -->
    <el-aside :width="ui.sidebarCollapsed ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <el-icon :size="26" color="#2e86ab"><LocationFilled /></el-icon>
        <span v-show="!ui.sidebarCollapsed">LandVISION</span>
      </div>
      <el-menu
        :default-active="route.path"
        :collapse="ui.sidebarCollapsed"
        router
        background-color="#0f1b2d"
        text-color="rgba(255,255,255,.68)"
        active-text-color="#4fc3f7"
        class="app-menu"
      >
        <template v-for="group in menuGroups" :key="group.title">
          <div v-if="!ui.sidebarCollapsed" class="menu-group-title">{{ group.title }}</div>
          <el-menu-item v-for="m in group.items" :key="m.path" :index="m.path">
            <el-icon><component :is="m.icon" /></el-icon>
            <template #title>
              <span class="menu-title">
                <span v-if="m.step" class="step-badge">{{ m.step }}</span>
                {{ m.title }}
              </span>
            </template>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶栏：折叠 + 项目选择 + 全局搜索 + 通知 + 主题 + 用户 + 帮助 -->
      <el-header class="app-header">
        <div class="header-left">
          <el-icon class="collapse-btn" :size="20" @click="ui.toggleSidebar()">
            <Fold v-if="!ui.sidebarCollapsed" />
            <Expand v-else />
          </el-icon>
          <div class="header-title">国土空间数据管理与智能分析可视化平台</div>
        </div>

        <div class="header-right">
          <!-- v2.0：分析项目选择 / 新建入口 -->
          <el-select
            v-model="selectedProjectId"
            placeholder="选择分析项目（或新建）"
            size="small"
            style="width: 200px"
            clearable
            @change="onProjectChange"
          >
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-button size="small" type="primary" plain @click="projectDialogVisible = true">
            <el-icon :size="13"><Plus /></el-icon>&nbsp;新建项目
          </el-button>

          <!-- 全局搜索：地块名称/编号 -->
          <el-select
            v-model="searchValue"
            filterable
            remote
            clearable
            :remote-method="searchParcels"
            :loading="searchLoading"
            placeholder="全局搜索地块…"
            class="global-search"
            @change="onSearchSelect"
          >
            <el-option
              v-for="p in searchResults"
              :key="p.id"
              :label="`${p.parcel_code} · ${p.name}（${p.land_use}）`"
              :value="p.id"
            />
          </el-select>

          <!-- 消息通知 -->
          <el-popover placement="bottom-end" width="300" trigger="click">
            <template #reference>
              <el-badge :value="ui.unreadCount" :hidden="!ui.unreadCount" class="header-badge">
                <el-icon :size="18" class="header-icon"><Bell /></el-icon>
              </el-badge>
            </template>
            <div class="notice-head">
              <b>消息通知</b>
              <el-button text size="small" type="primary" @click="ui.markAllRead()">全部已读</el-button>
            </div>
            <div v-for="n in ui.notifications" :key="n.id" class="notice-item">
              <el-tag size="small" :type="n.type === 'success' ? 'success' : n.type === 'warning' ? 'warning' : 'info'">
                {{ n.title }}
              </el-tag>
              <div class="notice-desc">{{ n.desc }}</div>
              <div class="notice-time">{{ n.time }}</div>
            </div>
          </el-popover>

          <!-- 深浅主题 -->
          <el-tooltip :content="ui.isDark ? '切换浅色主题' : '切换深色主题'" placement="bottom">
            <el-icon :size="18" class="header-icon" @click="ui.toggleTheme()">
              <Sunny v-if="ui.isDark" />
              <Moon v-else />
            </el-icon>
          </el-tooltip>

          <!-- 帮助 -->
          <el-tooltip content="帮助文档（docs/07-启动调试指南）" placement="bottom">
            <a class="header-icon" href="https://github.com/" target="_blank" style="display:flex">
              <el-icon :size="18"><QuestionFilled /></el-icon>
            </a>
          </el-tooltip>

          <!-- 用户中心 -->
          <el-dropdown>
            <span class="user-entry">
              <el-avatar :size="28" style="background:#2e86ab">管</el-avatar>
              <span class="user-name">管理员</span>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item disabled>个人中心（演示）</el-dropdown-item>
                <el-dropdown-item disabled>账号设置（演示）</el-dropdown-item>
                <el-dropdown-item divided disabled>退出登录（演示）</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <!-- 内容区 -->
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 新建项目对话框 -->
    <el-dialog v-model="projectDialogVisible" title="新建分析项目" width="480px">
      <el-form :model="projectForm" label-width="90px">
        <el-form-item label="项目名称">
          <el-input v-model="projectForm.name" placeholder="如：洪山区城市更新分析" />
        </el-form-item>
        <el-form-item label="基期年份">
          <el-input-number v-model="projectForm.base_year" :min="1990" :max="2100" />
        </el-form-item>
        <el-form-item label="末期年份">
          <el-input-number v-model="projectForm.current_year" :min="1990" :max="2100" />
        </el-form-item>
        <el-alert type="info" :closable="false"
          title="分析范围（可选）稍后可在数据驾驶舱中划定；项目创建后，各分析模块自动继承项目范围与期次设置。" />
      </el-form>
      <template #footer>
        <el-button @click="projectDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="projectCreating" @click="createProjectNow">创建</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUiStore } from './stores/ui'
import { getParcels, getProjects, createProject } from './api'

const route = useRoute()
const router = useRouter()
const ui = useUiStore()

// 菜单分组：总览 / 数据管理 / 分析决策（推荐流程编号 1~5）/ 输出
const menuGroups = [
  { title: '总览', items: [{ path: '/dashboard', title: '数据驾驶舱', icon: 'Odometer' }] },
  { title: '数据管理', items: [{ path: '/parcels', title: '地块管理', icon: 'Grid', step: 1 }] },
  {
    title: '分析决策（推荐流程 2→5）',
    items: [
      { path: '/transition', title: '用地转移矩阵', icon: 'Sort', step: 2 },
      { path: '/planning', title: '三区三线体检', icon: 'Stamp', step: 3 },
      { path: '/suitability', title: '适宜性评价', icon: 'Histogram', step: 4 },
      { path: '/accessibility', title: '设施可达性', icon: 'Position', step: 5 },
    ],
  },
  { title: '输出', items: [{ path: '/report', title: '报告生成', icon: 'Document', step: 6 }] },
]

// ---------- v2.0 分析项目 ----------
const projects = ref([])
const selectedProjectId = ref(null)
const projectDialogVisible = ref(false)
const projectCreating = ref(false)
const projectForm = ref({ name: '', base_year: 2020, current_year: 2026 })

async function loadProjects() {
  projects.value = await getProjects()
  if (ui.currentProjectId) {
    selectedProjectId.value = projects.value.some((p) => p.id === ui.currentProjectId)
      ? ui.currentProjectId : null
  }
}

function onProjectChange(projectId) {
  const project = projectId ? projects.value.find((p) => p.id === projectId) : null
  ui.setProject(project)
  ElMessage.success(project ? `已切换到项目「${project.name}」` : '已退出项目上下文（全量数据）')
}

async function createProjectNow() {
  if (!projectForm.value.name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  projectCreating.value = true
  try {
    const project = await createProject({ ...projectForm.value, name: projectForm.value.name.trim() })
    await loadProjects()
    selectedProjectId.value = project.id
    ui.setProject(project)
    projectDialogVisible.value = false
    projectForm.value = { name: '', base_year: 2020, current_year: 2026 }
    ElMessage.success(`项目「${project.name}」已创建，可到驾驶舱划定分析范围`)
  } catch (e) {
    ElMessage.error('创建失败：' + (e?.message || '未知原因'))
  } finally {
    projectCreating.value = false
  }
}

onMounted(loadProjects)

// 全局搜索
const searchValue = ref(null)
const searchResults = ref([])
const searchLoading = ref(false)

async function searchParcels(keyword) {
  if (!keyword) return
  searchLoading.value = true
  try {
    const data = await getParcels({ q: keyword, page: 1, page_size: 8 })
    searchResults.value = data.items
  } finally {
    searchLoading.value = false
  }
}

function onSearchSelect(parcelId) {
  if (!parcelId) return
  searchValue.value = null
  router.push({ path: '/parcels', query: { highlight: parcelId } })
}
</script>

<style scoped>
.app-layout {
  height: 100%;
}
.app-aside {
  background: #0f1b2d;
  transition: width 0.2s ease;
  overflow: hidden;
}
.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 1px;
  white-space: nowrap;
}
.app-menu {
  border-right: none;
  height: calc(100% - 60px);
  overflow-y: auto;
}
.menu-group-title {
  padding: 14px 20px 4px;
  font-size: 11px;
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 2px;
}
.menu-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.step-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: rgba(79, 195, 247, 0.18);
  color: #4fc3f7;
  font-size: 11px;
  line-height: 1;
}

.app-header {
  background: var(--lv-surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  z-index: 5;
  border-bottom: 1px solid var(--lv-border);
}
.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.collapse-btn {
  cursor: pointer;
  color: var(--lv-text-secondary);
}
.collapse-btn:hover {
  color: var(--lv-primary);
}
.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--lv-text);
}
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
}
.global-search {
  width: 220px;
}
.header-icon {
  cursor: pointer;
  color: var(--lv-text-secondary);
  display: flex;
  align-items: center;
}
.header-icon:hover {
  color: var(--lv-primary);
}
.header-badge {
  display: flex;
  align-items: center;
}
.user-entry {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: var(--lv-text);
  outline: none;
}
.user-name {
  font-size: 13px;
}
.notice-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--lv-border);
  margin-bottom: 8px;
}
.notice-item {
  padding: 8px 0;
  border-bottom: 1px dashed var(--lv-border);
}
.notice-desc {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-top: 4px;
}
.notice-time {
  font-size: 11px;
  color: var(--lv-text-tertiary);
  margin-top: 2px;
}

.app-main {
  padding: 16px;
  overflow-y: auto;
  background: var(--lv-bg);
}
</style>
