# -*- coding: utf-8 -*-
"""
冒烟测试：Demo 模式下验证全部接口
（含企业级特性：分页/统一错误码/健康检查/审计/行政区/SHP 导入）。

运行：cd backend && ..\\venv\\Scripts\\python.exe -m pytest tests -v
（依赖 httpx/pytest/pyshp，已写入 requirements.txt）
"""
import io
import os
import sys
import zipfile

import shapefile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 强制 Demo 模式，避免测试依赖数据库
os.environ["LANDVISION_DEMO"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


def _make_shp_zip(name="test_parcels", encoding="utf-8"):
    """用 pyshp 在内存中构造一个 Shapefile zip（2 个面要素 + 属性字段）。

    encoding 参数用于构造 GBK 编码的 DBF（天地图数据常见），验证编码自动回退。
    """
    shp = io.BytesIO()
    shx = io.BytesIO()
    dbf = io.BytesIO()
    w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, encoding=encoding)
    w.field("XMMC", "C", 50)      # 名称
    w.field("DLMC", "C", 50)      # 地类
    w.field("XZQMC", "C", 50)     # 行政区
    w.poly([[[114.30, 30.49], [114.32, 30.49], [114.32, 30.51], [114.30, 30.51], [114.30, 30.49]]])
    w.record("测试地块一", "住宅", "武汉市洪山区")
    w.poly([[[114.33, 30.49], [114.35, 30.49], [114.35, 30.51], [114.33, 30.51], [114.33, 30.49]]])
    w.record("测试地块二", "工矿仓储", "武汉市洪山区")
    w.close()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(f"{name}.shp", shp.getvalue())
        zf.writestr(f"{name}.shx", shx.getvalue())
        zf.writestr(f"{name}.dbf", dbf.getvalue())
        zf.writestr(f"{name}.prj",
                    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"],PRIMEM["Greenwich",0],'
                    'UNIT["Degree",0.0174532925199433]]')
        if encoding == "gbk":
            zf.writestr(f"{name}.cpg", "936")
    return buf.getvalue()


def test_root_and_health():
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "DEMO"

    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-Request-ID")


def test_system_info_and_audit():
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    assert resp.json()["service"] == "LandVISION API"

    resp = client.get("/api/system/audit")
    assert "items" in resp.json()


def test_regions():
    # 省级列表
    resp = client.get("/api/regions", params={"level": "province", "page_size": 100})
    data = resp.json()
    assert data["total"] == 34
    names = [r["name"] for r in data["items"]]
    assert "湖北省" in names and "北京市" in names and "西藏自治区" in names

    # 省级 GeoJSON
    resp = client.get("/api/regions/geojson")
    fc = resp.json()
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 34
    assert all(f["geometry"]["type"] == "MultiPolygon" for f in fc["features"])

    # 湖北省详情 + 定位
    resp = client.get("/api/regions/420000")
    assert resp.json()["name"] == "湖北省"
    resp = client.get("/api/regions/420000/locate")
    locate = resp.json()
    assert locate["center"][0] > 108 and locate["center"][0] < 116  # 湖北省经度范围


def test_parcels_pagination_and_filters():
    resp = client.get("/api/parcels", params={"page": 1, "page_size": 5})
    data = resp.json()
    assert data["total"] == 10
    assert len(data["items"]) == 5

    # 行政区划代码过滤（武汉市洪山区 420111）
    resp = client.get("/api/parcels", params={"region_code": "420111", "page_size": 100})
    items = resp.json()["items"]
    assert items and all(p["region_code"] == "420111" for p in items)

    # 用地性质过滤（12 大类）
    resp = client.get("/api/parcels", params={"land_use": "住宅用地", "page_size": 100})
    assert all(p["land_use"] == "住宅用地" for p in resp.json()["items"])


