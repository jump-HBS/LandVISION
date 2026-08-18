# -*- coding: utf-8 -*-
"""
SHP 上传解析与入库服务。

流程：
  前端上传 zip（含 .shp/.shx/.dbf/.prj）→ pyshp 解析 → 坐标转 GeoJSON
  → 属性字段映射 → 批量入库（地块 parcels / 行政区 regions）

兼容性增强（v1.2.1）：
  * DBF 中文编码自动识别（.cpg → UTF-8 → GBK → latin-1 回退），天地图数据常用 GBK；
  * 坐标系校验给出检测到的坐标系名称，投影坐标系附带 GDAL 转换命令；
  * MultiPolygon 自动拆分为多个地块；
  * 全部失败原因随响应返回（skipped 列表），便于排查。
"""
import io
import json
import logging
import time
import zipfile

import shapefile

from ..config import settings
from ..schemas import LAND_USE_TYPES
from .. import demo_data
from .regions import import_regions
from .spatial import is_demo

logger = logging.getLogger("landvision.shp_import")

# 进程内批次自增序号：即使两次导入在同一秒发生，编号也不会重复
_BATCH_SEQ = [0]


class ShpImportError(Exception):
    """SHP 解析/校验失败（业务异常，路由层转 422）。"""


def _read_prj(files: dict) -> str:
    """读取 .prj 文件内容（可能缺失）。"""
    for name, data in files.items():
        if name.lower().endswith(".prj"):
            return data.decode("utf-8", errors="ignore")
    return ""


def _prj_name(files: dict) -> str:
    """从 prj 提取坐标系名称（错误提示用）。"""
    prj = _read_prj(files)
    if not prj:
        return "（无 .prj 文件，按 WGS84 处理）"
    for token in ("PROJCS", "GEOGCS"):
        idx = prj.upper().find(token)
        if idx >= 0:
            start = prj.find('"', idx)
            end = prj.find('"', start + 1)
            if start >= 0 and end > start:
                return prj[start + 1:end]
    return prj[:60]


def _check_srid(files: dict) -> None:
    """校验坐标系为地理坐标系（WGS84 / CGCS2000 经纬度）；投影坐标系给出明确指引。"""
    prj = _read_prj(files)
    if not prj:
        return  # 无 prj 时假定 4326（并在结果中提示）
    upper = prj.upper()
    is_geographic = (
        "GEOGCS" in upper or "GCS" in upper
        or "WGS_1984" in upper or "WGS 84" in upper
        or "4326" in upper
    )
    if is_geographic:
        return
    raise ShpImportError(
        f"坐标系不支持：检测到投影坐标系「{_prj_name(files)}」。"
        f"平台要求地理坐标系（WGS84/CGCS2000 经纬度，单位：度）。"
        f"请先用 GDAL 转换：gdalwarp -t_srs EPSG:4326 input.shp output.shp"
    )


def _read_cpg(files: dict) -> str | None:
    """读取 .cpg 编码声明文件（天地图数据常带，如 UTF-8 / 936=GBK）。"""
    for name, data in files.items():
        if name.lower().endswith(".cpg"):
            text = data.decode("ascii", errors="ignore").strip().lower()
            if text in ("utf-8", "utf8", "65001"):
                return "utf-8"
            if text in ("gbk", "936", "gb2312", "cp936"):
                return "gbk"
            return text or None
    return None


def _open_reader(files: dict, shp_name: str, shx: str, dbf: str) -> tuple:
    """按候选编码逐个尝试打开 Reader，返回 (reader, encoding)。

    pyshp 在读取 DBF 记录时才会解码字符串，因此用"试读第一条记录"的方式验证编码。
    """
    encodings = []
    cpg = _read_cpg(files)
    if cpg:
        encodings.append(cpg)
    encodings += ["utf-8", "gbk", "latin-1"]
    seen = []
    for enc in encodings:
        if enc in seen:
            continue
        seen.append(enc)
        try:
            reader = shapefile.Reader(
                shp=io.BytesIO(files[shp_name]),
                shx=io.BytesIO(files[shx]),
                dbf=io.BytesIO(files[dbf]),
                encoding=enc,
            )
            # 试读第一条记录验证编码是否可行
            for _rec in reader.iterShapeRecords():
                break
            return reader, enc
        except (UnicodeDecodeError, LookupError):
            continue
    raise ShpImportError("无法解析 .dbf 属性表编码（尝试了 UTF-8/GBK/latin-1）")


