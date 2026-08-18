import { createRouter, createWebHistory } from 'vue-router'

// 5 个页面：Dashboard / 地块管理 / 规划审查 / 监测 / 报告
const routes = [
  {
    path: '/',
    redirect: '/dashboard',
  },
  {
    path: '/dashboard',
    name: 'dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { title: '数据驾驶舱', icon: 'Odometer' },
  },
  {
    path: '/parcels',
    name: 'parcels',
    component: () => import('../views/ParcelManagementView.vue'),
    meta: { title: '地块管理', icon: 'Grid' },
  },
  {
    path: '/transition',
    name: 'transition',
    component: () => import('../views/TransferMatrixView.vue'),
    meta: { title: '用地转移矩阵', icon: 'Sort' },
  },
  {
    path: '/suitability',
    name: 'suitability',
    component: () => import('../views/SuitabilityView.vue'),
    meta: { title: '适宜性评价', icon: 'Histogram' },
  },
  {
    path: '/accessibility',
    name: 'accessibility',
    component: () => import('../views/AccessibilityView.vue'),
    meta: { title: '设施可达性', icon: 'Position' },
  },
  {
    path: '/planning',
    name: 'planning',
    component: () => import('../views/PlanningCheckView.vue'),
    meta: { title: '三区三线体检', icon: 'Stamp' },
  },
  {
    path: '/report',
    name: 'report',
    component: () => import('../views/ReportView.vue'),
    meta: { title: '报告生成', icon: 'Document' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  document.title = to.meta.title
    ? `${to.meta.title} - LandVISION`
    : 'LandVISION'
})

export default router
