# -*- coding: utf-8 -*-
"""
tools/build_regions.py —— 中国行政区划（省-市-县）数据构建脚本

输入：
  1. tools/assets/china_provinces.json   省级行政区（已内置，DataV 公开数据）
  2. 项目根目录 中国_县.geojson           县域行政区（用户从天地图下载，gb 码= '156'+6位标准码）
  3. DataV 省级下级数据（本脚本在线下载并缓存，用于提取地级市名称）

输出：
  1. backend/app/data/china_regions.json  县/市级数据（Demo 模式懒加载，4 级检索）
  2. database/05_cities_counties.json      与 1 相同内容的副本（供入库脚本使用）

用法：
  venv\\Scripts\\python.exe tools\\build_regions.py
"""
import json
import os
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROVINCES_JSON = os.path.join(ROOT, "tools", "assets", "china_provinces.json")
COUNTIES_JSON = os.path.join(ROOT, "中国_县.geojson")
OUT_DATA = os.path.join(ROOT, "backend", "app", "data")
OUT_JSON = os.path.join(OUT_DATA, "china_regions.json")
OUT_SQL_DIR = os.path.join(ROOT, "database")
CACHE_DIR = os.path.join(ROOT, "tools", "assets", "province_children")


def download(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "landvision-build/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def build_city_map():
    """下载 34 个省级下级文件，提取 地级市 code → name 映射。"""
    with open(PROVINCES_JSON, encoding="utf-8") as f:
        provinces = [feat["properties"]["adcode"]
                     for feat in json.load(f)["features"]
                     if str(feat["properties"]["adcode"]).isdigit()
                     and str(feat["properties"]["adcode"]).endswith("0000")]
    os.makedirs(CACHE_DIR, exist_ok=True)
    city_map = {}
    for code in provinces:
        cache = os.path.join(CACHE_DIR, f"{code}.json")
        try:
            if os.path.exists(cache):
                with open(cache, encoding="utf-8") as f:
                    fc = json.load(f)
            else:
                fc = download(f"https://geo.datav.aliyun.com/areas_v3/bound/{code}_full.json")
                with open(cache, "w", encoding="utf-8") as f:
                    json.dump(fc, f, ensure_ascii=False)
                time.sleep(0.3)
            for feat in fc.get("features", []):
                p = feat["properties"]
                adcode = str(p.get("adcode") or "")
                name = (p.get("name") or "").strip()
                if not adcode.isdigit() or not name:
                    continue
                # 直辖市（11/12/31/50）下级是区县，其他省级下级是地级市
                if adcode[:2] in ("11", "12", "31", "50"):
                    continue
                if adcode.endswith("00") and adcode != code:
                    city_map[adcode] = name
        except Exception as exc:  # noqa: BLE001 —— 单个省份失败不阻断
            print(f"[warn] 下载 {code} 失败: {exc}")
    return city_map


def standard_code(gb: str) -> str:
    """天地图 gb 码（如 156420704）→ 标准 6 位区划码（420704）。"""
    gb = str(gb or "").strip()
    if len(gb) == 9 and gb.startswith("156"):
        return gb[3:]
    if len(gb) == 6:
        return gb
    return gb


def main():
    print("1/4 读取省级数据…")
    with open(PROVINCES_JSON, encoding="utf-8") as f:
        provinces = json.load(f)["features"]
    province_names = {
        str(p["properties"]["adcode"]): p["properties"]["name"] for p in provinces
    }

    print("2/4 下载地级市名称映射（DataV，34 个省）…")
    city_map = build_city_map()
    print(f"    共获得地级市映射 {len(city_map)} 条")

    print("3/4 解析县域数据（中国_县.geojson）…")
    with open(COUNTIES_JSON, encoding="utf-8") as f:
        county_fc = json.load(f)

    counties = []
    seen_codes = set()
    for feat in county_fc["features"]:
        props = feat["properties"]
        name = (props.get("name") or "").strip()
        gb = standard_code(props.get("gb") or "")
        if not name or len(gb) != 6 or not gb.isdigit():
            continue
        if gb in seen_codes:
            continue
        seen_codes.add(gb)
        province_code = gb[:2] + "0000"
        city_code = gb[:4] + "00"
        counties.append({
            "code": gb,
            "name": name,
            "level": "county",
            "parent_code": city_code,
            "province_name": province_names.get(province_code, ""),
            "city_name": city_map.get(city_code, ""),
            "geometry": feat["geometry"],
        })

    # 派生地级市列表（去重；名称缺失时用 "XX市" 占位）
    cities = {}
    for c in counties:
        if c["parent_code"] not in cities:
            cities[c["parent_code"]] = {
                "code": c["parent_code"],
                "name": c["city_name"] or f"地级市{c['parent_code'][:4]}",
                "level": "city",
                "parent_code": c["parent_code"][:2] + "0000",
                "geometry": None,
            }
    print(f"    县域 {len(counties)} 个，地级市 {len(cities)} 个")

    print("4/4 写出数据文件…")
    os.makedirs(OUT_DATA, exist_ok=True)
    payload = {
        "cities": sorted(cities.values(), key=lambda x: x["code"]),
        "counties": counties,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    with open(os.path.join(OUT_SQL_DIR, "05_cities_counties.json"),
              "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[OK] {OUT_JSON}  {os.path.getsize(OUT_JSON) / 1e6:.1f} MB")
    print(f"[OK] {os.path.join(OUT_SQL_DIR, '05_cities_counties.json')}")


if __name__ == "__main__":
    main()
