# ============================================================
# LandVISION v3.0 POSTGIS 实测脚本（对 http://127.0.0.1:8000 执行）
# 覆盖：POI 导入校验/导入、上传强制项目校验、框选删除、
#       严格范围聚合、适宜性矛盾端点、项目清理
# 注意：JSON 请求体一律用无 BOM 的 UTF-8 文件（curl --data-binary @file）
# ============================================================
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$b = "http://127.0.0.1:8000"
$tmp = Join-Path $env:TEMP "lv3test"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$Utf8NoBom = [System.Text.UTF8Encoding]::new($false)

function WJson([string]$path, [string]$text) {
    [System.IO.File]::WriteAllText($path, $text, $Utf8NoBom)
}

function Assert($cond, $msg) {
    if (-not $cond) { throw "ASSERT FAILED: $msg" }
    Write-Output "PASS: $msg"
}

# ---------- 1. 点要素 SHP zip（pyshp 生成） ----------
@"
import io, zipfile, shapefile
shp = io.BytesIO(); shx = io.BytesIO(); dbf = io.BytesIO()
w = shapefile.Writer(shp=shp, shx=shx, dbf=dbf, encoding='utf-8')
w.field('NAME', 'C', 50)
w.field('TYPE', 'C', 50)
w.point(114.339, 30.5045); w.record('实测POI站', '交通')
w.point(114.346, 30.5035); w.record('实测商场', '商业')
w.close()
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('pois.shp', shp.getvalue())
    zf.writestr('pois.shx', shx.getvalue())
    zf.writestr('pois.dbf', dbf.getvalue())
    zf.writestr('pois.prj', 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984"],PRIMEM["Greenwich",0],UNIT["Degree",0.0174532925199433]]')
open(r'$tmp\pois.zip', 'wb').write(buf.getvalue())
print('zip ok')
"@ | Out-File -Encoding utf8 "$tmp\mkzip.py"
& ..\venv\Scripts\python.exe "$tmp\mkzip.py" | Out-Null

# ---------- 2. 上传强制项目校验（缺失 422 / 不存在 404） ----------
$code = curl.exe -s -o "$tmp\r1.json" -w "%{http_code}" -X POST "$b/api/pois/import" -F "file=@$tmp\pois.zip"
Assert ($code -eq "422") "POI 导入无项目 -> 422（实际 $code）"
$code = curl.exe -s -o "$tmp\r2.json" -w "%{http_code}" -X POST "$b/api/pois/import" -F "file=@$tmp\pois.zip" -F "project_id=99999"
Assert ($code -eq "404") "POI 导入项目不存在 -> 404（实际 $code）"
$code = curl.exe -s -o "$tmp\r3.json" -w "%{http_code}" -X POST "$b/api/parcels/import-shp" -F "file=@$tmp\pois.zip" -F "project_id=99999"
Assert ($code -eq "404") "地块导入项目不存在 -> 404（实际 $code）"
$code = curl.exe -s -o "$tmp\r4.json" -w "%{http_code}" -X POST "$b/api/analysis/transition/import-shp" -F "file=@$tmp\pois.zip" -F "period=base" -F "project_id=99999"
Assert ($code -eq "404") "期次导入项目不存在 -> 404（实际 $code）"
$code = curl.exe -s -o "$tmp\r5.json" -w "%{http_code}" -X POST "$b/api/planning/zones/import-shp" -F "file=@$tmp\pois.zip" -F "zone_type=urban_growth_boundary" -F "project_id=99999"
Assert ($code -eq "404") "控制线导入项目不存在 -> 404（实际 $code）"

# ---------- 3. 建项目（范围覆盖演示区 1-10 号地块） ----------
$scopeJson = '{"type":"Polygon","coordinates":[[[114.325,30.485],[114.356,30.485],[114.356,30.52],[114.325,30.52],[114.325,30.485]]]}'
$projBody = @{ name = "v3.0实测项目"; base_year = 2020; current_year = 2026; scope = ($scopeJson | ConvertFrom-Json) } | ConvertTo-Json -Depth 10
WJson "$tmp\proj.json" $projBody
$projResp = curl.exe -s -X POST "$b/api/projects" -H "Content-Type: application/json" --data-binary "@$tmp\proj.json"
$projId = ($projResp | ConvertFrom-Json).id
Assert ($projId -gt 0) "项目创建成功 id=$projId"

# ---------- 4. POI 点要素导入（关联项目） ----------
$poiResp = curl.exe -s -X POST "$b/api/pois/import" -F "file=@$tmp\pois.zip" -F "project_id=$projId" -F "period=base"
$poi = $poiResp | ConvertFrom-Json
Assert ($poi.imported -eq 2) "POI 导入成功 2 条（实际 $($poi.imported)）"
Assert ($poi.project_id -eq $projId) "POI 已关联项目"

# ---------- 5. 框选删除（新建 2 宗测试地块，锁定 1 宗） ----------
$parcelA = '{"parcel_code":"V3T-A","name":"v3实测地块A","land_use":"耕地","geometry":{"type":"Polygon","coordinates":[[[113.70,29.80],[113.71,29.80],[113.71,29.81],[113.70,29.81],[113.70,29.80]]]}}'
$parcelB = '{"parcel_code":"V3T-B","name":"v3实测地块B","land_use":"园地","geometry":{"type":"Polygon","coordinates":[[[113.72,29.80],[113.73,29.80],[113.73,29.81],[113.72,29.81],[113.72,29.80]]]}}'
WJson "$tmp\pa.json" $parcelA
WJson "$tmp\pb.json" $parcelB
$idA = (curl.exe -s -X POST "$b/api/parcels" -H "Content-Type: application/json" --data-binary "@$tmp\pa.json" | ConvertFrom-Json).id
$idB = (curl.exe -s -X POST "$b/api/parcels" -H "Content-Type: application/json" --data-binary "@$tmp\pb.json" | ConvertFrom-Json).id
WJson "$tmp\lock.json" '{"locked":true}'
$lockCode = curl.exe -s -o "$tmp\lockresp.json" -w "%{http_code}" -X POST "$b/api/parcels/$idA/lock" -H "Content-Type: application/json" --data-binary "@$tmp\lock.json"
Assert ($lockCode -eq "200") "锁定地块 A 成功（$lockCode）"
WJson "$tmp\del.json" '{"geometry":{"type":"Polygon","coordinates":[[[113.69,29.79],[113.74,29.79],[113.74,29.82],[113.69,29.82],[113.69,29.79]]]},"mode":"intersects"}'
$del = curl.exe -s -X POST "$b/api/parcels/delete-by-geometry" -H "Content-Type: application/json" --data-binary "@$tmp\del.json" | ConvertFrom-Json
Assert (@($del.deleted) -contains $idB) "框选删除删除了未锁定地块 B"
Assert (@($del.locked | ForEach-Object { $_.id }) -contains $idA) "框选删除跳过了锁定地块 A"
WJson "$tmp\unlock.json" '{"locked":false}'
curl.exe -s -X POST "$b/api/parcels/$idA/lock" -H "Content-Type: application/json" --data-binary "@$tmp\unlock.json" | Out-Null
curl.exe -s -X DELETE "$b/api/parcels/$idA" | Out-Null

# ---------- 6. 各模块分析（项目持久化） ----------
WJson "$tmp\acc.json" (@{ facility_types = @(); radius_m = 800; project_id = $projId } | ConvertTo-Json)
$acc = curl.exe -s -X POST "$b/api/analysis/accessibility/analyze" -H "Content-Type: application/json" --data-binary "@$tmp\acc.json" | ConvertFrom-Json
Assert ($acc.parcel_total -gt 0) "可达性分析完成（地块 $($acc.parcel_total)，持久化=$($acc.persisted)）"

WJson "$tmp\sui.json" (@{ target = "建设用地适宜性"; weights = @{}; scope = ($scopeJson | ConvertFrom-Json); project_id = $projId } | ConvertTo-Json -Depth 10)
$sui = curl.exe -s -X POST "$b/api/analysis/suitability/evaluate" -H "Content-Type: application/json" --data-binary "@$tmp\sui.json" | ConvertFrom-Json
$suiCells = @($sui.cells_geojson.features).Count
Assert ($suiCells -gt 0) "适宜性评价完成（格网 $suiCells）"

WJson "$tmp\rv.json" (@{ project_id = $projId } | ConvertTo-Json)
$rv = curl.exe -s -X POST "$b/api/planning/review" -H "Content-Type: application/json" --data-binary "@$tmp\rv.json" | ConvertFrom-Json
Assert ($rv.parcel_count -gt 0) "批量体检完成（地块 $($rv.parcel_count)）"

# ---------- 7. 驾驶舱：全项目 vs 严格子范围 ----------
WJson "$tmp\ds.json" (@{ project_id = $projId } | ConvertTo-Json)
$ds = curl.exe -s -X POST "$b/api/dashboard/summary" -H "Content-Type: application/json" --data-binary "@$tmp\ds.json" | ConvertFrom-Json
Assert ($ds.suitability.cell_total -gt 0) "驾驶舱持久化适宜性数据可用（格网 $($ds.suitability.cell_total)）"
Assert ($ds.planning_review.review_parcel_count -gt 0) "驾驶舱持久化体检数据可用（地块 $($ds.planning_review.review_parcel_count)）"

$farJson = '{"type":"Polygon","coordinates":[[[114.325,30.485],[114.327,30.485],[114.327,30.49],[114.325,30.49],[114.325,30.485]]]}'
WJson "$tmp\sub.json" (@{ project_id = $projId; scope = ($farJson | ConvertFrom-Json); scope_label = "远角子范围" } | ConvertTo-Json -Depth 10)
$sub = curl.exe -s -X POST "$b/api/dashboard/summary" -H "Content-Type: application/json" --data-binary "@$tmp\sub.json" | ConvertFrom-Json
Assert ($sub.scope.strict -eq $true) "驾驶舱标注严格范围聚合"
Assert ($sub.overview.parcel_total -eq 0) "子范围内地块数收敛为 0（实际 $($sub.overview.parcel_total)）"
Assert ($sub.overview.poi_total -eq 0) "子范围内 POI 收敛为 0（实际 $($sub.overview.poi_total)）"
Assert ($sub.planning_review.review_parcel_count -eq 0) "子范围内体检记录收敛为 0（实际 $($sub.planning_review.review_parcel_count)）"
Assert ($sub.accessibility.parcel_total -eq 0) "子范围内可达性地块收敛为 0（实际 $($sub.accessibility.parcel_total)）"

# ---------- 8. 适宜性矛盾端点 ----------
$cf = curl.exe -s "$b/api/analysis/suitability/conflicts?project_id=$projId" | ConvertFrom-Json
Assert ($null -ne $cf) "适宜性矛盾端点可用（conflicts=$(@($cf.conflicts).Count)）"

# ---------- 9. 清理 ----------
$code = curl.exe -s -o "$tmp\clean.json" -w "%{http_code}" -X DELETE "$b/api/projects/$projId"
Assert ($code -eq "200") "项目删除成功（$code）"
@"
import httpx
b = 'http://127.0.0.1:8000'
r = httpx.get(f'{b}/api/pois', params={'page_size': 100}).json()
for it in r.get('items', []):
    if '实测' in (it.get('name') or ''):
        httpx.delete(f"{b}/api/pois/{it['id']}")
print('poi cleanup done')
"@ | Out-File -Encoding utf8 "$tmp\poiclean.py"
& ..\venv\Scripts\python.exe "$tmp\poiclean.py" | Out-Null

Write-Output "=== v3.0 POSTGIS 实测全部通过 ==="
