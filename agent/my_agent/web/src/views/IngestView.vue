<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadUpload, ingest, listUploads } from '../api/client'

const fileList = ref([]) // el-upload 的受控文件列表
const loading = ref(false)
const result = ref(null)

// 上传历史
const history = ref([])
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await listUploads()
  } catch {
    // 拦截器已弹错
  } finally {
    historyLoading.value = false
  }
}

async function download(record) {
  try {
    await downloadUpload(record)
  } catch {
    // 拦截器已弹错
  }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 手动上传：选中文件后由「开始入库」按钮触发，避免一选就传
async function submit() {
  const raw = fileList.value[0]?.raw
  if (!raw) {
    ElMessage.warning('请先选择一个 PDF 文件')
    return
  }

  loading.value = true
  result.value = null
  try {
    result.value = await ingest(raw)
    ElMessage.success(result.value.deduplicated ? '内容已存在，未重复入库' : '入库完成')
    loadHistory()
  } catch {
    // 拦截器已弹错
  } finally {
    loading.value = false
  }
}

function clear() {
  fileList.value = []
  result.value = null
}

// el-upload 的 on-change / on-remove 签名都是 (uploadFile, uploadFiles)：
// 第一个是单个文件对象，第二个才是完整列表——取第二个来更新受控列表。
// 只保留最后选中的那个，避免误传多个。
function onChange(_file, files) {
  fileList.value = files.length ? [files[files.length - 1]] : []
  result.value = null
}

onMounted(loadHistory)
</script>

<template>
  <div class="page">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        上传 PDF 课件：后端会「解析 -> 分块 -> 向量化 -> 写入 Chroma 私有库」。
        入库后在「检索调试」里就能查到这些片段。
      </template>
    </el-alert>

    <el-upload
      drag
      accept=".pdf"
      :auto-upload="false"
      v-model:file-list="fileList"
      :on-change="onChange"
      :on-remove="onChange"
      class="uploader"
    >
      <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
      <div class="el-upload__text">把 PDF 拖到这里，或<em>点击选择</em></div>
      <template #tip>
        <div class="el-upload__tip">仅支持 PDF；解析不出文本的扫描版会返回 400</div>
      </template>
    </el-upload>

    <div class="actions">
      <el-button type="primary" :loading="loading" :disabled="!fileList.length" @click="submit">
        开始入库
      </el-button>
      <el-button :disabled="loading" @click="clear">清空</el-button>
    </div>

    <el-card v-if="loading" shadow="never">
      <el-icon class="is-loading"><Loading /></el-icon>
      正在向量化并写库…
    </el-card>

    <el-result
      v-if="result"
      :icon="result.deduplicated ? 'info' : 'success'"
      :title="result.deduplicated ? '内容已存在，未重复入库' : '入库成功'"
    >
      <template #sub-title>
        <div class="result-line">文件：{{ result.filename }}</div>
        <div class="result-line">
          写入片段数：
          <el-tag type="success">{{ result.chunks }}</el-tag>
        </div>
        <div class="result-line">
          目标库：<el-tag type="info">{{ result.collection }}</el-tag>
        </div>
        <div v-if="result.deduplicated" class="result-line">
          相同内容的文件此前已入库，直接沿用了历史记录。
        </div>
      </template>
    </el-result>

    <el-card shadow="never">
      <template #header>
        <div class="history-head">
          <span>上传历史</span>
          <el-button size="small" :loading="historyLoading" @click="loadHistory">
            刷新
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="historyLoading"
        :data="history"
        size="small"
        empty-text="还没有上传记录"
      >
        <el-table-column prop="filename" label="文件名" min-width="180" show-overflow-tooltip />
        <el-table-column label="大小" width="90">
          <template #default="{ row }">{{ formatSize(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="chunks" label="片段数" width="80" />
        <el-table-column label="上传时间" width="150">
          <template #default="{ row }">{{ formatTime(row.uploaded_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="download(row)">
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 720px;
}

.tip :deep(.el-alert__title) {
  line-height: 1.6;
}

.actions {
  display: flex;
  gap: 12px;
}

.result-line {
  margin: 6px 0;
  color: #606266;
  font-size: 14px;
}

.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
}
</style>
