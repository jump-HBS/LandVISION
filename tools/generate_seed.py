# -*- coding: utf-8 -*-
"""
tools/generate_seed.py —— LandVISION 种子数据生成器（单一数据源）

从本文件定义的"演示区数据集" + tools/assets/china_provinces.json（省级行政区）
同时生成三个产物，保证两种运行模式数据一致：
  1. database/02_seed_data.sql        → 业务演示数据（PostgreSQL + PostGIS 入库）
  2. database/03_regions.sql          → 中国省级行政区数据（入库）
  3. backend/app/demo_data.py         → 后端 Demo 模式（内存数据 + shapely）

用法：
  cd C:\\landvision-project
  venv\\Scripts\\python.exe tools\\generate_seed.py

修改数据：只改本文件的 *_SPECS，然后重新运行即可重新生成全部产物。
用地性质遵循《国土空间调查规划用地用海分类（试行）》/ GB/T 21010-2017 一级类。
"""
import json
import math
import os

# ---------------------------------------------------------------------------
# 12 大类用地（GB/T 21010-2017 一级类）
# 值：(容积率上限, 建筑限高米)；非建设用地两类参数为 None
# 配色为参照自然资源制图惯例的示意色
# ---------------------------------------------------------------------------
LAND_USE_TYPES = [
    ("耕地",                          None, None),
    ("园地",                          None, None),
    ("林地",                          None, None),
    ("草地",                          None, None),
    ("商服用地",                      4.0,  120),
    ("工矿仓储用地",                  1.5,  30),
    ("住宅用地",                      2.5,  80),
    ("公共管理与公共服务用地",         2.0,  40),
    ("特殊用地",                      1.2,  24),
    ("交通运输用地",                  0.5,  20),
    ("水域及水利设施用地",             None, None),
    ("其他土地",                      0.5,  12),
]

# ---------------------------------------------------------------------------
# 演示区设定：武汉市洪山区（区划代码 420111），中心约 (114.340, 30.500)
# ---------------------------------------------------------------------------

DEMO_REGION_CODE = "420111"
DEMO_REGION_NAME = "武汉市洪山区"
DEMO_CENTER = (114.340, 30.500)

LON_SCALE = 111320 * math.cos(math.radians(30.5))   # 每度经度≈米（武汉纬度）
LAT_SCALE = 110540                                   # 每度纬度≈米

PARCEL_HALF_W = 0.0035
PARCEL_HALF_H = 0.0028
JITTER = [(-0.0003, -0.0002), (0.0002, -0.0003), (0.0003, 0.0002), (-0.0002, 0.0003)]

# 地块：(编号, 名称, 用地大类, 建档日期, 中心经度, 中心纬度)
# 10 个地块覆盖 10 个一级类；建档日期跨月分布，支持"本月新增/环比"统计
PARCEL_SPECS = [
    ("A-01", "南湖耕地示范片",   "耕地",                     "2026-01-12", 114.3310, 30.5070),
    ("A-02", "光谷商务中心",     "商服用地",                 "2026-02-03", 114.3405, 30.5070),
    ("A-03", "滨江住宅区",       "住宅用地",                 "2026-02-25", 114.3500, 30.5070),
    ("B-01", "高新制造园",       "工矿仓储用地",             "2026-03-18", 114.3310, 30.4990),
    ("B-02", "市民服务中心",     "公共管理与公共服务用地",   "2026-04-09", 114.3405, 30.4990),
    ("B-03", "南湖生态园",       "园地",                     "2026-05-21", 114.3500, 30.4990),
    ("C-01", "城市森林公园",     "林地",                     "2026-06-30", 114.3310, 30.4910),
    ("C-02", "长江生态绿地",     "草地",                     "2026-07-15", 114.3405, 30.4910),
    ("C-03", "南站交通枢纽",     "交通运输用地",             "2026-08-05", 114.3500, 30.4910),
    ("D-01", "东湖水域保护区",   "水域及水利设施用地",       "2026-08-12", 114.3360, 30.5150),
]

# 地块大类 → (容积率, 限高) 查找表
LAND_USE_ATTRS = {name: (far, height) for name, far, height in LAND_USE_TYPES}

