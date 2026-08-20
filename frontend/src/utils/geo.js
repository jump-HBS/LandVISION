/**
 * 前端几何计算工具库（纯 JS，无第三方依赖）
 * 用于：坐标拾取换算、距离/面积测量、框选/圈选/多边形选择命中判断
 */

const R = 6371000 // 地球平均半径（米）

/** 两点间球面距离（米），Haversine 公式 */
export function haversineDistance(lng1, lat1, lng2, lat2) {
  const toRad = (d) => (d * Math.PI) / 180
  const dLat = toRad(lat2 - lat1)
  const dLng = toRad(lng2 - lng1)
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

/** 折线总长度（米），坐标格式 [[lng,lat], ...] */
export function lineLengthM(coords) {
  let total = 0
  for (let i = 1; i < coords.length; i++) {
    total += haversineDistance(coords[i - 1][0], coords[i - 1][1], coords[i][0], coords[i][1])
  }
  return total
}

/** 多边形面积（平方米），坐标格式 [[lng,lat], ...]（经纬度近似球面积） */
export function polygonAreaSqm(ring) {
  const n = ring.length
  if (n < 3) return 0
  let area = 0
  for (let i = 0; i < n; i++) {
    const [x1, y1] = ring[i]
    const [x2, y2] = ring[(i + 1) % n]
    area += (x2 - x1) * (2 + Math.sin((y1 * Math.PI) / 180) + Math.sin((y2 * Math.PI) / 180))
  }
  return Math.abs((area * R * R * Math.PI) / 360)
}

/** 射线法判断点是否在多边形内（点 [lng,lat]，多边形 [[lng,lat],...]） */
export function pointInPolygon(point, polygon) {
  const [x, y] = point
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) {
      inside = !inside
    }
  }
  return inside
}

/** 点是否在圆内（中心 [lng,lat]，半径米） */
export function pointInCircle(point, center, radiusM) {
  return haversineDistance(point[0], point[1], center[0], center[1]) <= radiusM
}

/** 点是否在矩形内（bbox: [[minx,miny],[maxx,maxy]]） */
export function pointInBBox(point, bbox) {
  const [x, y] = point
  return x >= bbox[0][0] && x <= bbox[1][0] && y >= bbox[0][1] && y <= bbox[1][1]
}

/** 多边形的包围盒 bbox */
export function ringBBox(ring) {
  const xs = ring.map((p) => p[0])
  const ys = ring.map((p) => p[1])
  return [
    [Math.min(...xs), Math.min(...ys)],
    [Math.max(...xs), Math.max(...ys)],
  ]
}

/** GeoJSON 几何的质心（面/线取坐标平均，教学够用） */
export function geometryCentroid(geometry) {
  if (!geometry) return null
  const coords = geometry.coordinates.flat(Infinity)
  const pts = []
  for (let i = 0; i + 1 < coords.length; i += 2) pts.push([coords[i], coords[i + 1]])
  if (!pts.length) return null
  const sum = pts.reduce((acc, p) => [acc[0] + p[0], acc[1] + p[1]], [0, 0])
  return [sum[0] / pts.length, sum[1] / pts.length]
}

/** 判断要素（以质心）是否命中选择形状 */
export function featureInShape(feature, shape) {
  const centroid = geometryCentroid(feature.geometry)
  if (!centroid) return false
  switch (shape.type) {
    case 'box':
      return pointInBBox(centroid, shape.bbox)
    case 'circle':
      return pointInCircle(centroid, shape.center, shape.radiusM)
    case 'polygon':
      return pointInPolygon(centroid, shape.ring)
    default:
      return false
  }
}

/** v4.0.3：防抖工具（地图 moveend 缩放/平移风暴 → 合并为一次加载） */
export function debounce(fn, wait = 400) {
  let timer = null
  return function debounced(...args) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn.apply(this, args)
    }, wait)
  }
}
