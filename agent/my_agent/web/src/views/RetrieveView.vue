<script setup>
import { ref } from 'vue'
import { retrieve } from '../api/client'

const query = ref('')
const topK = ref(4)
const loading = ref(false)
const result = ref(null)

async function run() {
  const text = query.value.trim()
  if (!text || loading.value) return

  loading.value = true
  result.value = null
  try {
    result.value = await retrieve(text, topK.value)
  } catch {
    // 拦截器已弹错
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <el-alert type="info" :closable="false" show-icon class="tip">
      <template #title>
        只跑检索、不经过大模型：看课件库里究竟命中了哪些片段。
        命中私有库（绿标）说明有课件依据；灰标表示没找到，回答时应标注「无课件依据」。
      </template>
    </el-alert>

    <div class="composer">
      <el-input
        v-model="query"
        placeholder="输入要检索的内容，例如课件的某个主题"
        :disabled="loading"
        @keydown.enter.exact.prevent="run"
      />
      <el-input-number v-model="topK" :min="1" :max="10" :disabled="loading" />
      <el-button type="primary" :loading="loading" @click="run">检索</el-button>
    </div>

    <el-card v-if="loading" shadow="never">
      <el-skeleton :rows="4" animated />
    </el-card>

    <template v-if="result">
      <el-card shadow="never">
        <template #header>
          <div class="card-head">
            <span>检索结果</span>
            <el-tag :type="result.hit_private ? 'success' : 'info'" effect="dark" size="small">
              {{ result.hit_private ? '命中课件库' : '未命中课件依据' }}
            </el-tag>
          </div>
        </template>

        <el-empty v-if="!result.chunks.length" description="没有检索到相关片段" />

        <el-card
          v-for="(c, i) in result.chunks"
          :key="i"
          shadow="never"
          class="chunk"
        >
          <div class="chunk-no">片段 {{ i + 1 }}</div>
          <div class="pre-wrap chunk-text">{{ c }}</div>
        </el-card>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tip :deep(.el-alert__title) {
  line-height: 1.6;
}

.composer {
  display: flex;
  gap: 12px;
  align-items: center;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chunk {
  margin-bottom: 10px;
  background: #fafcff;
}

.chunk-no {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.chunk-text {
  font-size: 13px;
  line-height: 1.7;
}
</style>
