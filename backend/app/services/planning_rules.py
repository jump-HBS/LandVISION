# -*- coding: utf-8 -*-
"""
三区三线体检规则矩阵服务（可配置，JSON 文件存储）。

规则矩阵：12 用地大类 × 3 管控区类型 → conclusion（conflict / warning / pass）。
默认矩阵来自 backend/app/data/planning_rules.json，管理员可通过
PUT /api/planning/rules 更新（写回 JSON 文件，即时生效）。
"""
import json
import threading
from pathlib import Path
from typing import Dict

from ..schemas import LAND_USE_TYPES, ZONE_TYPE_LABELS

RULES_FILE = Path(__file__).resolve().parent.parent / "data" / "planning_rules.json"

# 结论 → 中文等级
CONCLUSION_LEVEL = {"conflict": "冲突", "warning": "警告", "pass": "通过"}

_LOCK = threading.Lock()
_CACHE: Dict = {}


def _default_matrix() -> dict:
    """内置默认矩阵（与 JSON 文件一致的兜底）。"""
    m = {}
    for lu in LAND_USE_TYPES:
        m[lu] = {z: "pass" for z in ZONE_TYPE_LABELS}
    # 国土空间规划管控逻辑默认矩阵
    defaults = {
        "耕地": ("pass", "warning", "pass"),
        "园地": ("conflict", "warning", "warning"),
        "林地": ("conflict", "pass", "warning"),
        "草地": ("conflict", "pass", "warning"),
        "商服用地": ("conflict", "conflict", "pass"),
        "工矿仓储用地": ("conflict", "conflict", "pass"),
        "住宅用地": ("conflict", "conflict", "pass"),
        "公共管理与公共服务用地": ("conflict", "conflict", "pass"),
        "特殊用地": ("warning", "conflict", "pass"),
        "交通运输用地": ("conflict", "warning", "pass"),
        "水域及水利设施用地": ("warning", "pass", "pass"),
        "其他土地": ("warning", "pass", "warning"),
    }
    for lu, (farm, eco, urb) in defaults.items():
        m[lu] = {
            "permanent_basic_farmland": farm,
            "ecological_red_line": eco,
            "urban_growth_boundary": urb,
        }
    return m


def load_matrix() -> dict:
    """读取规则矩阵（带内存缓存）。"""
    global _CACHE
    if _CACHE:
        return _CACHE
    with _LOCK:
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                payload = json.load(f)
            matrix = payload.get("matrix", {})
            # 与内置默认合并（保证 12×3 全覆盖）
            merged = _default_matrix()
            for lu, row in matrix.items():
                if lu in merged:
                    for z, c in row.items():
                        if z in merged[lu] and c in ("conflict", "warning", "pass"):
                            merged[lu][z] = c
            _CACHE = merged
        except Exception:  # noqa: BLE001 —— 文件缺失/损坏时用内置默认
            _CACHE = _default_matrix()
    return _CACHE


def save_matrix(matrix: dict) -> None:
    """校验并写回规则矩阵（仅接受 12 大类 × 标准三线 × 合法结论）。"""
    clean = {}
    for lu in LAND_USE_TYPES:
        row = matrix.get(lu)
        if not isinstance(row, dict):
            raise ValueError(f"缺少用地类型规则行：{lu}")
        clean[lu] = {}
        for z in ZONE_TYPE_LABELS:
            c = row.get(z)
            if c not in ("conflict", "warning", "pass"):
                raise ValueError(f"{lu} × {z} 的结论必须为 conflict / warning / pass")
            clean[lu][z] = c
    with _LOCK:
        payload = {"version": "v2.0", "matrix": clean}
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        global _CACHE
        _CACHE = clean


def verdict_for(land_use: str, zone_type: str) -> str:
    """判定：返回 conclusion（conflict / warning / pass）。"""
    matrix = load_matrix()
    row = matrix.get(land_use, {})
    return row.get(zone_type, "pass")


def verdict_level(conclusion: str) -> str:
    return CONCLUSION_LEVEL.get(conclusion, "通过")


def rules_table() -> list:
    """规则矩阵展示表：每行 = 一个用地类型，三列管控区结论（中文等级）。"""
    matrix = load_matrix()
    rows = []
    for lu in LAND_USE_TYPES:
        row = {"land_use": lu}
        for z in ZONE_TYPE_LABELS:
            row[z] = verdict_level(matrix[lu][z])
        rows.append(row)
    return rows


def reload_rules() -> None:
    global _CACHE
    _CACHE = {}
    load_matrix()
