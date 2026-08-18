# LandVISION —— 国土空间数据管理与智能分析可视化平台

> 全栈 GIS 教学与实战项目：PostgreSQL + PostGIS 空间数据库 → FastAPI 后端 → Vue 3 + MapLibre 前端。
> **v1.2**：用地性质升级为 GB/T 21010-2017 一级类（12 大类）、中国全境省级行政区（市/县可 SHP 导入）、
> SHP 地块批量上传入库、地图全屏主视觉（组件图标化点击展开）、右上角行政区选择器（县域级查找）、
> 统一错误码/分页/审计/限流/健康检查/Alembic 迁移/深浅主题/图表-地图双向联动。
> **v1.3**：新增“分析决策”四大模块 —— 用地变化转移矩阵（模块一）、土地适宜性评价（模块二）、
> 服务设施可达性分析（模块三）、三区三线合规性批量体检（模块四：问题台账 + CSV 导出 + 图上定位）。
> **v2.0**：期次管理显性化（period 必填默认基期、上传关联项目与期次）；引入“分析项目”实体（范围统一继承与变更确认）；
> 四大分析结果持久化（变化图斑/适宜性格网/体检结果/可达性结果，驾驶舱从持久化表取数）；
> 三区三线术语规范化（标准英文代码 + 规范线型：红线实线 3px/农田实线 2.5px/边界虚线 2px）与可配置规则矩阵（12 地类 × 三线，判定依据含亩数）；
> 模块间业务联动（转移矩阵→体检/适宜性/可达性、适宜性↔体检、可达性→设施选址、推荐流程与跳转传参）；
> 驾驶舱重构为项目工作台（流程进度/结论下钻）、报告升级为综合分析（项目概况→现状评价→问题识别→原因分析→规划建议→附录）；
> 地图要素批量选中删除 + 锁定机制 + 地图绘制持久化（map_features）。
> **v3.0**：Git 版本管理（`main` 主干 + `dev-3.0` 分支分阶段提交、合并回主干并打 `v3.0` 标签）；POI 点要素独立导入（点面严格分离）；
> 上传数据强制关联分析项目（缺失 422 / 项目不存在 404）；结果表与标注表补 GiST 空间索引（范围查询走 Index Scan）；
> 驾驶舱/报告严格范围聚合（全数据源按范围过滤 + ST_Intersection 面积裁剪，前端「已按此范围聚合」徽标）；
> 地图框选删除（delete-by-geometry，跳过锁定项）+ 锁定地块虚线描边；
> 转移矩阵→可达性设施类型自动预置、适宜性矛盾提示（高度/中等适宜 × 体检冲突）；
> 报告问题钻取修正（违规变化→转移矩阵页）+ 驾驶舱分析版本事件自动刷新；三区三线图例线型预览。

本仓库依据《项目手册与学习指南.docx》构建，目标是让你在 **不依赖真实服务器** 的情况下，先跑通全栈流程、理解每层原理，再逐步接入真实空间数据（行政区划 / SHP 地块）。

---

## 1. 快速开始（5 分钟跑通，无需 PostgreSQL）

> 最简单的方式：双击项目根目录的 **`启动项目.bat`**，脚本会检测端口占用、自动启动后端与前端，并在前端就绪后自动打开浏览器 http://localhost:5173。
> 停止服务：关闭两个黑色命令行窗口，或双击 **`停止项目.bat`**（同时清理 8000/5173 端口残留进程）。
> 手动启动请按下面 1.1 / 1.2 两条命令分别在两个终端执行。

### 1.1 启动后端（Demo 模式，内存数据）