def parse_shp_zip(zip_bytes: bytes) -> dict:
    """解析 zip 压缩包内的 Shapefile，返回统一结构。

    返回：{"features": [...], "fields": [...], "has_prj": bool, "encoding": str}
    """
    if len(zip_bytes) > settings.max_upload_mb * 1024 * 1024:
        raise ShpImportError(f"压缩包超过 {settings.max_upload_mb}MB 上限（当前 {len(zip_bytes) / 1024 / 1024:.1f}MB）")

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ShpImportError("不是有效的 zip 压缩包——请把 .shp/.shx/.dbf/.prj 四个文件打包成 zip 后上传") from exc

    files = {}
    for info in zf.infolist():
        if info.file_size > settings.max_upload_mb * 1024 * 1024:
            raise ShpImportError(f"压缩包内文件 {info.filename} 过大")
        files[info.filename] = zf.read(info.filename)

    shp_name = next((n for n in files if n.lower().endswith(".shp")), None)
    if not shp_name:
        raise ShpImportError("压缩包中未找到 .shp 文件。Shapefile 必须包含 .shp/.shx/.dbf（建议另带 .prj）四个文件")

    base = shp_name[:-4]
    shx = next((n for n in files if n.lower() == (base + ".shx").lower()), None)
    dbf = next((n for n in files if n.lower() == (base + ".dbf").lower()), None)
    if not shx or not dbf:
        missing = []
        if not shx:
            missing.append(".shx")
        if not dbf:
            missing.append(".dbf")
        raise ShpImportError(f"Shapefile 不完整：缺少 {', '.join(missing)} 文件（需与 .shp 同名）")

    _check_srid(files)

    try:
        reader, encoding = _open_reader(files, shp_name, shx, dbf)
        field_names = [f[0] for f in reader.fields[1:]]  # 去掉 DeletionFlag

        features = []
        skipped_shapes = 0
        for shape_rec in reader.iterShapeRecords():
            geom_type = shape_rec.shape.shapeTypeName
            if geom_type not in ("POLYGON", "MULTIPOLYGON", "POINT", "MULTIPOINT"):
                skipped_shapes += 1
                continue
            geometry = shape_rec.shape.__geo_interface__
            props = dict(zip(field_names, [str(v) if v is not None else "" for v in shape_rec.record]))
            features.append({"geometry": geometry, "properties": props})
    except UnicodeDecodeError as exc:
        raise ShpImportError(f".dbf 属性表编码无法解析（{exc}），请确认数据为 UTF-8 或 GBK 编码") from exc
    except shapefile.ShapefileException as exc:
        raise ShpImportError(f"Shapefile 解析失败：{exc}") from exc

    if not features:
        hint = "（其中 {skipped_shapes} 个要素为线/点类型已忽略）" if skipped_shapes else ""
        raise ShpImportError(f"文件中没有可用的面要素{hint}。地块导入需要 Polygon/MultiPolygon 类型")

    return {"features": features, "fields": field_names,
            "has_prj": bool(_read_prj(files)), "encoding": encoding}


def _pick_field(fields: list, candidates: list, user_field: str = None) -> str | None:
    """字段映射：优先用户指定，否则按候选名自动匹配。"""
    if user_field:
        if user_field not in fields:
            raise ShpImportError(f"指定的字段 {user_field} 不存在，可用字段：{', '.join(fields)}")
        return user_field
    for c in candidates:
        if c in fields:
            return c
    return None


def _normalize_land_use(raw: str) -> str:
    """用地性质清洗：容错映射到 12 大类；无法识别时给'其他土地'。"""
    text = (raw or "").strip()
    if text in LAND_USE_TYPES:
        return text
    alias = {
        "耕地": "耕地", "水田": "耕地", "旱地": "耕地",
        "园地": "园地", "果园": "园地", "茶园": "园地",
        "林地": "林地", "灌木林": "林地", "有林地": "林地",
        "草地": "草地", "牧草地": "草地", "人工草地": "草地",
        "商服": "商服用地", "商业": "商服用地", "商服用地": "商服用地", "商业服务业": "商服用地",
        "工业": "工矿仓储用地", "采矿": "工矿仓储用地", "仓储": "工矿仓储用地",
        "住宅": "住宅用地", "居住": "住宅用地", "城镇住宅": "住宅用地", "农村宅基地": "住宅用地",
        "公共管理": "公共管理与公共服务用地", "公共服务": "公共管理与公共服务用地",
        "特殊用地": "特殊用地", "军事": "特殊用地",
        "交通": "交通运输用地", "公路": "交通运输用地", "铁路": "交通运输用地",
        "水域": "水域及水利设施用地", "水利": "水域及水利设施用地",
        "其他": "其他土地", "空闲地": "其他土地",
    }
    for key, value in alias.items():
        if key in text:
            return value
    return "其他土地"


