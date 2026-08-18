import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'
import drag from './directives/drag'
import { useUiStore } from './stores/ui'
import './styles/main.css'

const app = createApp(App)

// 全局注册拖拽指令（地图浮动组件可拖动）
app.directive('drag', drag)

// 全局注册 Element Plus 图标（供 <component :is="iconName"> 使用）
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })

// 应用持久化主题
useUiStore().applyTheme()

app.mount('#app')
