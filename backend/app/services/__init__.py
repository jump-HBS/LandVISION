# -*- coding: utf-8 -*-
"""
服务层包。业务逻辑全部放在这里，路由层保持"薄"。

每个服务函数都支持两种数据来源：
  * Demo 模式（settings.runtime_demo_mode=True）→ 操作 demo_data 内存数据 + shapely 运算
  * POSTGIS 模式 → 操作 PostgreSQL + PostGIS（SQLAlchemy/GeoAlchemy2 查询）

对外暴露的辅助工具：
  from .spatial import is_demo, parse_bbox, distance_m, buffer_geojson
"""