```powershell
cd C:\landvision-project\backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

- API 文档（Swagger UI）：http://127.0.0.1:8000/docs
- 默认进入 **Demo 模式**（内置 10 个地块（12 大类用地）、20 个 POI、3 条三区三线控制线、**34 个省级行政区**），所有接口立即可用。
- 后端日志会打印 `当前运行模式：DEMO` 或 `POSTGIS`。
- 企业级特性：`GET /healthz`、`GET /api/system/audit`、统一错误码、限流、安全头、SHP 导入。

### 1.2 启动前端

```powershell
cd C:\landvision-project\frontend
npm install        # 首次需要，约 1-3 分钟
npm run dev        # 开发服务器
```

- 访问 http://localhost:5173 ，Vite 会把 `/api` 代理到后端 8000 端口。
- 所有页面地图全屏；右上角**行政区选择器**（国家→省→市→县四级）支持县域查找定位；
  地块管理页可上传 SHP 批量入库；顶栏切换深浅主题。
- **已接入本机 PostgreSQL（POSTGIS 模式）**：34 省 + 346 市 + 2883 县（含边界几何）+ 演示业务数据已入库。
  数据库凭据见 `backend/.env`（如需换密码，同步修改此文件）。

### 1.3 接入真实 PostgreSQL + PostGIS（进阶）

见 [`database/`](database/) 目录的 SQL 脚本（00→01→03→02 顺序执行，或 `backend/` 下的 Alembic 迁移），以及 [`外部工作清单.md`](外部工作清单.md)。

---

## 2. 目录结构

```
landvision-project/
├── backend/            # FastAPI 后端（10 组路由 + 9 个服务模块 + 中间件 + 迁移 + 测试）
├── frontend/           # Vue 3 + Vite 前端（7 个页面 + 4 个核心组件）
├── database/           # PostGIS 建表 / 业务种子 / 省级行政区 / GDAL 预处理
├── deploy/             # Docker Compose + Nginx 生产部署
├── docs/               # 学习文档（01~09）
├── tools/              # 种子数据生成器 + 省级行政区 GeoJSON 资产
├── .github/workflows/  # CI 流水线
├── 项目实现框架.md      # 实现原理与底层逻辑（必读）
├── 外部工作清单.md      # 需要在项目文件夹之外完成的工作（含天地图县域 SHP 下载教程）
├── 项目说明书.docx      # 项目说明书（细化到每个文件的职责说明，tools/generate_manual_docx.py 生成）
└── 项目手册与学习指南.docx
```

详细目录职责见 [`docs/03-目录结构.md`](docs/03-目录结构.md)。

---

## 3. 六层技术架构

| 层 | 技术 | 位置 |
|---|---|---|
| ① 数据存储层 | PostgreSQL 16 + PostGIS 3.x（五张业务表 + 项目/结果/标注表，共十张） | `database/` |
| ② 数据访问层 | SQLAlchemy 2.0 + GeoAlchemy2 | `backend/app/models.py`、`database.py` |
| ③ 业务服务层 | spatial / regions / shp_import / planning_check / analysis / report_gen / projects / map_features / planning_rules | `backend/app/services/` |
| ④ 接口层 | FastAPI 10 组路由 | `backend/app/routers/` |
| ⑤ 前端框架层 | Vue 3 + Vite + Pinia + Vue Router + Axios | `frontend/src/` |
| ⑥ 可视化层 | MapLibre GL JS（地图）+ ECharts（图表）+ Element Plus（UI） | `frontend/src/components`、`views` |

---

## 4. 接口总览（10 组路由）

| 前缀 | 功能 | 关键接口 |
|---|---|---|
| `/api/parcels` | 地块管理 | 分页/GeoJSON（期次过滤）/ CRUD / **SHP 导入（强制关联项目与期次）** / 批量删除 / **框选删除 delete-by-geometry** / 锁定 / 批量设置期次 |
| `/api/regions` | 行政区划 | 省/市/县列表 / GeoJSON / 定位 / **SHP 导入** |
| `/api/pois` | 兴趣点 | 分页列表 / GeoJSON / 按类型过滤 / 批量删除 / **点要素 SHP 导入（强制项目关联）** |
| `/api/analysis` | **空间分析（模块一~三）** | 转移矩阵（图斑持久化）/ 适宜性评价（格网持久化 + **矛盾提示**）/ 可达性分析（结果持久化）/ 设施选址 / SHP 范围解析 |
| `/api/planning` | **三区三线体检（模块四）** | 标准三线管理 / 规则矩阵（查看与配置）/ 批量体检（结果持久化）/ 图斑体检 / **台账 CSV 导出** |
| `/api/projects` | **分析项目** | 项目 CRUD（范围统一继承与变更确认） |
| `/api/map-features` | 地图标注 | 地图绘制持久化 / 锁定 / 批量删除 |
| `/api/dashboard` | **数据驾驶舱（项目工作台）** | 持久化结果优先统筹 + 流程进度 / 问题清单 / 规划建议 |
| `/api/report` | 报告生成 | 综合分析六章节（项目概况→现状评价→问题识别→原因分析→规划建议→附录）/ 下载 Markdown |
| `/api/system` | 系统 | 服务信息 / 审计日志 |

完整接口说明见 [`docs/05-后端接口设计.md`](docs/05-后端接口设计.md)。

---

## 5. 页面总览（7 个页面）

| 分组 | 页面 |
|---|---|
| 总览 | Dashboard（驾驶舱 = 项目工作台）—— 项目信息 + 流程进度 + 结论摘要下钻 + 问题/建议 + 范围管理（严格范围聚合徽标 + 分析版本自动刷新） |
| 数据管理 | 地块管理（期次筛选 / 上传强制关联项目期次 / 批量删除锁定 / **框选删除** / **POI 管理** / 地图标注） |
| 分析决策 | 用地转移矩阵（模块一）· 三区三线体检（模块四）· 适宜性评价（模块二）· 设施可达性（模块三）—— 推荐流程 ②→⑤ |
| 输出 | 报告生成（继承项目与范围，综合分析 + 问题清单 + 规划建议） |

---

## 6. 学习路线（与《学习指南》7 个模块对应）

| 模块 | 对应代码 | 建议 |
|---|---|---|
| 模块一 PostgreSQL + PostGIS | `database/*.sql` | 先装数据库，跑通 SQL |
| 模块二 FastAPI | `backend/app/**` | Demo 模式下先理解接口 |
| 模块三 空间分析算法 | `backend/app/services/analysis.py`、`planning_check.py` | 叠加求交 / 格网加权叠加 / 质心距离判定 |
| 模块四 Vue 3 | `frontend/src/router|store|utils` | 先跑通页面跳转 |
| 模块五 MapLibre | `frontend/src/components/MapView.vue` | 核心可视化 |
| 模块六 ECharts + Element Plus | `frontend/src/views/*` | 图表与表单 |
| 模块七 Docker + Nginx | `deploy/` | 最后学习 |

**必读**：动手写代码前，先读 [`项目实现框架.md`](项目实现框架.md)，理解每一层"为什么这样做"。
