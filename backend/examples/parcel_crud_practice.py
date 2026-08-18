# -*- coding: utf-8 -*-
"""
独立练习脚本（从早期学习版本迁移保存）：FastAPI 最小 CRUD 示例。

用途：对照学习"路由 / Pydantic / 状态"三件套，与本项目的正式结构对比。
运行：cd backend && python examples/parcel_crud_practice.py
访问：http://127.0.0.1:8001/docs
"""
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="LandVISION API 练习")


# ---------- Pydantic 模型：定义数据格式 ----------
class ParcelBase(BaseModel):
    name: str
    land_use: str
    area_sqm: float


class ParcelCreate(ParcelBase):
    far_limit: Optional[float] = None
    height_limit: Optional[float] = None


class ParcelResponse(ParcelBase):
    id: int
    far_limit: Optional[float] = None
    height_limit: Optional[float] = None


# ---------- 模拟数据库：用一个列表代替 ----------
fake_db = []
next_id = 1


# ---------- 路由：处理不同请求 ----------
@app.get("/")
def read_root():
    return {"message": "Hello LandVISION"}


@app.get("/parcels/{parcel_id}", response_model=ParcelResponse)
def get_parcel(parcel_id: int):
    for p in fake_db:
        if p["id"] == parcel_id:
            return p
    # 如果没找到，返回 404 错误
    raise HTTPException(status_code=404, detail="Parcel not found")


@app.post("/parcels", response_model=ParcelResponse, status_code=201)
def create_parcel(parcel: ParcelCreate):
    global next_id
    new_parcel = parcel.model_dump()
    new_parcel["id"] = next_id
    next_id += 1
    fake_db.append(new_parcel)
    return new_parcel


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
