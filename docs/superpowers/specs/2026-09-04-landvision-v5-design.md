# LandVISION V5.0 架构设计

## 背景

当前系统的主要问题是项目上下文不持久、业务数据与项目弱关联、地图加载仍采用
视野 bbox 拉取 GeoJSON 的方式。V5.0 在当前仓库以 `dev-5.0` 分支做外科手术式
重构，保留已经验证的 FastAPI 分析服务、SHP 解析、行政区数据和规则矩阵。

## 目标

1. 项目成为全局第一状态，刷新后自动恢复，创建时同时确定名称和范围。
2. 地块、兴趣点、三区三线、地图标注统一绑定当前项目，换项目后不可串数据。
3. 删除地块和兴趣点中的冗余字段，将项目关联从 `project_id` 改为 `project_name`。
4. 地块导入字段收敛为：期次、编号、名称、用地类型。
5. 地图使用 PostGIS `ST_AsMVT` 矢量瓦片，兼顾项目全貌和缩放细节。
6. 分析模块继续复用现有算法，只统一项目范围和数据绑定。

## 数据模型

- `parcels`
  - 删除 `district`、`region_code`、`far_limit`、`height_limit`。
  - 删除 `project_id`，新增 `project_name`。
- `pois`
  - 删除 `project_id`，新增 `project_name`。
- `planning_control`
  - 删除 `project_id`，新增 `project_name`。
- `map_features`
  - 删除 `project_id`，新增 `project_name`。
- 分析结果表继续使用 `project_id` 关联 `analysis_projects`，避免结果持久化语义变化。

迁移策略：

- 已有 `project_id` 数据通过 `analysis_projects` 回填名称。
- 无项目归属的旧种子数据绑定到默认演示项目，避免孤数据。
- `district_distribution` 因冗余字段移除而不再产出真实行政区分布，保留空结果兼容前端。

## 后端接口

- 业务数据列表、GeoJSON、删除、锁定、导入都按 `project_name` 过滤。
- SHP 导入不再接收 `project_id`，改为接收并校验 `project_name`。
- 新增 `GET /api/parcels/tiles/{z}/{x}/{y}`，返回 Mapbox Vector Tile。
- 地图瓦片支持 `project_name` 和 `period` 参数。

## 前端结构

- `ui` store 持久化当前项目 id，启动时恢复项目详情。
- 新建项目对话框包含项目名称、年份、行政区/SHP 范围。
- 数据管理页不再出现“所属项目”选择框。
- MapLibre 使用矢量瓦片源渲染地块；POI、控制线继续使用 GeoJSON 但按项目过滤。
- 表格分页与地图瓦片解耦，地图不再依赖 bbox GeoJSON 缓存。

## 验证

- DEMO 模式 pytest 通过。
- POSTGIS 模式真实库查询通过。
- 前端 `npm run build` 通过。
- 手动验证刷新恢复项目、项目切换数据隔离、地块瓦片加载。
