/**
 * 全局配色规范（地图 + 图表 + 图例统一引用，保证视觉一致性）
 *
 * 用地性质配色：GB/T 21010-2017《土地利用现状分类》一级类（12 大类）示意色，
 * 参照自然资源部制图惯例（黄系=农业、红橙=建设、绿系=生态、蓝系=水域）。
 *
 * 三区三线制图样式（v2.0 规范，刚性约束边界：颜色鲜明、线型易区分、无填充）：
 *   生态保护红线   #E53935（正红） 实线 solid  3px
 *   永久基本农田   #FFB300（金黄） 实线 solid  2.5px
 *   城镇开发边界   #1E88E5（亮蓝） 虚线 dashed 2px
 */

// 用地性质（12 大类）→ 主色
export const LAND_USE_COLORS = {
  耕地: '#F5E28D',
  园地: '#CDE08B',
  林地: '#5B9A57',
  草地: '#A8CF8D',
  商服用地: '#E4572E',
  工矿仓储用地: '#A58BB9',
  住宅用地: '#FFC24D',
  公共管理与公共服务用地: '#E8878F',
  特殊用地: '#8C6E63',
  交通运输用地: '#9AA4AD',
  水域及水利设施用地: '#4FA8D8',
  其他土地: '#C9B99A',
}

// 用地性质标准顺序（图例/图表按此排序）
export const LAND_USE_ORDER = [
  '耕地', '园地', '林地', '草地', '商服用地', '工矿仓储用地',
  '住宅用地', '公共管理与公共服务用地', '特殊用地', '交通运输用地',
  '水域及水利设施用地', '其他土地',
]

// POI 类型 → 主色
export const POI_COLORS = {
  交通: '#ef4444',
  商业: '#f97316',
  教育: '#06b6d4',
  医疗: '#ec4899',
  休闲: '#84cc16',
}

// 变化类型 → 主色（转移矩阵变化图斑）
export const CHANGE_COLORS = {
  新增建设: '#ef4444',
  拆除: '#64748b',
  植被变化: '#22c55e',
  水域变化: '#0ea5e9',
}

// ---------- 三区三线（v2.0 标准术语） ----------
export const ZONE_TYPE_LABELS = {
  permanent_basic_farmland: '永久基本农田',
  ecological_red_line: '生态保护红线',
  urban_growth_boundary: '城镇开发边界',
}

export const ZONE_TYPE_COLORS = {
  ecological_red_line: '#E53935',
  permanent_basic_farmland: '#FFB300',
  urban_growth_boundary: '#1E88E5',
}

// 三线线型样式：刚性约束边界，无填充、边界清晰（{color, width, dash}）
export const ZONE_TYPE_LINE_STYLES = {
  ecological_red_line: { color: '#E53935', width: 3, dash: [] },        // 正红 实线 3px
  permanent_basic_farmland: { color: '#FFB300', width: 2.5, dash: [] }, // 金黄 实线 2.5px
  urban_growth_boundary: { color: '#1E88E5', width: 2, dash: [8, 4] },  // 亮蓝 虚线 2px
}

export const ZONE_TYPE_ORDER = ['ecological_red_line', 'permanent_basic_farmland', 'urban_growth_boundary']

// 体检结论配色
export const VERDICT_COLORS = {
  冲突: '#dc2626',
  警告: '#f59e0b',
  提示: '#3b82f6',
  通过: '#16a34a',
}

// 图例元数据：{ label, color } 列表（LegendPanel / 图表共用）
export const LAND_USE_LEGEND = LAND_USE_ORDER.map((label) => ({ label, color: LAND_USE_COLORS[label] }))
export const POI_LEGEND = Object.entries(POI_COLORS).map(([label, color]) => ({ label, color }))
export const CHANGE_LEGEND = Object.entries(CHANGE_COLORS).map(([label, color]) => ({ label, color }))
export const ZONE_LEGEND = ZONE_TYPE_ORDER.map((code) => ({
  label: ZONE_TYPE_LABELS[code],
  color: ZONE_TYPE_COLORS[code],
  // v3.0：图例中预览线型（线宽 + 虚线样式）
  line: {
    width: ZONE_TYPE_LINE_STYLES[code].width,
    dash: ZONE_TYPE_LINE_STYLES[code].dash,
  },
}))
