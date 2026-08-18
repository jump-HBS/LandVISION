-- ===================================================================
-- LandVISION 业务演示数据（由 tools/generate_seed.py 自动生成）
-- 演示区：武汉市洪山区（420111）；用地性质遵循 GB/T 21010-2017 一级类
-- 执行顺序：00_create_database.sql → 01_init_schema.sql → 03_regions.sql → 本文件
-- ===================================================================

BEGIN;

DELETE FROM planning_control;
DELETE FROM pois;
DELETE FROM parcels;

-- ---------- 10 个示例地块（12 大类用地覆盖 10 类） ----------
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('A-01', '南湖耕地示范片', '耕地', '武汉市洪山区', '420111', 485175.72, NULL, NULL, '2026-01-12', ST_GeomFromText('POLYGON((114.3272 30.504, 114.3347 30.5039, 114.3348 30.51, 114.3273 30.5101, 114.3272 30.504))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('A-02', '光谷商务中心', '商服用地', '武汉市洪山区', '420111', 485175.72, 4.0, 120, '2026-02-03', ST_GeomFromText('POLYGON((114.3367 30.504, 114.3442 30.5039, 114.3443 30.51, 114.3368 30.5101, 114.3367 30.504))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('A-03', '滨江住宅区', '住宅用地', '武汉市洪山区', '420111', 485175.72, 2.5, 80, '2026-02-25', ST_GeomFromText('POLYGON((114.3462 30.504, 114.3537 30.5039, 114.3538 30.51, 114.3463 30.5101, 114.3462 30.504))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('B-01', '高新制造园', '工矿仓储用地', '武汉市洪山区', '420111', 485175.73, 1.5, 30, '2026-03-18', ST_GeomFromText('POLYGON((114.3272 30.496, 114.3347 30.4959, 114.3348 30.502, 114.3273 30.5021, 114.3272 30.496))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('B-02', '市民服务中心', '公共管理与公共服务用地', '武汉市洪山区', '420111', 485175.73, 2.0, 40, '2026-04-09', ST_GeomFromText('POLYGON((114.3367 30.496, 114.3442 30.4959, 114.3443 30.502, 114.3368 30.5021, 114.3367 30.496))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('B-03', '南湖生态园', '园地', '武汉市洪山区', '420111', 485175.73, NULL, NULL, '2026-05-21', ST_GeomFromText('POLYGON((114.3462 30.496, 114.3537 30.4959, 114.3538 30.502, 114.3463 30.5021, 114.3462 30.496))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('C-01', '城市森林公园', '林地', '武汉市洪山区', '420111', 485175.72, NULL, NULL, '2026-06-30', ST_GeomFromText('POLYGON((114.3272 30.488, 114.3347 30.4879, 114.3348 30.494, 114.3273 30.4941, 114.3272 30.488))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('C-02', '长江生态绿地', '草地', '武汉市洪山区', '420111', 485175.72, NULL, NULL, '2026-07-15', ST_GeomFromText('POLYGON((114.3367 30.488, 114.3442 30.4879, 114.3443 30.494, 114.3368 30.4941, 114.3367 30.488))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('C-03', '南站交通枢纽', '交通运输用地', '武汉市洪山区', '420111', 485175.72, 0.5, 20, '2026-08-05', ST_GeomFromText('POLYGON((114.3462 30.488, 114.3537 30.4879, 114.3538 30.494, 114.3463 30.4941, 114.3462 30.488))', 4326));
INSERT INTO parcels (parcel_code, name, land_use, district, region_code, area_sqm, far_limit, height_limit, created_at, geom) VALUES ('D-01', '东湖水域保护区', '水域及水利设施用地', '武汉市洪山区', '420111', 485175.72, NULL, NULL, '2026-08-12', ST_GeomFromText('POLYGON((114.3322 30.512, 114.3397 30.5119, 114.3398 30.518, 114.3323 30.5181, 114.3322 30.512))', 4326));

-- ---------- 20 个兴趣点 ----------
INSERT INTO pois (name, poi_type, geom) VALUES ('地铁站A', '交通', ST_GeomFromText('POINT(114.339 30.5045)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('地铁站B', '交通', ST_GeomFromText('POINT(114.349 30.496)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('公交枢纽', '交通', ST_GeomFromText('POINT(114.346 30.511)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('高铁站', '交通', ST_GeomFromText('POINT(114.353 30.489)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('万象城', '商业', ST_GeomFromText('POINT(114.3415 30.5055)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('银泰中心', '商业', ST_GeomFromText('POINT(114.346 30.5035)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('生鲜超市', '商业', ST_GeomFromText('POINT(114.3495 30.5005)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('家居城', '商业', ST_GeomFromText('POINT(114.3385 30.4945)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('第一中学', '教育', ST_GeomFromText('POINT(114.3455 30.5105)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('实验小学', '教育', ST_GeomFromText('POINT(114.335 30.5)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('职业技术学院', '教育', ST_GeomFromText('POINT(114.352 30.4935)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('市人民医院', '医疗', ST_GeomFromText('POINT(114.3435 30.5005)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('社区诊所', '医疗', ST_GeomFromText('POINT(114.353 30.5075)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('妇幼保健院', '医疗', ST_GeomFromText('POINT(114.3365 30.5095)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('中央公园', '休闲', ST_GeomFromText('POINT(114.34 30.4985)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('体育中心', '休闲', ST_GeomFromText('POINT(114.349 30.506)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('滨江绿道', '休闲', ST_GeomFromText('POINT(114.354 30.502)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('文化馆', '休闲', ST_GeomFromText('POINT(114.338 30.5015)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('图书馆', '休闲', ST_GeomFromText('POINT(114.3475 30.5025)', 4326));
INSERT INTO pois (name, poi_type, geom) VALUES ('电影院', '休闲', ST_GeomFromText('POINT(114.3455 30.5075)', 4326));

-- ---------- 3 条三区三线控制线（标准英文类型代码） ----------
INSERT INTO planning_control (zone_name, zone_type, zone_level, control_desc, geom) VALUES ('长江沿岸生态保护红线', 'ecological_red_line', '国家级', '禁止任何开发建设活动，严格管控', ST_GeomFromText('POLYGON((114.328 30.482, 114.358 30.482, 114.358 30.49, 114.347 30.491, 114.333 30.4905, 114.328 30.487, 114.328 30.482))', 4326));
INSERT INTO planning_control (zone_name, zone_type, zone_level, control_desc, geom) VALUES ('南部基本农田保护区', 'permanent_basic_farmland', '国家级', '严禁非农化、非粮化', ST_GeomFromText('POLYGON((114.352 30.483, 114.364 30.483, 114.364 30.493, 114.352 30.493, 114.352 30.483))', 4326));
INSERT INTO planning_control (zone_name, zone_type, zone_level, control_desc, geom) VALUES ('洪山区城镇开发边界', 'urban_growth_boundary', '市级', '开发建设活动应在边界内进行，界外需专题论证', ST_GeomFromText('POLYGON((114.326 30.484, 114.36 30.484, 114.36 30.514, 114.326 30.514, 114.326 30.484))', 4326));

COMMIT;
