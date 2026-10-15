<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { ingest } from '../api/client'

const fileList = ref([]) // el-upload 的受控文件列表
const loading = ref(false)
const result = ref(null)

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
    ElMessage.success('入库完成')
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

    <el-result v-if="result" icon="success" title="入库成功">
      <template #sub-title>
        <div class="result-line">文件：{{ result.filename }}</div>
        <div class="result-line">
          写入片段数：
          <el-tag type="success">{{ result.chunks }}</el-tag>
        </div>
        <div class="result-line">
          目标库：<el-tag type="info">{{ result.collection }}</el-tag>
        </div>
      </template>
    </el-result>
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
</style>