def import_parcels_from_zip(zip_bytes: bytes, db=None, name_field: str = None,
                            land_use_field: str = None, region_field: str = None,
                            region_code: str = None, period: str = None,
                            project_id: int = None) -> dict:
    """解析 zip 并将面要素导入地块表（关联项目与期次）。"""
    parsed = parse_shp_zip(zip_bytes)
    fields = parsed["fields"]
    name_f = _pick_field(fields, ["name", "NAME", "地块名称", "XMMC", "MC"], name_field)
    lu_f = _pick_field(fields, ["land_use", "LAND_USE", "DLMC", "地类名称", "用地性质", "YDLB"], land_use_field)
    reg_f = _pick_field(fields, ["district", "XZQMC", "行政区", "region"], region_field)

    imported, skipped = 0, []
    # 批次号 = 时间戳 + 进程内自增序号，保证每次导入编号唯一（重复导入不会撞唯一约束）
    _BATCH_SEQ[0] += 1
    batch = f"{time.strftime('%m%d%H%M%S')}-{_BATCH_SEQ[0]}"
    for f in parsed["features"]:
        geom = f["geometry"]
        if geom["type"] == "Point":
            skipped.append({"reason": "点要素不支持地块导入（仅支持面）", "name": str(f["properties"].get(name_f) or "") if name_f else ""})
            continue
        if geom["type"] not in ("Polygon", "MultiPolygon"):
            skipped.append({"reason": f"不支持的几何类型 {geom['type']}", "name": ""})
            continue
        # MultiPolygon 拆分为多个地块（每个部分独立入库）
        polys = [{"type": "Polygon", "coordinates": rings}
                 for rings in geom["coordinates"]] if geom["type"] == "MultiPolygon" else [geom]

        props = f["properties"]
        name = str(props.get(name_f) or "").strip() if name_f else ""
        land_use = _normalize_land_use(str(props.get(lu_f) or "")) if lu_f else "其他土地"
        district = str(props.get(reg_f) or "").strip() if reg_f else ""

        for idx, poly in enumerate(polys):
            suffix = f"-{idx + 1}" if len(polys) > 1 else ""
            record = {
                "parcel_code": f"IMP-{batch}-{imported + 1:04d}",
                "name": (name or f"导入地块{imported + 1}") + suffix,
                "land_use": land_use,
                "district": district or None,
                "region_code": region_code or None,
                "area_sqm": None,
                "far_limit": None,
                "height_limit": None,
                "period": period or "base",
                "project_id": project_id,
                "geometry": poly,
            }
            try:
                _insert_parcel(db, record)
                imported += 1
            except Exception as exc:  # noqa: BLE001 —— 单条失败不中断整批
                skipped.append({"reason": str(exc), "name": record["name"]})

    logger.info("SHP 导入完成：成功 %d 条，跳过 %d 条（编码=%s，字段=%s）",
                imported, len(skipped), parsed.get("encoding"), fields)
    return {"imported": imported, "skipped": skipped, "fields": fields,
            "has_prj": parsed["has_prj"], "encoding": parsed.get("encoding"),
            "period": period or "base", "project_id": project_id}


def import_regions_from_zip(zip_bytes: bytes, db=None, level: str = "county",
                            parent_code: str = None, code_field: str = None,
                            name_field: str = None) -> dict:
    """解析 zip 并将面要素导入行政区表（市/县级）。"""
    parsed = parse_shp_zip(zip_bytes)
    fields = parsed["fields"]
    code_f = _pick_field(fields, ["code", "CODE", "adcode", "XZQDM", "行政区代码"], code_field)
    name_f = _pick_field(fields, ["name", "NAME", "XZQMC", "行政区名称"], name_field)

    features = []
    for f in parsed["features"]:
        props = f["properties"]
        features.append({
            "geometry": f["geometry"],
            "properties": {
                "code": str(props.get(code_f) or "").strip() if code_f else "",
                "name": str(props.get(name_f) or "").strip() if name_f else "",
            },
        })
    result = import_regions(features, level, parent_code, db)
    logger.info("行政区 SHP 导入完成：成功 %d 条，跳过 %d 条", result["imported"], len(result["skipped"]))
    return result


def _insert_parcel(db, record: dict) -> dict:
    """单条地块入库（复用 spatial.create_parcel 的双模式逻辑）。"""
    from .spatial import create_parcel
    return create_parcel(record, db)
