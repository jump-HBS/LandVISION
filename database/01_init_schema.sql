-- ===================================================================
-- LandVISION —— 01 初始化表结构（四张业务表 + 空间索引）
-- 设计要点：
--   * 所有几何字段统一 geometry(..., 4326)（WGS84 经纬度，与前端 GeoJSON 一致）
--   * 所有几何字段均建 GiST 空间索引（bbox 粗筛 → 精确空间判断两段式查询）
--   * 面积/容积率/限高等冗余存储常用展示字段，减少高频计算
-- ===================================================================

-- ---------- 1. 地块表 parcels ----------
CREATE TABLE IF NOT EXISTS parcels (
    id            SERIAL PRIMARY KEY,            -- 自增主键
    parcel_code   VARCHAR(50) UNIQUE NOT NULL,   -- 地块编号（业务编码，如 A-01）
    name          VARCHAR(100) NOT NULL,         -- 地块名称
    land_use      VARCHAR(50) NOT NULL,          -- 用地性质（GB/T 21010-2017 一级类，12 大类）
    district      VARCHAR(50),                   -- 行政区名称（如 武汉市洪山区）
    region_code   VARCHAR(20),                   -- 行政区划代码（GB/T 2260，如 420111）
    area_sqm      NUMERIC(14, 2),                -- 面积（平方米）
    far_limit     NUMERIC(6, 2),                 -- 容积率上限
    height_limit  NUMERIC(6, 2),                 -- 建筑限高（米）
    geom          geometry(Polygon, 4326) NOT NULL,  -- 地块边界（面）
    created_at    TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_parcels_geom ON parcels USING GIST (geom);

-- ---------- 2. 兴趣点表 pois ----------
CREATE TABLE IF NOT EXISTS pois (
    id        SERIAL PRIMARY KEY,
    name      VARCHAR(100) NOT NULL,
    poi_type  VARCHAR(50) NOT NULL,              -- 交通/商业/教育/医疗/休闲
    geom      geometry(Point, 4326) NOT NULL     -- 点位
);
CREATE INDEX IF NOT EXISTS idx_pois_geom ON pois USING GIST (geom);

-- ---------- 3. 规划控制区表 planning_control ----------
CREATE TABLE IF NOT EXISTS planning_control (
    id           SERIAL PRIMARY KEY,
    zone_name    VARCHAR(100) NOT NULL,
    zone_type    VARCHAR(50) NOT NULL,           -- 生态保护红线/永久基本农田/城镇开发边界/历史文化保护区
    zone_level   VARCHAR(20),                    -- 国家级/省级/市级
    control_desc TEXT,                           -- 管控要求描述
    geom         geometry(Polygon, 4326) NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_planning_geom ON planning_control USING GIST (geom);

-- ---------- 4. 行政区划表 regions（省/市/县三级） ----------
CREATE TABLE IF NOT EXISTS regions (
    id           SERIAL PRIMARY KEY,
    code         VARCHAR(20) UNIQUE NOT NULL,    -- 行政区划代码（GB/T 2260）
    name         VARCHAR(100) NOT NULL,
    level        VARCHAR(20) NOT NULL,           -- province / city / county
    parent_code  VARCHAR(20),                    -- 上级代码（省级为 100000）
    geom         geometry(MultiPolygon, 4326)    -- 行政区边界（省级内置，市/县经 SHP 导入）
);
CREATE INDEX IF NOT EXISTS idx_regions_geom ON regions USING GIST (geom);

-- ===================================================================
-- 核心空间查询示例（对照《项目实现框架.md》第四节理解）：
--
-- ① 按视野范围查询地块（前端地图 moveend 时调用）
--    SELECT id, parcel_code, name, ST_AsGeoJSON(geom) AS geometry
--    FROM parcels
--    WHERE geom && ST_MakeEnvelope(116.39, 39.88, 116.42, 39.91, 4326);
--
-- ② 统计某地块 800 米内各类 POI 数量（设施可达性分析模块）
--    SELECT p.poi_type, COUNT(*)
--    FROM parcels pl
--    JOIN pois p ON ST_DWithin(pl.geom::geography, p.geom::geography, 800)
--    WHERE pl.parcel_code = 'A-01'
--    GROUP BY p.poi_type;
--
-- ③ 地块与规划控制区叠加分析（三区三线体检模块）
--    SELECT pl.parcel_code, z.zone_name, z.zone_type,
--           ST_Area(ST_Intersection(pl.geom, z.geom)::geography) / 10000 AS overlap_ha
--    FROM parcels pl
--    JOIN planning_control z ON ST_Intersects(pl.geom, z.geom)
--    WHERE pl.parcel_code = 'C-01';
-- ===================================================================