# POI：(名称, 类型, 经度, 纬度)
POI_SPECS = [
    ("地铁站A",     "交通", 114.3390, 30.5045),
    ("地铁站B",     "交通", 114.3490, 30.4960),
    ("公交枢纽",    "交通", 114.3460, 30.5110),
    ("高铁站",      "交通", 114.3530, 30.4890),
    ("万象城",      "商业", 114.3415, 30.5055),
    ("银泰中心",    "商业", 114.3460, 30.5035),
    ("生鲜超市",    "商业", 114.3495, 30.5005),
    ("家居城",      "商业", 114.3385, 30.4945),
    ("第一中学",    "教育", 114.3455, 30.5105),
    ("实验小学",    "教育", 114.3350, 30.5000),
    ("职业技术学院", "教育", 114.3520, 30.4935),
    ("市人民医院",  "医疗", 114.3435, 30.5005),
    ("社区诊所",    "医疗", 114.3530, 30.5075),
    ("妇幼保健院",  "医疗", 114.3365, 30.5095),
    ("中央公园",    "休闲", 114.3400, 30.4985),
    ("体育中心",    "休闲", 114.3490, 30.5060),
    ("滨江绿道",    "休闲", 114.3540, 30.5020),
    ("文化馆",      "休闲", 114.3380, 30.5015),
    ("图书馆",      "休闲", 114.3475, 30.5025),
    ("电影院",      "休闲", 114.3455, 30.5075),
]

# 规划控制区：(名称, 类型, 级别, 描述, 顶点列表[经,纬])
ZONE_SPECS = [
    ("长江沿岸生态保护红线", "生态保护红线", "国家级",
     "禁止任何开发建设活动，严格管控",
     [(114.3280, 30.4820), (114.3580, 30.4820), (114.3580, 30.4900),
      (114.3470, 30.4910), (114.3330, 30.4905), (114.3280, 30.4870)]),
    ("南部基本农田保护区", "永久基本农田", "国家级",
     "严禁非农化、非粮化",
     [(114.3520, 30.4830), (114.3640, 30.4830), (114.3640, 30.4930), (114.3520, 30.4930)]),
    ("洪山区城镇开发边界", "城镇开发边界", "市级",
     "开发建设活动应在边界内进行，界外需专题论证",
     [(114.3260, 30.4840), (114.3600, 30.4840), (114.3600, 30.5140), (114.3260, 30.5140)]),
    ("老街历史文化保护区", "历史文化保护区", "省级",
     "新建改建需符合风貌管控要求",
     [(114.3395, 30.5005), (114.3435, 30.5005), (114.3435, 30.5030), (114.3395, 30.5030)]),
]

# 变化监测记录：(关联地块编号, 变化类型, 置信度, 日期, 左下角, 右上角)
# 置信度 < 80 视为"待核实"
CHANGE_SPECS = [
    ("A-02", "新增建设", 92, "2026-03-15", (114.3425, 30.5040), (114.3450, 30.5065)),
    ("B-01", "拆除",     87, "2026-04-02", (114.3330, 30.4960), (114.3355, 30.4980)),
    ("C-01", "植被变化", 78, "2026-04-20", (114.3335, 30.4880), (114.3360, 30.4900)),
    ("D-01", "新增建设", 95, "2026-05-11", (114.3370, 30.5130), (114.3400, 30.5150)),
    ("C-02", "水域变化", 81, "2026-05-28", (114.3425, 30.4895), (114.3450, 30.4910)),
    ("B-03", "新增建设", 89, "2026-06-10", (114.3510, 30.4960), (114.3535, 30.4980)),
    ("B-02", "新增建设", 62, "2026-08-01", (114.3425, 30.4980), (114.3450, 30.5000)),
]

# ---------------------------------------------------------------------------
# 省级行政区（tools/assets/china_provinces.json，DataV 公开数据）
# ---------------------------------------------------------------------------

PROVINCES_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "assets", "china_provinces.json")


def load_provinces():
    """读取省级行政区 GeoJSON（过滤九段线占位要素）。"""
    with open(PROVINCES_JSON, encoding="utf-8") as f:
        fc = json.load(f)
    regions = []
    for feat in fc["features"]:
        props = feat["properties"]
        code, name = props.get("adcode"), (props.get("name") or "").strip()
        if not name or not str(code).isdigit() or not str(code).endswith("0000"):
            continue  # 过滤九段线(100000_JD)等非省级要素
        geom = feat["geometry"]
        # Polygon → MultiPolygon 统一
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        regions.append({
            "code": str(code),
            "name": name,
            "level": "province",
            "parent_code": "100000",
            "geometry": geom,
        })
    return regions


