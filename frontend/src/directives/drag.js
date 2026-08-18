/**
 * v-drag —— 通用拖拽指令（用于地图上的浮动组件）
 *
 * 用法：
 *   <div v-drag>...</div>
 *   元素需为 position: absolute/fixed；拖拽通过 transform: translate 实现，
 *   与 CSS 的 right/top 定位叠加，不破坏响应式布局。
 *
 * 特性：
 *  - 移动超过 5px 判定为拖拽，否则保持正常点击（按钮可正常使用）
 *  - 拖拽结束吞掉本次 click，避免"拖动后误触发按钮"
 *  - 面板内输入控件（input/select/upload）不启动拖拽
 */
export default {
  mounted(el) {
    let startX = 0
    let startY = 0
    let baseDX = 0
    let baseDY = 0
    let moved = false

    const getOffsets = () => {
      const m = (el.style.transform || '').match(
        /translate\(\s*([-\d.]+)px,\s*([-\d.]+)px\)/
      )
      return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0]
    }

    const onMove = (e) => {
      const dx = e.clientX - startX
      const dy = e.clientY - startY
      if (!moved && Math.abs(dx) + Math.abs(dy) > 5) {
        moved = true
        el.style.transition = 'none'
      }
      if (moved) {
        el.style.transform = `translate(${baseDX + dx}px, ${baseDY + dy}px)`
      }
    }

    const onUp = () => {
      document.removeEventListener('mousemove', onMove)
      if (moved) {
        // 吞掉拖拽结束触发的 click，避免误触发按钮
        const swallow = (ev) => {
          ev.stopPropagation()
          ev.preventDefault()
          el.removeEventListener('click', swallow, true)
        }
        el.addEventListener('click', swallow, true)
        setTimeout(() => el.removeEventListener('click', swallow, true), 0)
        moved = false
      }
    }

    const onDown = (e) => {
      if (e.button !== 0) return
      // 面板内的交互控件不启动拖拽
      if (e.target.closest('input, textarea, .el-select, .el-upload, .el-checkbox, .el-radio, button.rs-icon')) {
        return
      }
      startX = e.clientX
      startY = e.clientY
      const [dx, dy] = getOffsets()
      baseDX = dx
      baseDY = dy
      moved = false
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp, { once: true })
    }

    el.addEventListener('mousedown', onDown)
    el.style.userSelect = 'none'
    el.style.touchAction = 'none'
    el.style.cursor = 'grab'

    el._dragCleanup = () => {
      el.removeEventListener('mousedown', onDown)
      document.removeEventListener('mousemove', onMove)
    }
  },
  unmounted(el) {
    if (el._dragCleanup) el._dragCleanup()
  },
}
