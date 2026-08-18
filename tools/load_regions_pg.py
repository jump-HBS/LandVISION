# -*- coding: utf-8 -*-
"""
tools/load_regions_pg.py —— 中国行政区划数据一键导入 PostgreSQL

导入内容：
  1. 省级 34 个（tools/assets/china_provinces.json，含边界几何）
  2. 地级市 348 个（database/05_cities_counties.json，含边界几何——DataV 省级下级缓存提取）
  3. 县域 2891 个（database/05_cities_counties.json，含边界几何）

前置条件：
  * PostgreSQL 16 + PostGIS 已安装，landvision 库已建（database/00_create_database.sql）
  * 表结构已建（Alembic：cd backend && alembic upgrade head）
  * 密码通过命令行参数或环境变量 PGPASSWORD 提供

用法：
  venv\\Scripts\\python.exe tools\\load_regions_pg.py postgres 你的密码
  或 PGPASSWORD=你的密码 venv\\Scripts\\python.exe tools\\load_regions_pg.py postgres
"""
import json
import os
import sys

import psycopg2
from shapely.geometry import shape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVINCES_JSON = os.path.join(ROOT, "tools", "assets", "china_provinces.json")
SUB_JSON = os.path.join(ROOT, "database", "05_cities_counties.json")


def main():
    user = sys.argv[1] if len(sys.argv) > 1 else "postgres"
    password = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("PGPASSWORD", "")
    if not password:
        print("用法：python tools/load_regions_pg.py <用户名> <密码>")
        sys.exit(1)

    conn = psycopg2.connect(host="127.0.0.1", port=5432, user=user,
                            password=password, dbname="landvision", connect_timeout=5)
    conn.autocommit = False
    cur = conn.cursor()

    def insert(code, name, level, parent_code, geom_wkt):
        cur.execute(
            "INSERT INTO regions (code, name, level, parent_code, geom) "
            "VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326)) "
            "ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, "
            "level=EXCLUDED.level, parent_code=EXCLUDED.parent_code, geom=EXCLUDED.geom",
            (code, name, level, parent_code, geom_wkt),
        )

    # 1) 省级
    with open(PROVINCES_JSON, encoding="utf-8") as f:
        prov_fc = json.load(f)
    n_prov = 0
    for feat in prov_fc["features"]:
        p = feat["properties"]
        code, name = str(p.get("adcode")), (p.get("name") or "").strip()
        if not name or not code.isdigit() or not code.endswith("0000"):
            continue
        geom = feat["geometry"]
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        insert(code, name, "province", "100000", shape(geom).wkt)
        n_prov += 1
    print(f"省级：{n_prov} 个")

    # 2) 市 + 县
    with open(SUB_JSON, encoding="utf-8") as f:
        payload = json.load(f)

    # 2.1 市级边界几何：从 DataV 省级下级缓存提取（tools/assets/province_children/*.json）
    cache_dir = os.path.join(ROOT, "tools", "assets", "province_children")
    city_geoms = {}
    if os.path.isdir(cache_dir):
        for fn in os.listdir(cache_dir):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(cache_dir, fn), encoding="utf-8") as f:
                    fc = json.load(f)
                for feat in fc.get("features", []):
                    p = feat["properties"]
                    adcode = str(p.get("adcode") or "")
                    if adcode.isdigit() and adcode.endswith("00") and adcode[2:4] != "00":
                        city_geoms[adcode] = feat["geometry"]
            except Exception:
                continue
    print(f"市级边界几何缓存：{len(city_geoms)} 个")

    n_city = 0
    n_city_geom = 0
    for c in payload["cities"]:
        geom = city_geoms.get(c["code"])
        wkt = None
        if geom:
            if geom["type"] == "Polygon":
                geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
            wkt = shape(geom).wkt
            n_city_geom += 1
        insert(c["code"], c["name"], "city", c["parent_code"], wkt)
        n_city += 1
    print(f"地级市：{n_city} 个（含边界几何 {n_city_geom} 个）")

    n_county = 0
    for c in payload["counties"]:
        geom = c["geometry"]
        if geom["type"] == "Polygon":
            geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}
        insert(c["code"], c["name"], "county", c["parent_code"], shape(geom).wkt)
        n_county += 1
        if n_county % 500 == 0:
            conn.commit()
            print(f"  县域进度：{n_county}/{len(payload['counties'])}")
    conn.commit()
    print(f"县域：{n_county} 个")

    cur.execute("SELECT level, COUNT(*) FROM regions GROUP BY level ORDER BY level")
    print("最终统计:", cur.fetchall())
    conn.close()
    print("[OK] 导入完成")


if __name__ == "__main__":
    main()
