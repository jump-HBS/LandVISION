-- ===================================================================
-- LandVISION —— 00 创建数据库与启用 PostGIS 扩展
-- 前置：已安装 PostgreSQL 16 + PostGIS 3.x（见《外部工作清单.md》第 1 节）
-- 执行方式：pgAdmin 中选中服务器执行，或命令行 psql -U postgres -f 本文件
-- ===================================================================

-- 1. 创建数据库（PostGIS 是数据库级扩展，需先有库）
--    注意：CREATE DATABASE 不能在事务块内执行
CREATE DATABASE landvision
    WITH ENCODING = 'UTF8'
    LC_COLLATE = 'Chinese (Simplified)_China.936'
    LC_CTYPE = 'Chinese (Simplified)_China.936'
    TEMPLATE = template0;

-- 2. 切换到 landvision 数据库后再执行以下语句：
--    pgAdmin 中：右键 landvision -> Query Tool
--    命令行：psql -U postgres -d landvision

-- 3. 启用空间扩展（PostGIS 提供 geometry 类型与 ST_* 函数）
CREATE EXTENSION IF NOT EXISTS postgis;

-- 4. 验证
SELECT PostGIS_Version();        -- 应返回 3.x 版本号
SELECT ST_Area(ST_Buffer(ST_Point(0, 0), 1));  -- 返回数字即扩展可用

-- 5. 下一步：执行 01_init_schema.sql 建表，再执行 02_seed_data.sql 灌入演示数据