# ---------------------------------------------------------------------------
# 数据集构建
# ---------------------------------------------------------------------------

def _polygon_ring(cx, cy, half_w, half_h, jitter):
    offsets = [(-half_w, -half_h), (half_w, -half_h), (half_w, half_h), (-half_w, half_h)]
    ring = []
    for (ox, oy), (jx, jy) in zip(offsets, jitter):
        ring.append([round(cx + ox + jx, 6), round(cy + oy + jy, 6)])
    ring.append(ring[0])
    return ring


def _polygon_area_sqm(ring):
    xs = [p[0] * LON_SCALE for p in ring]
    ys = [p[1] * LAT_SCALE for p in ring]
    area = 0.0
    for i in range(len(ring) - 1):
        area += xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
    return abs(area) / 2.0


def build_dataset():
    parcels = []
    for i, (code, name, land_use, created, cx, cy) in enumerate(PARCEL_SPECS, start=1):
        ring = _polygon_ring(cx, cy, PARCEL_HALF_W, PARCEL_HALF_H, JITTER)
        far, height = LAND_USE_ATTRS.get(land_use, (None, None))
        parcels.append({
            "id": i,
            "parcel_code": code,
            "name": name,
            "land_use": land_use,
            "district": DEMO_REGION_NAME,
            "region_code": DEMO_REGION_CODE,
            "area_sqm": round(_polygon_area_sqm(ring), 2),
            "far_limit": far,
            "height_limit": height,
            "created_at": created,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    pois = []
    for i, (name, ptype, lon, lat) in enumerate(POI_SPECS, start=1):
        pois.append({
            "id": i,
            "name": name,
            "poi_type": ptype,
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })

    zones = []
    for i, (name, ztype, level, desc, ring) in enumerate(ZONE_SPECS, start=1):
        ring_closed = [[float(x), float(y)] for (x, y) in ring] + [[float(ring[0][0]), float(ring[0][1])]]
        zones.append({
            "id": i,
            "zone_name": name,
            "zone_type": ztype,
            "zone_level": level,
            "control_desc": desc,
            "area_sqm": round(_polygon_area_sqm(ring_closed), 2),
            "geometry": {"type": "Polygon", "coordinates": [ring_closed]},
        })

    changes = []
    for i, (code, ctype, conf, date, lo, hi) in enumerate(CHANGE_SPECS, start=1):
        ring = [[lo[0], lo[1]], [hi[0], lo[1]], [hi[0], hi[1]], [lo[0], hi[1]], [lo[0], lo[1]]]
        changes.append({
            "id": i,
            "parcel_code": code,
            "change_type": ctype,
            "area_sqm": round(_polygon_area_sqm(ring), 2),
            "confidence": conf,
            "detected_date": date,
            "geometry": {"type": "Polygon", "coordinates": [ring]},
        })

    regions = load_provinces()
    return parcels, pois, zones, changes, regions


# ---------------------------------------------------------------------------
# SQL 产物
# ---------------------------------------------------------------------------

def _wkt(geom):
    if geom["type"] == "Point":
        lon, lat = geom["coordinates"]
        return f"POINT({lon} {lat})"
    if geom["type"] == "Polygon":
        ring = geom["coordinates"][0]
        pts = ", ".join(f"{p[0]} {p[1]}" for p in ring)
        return f"POLYGON(({pts}))"
    if geom["type"] == "MultiPolygon":
        polys = []
        for rings in geom["coordinates"]:
            outer = ", ".join(f"{p[0]} {p[1]}" for p in rings[0])
            polys.append(f"(({outer}))")
        return f"MULTIPOLYGON({', '.join(polys)})"
    raise ValueError(f"不支持的几何类型 {geom['type']}")


def render_business_sql(parcels, pois, zones, changes):
    lines = [
        "-- ===================================================================",
        "-- LandVISION 业务演示数据（由 tools/generate_seed.py 自动生成）",
        "-- 演示区：武汉市洪山区（420111）；用地性质遵循 GB/T 21010-2017 一级类",
        "-- 执行顺序：00_create_database.sql → 01_init_schema.sql → 03_regions.sql → 本文件",
        "-- ===================================================================",
        "", "BEGIN;", "",
        "DELETE FROM change_records;", "DELETE FROM planning_control;",
        "DELETE FROM pois;", "DELETE FROM parcels;", "",
    ]

    lines.append("-- ---------- 10 个示例地块（12 大类用地覆盖 10 类） ----------")
    for p in parcels:
        lines.append(
            "INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, "
            "far_limit, height_limit, created_at, geom) VALUES "
            f"('{p['parcel_code']}', '{p['name']}', '{p['land_use']}', '{p['district']}', "
            f"'{p['region_code']}', {p['area_sqm']}, "
            f"{p['far_limit'] if p['far_limit'] is not None else 'NULL'}, "
            f"{p['height_limit'] if p['height_limit'] is not None else 'NULL'}, "
            f"'{p['created_at']}', ST_GeomFromText('{_wkt(p['geometry'])}', 4326));"
        )
    lines.append("")
    lines.append("-- ---------- 20 个兴趣点 ----------")
    for poi in pois:
        lines.append(
            "INSERT INTO pois (name, poi_type, geom) VALUES "
            f"('{poi['name']}', '{poi['poi_type']}', ST_GeomFromText('{_wkt(poi['geometry'])}', 4326));"
        )
    lines.append("")
    lines.append("-- ---------- 4 个规划控制区 ----------")
    for z in zones:
        lines.append(
            "INSERT INTO planning_control (zone_name, zone_type, zone_level, control_desc, geom) VALUES "
            f"('{z['zone_name']}', '{z['zone_type']}', '{z['zone_level']}', '{z['control_desc']}', "
            f"ST_GeomFromText('{_wkt(z['geometry'])}', 4326));"
        )
    lines.append("")
    lines.append("-- ---------- 7 条变化监测记录 ----------")
    for c in changes:
        lines.append(
            "INSERT INTO change_records (parcel_code, change_type, area_sqm, confidence, detected_date, geom) VALUES "
            f"('{c['parcel_code']}', '{c['change_type']}', {c['area_sqm']}, {c['confidence']}, "
            f"'{c['detected_date']}', ST_GeomFromText('{_wkt(c['geometry'])}', 4326));"
        )
    lines += ["", "COMMIT;", ""]
    return "\n".join(lines)


def render_regions_sql(regions):
    lines = [
        "-- ===================================================================",
        "-- 中国省级行政区数据（由 tools/generate_seed.py 自动生成）",
        "-- 数据源：阿里 DataV 公开 GeoJSON（geo.datav.aliyun.com）",
        "-- 坐标系：WGS84（EPSG:4326）",
        "-- ===================================================================",
        "", "BEGIN;", "",
        "DELETE FROM regions WHERE level = 'province';", "",
    ]
    for r in regions:
        lines.append(
            "INSERT INTO regions (code, name, level, parent_code, geom) VALUES "
            f"('{r['code']}', '{r['name']}', 'province', '{r['parent_code']}', "
            f"ST_GeomFromText('{_wkt(r['geometry'])}', 4326));"
        )
    lines += ["", "COMMIT;", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Python 产物（backend/app/demo_data.py）
# ---------------------------------------------------------------------------

DEMO_PY_HEADER = '''# -*- coding: utf-8 -*-
"""
Demo 模式内存数据集（由 tools/generate_seed.py 自动生成，请勿手工修改数据部分）。

与 database/02_seed_data.sql、03_regions.sql 一一对应。
坐标系：WGS84（EPSG:4326），geometry 为 GeoJSON 字典。
用地性质遵循 GB/T 21010-2017 一级类（12 大类）。
"""
from shapely.geometry import shape as _shapely_shape

LAND_USE_TYPES = [
    "耕地", "园地", "林地", "草地", "商服用地", "工矿仓储用地", "住宅用地",
    "公共管理与公共服务用地", "特殊用地", "交通运输用地", "水域及水利设施用地", "其他土地",
]

DEMO_REGION_CODE = "420111"
DEMO_REGION_NAME = "武汉市洪山区"

'''

DEMO_PY_FOOTER = '''

# ---------------------------------------------------------------------------
# 便捷访问函数（供 services 层使用）
# ---------------------------------------------------------------------------

def _fc(features):
    return {"type": "FeatureCollection", "features": features}


def parcel_features():
    return [
        {"type": "Feature", "geometry": p["geometry"], "properties": {
            "id": p["id"], "parcel_code": p["parcel_code"], "name": p["name"],
            "land_use": p["land_use"], "district": p["district"],
            "region_code": p["region_code"], "area_sqm": p["area_sqm"],
            "far_limit": p["far_limit"], "height_limit": p["height_limit"],
            "created_at": p["created_at"],
        }} for p in PARCELS
    ]


def poi_features():
    return [
        {"type": "Feature", "geometry": p["geometry"], "properties": {
            "id": p["id"], "name": p["name"], "poi_type": p["poi_type"],
        }} for p in POIS
    ]


def zone_features():
    return [
        {"type": "Feature", "geometry": z["geometry"], "properties": {
            "id": z["id"], "zone_name": z["zone_name"], "zone_type": z["zone_type"],
            "zone_level": z["zone_level"], "control_desc": z["control_desc"],
            "area_sqm": z["area_sqm"],
        }} for z in PLANNING_ZONES
    ]


def change_features():
    return [
        {"type": "Feature", "geometry": c["geometry"], "properties": {
            "id": c["id"], "parcel_code": c["parcel_code"], "change_type": c["change_type"],
            "area_sqm": c["area_sqm"], "confidence": c["confidence"],
            "detected_date": c["detected_date"],
        }} for c in CHANGE_RECORDS
    ]


def region_features():
    return [
        {"type": "Feature", "geometry": r["geometry"], "properties": {
            "code": r["code"], "name": r["name"], "level": r["level"],
            "parent_code": r["parent_code"],
        }} for r in REGIONS
    ]


def parcels_geojson():
    return _fc(parcel_features())


def pois_geojson():
    return _fc(poi_features())


def zones_geojson():
    return _fc(zone_features())


def changes_geojson():
    return _fc(change_features())


def regions_geojson():
    return _fc(region_features())


def shapely_geom(geojson):
    """GeoJSON 字典 → shapely 几何对象（Demo 模式空间运算核心）。"""
    return _shapely_shape(geojson)


def next_id(items):
    return max((it["id"] for it in items), default=0) + 1
'''


def render_demo_py(parcels, pois, zones, changes, regions):
    def fmt_list(name, items):
        body = f"{name} = [\n"
        for it in items:
            body += "    " + repr(it) + ",\n"
        body += "]\n"
        return body

    parts = [DEMO_PY_HEADER]
    parts.append(fmt_list("PARCELS", parcels))
    parts.append("")
    parts.append(fmt_list("POIS", pois))
    parts.append("")
    parts.append(fmt_list("PLANNING_ZONES", zones))
    parts.append("")
    parts.append(fmt_list("CHANGE_RECORDS", changes))
    parts.append("")
    parts.append(fmt_list("REGIONS", regions))
    parts.append(DEMO_PY_FOOTER)
    return "".join(parts)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parcels, pois, zones, changes, regions = build_dataset()

    out_sql = os.path.join(root, "database", "02_seed_data.sql")
    with open(out_sql, "w", encoding="utf-8") as f:
        f.write(render_business_sql(parcels, pois, zones, changes))

    out_reg = os.path.join(root, "database", "03_regions.sql")
    with open(out_reg, "w", encoding="utf-8") as f:
        f.write(render_regions_sql(regions))

    out_py = os.path.join(root, "backend", "app", "demo_data.py")
    with open(out_py, "w", encoding="utf-8") as f:
        f.write(render_demo_py(parcels, pois, zones, changes, regions))

    print(f"[OK] {os.path.basename(out_sql)}  {os.path.getsize(out_sql)} bytes")
    print(f"[OK] {os.path.basename(out_reg)}  {os.path.getsize(out_reg)} bytes（省级行政区 {len(regions)} 个）")
    print(f"[OK] {os.path.basename(out_py)}  {os.path.getsize(out_py)} bytes")


if __name__ == "__main__":
    main()