def test_parcels_flow():
    resp = client.get("/api/parcels/geojson")
    fc = resp.json()
    assert len(fc["features"]) == 10
    assert fc["features"][0]["properties"]["region_code"] == "420111"

    # 12 大类校验：非法用地性质 → 422
    resp = client.post("/api/parcels", json={
        "parcel_code": "BAD-01", "name": "非法地块", "land_use": "绿地",
        "geometry": {"type": "Polygon", "coordinates": [[[114.3, 30.5], [114.31, 30.5],
                                                         [114.31, 30.51], [114.3, 30.51], [114.3, 30.5]]]},
    })
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"

    # 重复编号 → 409
    resp = client.post("/api/parcels", json={
        "parcel_code": "A-01", "name": "重复地块", "land_use": "住宅用地",
        "geometry": {"type": "Polygon", "coordinates": [[[114.3, 30.5], [114.31, 30.5],
                                                         [114.31, 30.51], [114.3, 30.51], [114.3, 30.5]]]},
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "CONFLICT"

    # 新建 → 更新 → 删除
    resp = client.post("/api/parcels", json={
        "parcel_code": "TEST-01", "name": "测试地块", "land_use": "耕地",
        "district": "武汉市洪山区", "region_code": "420111",
        "area_sqm": 10000, "far_limit": None, "height_limit": None,
        "geometry": {"type": "Polygon", "coordinates": [[[114.3, 30.5], [114.31, 30.5],
                                                         [114.31, 30.51], [114.3, 30.51], [114.3, 30.5]]]},
    })
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    resp = client.put(f"/api/parcels/{new_id}", json={"name": "测试地块-改"})
    assert resp.json()["name"] == "测试地块-改"

    resp = client.delete(f"/api/parcels/{new_id}")
    assert resp.status_code == 204


def test_shp_import_parcels():
    """SHP zip 上传 → 解析 → 地块入库（端到端）。"""
    zip_bytes = _make_shp_zip()
    resp = client.post(
        "/api/parcels/import-shp",
        files={"file": ("parcels.zip", zip_bytes, "application/zip")},
        data={"region_code": "420111"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 2, result
    # 地类容错映射：住宅 → 住宅用地、工矿仓储 → 工矿仓储用地
    items = client.get("/api/parcels", params={"page_size": 100, "q": "IMP-"}).json()["items"]
    codes = [i["parcel_code"] for i in items]
    assert len(codes) >= 2
    # 面积必须按几何自动计算（不能为 0/None）——回归：导入地块面积缺失 Bug
    imported_items = [i for i in items if i["parcel_code"].startswith("IMP-")]
    assert all((i["area_sqm"] or 0) > 1000 for i in imported_items), imported_items

    # 非 zip → 422
    resp = client.post(
        "/api/parcels/import-shp",
        files={"file": ("bad.txt", b"not a zip", "text/plain")},
    )
    assert resp.status_code == 422


def test_shp_import_gbk_encoding():
    """GBK 编码 DBF（天地图数据常见）自动回退解析。"""
    zip_bytes = _make_shp_zip(name="gbk_parcels", encoding="gbk")
    resp = client.post(
        "/api/parcels/import-shp",
        files={"file": ("gbk.zip", zip_bytes, "application/zip")},
        data={"region_code": "420111"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] == 2, result
    assert result["encoding"] == "gbk"


def test_shp_import_regions():
    """SHP 导入县级行政区（端到端）。"""
    zip_bytes = _make_shp_zip(name="counties")
    resp = client.post(
        "/api/regions/import",
        files={"file": ("counties.zip", zip_bytes, "application/zip")},
        data={"level": "county", "parent_code": "420100",
              "code_field": "XMMC", "name_field": "XMMC"},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["imported"] >= 1, result

    # 新行政区可被查询
    resp = client.get("/api/regions", params={"level": "county", "page_size": 100})
    assert resp.json()["total"] >= 1


def test_error_format():
    resp = client.get("/api/parcels/99999")
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOT_FOUND"

    resp = client.post("/api/parcels", json={"parcel_code": ""})
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"


def test_pois():
    resp = client.get("/api/pois", params={"poi_type": "交通", "page_size": 100})
    assert resp.json()["total"] >= 4
    resp = client.get("/api/pois/geojson")
    assert resp.json()["type"] == "FeatureCollection"


def test_planning():
    resp = client.get("/api/planning/zones")
    assert len(resp.json()) == 3  # 三区三线（历史文化保护区已按 v2.0 移除）

    # 规则矩阵
    resp = client.get("/api/planning/rules")
    rules = resp.json()
    assert len(rules["rows"]) == 12  # 12 用地大类
    assert {z["code"] for z in rules["zone_types"]} == {
        "permanent_basic_farmland", "ecological_red_line", "urban_growth_boundary"}

    resp = client.get("/api/planning/check/7")
    data = resp.json()
    assert data["overall"] in ("冲突", "警告", "提示", "通过")
    assert "district" in data["parcel"]
    # 判定依据：冲突/警告时必须有 message
    for d in data["details"]:
        assert d["message"]

    resp = client.post("/api/planning/check", json={
        "geometry": {"type": "Polygon", "coordinates": [[[114.331, 30.483], [114.355, 30.483],
                                                         [114.355, 30.489], [114.331, 30.489], [114.331, 30.483]]]},
        "land_use": "林地",
    })
    assert resp.status_code == 200


def test_planning_zone_crud_and_review():
    """三区三线控制线管理 + 批量体检（端到端，规则矩阵判定）。"""
    # 新增控制线：覆盖 A-01（耕地示范片，位于 114.3310,30.5070 附近）
    resp = client.post("/api/planning/zones", json={
        "zone_name": "测试永久基本农田",
        "zone_type": "permanent_basic_farmland",
        "control_desc": "测试控制线",
        "geometry": {"type": "Polygon", "coordinates": [[[114.328, 30.504], [114.336, 30.504],
                                                         [114.336, 30.512], [114.328, 30.512], [114.328, 30.504]]]},
    })
    assert resp.status_code == 201
    zone_id = resp.json()["id"]

    # 类型校验：非法类型 422
    resp = client.post("/api/planning/zones", json={
        "zone_name": "非法类型", "zone_type": "商业用地",
        "geometry": {"type": "Polygon", "coordinates": [[[114.30, 30.49], [114.31, 30.49],
                                                         [114.31, 30.50], [114.30, 30.50], [114.30, 30.49]]]},
    })
    assert resp.status_code == 422

    # 锁定控制线 → 删除被拒
    client.post(f"/api/planning/zones/{zone_id}/lock", json={"locked": True})
    resp = client.delete(f"/api/planning/zones/{zone_id}")
    assert resp.status_code == 409
    client.post(f"/api/planning/zones/{zone_id}/lock", json={"locked": False})

    # 批量体检：指定 A-01（id=1，耕地）占用基本农田 → 规则矩阵判定为"通过"
    resp = client.post("/api/planning/review", json={
        "parcel_ids": [1],
        "zone_ids": [zone_id],
    })
    assert resp.status_code == 200
    result = resp.json()
    assert result["parcel_count"] == 1
    assert len(result["rows"]) == 1
    assert result["rows"][0]["total_occupied_sqm"] > 0
    # 耕地 × 永久基本农田 → 通过（规则矩阵）
    overlap = result["rows"][0]["overlaps"][0]
    assert overlap["zone_type"] == "permanent_basic_farmland"
    assert overlap["level"] == "通过"
    assert overlap["message"]

    # 带范围审查：范围选在别处（远离地块），结果应为 0
    resp = client.post("/api/planning/review", json={
        "scope": {"type": "Polygon", "coordinates": [[[113.90, 30.20], [113.95, 30.20],
                                                      [113.95, 30.25], [113.90, 30.25], [113.90, 30.20]]]},
    })
    assert resp.status_code == 200
    assert resp.json()["parcel_count"] == 0

    # 删除控制线
    resp = client.delete(f"/api/planning/zones/{zone_id}")
    assert resp.status_code == 204


def test_report():
    resp = client.post("/api/report/generate", json={
        "project_name": "测试报告", "period": "2026 Q3", "author": "tester",
    })
    assert resp.status_code == 200
    report = resp.json()
    assert report["overview"]["parcel_total"] >= 10
    assert report["overview"]["region_total"] >= 34  # 省级 34 + 测试导入的县级
    # 12 大类全量输出
    assert len(report["land_use_distribution"]) == 12
    assert "valuation" not in report  # 评估模块已移除
    assert "change_monitoring" not in report  # 变化监测模块已移除
    assert "district_distribution" in report
    # 新模块章节：转移矩阵 / 三区三线体检 / 设施可达性 / 适宜性
    assert "transition_analysis" in report
    assert report["transition_analysis"]["has_data"] is False  # 演示数据未标记期次
    assert "planning_review" in report
    assert "accessibility" in report
    assert "suitability" in report
    assert report["accessibility"]["parcel_total"] >= 10
    # 综合分析章节：问题清单 + 规划建议 + 流程进度
    assert "problems" in report
    assert "suggestions" in report
    assert "progress" in report
    assert "missing" in report["progress"]
    # 范围说明：无范围 → 全量数据
    assert report["scope"]["has_scope"] is False
    assert report["scope"]["label"] == "全量数据"

    resp = client.get("/api/report/latest/download")
    assert resp.status_code == 200
    assert "项目概况" in resp.text
    assert "现状评价" in resp.text
    assert "问题识别" in resp.text
    assert "原因分析" in resp.text
    assert "规划建议" in resp.text
    assert "附录数据表" in resp.text
    assert "变化监测" not in resp.text


def test_dashboard_summary():
    """驾驶舱统筹汇总：按范围聚合，且与报告共用同一数据源。"""
    resp = client.post("/api/dashboard/summary", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["scope"]["has_scope"] is False
    assert data["overview"]["parcel_total"] >= 10
    assert len(data["land_use_distribution"]) == 12
    assert "planning_review" in data
    assert "accessibility" in data
    assert "transition_analysis" in data
    assert "progress" in data and "missing" in data["progress"]

    # 划定范围（演示区局部矩形）→ 数据应收敛到范围内
    scope = {"type": "Polygon", "coordinates": [[
        [114.33, 30.49], [114.36, 30.49], [114.36, 30.51], [114.33, 30.51], [114.33, 30.49]]]}
    resp2 = client.post("/api/dashboard/summary",
                        json={"scope": scope, "scope_label": "测试范围"})
    assert resp2.status_code == 200
    d2 = resp2.json()
    assert d2["scope"]["has_scope"] is True
    assert d2["scope"]["label"] == "测试范围"
    assert 0 < d2["overview"]["parcel_total"] < data["overview"]["parcel_total"]

    # 报告继承同一范围 → 数据一致
    resp3 = client.post("/api/report/generate", json={
        "project_name": "范围报告", "period": "Q", "author": "t",
        "scope": scope, "scope_label": "测试范围",
    })
    r3 = resp3.json()
    assert r3["scope"]["label"] == "测试范围"
    assert r3["overview"]["parcel_total"] == d2["overview"]["parcel_total"]
    md = client.get("/api/report/latest/download")
    assert "分析范围**：测试范围" in md.text


def test_projects_and_persistence():
    """v2.0：分析项目 CRUD + 范围继承校验 + 分析结果持久化。"""
    # 新建项目（范围 = 演示区局部）
    scope = {"type": "Polygon", "coordinates": [[
        [114.33, 30.49], [114.36, 30.49], [114.36, 30.51], [114.33, 30.51], [114.33, 30.49]]]}
    resp = client.post("/api/projects", json={
        "name": "测试分析项目", "base_year": 2020, "current_year": 2026, "scope": scope})
    assert resp.status_code == 200
    project = resp.json()
    project_id = project["id"]
    assert project["scope_geojson"] == scope

    # 范围变更需确认 → 409
    resp = client.put(f"/api/projects/{project_id}", json={"scope": None})
    assert resp.status_code == 409
    # 确认后成功
    resp = client.put(f"/api/projects/{project_id}", json={"scope": None,
                                                           "confirm_scope_change": True})
    assert resp.status_code == 200

    # 可达性分析（项目内）→ 结果持久化
    resp = client.post("/api/analysis/accessibility/analyze", json={
        "facility_types": [], "radius_m": 800, "project_id": project_id})
    assert resp.status_code == 200
    result = resp.json()
    assert result["parcel_total"] >= 10
    assert result.get("persisted") is True
    rows = client.get(f"/api/analysis/accessibility/results?project_id={project_id}").json()
    assert len(rows) >= 1
    assert rows[0]["coverage_rate"] == result["coverage_rate"]

    # 适宜性评价（项目内）→ 格网持久化
    resp = client.post("/api/analysis/suitability/evaluate", json={
        "target": "建设用地适宜性", "weights": {}, "scope": scope, "project_id": project_id})
    assert resp.status_code == 200
    grids = client.get(f"/api/analysis/suitability/grids?project_id={project_id}").json()
    assert grids["count"] > 0

    # 批量体检（项目内）→ 结果持久化
    resp = client.post("/api/planning/review", json={"project_id": project_id})
    assert resp.status_code == 200
    check_rows = client.get(f"/api/planning/results?project_id={project_id}").json()
    assert len(check_rows) > 0

    # 驾驶舱按项目统筹：持久化结果优先 + 流程进度
    summary = client.post("/api/dashboard/summary",
                          json={"project_id": project_id}).json()
    assert summary["project"]["name"] == "测试分析项目"
    assert summary["progress"]["accessibility"] is True
    assert summary["progress"]["suitability"] is True
    assert summary["progress"]["planning"] is True

    # 子范围校验：项目外范围 → 422
    far_scope = {"type": "Polygon", "coordinates": [[
        [113.9, 30.2], [113.95, 30.2], [113.95, 30.25], [113.9, 30.25], [113.9, 30.2]]]}
    project2 = client.post("/api/projects", json={
        "name": "范围项目", "base_year": 2020, "current_year": 2026, "scope": scope}).json()
    resp = client.post("/api/analysis/accessibility/analyze", json={
        "facility_types": [], "radius_m": 800,
        "project_id": project2["id"], "scope": far_scope})
    assert resp.status_code == 422

    # 清理
    client.delete(f"/api/projects/{project_id}")
    client.delete(f"/api/projects/{project2['id']}")


def test_period_lock_batch_and_mapfeatures():
    """v2.0：期次筛选 / 锁定 / 批量删除 / 地图标注。"""
    # 期次筛选
    resp = client.get("/api/parcels", params={"period": "base", "page_size": 100})
    assert resp.status_code == 200
    assert all(i["period"] == "base" for i in resp.json()["items"])

    # 无期次数据修复：批量设置期次
    resp = client.post("/api/parcels/batch-set-period",
                       params={"period": "base", "ids": "1,2"})
    assert resp.json()["updated"] == 2

    # 锁定地块 → 删除被拒 → 批量删除跳过锁定
    client.post("/api/parcels/1/lock", json={"locked": True})
    resp = client.delete("/api/parcels/1")
    assert resp.status_code == 409
    resp = client.post("/api/parcels/batch-delete", json={"ids": [1, 2]})
    result = resp.json()
    assert result["deleted"] == [2]
    assert result["locked"][0]["id"] == 1
    client.post("/api/parcels/1/lock", json={"locked": False})

    # 地图标注：保存绘制 → 列表 → 锁定 → 批量删除跳过锁定
    resp = client.post("/api/map-features", json={
        "name": "测试标注点", "feature_type": "point",
        "geometry": {"type": "Point", "coordinates": [114.34, 30.50]}})
    assert resp.status_code == 201
    fid = resp.json()["id"]
    fc = client.get("/api/map-features/geojson").json()
    assert fc["count"] >= 1
    client.post(f"/api/map-features/{fid}/lock", json={"locked": True})
    resp = client.post("/api/map-features/batch-delete", json={"ids": [fid]})
    assert resp.json()["locked"][0]["id"] == fid
    client.post(f"/api/map-features/{fid}/lock", json={"locked": False})
    client.delete(f"/api/map-features/{fid}")
