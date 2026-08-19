<template>
  <div class="page-fullmap">
    <!-- 全屏地图（批量选择模式 + 保存绘制） -->
    <MapView
      ref="mapRef"
      :parcels="mapParcelsGeojson"
      :pois="store.poisGeojson"
      :zones="store.zonesGeojson"
      :region-boundary="boundaryGeojson"
      :highlight-id="highlightId"
      :batch-select="batchMode"
      :show-save-drawing="true"
      enable-selection
      selection-delete
      selection-collect-all
      @parcel-click="onMapClick"
      @parcel-detail="onParcelDetail"
      @poi-click="onPoiMapClick"
      @poi-detail="onPoiDetail"
      @region-select="onRegionSelect"
      @region-locate="onRegionLocate"
      @batch-selection="onBatchSelection"
      @save-drawing="onSaveDrawing"
      @selection-delete="onSelectionDelete"
    />

    <!-- v4.0：圈选删除使用提示（工具条位于地图左上角：框选/圈选/多边形） -->
    <div v-if="panelOpen !== 'table'" class="map-widget-draw-hint" @click="togglePanel('table')">
      圈选删除：点击地图左上角 <b>框选</b>/<b>圈选</b>/<b>多边形</b> 工具绘制范围，
      自动统计范围内地块 + 兴趣点 + 控制线，点击「删除选中要素」一键清理
    </div>

    <!-- 左侧：图标按钮 -->
    <button class="page-icon-btn icon-left" :class="{ active: panelOpen === 'table' }"
            title="地块列表" @click="togglePanel('table')">
      <el-icon :size="18"><Grid /></el-icon>
    </button>
    <button class="page-icon-btn icon-left2" title="导入 SHP" @click="openImport">
      <el-icon :size="18"><UploadFilled /></el-icon>
    </button>
    <button class="page-icon-btn icon-left3" :class="{ active: batchMode }"
            title="批量选择（点击地图要素进入选中集）" @click="toggleBatchMode">
      <el-icon :size="18"><Finished /></el-icon>
    </button>
    <button class="page-icon-btn icon-left4" :class="{ active: panelOpen === 'features' }"
            title="标注图层（地图绘制持久化）" @click="togglePanel('features')">
      <el-icon :size="18"><EditPen /></el-icon>
    </button>
    <button class="page-icon-btn icon-left5" :class="{ active: panelOpen === 'pois' }"
            title="兴趣点管理（点要素 SHP 导入/删除）" @click="togglePanel('pois')">
      <el-icon :size="18"><Place /></el-icon>
    </button>

    <!-- 左侧展开：地块列表面板 -->
    <div v-if="panelOpen === 'table'" class="page-panel panel-left glass-panel">
      <div class="panel-title">地块列表（期次显性化）</div>
      <div class="filter-row">
        <el-checkbox-group v-model="showPeriods" size="small" @change="loadPage(1)">
          <el-checkbox-button label="base">基期</el-checkbox-button>
          <el-checkbox-button label="current">末期</el-checkbox-button>
          <el-checkbox-button label="none">无期次</el-checkbox-button>
        </el-checkbox-group>
        <el-input v-model="query" placeholder="搜索名称/编号" clearable size="small" style="width:130px" @keyup.enter="loadPage(1)" />
        <el-select v-model="landUse" placeholder="用地类型" clearable filterable size="small" style="width:120px" @change="loadPage(1)">
          <el-option v-for="lu in LAND_USE_ORDER" :key="lu" :label="lu" :value="lu" />
        </el-select>
        <el-button size="small" type="primary" @click="loadPage(1)">查询</el-button>
        <el-button size="small" type="success" @click="openCreate">新增</el-button>
        <el-button size="small" type="danger" plain :disabled="!selectedRows.length"
                   @click="onBatchDelete">批量删{{ selectedRows.length ? `(${selectedRows.length})` : '' }}</el-button>
      </div>
      <div class="scope-hint">
        勾选即显示对应期次（表格 + 地图同步，基期实线 / 末期虚线描边）；全部取消则隐藏地块图层。
      </div>
      <el-tag v-if="activeRegion" closable size="small" class="mb" @close="clearRegionFilter">
        当前行政区：{{ activeRegion.name }}（{{ activeRegion.code }}）
      </el-tag>

      <el-skeleton v-if="loading && !loadedOnce" :rows="8" animated />
      <template v-else>
        <el-empty v-if="!store.parcels.length && !loading" description="暂无地块数据">
          <el-button type="primary" size="small" @click="loadPage(1)">重新加载</el-button>
        </el-empty>
        <el-table
          v-else :data="store.parcels" highlight-current-row height="400"
          v-loading="loading" @row-click="onRowClick"
          @selection-change="(rows) => (selectedRows = rows)"
        >
          <el-table-column type="selection" width="38" />
          <el-table-column prop="parcel_code" label="编号" width="80" />
          <el-table-column prop="name" label="名称" min-width="104" show-overflow-tooltip />
          <el-table-column label="期次" width="62" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.period === 'current' ? 'warning' : 'success'" effect="plain">
                {{ row.period === 'current' ? '末期' : '基期' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="land_use" label="用地类型" width="88" show-overflow-tooltip>
            <template #default="{ row }">
              <el-tag size="small" :color="LAND_USE_COLORS[row.land_use] || undefined" style="border:none;color:#fff">
                {{ row.land_use }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="area_sqm" label="公顷" width="74" align="right">
            <template #default="{ row }">{{ (row.area_sqm / 10000).toFixed(2) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="{ row }">
              <el-button size="small" link type="primary" @click.stop="onRowClick(row)">查看</el-button>
              <el-button size="small" link :type="row.locked ? 'warning' : 'info'" @click.stop="toggleLock(row)">
                {{ row.locked ? '解锁' : '锁定' }}
              </el-button>
              <el-button size="small" link type="danger" @click.stop="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          v-if="total > pageSize"
          class="mt" background small layout="total, prev, pager, next"
          :total="total" :page-size="pageSize" :current-page="page"
          @current-change="loadPage"
        />
      </template>
    </div>

    <!-- 左侧展开：地图标注面板（绘制数据持久化） -->
    <div v-if="panelOpen === 'features'" class="page-panel panel-left glass-panel">
      <div class="panel-title">地图标注（绘制数据保存至数据库）</div>
      <div class="scope-hint">
        在地图上使用左侧工具绘制点/线/面（或测量）后，点击地图上的「保存当前绘制」按钮入库；标注支持锁定与批量删除。
      </div>
      <el-table :data="mapFeatures" size="small" max-height="420" v-loading="featuresLoading">
        <el-table-column prop="name" label="名称" min-width="100" show-overflow-tooltip />
        <el-table-column prop="feature_type" label="类型" width="64">
          <template #default="{ row }">{{ { point: '点', line: '线', polygon: '面' }[row.feature_type] || row.feature_type }}</template>
        </el-table-column>
        <el-table-column label="锁定" width="56" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.locked" size="small" type="danger">锁定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link :type="row.locked ? 'warning' : 'info'" @click="toggleFeatureLock(row)">
              {{ row.locked ? '解锁' : '锁定' }}
            </el-button>
            <el-button size="small" link type="danger" @click="onDeleteFeature(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 左侧展开：兴趣点管理面板（v3.0：点面分离，POI 仅接受点要素） -->
    <div v-if="panelOpen === 'pois'" class="page-panel panel-left glass-panel">
      <div class="panel-title">兴趣点管理（POI）</div>
      <div class="scope-hint">
        兴趣点为点要素（交通/商业/教育/医疗/休闲）。SHP 导入时仅接受点要素，面要素请使用「导入 SHP」地块入口；上传数据必须关联分析项目。
      </div>
      <div class="filter-row">
        <el-select v-model="poiType" placeholder="全部类型" clearable size="small" style="width:110px" @change="loadPois">
          <el-option v-for="t in ['交通', '商业', '教育', '医疗', '休闲']" :key="t" :label="t" :value="t" />
        </el-select>
        <el-button size="small" type="primary" @click="openPoiImport">导入 POI SHP</el-button>
        <span class="poi-total">共 {{ poiTotal }} 个</span>
      </div>
      <el-table :data="poiItems" size="small" max-height="420" v-loading="poiLoading">
        <el-table-column prop="name" label="名称" min-width="120" show-overflow-tooltip />
        <el-table-column prop="poi_type" label="类型" width="70">
          <template #default="{ row }">
            <el-tag size="small" :color="POI_COLORS[row.poi_type] || undefined" style="border:none;color:#fff">
              {{ row.poi_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="locked" label="锁定" width="56" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.locked" size="small" type="danger">锁定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button size="small" link :type="row.locked ? 'warning' : 'info'" @click="togglePoiLock(row)">
              {{ row.locked ? '解锁' : '锁定' }}
            </el-button>
            <el-button size="small" link type="danger" @click="onDeletePoi(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-if="poiTotal > poiPageSize"
        class="mt" background small layout="total, prev, pager, next"
        :total="poiTotal" :page-size="poiPageSize" :current-page="poiPage"
        @current-change="loadPois"
      />
    </div>

    <!-- 详情抽屉 -->
    <ParcelInfo
      v-model="drawerVisible"
      :parcel="store.selectedParcel"
      :planning="planningResult"
      :project-name="projectName"
      @fly-to="flyToSelected"
      @goto-planning="gotoPlanning"
      @goto-transition="gotoTransition"
    />

    <!-- v4.0：POI 详情对话框（地图点要素点击查看属性） -->
    <el-dialog v-model="poiDetailVisible" title="兴趣点详情" width="420px">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="名称">{{ poiDetail.name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="类型">
          <el-tag size="small" :color="POI_COLORS[poiDetail.poi_type] || undefined" style="border:none;color:#fff">
            {{ poiDetail.poi_type || '-' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="ID">{{ poiDetail.id }}</el-descriptions-item>
        <el-descriptions-item label="锁定状态">
          <el-tag v-if="poiDetail.locked" size="small" type="danger">已锁定（不可删除）</el-tag>
          <el-tag v-else size="small" type="success">未锁定</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button @click="flyToPoi">地图定位</el-button>
        <el-button :type="poiDetail.locked ? 'warning' : 'info'" @click="togglePoiLock(poiDetail)">
          {{ poiDetail.locked ? '解除锁定' : '锁定' }}
        </el-button>
        <el-button type="danger" :disabled="poiDetail.locked" @click="onDeletePoi(poiDetail)">删除</el-button>
        <el-button @click="poiDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 新增对话框 -->
    <el-dialog v-model="dialogVisible" title="新增地块" width="520px">
      <el-form :model="form" label-width="96px">
        <el-form-item label="地块编号"><el-input v-model="form.parcel_code" placeholder="如 E-01" /></el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="用地类型">
          <el-select v-model="form.land_use" filterable style="width:100%">
            <el-option v-for="lu in LAND_USE_ORDER" :key="lu" :label="lu" :value="lu" />
          </el-select>
        </el-form-item>
        <el-form-item label="期次">
          <el-radio-group v-model="form.period">
            <el-radio-button label="base">基期</el-radio-button>
            <el-radio-button label="current">末期</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="form.project_id" clearable style="width:100%" placeholder="选择分析项目（可选）">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="行政区名称">
          <el-input v-model="form.district" placeholder="如 武汉市洪山区" />
        </el-form-item>
        <el-form-item label="区划代码">
          <el-input v-model="form.region_code" placeholder="如 420111" />
        </el-form-item>
        <el-form-item label="面积(㎡)"><el-input-number v-model="form.area_sqm" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="容积率"><el-input-number v-model="form.far_limit" :min="0" :step="0.1" style="width:100%" /></el-form-item>
        <el-form-item label="限高(m)"><el-input-number v-model="form.height_limit" :min="0" style="width:100%" /></el-form-item>
        <el-form-item label="几何(GeoJSON)">
          <el-input v-model="form.geometryText" type="textarea" :rows="4" placeholder="Polygon GeoJSON，可点击下方按钮自动生成" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="fillDefaultGeometry">生成演示几何</el-button>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>

    <!-- SHP 导入对话框（项目 + 期次必选） -->
    <el-dialog v-model="importVisible" title="导入 SHP 地块数据" width="560px">
      <el-alert type="info" :closable="false" class="mb"
        title="要求：zip 压缩包，内含同名 .shp/.shx/.dbf（建议带 .prj）；坐标系为经纬度（WGS84/CGCS2000，单位：度）；要素为面（Polygon）。投影坐标需先用 GDAL 转换，中文编码 UTF-8/GBK 均可自动识别。" />
      <el-upload drag :auto-upload="false" :limit="1" accept=".zip"
                 :on-change="onFileChange" :on-remove="() => (importFile = null)">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 SHP zip 拖到此处，或<em>点击选择文件</em></div>
      </el-upload>
      <el-form label-width="110px" class="mt">
        <el-form-item label="期次（必选）">
          <el-radio-group v-model="importOpts.period">
            <el-radio-button label="base">基期</el-radio-button>
            <el-radio-button label="current">末期</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属项目（必选）">
          <el-select v-model="importOpts.project_id" style="width:100%" placeholder="选择分析项目（必选，无项目请先在顶栏创建）">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称字段"><el-input v-model="importOpts.name_field" placeholder="自动识别（如 XMMC/MC/name）" /></el-form-item>
        <el-form-item label="用地类型字段"><el-input v-model="importOpts.land_use_field" placeholder="自动识别（如 DLMC/地类名称）" /></el-form-item>
        <el-form-item label="行政区字段"><el-input v-model="importOpts.region_field" placeholder="自动识别（如 XZQMC）" /></el-form-item>
        <el-form-item label="区划代码"><el-input v-model="importOpts.region_code" placeholder="如 420111（可选）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="importing" :disabled="!importFile" @click="doImport">
          开始导入
        </el-button>
      </template>

      <!-- 导入结果明细 -->
      <template v-if="importResult">
        <el-alert class="mt" :type="importResult.imported > 0 ? 'success' : 'warning'" :closable="false"
          :title="`导入完成：成功 ${importResult.imported} 条，跳过 ${importResult.skipped.length} 条`" />
        <div v-if="importResult.skipped.length" class="mt" style="max-height:180px;overflow-y:auto">
          <div v-for="(s, i) in importResult.skipped.slice(0, 20)" :key="i" class="skip-row">
            <el-tag size="small" type="warning">{{ s.name || '未知要素' }}</el-tag>
            <span class="skip-reason">{{ s.reason }}</span>
          </div>
          <div v-if="importResult.skipped.length > 20" class="skip-more">
            其余 {{ importResult.skipped.length - 20 }} 条已省略
          </div>
        </div>
        <div v-if="importResult.imported > 0" class="mt">
          <el-button size="small" type="success" @click="afterImportRefresh">刷新列表与地图</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- POI 导入对话框（v3.0：仅点要素，项目必选） -->
    <el-dialog v-model="poiImportVisible" title="导入 SHP 兴趣点（POI）" width="560px">
      <el-alert type="info" :closable="false" class="mb"
        title="要求：zip 压缩包，内含同名 .shp/.shx/.dbf（建议带 .prj）；坐标系为经纬度（WGS84/CGCS2000）；要素必须为点（Point）。面要素请使用「导入 SHP」地块入口；上传数据必须关联分析项目。" />
      <el-upload drag :auto-upload="false" :limit="1" accept=".zip"
                 :on-change="onPoiFileChange" :on-remove="() => (poiImportFile = null)">
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">将 POI 点要素 SHP zip 拖到此处，或<em>点击选择文件</em></div>
      </el-upload>
      <el-form label-width="110px" class="mt">
        <el-form-item label="期次">
          <el-radio-group v-model="poiImportOpts.period">
            <el-radio-button label="base">基期</el-radio-button>
            <el-radio-button label="current">末期</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="所属项目（必选）">
          <el-select v-model="poiImportOpts.project_id" style="width:100%" placeholder="选择分析项目（必选，无项目请先在顶栏创建）">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称字段"><el-input v-model="poiImportOpts.name_field" placeholder="自动识别（如 NAME/name）" /></el-form-item>
        <el-form-item label="类型字段"><el-input v-model="poiImportOpts.type_field" placeholder="自动识别（如 TYPE/类型）" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="poiImportVisible = false">取消</el-button>
        <el-button type="primary" :loading="poiImporting" :disabled="!poiImportFile" @click="doPoiImport">
          开始导入
        </el-button>
      </template>

      <!-- 导入结果明细 -->
      <template v-if="poiImportResult">
        <el-alert class="mt" :type="poiImportResult.imported > 0 ? 'success' : 'warning'" :closable="false"
          :title="`导入完成：成功 ${poiImportResult.imported} 条，跳过 ${poiImportResult.skipped.length} 条`" />
        <div v-if="poiImportResult.skipped.length" class="mt" style="max-height:180px;overflow-y:auto">
          <div v-for="(s, i) in poiImportResult.skipped.slice(0, 20)" :key="i" class="skip-row">
            <el-tag size="small" type="warning">{{ s.name || '未知要素' }}</el-tag>
            <span class="skip-reason">{{ s.reason }}</span>
          </div>
          <div v-if="poiImportResult.skipped.length > 20" class="skip-more">
            其余 {{ poiImportResult.skipped.length - 20 }} 条已省略
          </div>
        </div>
        <div v-if="poiImportResult.imported > 0" class="mt">
          <el-button size="small" type="success" @click="afterPoiImportRefresh">刷新列表与地图</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 保存绘制对话框 -->
    <el-dialog v-model="saveDrawVisible" title="保存地图绘制" width="440px">
      <el-form label-width="90px">
        <el-form-item label="标注名称">
          <el-input v-model="saveDrawForm.name" placeholder="如：巡查标注点 01" />
        </el-form-item>
        <el-form-item label="类型">
          <el-tag size="small">{{ { point: '点', line: '线', polygon: '面' }[saveDrawForm.feature_type] || '-' }}</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="saveDrawVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDraw" @click="doSaveDrawing">保存入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * ParcelManagementView —— 地块管理（v4.0）
 * 期次显示开关（勾选即显示：基期实线/末期虚线，表格+地图同步）/ 上传关联项目与期次 /
 * 地图圈选删除（框选/圈选/多边形 → 范围内地块+POI+控制线一键删除，锁定跳过）/
 * POI 点要素点击查看属性与删除 / 地图绘制持久化（标注面板 map_features）/
 * 详情抽屉（期次/项目/判定依据/模块跳转）。
 */
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { useParcelStore } from '../stores/parcel'
import { useUiStore } from '../stores/ui'
import {
  createParcel, deleteParcel, lockParcel, batchDeleteParcels,
  batchDeletePois, batchDeleteZones,
  importParcelsShp, importPoisShp, getPois, deletePoi, lockPoi,
  checkParcel, getRegion, getProjects,
  getMapFeatures, createMapFeature, deleteMapFeature, lockMapFeature,
} from '../api'
import { LAND_USE_COLORS, LAND_USE_ORDER, POI_COLORS } from '../utils/colors'
import MapView from '../components/MapView.vue'
import ParcelInfo from '../components/ParcelInfo.vue'

const store = useParcelStore()
const ui = useUiStore()
const route = useRoute()
const router = useRouter()

const mapRef = ref(null)
const boundaryGeojson = ref(null)
const panelOpen = ref(null)
const query = ref('')
const landUse = ref('')
// v4.0：期次显示开关（勾选即显示该期次，表格 + 地图同步；全部取消 = 隐藏地块图层）
const showPeriods = ref(['base', 'current'])
const page = ref(1)
const pageSize = ref(10)
const total = ref(0)
const loading = ref(false)
const loadedOnce = ref(false)
const highlightId = ref(null)
const drawerVisible = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const selectedRows = ref([])
const form = ref({})
const activeRegion = ref(null)
const planningResult = ref(null)

// 地图地块数据：按期次开关合并（基期 + 末期）
const mapParcelsGeojson = ref({ type: 'FeatureCollection', features: [] })

// 分析项目（上传关联）
const projects = ref([])
const projectName = computed(() => {
  const p = projects.value.find((x) => x.id === store.selectedParcel?.project_id)
  return p?.name || ''
})

// 批量选择（地图点击进入选中集）
const batchMode = ref(false)
const batchSelection = ref({ parcel_ids: [], poi_ids: [], zone_ids: [] })

// v4.0：POI 详情（地图点要素点击 → 属性对话框）
const poiDetailVisible = ref(false)
const poiDetail = ref({ id: null, name: '', poi_type: '', locked: false })

// 地图标注
const mapFeatures = ref([])
const featuresLoading = ref(false)
const saveDrawVisible = ref(false)
const saveDrawForm = ref({ name: '', feature_type: 'point' })
const pendingDrawing = ref(null)
const savingDraw = ref(false)

// SHP 导入
const importVisible = ref(false)
const importFile = ref(null)
const importOpts = ref({ period: 'base', project_id: null, name_field: '', land_use_field: '', region_field: '', region_code: '' })
const importing = ref(false)
const importResult = ref(null)

// v3.0：兴趣点（POI）管理 —— 点要素 SHP 导入 / 列表 / 删除
const poiItems = ref([])
const poiTotal = ref(0)
const poiPage = ref(1)
const poiPageSize = ref(10)
const poiType = ref('')
const poiLoading = ref(false)
const poiImportVisible = ref(false)
const poiImportFile = ref(null)
const poiImportOpts = ref({ period: 'base', project_id: null, name_field: '', type_field: '' })
const poiImporting = ref(false)
const poiImportResult = ref(null)

onMounted(async () => {
  await Promise.all([
    loadPage(1),
    loadMapParcels(),
    store.fetchPoisGeojson(),
    store.fetchZonesGeojson(),
    loadProjects(),
    loadMapFeatures(),
    loadPois(),
  ])
  if (route.query.highlight) {
    const id = Number(route.query.highlight)
    const p = store.parcels.find((x) => x.id === id)
    if (p) onRowClick(p)
  }
})

async function loadProjects() {
  projects.value = await getProjects()
}

function togglePanel(name) {
  panelOpen.value = panelOpen.value === name ? null : name
}

/** v4.0：按勾选期次加载地图地块（基期/末期合并显示，基期实线、末期虚线） */
async function loadMapParcels() {
  const tasks = []
  if (showPeriods.value.includes('base')) tasks.push(store.fetchParcelsGeojson({ period: 'base' }))
  else tasks.push(Promise.resolve({ type: 'FeatureCollection', features: [] }))
  if (showPeriods.value.includes('current')) tasks.push(store.fetchParcelsGeojson({ period: 'current' }))
  else tasks.push(Promise.resolve({ type: 'FeatureCollection', features: [] }))
  const [baseFc, currentFc] = await Promise.all(tasks)
  mapParcelsGeojson.value = {
    type: 'FeatureCollection',
    features: [...(baseFc.features || []), ...(currentFc.features || [])],
  }
}

/** 表格期次参数：只勾选单一期次时下推后端过滤；否则不过滤 */
function tablePeriodParam() {
  const s = showPeriods.value
  if (s.length === 1) return s[0]
  return undefined
}

async function loadPage(p) {
  page.value = p || page.value
  loading.value = true
  try {
    const data = await store.fetchParcels({
      q: query.value || undefined,
      land_use: landUse.value || undefined,
      region_code: activeRegion.value?.code || undefined,
      period: tablePeriodParam(),
      page: page.value,
      page_size: pageSize.value,
    })
    total.value = data?.total ?? 0
  } finally {
    loading.value = false
    loadedOnce.value = true
  }
  loadMapParcels() // 地图同步过滤（按勾选期次）
}

function onRowClick(row) {
  store.selectParcel(row)
  highlightId.value = row.id
  drawerVisible.value = true
  const feature = mapParcelsGeojson.value.features.find((f) => f.properties.id === row.id)
  if (feature && mapRef.value) mapRef.value.flyTo(feature)
  loadPlanning(row.id)
}

function onMapClick(feature) {
  store.selectParcel(feature.properties)
  highlightId.value = feature.properties.id
  loadPlanning(feature.properties.id)
}

function onParcelDetail(feature) {
  store.selectParcel(feature.properties)
  highlightId.value = feature.properties.id
  drawerVisible.value = true
  loadPlanning(feature.properties.id)
}

async function loadPlanning(parcelId) {
  try {
    planningResult.value = await checkParcel(parcelId)
  } catch (e) {
    planningResult.value = null
  }
}

function flyToSelected() {
  const feature = mapParcelsGeojson.value.features.find(
    (f) => f.properties.id === store.selectedParcel?.id
  )
  if (feature && mapRef.value) mapRef.value.flyTo(feature)
}

// ---------- v4.0 POI 点击查看 ----------
function onPoiMapClick(feature) {
  // 弹窗已在地图组件内展示（定位/查看详情按钮），这里仅同步选中态
  poiDetail.value = { ...(feature.properties || {}), id: feature.id ?? feature.properties?.id }
}

function onPoiDetail(feature) {
  poiDetail.value = { ...(feature.properties || {}), id: feature.id ?? feature.properties?.id }
  poiDetailVisible.value = true
}

function flyToPoi() {
  const feature = store.poisGeojson.features.find((f) => f.properties?.id === poiDetail.value.id)
  if (feature && mapRef.value) mapRef.value.flyTo(feature)
  poiDetailVisible.value = false
}

// ---------- 模块跳转（地块详情抽屉按钮） ----------
function gotoPlanning(parcel) {
  router.push({ path: '/planning', query: { parcel: parcel.id } })
}

function gotoTransition(parcel) {
  router.push({ path: '/transition', query: { parcel: parcel.id } })
}

// 行政区选择器联动
function onRegionSelect(region) {
  activeRegion.value = region?.level === 'county' ? region : null
  if (activeRegion.value) loadPage(1)
  else if (!region) { activeRegion.value = null; loadPage(1) }
}

function onRegionLocate(locate) {
  if (mapRef.value && locate.bbox) {
    mapRef.value.fitBounds(locate.bbox)
  }
  loadRegionBoundary(locate.code)
}

async function loadRegionBoundary(code) {
  try {
    const r = await getRegion(code)
    boundaryGeojson.value = r?.geometry
      ? { type: 'FeatureCollection', features: [{ type: 'Feature', geometry: r.geometry, properties: {} }] }
      : null
  } catch (e) {
    boundaryGeojson.value = null
  }
}

function clearRegionFilter() {
  activeRegion.value = null
  loadPage(1)
}

function openCreate() {
  form.value = {
    parcel_code: '', name: '', land_use: '住宅用地', period: 'base',
    project_id: ui.currentProjectId || null,
    district: activeRegion.value?.name || '', region_code: activeRegion.value?.code || '',
    area_sqm: 50000, far_limit: null, height_limit: null, geometryText: '',
  }
  dialogVisible.value = true
}

function fillDefaultGeometry() {
  const cx = 114.34, cy = 30.50
  const dx = 0.003, dy = 0.0025
  const ring = [
    [cx - dx, cy - dy], [cx + dx, cy - dy],
    [cx + dx, cy + dy], [cx - dx, cy + dy], [cx - dx, cy - dy],
  ]
  form.value.geometryText = JSON.stringify({ type: 'Polygon', coordinates: [ring] })
}

async function submitForm() {
  submitting.value = true
  try {
    const payload = {
      parcel_code: form.value.parcel_code,
      name: form.value.name,
      land_use: form.value.land_use,
      period: form.value.period,
      project_id: form.value.project_id || null,
      district: form.value.district || null,
      region_code: form.value.region_code || null,
      area_sqm: form.value.area_sqm,
      far_limit: form.value.far_limit,
      height_limit: form.value.height_limit,
      geometry: JSON.parse(form.value.geometryText || '{}'),
    }
    await createParcel(payload)
    ElMessage.success('地块创建成功')
    dialogVisible.value = false
    await loadPage(1)
  } catch (e) {
    ElMessage.error('保存失败：几何格式不正确或字段缺失')
  } finally {
    submitting.value = false
  }
}

// ---------- 锁定 / 删除 ----------
async function toggleLock(row) {
  await lockParcel(row.id, !row.locked)
  ElMessage.success(row.locked ? `已解锁 ${row.name}` : `已锁定 ${row.name}（锁定后不可删除）`)
  await loadPage(1)
}

async function onDelete(row) {
  await ElMessageBox.confirm(`确定删除地块 ${row.name}（${row.parcel_code}）吗？此操作不可恢复。`, '删除确认', {
    type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
  })
  try {
    await deleteParcel(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.warning(e?.message || '删除失败（可能已锁定）')
  }
  await loadPage(1)
}

async function onBatchDelete() {
  await ElMessageBox.confirm(
    `确定批量删除选中的 ${selectedRows.value.length} 宗地块吗？此操作不可恢复。`,
    '批量删除确认',
    { type: 'error', confirmButtonText: '全部删除', cancelButtonText: '取消' }
  )
  const result = await batchDeleteParcels(selectedRows.value.map((r) => r.id))
  if (result.locked.length) ElMessage.warning(`${result.locked.length} 宗地块已锁定，已跳过`)
  ElMessage.success(`已删除 ${result.deleted.length} 宗地块`)
  selectedRows.value = []
  await loadPage(1)
}

// ---------- v2.0 批量选择（地图点击） ----------
function toggleBatchMode() {
  batchMode.value = !batchMode.value
  if (!batchMode.value) mapRef.value?.clearBatchSelection()
  ElMessage.info(batchMode.value
    ? '批量选择模式：点击地图上的地块/POI/控制线进入选中集'
    : '已退出批量选择模式')
}

function onBatchSelection(selection) {
  batchSelection.value = selection
}

async function batchDeleteOnMap() {
  const sel = batchSelection.value
  const total = sel.parcel_ids.length + sel.poi_ids.length + sel.zone_ids.length
  if (!total) { ElMessage.warning('请先在地图上点击选择要素'); return }
  await ElMessageBox.confirm(
    `确定删除地图选中的要素吗？（地块 ${sel.parcel_ids.length} / POI ${sel.poi_ids.length} / 控制线 ${sel.zone_ids.length}）`,
    '批量删除确认', { type: 'error', confirmButtonText: '删除', cancelButtonText: '取消' }
  )
  const [p, poi, z] = await Promise.all([
    sel.parcel_ids.length ? batchDeleteParcels(sel.parcel_ids) : { deleted: [], locked: [] },
    sel.poi_ids.length ? batchDeletePois(sel.poi_ids) : { deleted: [], locked: [] },
    sel.zone_ids.length ? batchDeleteZones(sel.zone_ids) : { deleted: [], locked: [] },
  ])
  const lockedTotal = p.locked.length + poi.locked.length + z.locked.length
  ElMessage.success(`已删除 ${p.deleted.length + poi.deleted.length + z.deleted.length} 个要素` +
    (lockedTotal ? `，${lockedTotal} 个已锁定被跳过` : ''))
  mapRef.value?.clearBatchSelection()
  await Promise.all([loadPage(1), store.fetchPoisGeojson(), store.fetchZonesGeojson()])
}

async function lockSelectedOnMap() {
  const sel = batchSelection.value
  if (!sel.parcel_ids.length) { ElMessage.warning('请先选择地块（锁定功能针对地块）'); return }
  for (const id of sel.parcel_ids) {
    await lockParcel(id, true)
  }
  ElMessage.success(`已锁定 ${sel.parcel_ids.length} 宗地块`)
  mapRef.value?.clearBatchSelection()
  await loadPage(1)
}

// ---------- v4.0 圈选删除（框选/圈选/多边形 → 范围内地块 + POI + 控制线一键删除） ----------
async function onSelectionDelete(selection) {
  const parcelCount = selection?.count || 0
  const poiCount = selection?.poi_count || 0
  const zoneCount = selection?.zone_count || 0
  const total = parcelCount + poiCount + zoneCount
  if (!total) { ElMessage.warning('所选范围内没有可删除的要素'); return }
  await ElMessageBox.confirm(
    `确定删除圈选范围内的 ${total} 个要素吗？（地块 ${parcelCount} / 兴趣点 ${poiCount} / 控制线 ${zoneCount}；锁定要素自动跳过，此操作不可恢复）`,
    '圈选删除确认',
    { type: 'error', confirmButtonText: '全部删除', cancelButtonText: '取消' }
  )
  try {
    const [p, poi, z] = await Promise.all([
      (selection.features || []).length
        ? batchDeleteParcels((selection.features || []).map((f) => f.id ?? f.properties?.id))
        : { deleted: [], locked: [] },
      poiCount ? batchDeletePois(selection.poi_ids || []) : { deleted: [], locked: [] },
      zoneCount ? batchDeleteZones(selection.zone_ids || []) : { deleted: [], locked: [] },
    ])
    const deletedTotal = p.deleted.length + poi.deleted.length + z.deleted.length
    const lockedTotal = p.locked.length + poi.locked.length + z.locked.length
    ElMessage.success(`已删除 ${deletedTotal} 个要素` +
      (lockedTotal ? `，${lockedTotal} 个已锁定被跳过` : ''))
    mapRef.value?.clearSelection()
    await Promise.all([
      loadPage(1),
      loadMapParcels(),
      store.fetchPoisGeojson(),
      store.fetchZonesGeojson(),
      loadPois(),
    ])
  } catch (e) {
    ElMessage.error('圈选删除失败：' + (e?.message || '未知原因'))
  }
}

// ---------- 地图标注（绘制持久化） ----------
async function loadMapFeatures() {
  featuresLoading.value = true
  try {
    mapFeatures.value = await getMapFeatures()
  } finally {
    featuresLoading.value = false
  }
}

function onSaveDrawing(feature) {
  const typeMap = { Point: 'point', LineString: 'line', Polygon: 'polygon' }
  pendingDrawing.value = feature
  saveDrawForm.value = {
    name: `标注_${Date.now().toString().slice(-6)}`,
    feature_type: typeMap[feature?.geometry?.type] || 'point',
  }
  saveDrawVisible.value = true
}

async function doSaveDrawing() {
  if (!pendingDrawing.value || !saveDrawForm.value.name.trim()) {
    ElMessage.warning('请填写标注名称')
    return
  }
  savingDraw.value = true
  try {
    await createMapFeature({
      name: saveDrawForm.value.name.trim(),
      feature_type: saveDrawForm.value.feature_type,
      project_id: ui.currentProjectId || null,
      geometry: pendingDrawing.value.geometry,
    })
    ElMessage.success('绘制已保存到数据库（标注图层）')
    saveDrawVisible.value = false
    mapRef.value?.clearDrawing()
    await loadMapFeatures()
  } catch (e) {
    ElMessage.error('保存失败：' + (e?.message || '未知原因'))
  } finally {
    savingDraw.value = false
  }
}

async function toggleFeatureLock(row) {
  await lockMapFeature(row.id, !row.locked)
  ElMessage.success(row.locked ? '已解锁' : '已锁定（锁定后不可删除）')
  await loadMapFeatures()
}

async function onDeleteFeature(row) {
  await ElMessageBox.confirm(`确定删除标注 ${row.name} 吗？`, '删除确认', { type: 'warning' })
  try {
    await deleteMapFeature(row.id)
    await loadMapFeatures()
  } catch (e) {
    ElMessage.warning(e?.message || '删除失败（可能已锁定）')
  }
}

// ---------- SHP 导入 ----------
function openImport() {
  importResult.value = null
  importFile.value = null
  importOpts.value = {
    period: 'base', project_id: ui.currentProjectId || null,
    name_field: '', land_use_field: '', region_field: '', region_code: '',
  }
  importVisible.value = true
}

function onFileChange(file) {
  importFile.value = file.raw
}

async function doImport() {
  if (!importFile.value) return
  // v3.0：上传数据强制关联分析项目（后端同样校验，前端先行提示）
  if (!importOpts.value.project_id) {
    ElMessage.warning('请先选择所属项目（v3.0 起上传数据必须关联分析项目；无项目请先在顶栏「项目工作台」创建）')
    return
  }
  importing.value = true
  importResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    fd.append('period', importOpts.value.period || 'base')
    if (importOpts.value.project_id) fd.append('project_id', importOpts.value.project_id)
    for (const key of ['name_field', 'land_use_field', 'region_field', 'region_code']) {
      if (importOpts.value[key]) fd.append(key, importOpts.value[key])
    }
    const result = await importParcelsShp(fd)
    importResult.value = result
    if (result.imported > 0) {
      ElMessage.success(`导入完成：成功 ${result.imported} 条（期次：${importOpts.value.period === 'base' ? '基期' : '末期'}）`)
      await loadPage(1)
    } else {
      const firstReason = result.skipped?.[0]?.reason || '未知原因'
      ElMessage.warning(`导入未成功（0 条入库）：${firstReason}，详见下方明细`)
    }
  } catch (e) {
    // 后端拒绝原因已由拦截器弹出提示
  } finally {
    importing.value = false
  }
}

async function afterImportRefresh() {
  await loadPage(1)
  ElMessage.success('列表与地图已刷新')
}

// ---------- v3.0 兴趣点（POI）管理 ----------
async function loadPois(p) {
  poiPage.value = p || poiPage.value
  poiLoading.value = true
  try {
    const data = await getPois({
      poi_type: poiType.value || undefined,
      page: poiPage.value,
      page_size: poiPageSize.value,
    })
    poiItems.value = data?.items ?? []
    poiTotal.value = data?.total ?? 0
  } catch (e) {
    poiItems.value = []
  } finally {
    poiLoading.value = false
  }
}

function openPoiImport() {
  poiImportResult.value = null
  poiImportFile.value = null
  poiImportOpts.value = {
    period: 'base', project_id: ui.currentProjectId || null,
    name_field: '', type_field: '',
  }
  poiImportVisible.value = true
}

function onPoiFileChange(file) {
  poiImportFile.value = file.raw
}

async function doPoiImport() {
  if (!poiImportFile.value) return
  if (!poiImportOpts.value.project_id) {
    ElMessage.warning('请先选择所属项目（v3.0 起上传数据必须关联分析项目；无项目请先在顶栏「项目工作台」创建）')
    return
  }
  poiImporting.value = true
  poiImportResult.value = null
  try {
    const fd = new FormData()
    fd.append('file', poiImportFile.value)
    fd.append('period', poiImportOpts.value.period || 'base')
    fd.append('project_id', poiImportOpts.value.project_id)
    for (const key of ['name_field', 'type_field']) {
      if (poiImportOpts.value[key]) fd.append(key, poiImportOpts.value[key])
    }
    const result = await importPoisShp(fd)
    poiImportResult.value = result
    if (result.imported > 0) {
      ElMessage.success(`POI 导入完成：成功 ${result.imported} 条`)
      await Promise.all([loadPois(), store.fetchPoisGeojson()])
    } else {
      const firstReason = result.skipped?.[0]?.reason || '未知原因'
      ElMessage.warning(`POI 导入未成功（0 条入库）：${firstReason}，详见下方明细`)
    }
  } catch (e) {
    // 后端拒绝原因已由拦截器弹出提示
  } finally {
    poiImporting.value = false
  }
}

async function afterPoiImportRefresh() {
  await Promise.all([loadPois(), store.fetchPoisGeojson()])
  ElMessage.success('POI 列表与地图已刷新')
}

async function onDeletePoi(row) {
  await ElMessageBox.confirm(`确定删除兴趣点 ${row.name} 吗？`, '删除确认', { type: 'warning' })
  try {
    await deletePoi(row.id)
    ElMessage.success('已删除')
    if (poiDetail.value.id === row.id) poiDetailVisible.value = false
    await Promise.all([loadPois(), store.fetchPoisGeojson()])
  } catch (e) {
    ElMessage.warning(e?.message || '删除失败（可能已锁定）')
  }
}

async function togglePoiLock(row) {
  await lockPoi(row.id, !row.locked)
  ElMessage.success(row.locked ? `已解锁 ${row.name}` : `已锁定 ${row.name}（锁定后不可删除，圈选删除自动跳过）`)
  if (poiDetail.value.id === row.id) poiDetail.value.locked = !row.locked
  await Promise.all([loadPois(), store.fetchPoisGeojson()])
}
</script>

<style scoped>
.page-fullmap {
  position: relative;
  height: calc(100vh - 122px);
  min-height: 640px;
  border-radius: var(--lv-radius);
  overflow: hidden;
}
.page-fullmap :deep(.map-wrap) {
  border-radius: 0;
  position: absolute;
  inset: 0;
}
.page-icon-btn {
  position: absolute;
  z-index: 6;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: var(--lv-radius-sm);
  background: var(--lv-surface-glass);
  backdrop-filter: blur(8px);
  box-shadow: var(--lv-shadow);
  color: var(--lv-text-secondary);
  cursor: pointer;
}
.page-icon-btn:hover,
.page-icon-btn.active {
  background: var(--lv-primary);
  color: #fff;
}
.icon-left {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% - 65px));
}
.icon-left2 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% - 22px));
}
.icon-left3 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% + 21px));
}
.icon-left4 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% + 64px));
}
.icon-left5 {
  left: 10px;
  top: 50%;
  transform: translateY(calc(-50% + 107px));
}
/* v4.0：圈选删除使用提示条（地图左上角工具条下方） */
.map-widget-draw-hint {
  position: absolute;
  z-index: 6;
  left: 14px;
  top: 56px;
  max-width: 300px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--lv-text-secondary);
  background: var(--lv-surface-glass);
  backdrop-filter: blur(8px);
  border-radius: var(--lv-radius-sm);
  box-shadow: var(--lv-shadow);
  cursor: pointer;
}
.map-widget-draw-hint b {
  color: var(--lv-primary);
}
.page-panel {
  position: absolute;
  z-index: 6;
  width: 660px;
  max-width: 48vw;
  max-height: calc(100% - 28px);
  overflow-y: auto;
}
.panel-left {
  left: 54px;
  top: 14px;
  bottom: 14px;
}
.filter-row {
  display: flex;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
  align-items: center;
}
.scope-hint {
  font-size: 12px;
  color: var(--lv-text-secondary);
  margin-bottom: 10px;
}
.poi-total {
  font-size: 12px;
  color: var(--lv-text-tertiary);
  margin-left: auto;
}
.mt {
  margin-top: 10px;
}
.mb {
  margin-bottom: 10px;
}
.skip-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  border-bottom: 1px dashed var(--lv-border);
}
.skip-reason {
  font-size: 12px;
  color: var(--lv-text-secondary);
}
.skip-more {
  font-size: 12px;
  color: var(--lv-text-tertiary);
  padding: 6px 0;
}
</style>
