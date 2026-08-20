import axios from 'axios'
import { ElMessage } from 'element-plus'

/**
 * Axios 实例封装：
 *  1. baseURL 取自环境变量（开发 /api → Vite 代理 → 后端）
 *  2. 响应拦截器：直接返回 data；统一错误提示（适配后端统一错误码格式）
 *  3. 预留请求拦截器位置（后续加 Token 鉴权只改这里）
 */
const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api',
  timeout: 15000,
})

// ---------- 请求拦截器：预留 Token 注入位 ----------
request.interceptors.request.use(
  (config) => {
    // const token = localStorage.getItem('token')
    // if (token) config.headers.Authorization = `Bearer ${token}`
    return config
  },
  (error) => Promise.reject(error)
)

// ---------- 响应拦截器：统一取 data + 统一报错 ----------
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    // v4.0.3：取消的请求（地图快速缩放时中止上一批加载）不再弹错误提示
    if (axios.isCancel(error)) return Promise.reject(error)
    const body = error.response?.data
    let message = '网络请求失败，请检查后端是否已启动'
    if (error.code === 'ECONNABORTED' || !error.response) {
      message = '请求超时或后端繁忙（地图数据量大时请稍候片刻重试）'
    } else if (body && typeof body === 'object') {
      // 后端统一错误格式 {code, message, detail}
      message = body.message || (typeof body.detail === 'string' ? body.detail : '') || message
    } else if (typeof body === 'string') {
      message = body
    }
    // 避免重复提示
    if (!error.config?._silent) {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  }
)

export default request
