<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getPlanSession, getUsage, listPlanSessions, plan } from '../api/client'
import MarkdownView from '../components/MarkdownView.vue'

const input = ref('')
const userName = ref('')
const usage = ref(null)
const loading = ref(false)
const result = ref(null)

const STORAGE_KEY = 'plan_thread_id'

// thread_id 是规划记忆的钥匙：同一个 id 连续多轮，planner 能看到此前的请求。
// 存 localStorage，刷新页面也不丢——否则一刷新就换新 thread，看起来像「没记忆」。
const threadId = ref(loadThreadId())

function newThreadId() {
  return 'p-' + Math.random().toString(36).slice(2, 10)
}

function loadThreadId() {
  try {
    return localStorage.getItem(STORAGE_KEY) || newThreadId()
  } catch {
    return newThreadId() // 隐私模式等无法访问 localStorage
  }
}

function saveThreadId(id) {
  threadId.value = id
  try {
    localStorage.setItem(STORAGE_KEY, id)
  } catch {
    // 写不进去就算了，内存里仍是有效的
  }
}

// 历史规划会话
const sessions = ref([])
const sessionsLoading = ref(false)

// 子 Agent 角色 -> tag 颜色（对应后端 plan_graph.py 的 VALID_AGENTS）
const AGENT_TYPE = {
  knowledge: 'primary',
  code: 'success',
  writer: 'warning',
  reviewer: 'danger',
}
// 子任务状态 -> tag 颜色
const STATUS_TYPE = {
  pending: 'info',
  running: 'warning',
  success: 'success',
  failed: 'danger',
}
const STATUS_TEXT = {
  pending: '待执行',
  running: '执行中',
  success: '成功',
  failed: '失败',
}

/** ISO 时间 -> 今天显示 HH:mm，否则显示 MM-DD */
function formatTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const now = new Date()
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate()
  const pad = (n) => String(n).padStart(2, '0')
  return sameDay
    ? `${pad(d.getHours())}:${pad(d.getMinutes())}`
    : `${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    sessions.value = await listPlanSessions()
  } catch {
    // 拦截器已弹错
  } finally {
    sessionsLoading.value = false
  }
}

async function loadUsage() {
  try {
    usage.value = await getUsage()
  } catch {
    // 拦截器已弹错
  }
}

/** 点会话列表：把该规划会话拉回来（各轮请求 + 最后一次的计划/产出） */
async function openSession(session) {
  // 不能在 thread_id 与当前相同时提前返回：刷新页面后 result 是空的，
  // 但 localStorage 里的 thread_id 仍指向那条历史，提前返回会导致「点不开」。
  if (loading.value) return
  try {
    const detail = await getPlanSession(session.thread_id)
    saveThreadId(detail.thread_id)
    result.value = detail
  } catch {
    // 拦截器已弹错
  }
}

function newTask() {
  saveThreadId(newThreadId())
  result.value = null
  input.value = ''
}

async function run() {
  const text = input.value.trim()
  const name = userName.value.trim()
  if (!text || loading.value) return
  if (!name) {
    ElMessage.warning('请先输入姓名')
    return
  }

  loading.value = true
  result.value = null
  try {
    const res = await plan(text, threadId.value, name)
    saveThreadId(res.thread_id)
    result.value = res
    usage.value = { used: res.used, limit: res.limit, remaining: res.remaining }
    loadSessions() // 刷新列表，让新会话/时间/轮数/提问人跟上
  } catch {
    // 拦截器已弹错
    loadUsage()
  } finally {
    loading.value = false
  }
}

const resultsOf = (id) => result.value?.subtask_results?.[id]

onMounted(() => {
  loadSessions()
  loadUsage()
})
</script>

<template>
  <div class="plan">
    <!-- 左：历史规划会话 -->
    <el-card shadow="never" class="sessions">
      <template #header>
        <div class="sessions-head">
          <span>历史规划</span>
          <el-button size="small" type="primary" plain @click="newTask">新建</el-button>
        </div>
      </template>

      <div v-loading="sessionsLoading" class="sessions-body">
        <el-empty v-if="!sessions.length" description="还没有历史规划" :image-size="60" />
        <div
          v-for="s in sessions"
          :key="s.thread_id"
          class="session-item"
          :class="{ active: s.thread_id === threadId }"
          @click="openSession(s)"
        >
          <div class="session-preview">{{ s.preview }}</div>
          <div class="session-meta">
            <span class="session-owner">{{ s.user_name || '未署名' }}</span>
            <span>{{ formatTime(s.updated_at) }} · {{ s.request_count }} 轮</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 右：当前任务 -->
    <div class="main">
      <el-alert type="info" :closable="false" show-icon class="tip">
        <template #title>
          Plan-and-Execute：先由 planner 拆计划，再按依赖拓扑逐个执行子任务。
          复杂任务需调用大模型多次，可能要几十秒，请耐心等待。
        </template>
      </el-alert>

      <el-card shadow="never" class="bar">
        <div class="bar-row">
          <span class="label">姓名：</span>
          <el-input
            v-model="userName"
            size="small"
            class="name-input"
            placeholder="请输入姓名"
            :disabled="loading"
          />
          <span class="label">thread_id：</span>
          <el-tag type="info">{{ threadId }}</el-tag>
          <el-tag
            v-if="usage"
            :type="usage.remaining > 0 ? 'success' : 'danger'"
            size="small"
            effect="plain"
          >
            剩余 {{ usage.remaining }}/{{ usage.limit }} 次
          </el-tag>
          <span class="hint">同一 id 连续提问，planner 会记住此前的请求</span>
          <el-button
            size="small"
            type="primary"
            plain
            class="new-task"
            :disabled="loading"
            @click="newTask"
          >
            新任务
          </el-button>
        </div>
      </el-card>

      <div class="composer">
        <el-input
          v-model="input"
          placeholder="例如：用 Python 实现一个快速排序函数，并写一份简短的实验报告"
          :disabled="loading"
          @keydown.enter.exact.prevent="run"
        />
        <el-button type="primary" :loading="loading" @click="run">执行</el-button>
      </div>

      <el-card v-if="loading" shadow="never">
        <el-skeleton :rows="6" animated />
        <div class="running-tip">
          <el-icon class="is-loading"><Loading /></el-icon>
          正在规划并执行子任务…
        </div>
      </el-card>

      <template v-if="result">
        <el-card v-if="result.requests?.length" shadow="never">
          <template #header>本会话请求（{{ result.requests.length }} 轮）</template>
          <ol class="requests">
            <li v-for="(r, i) in result.requests" :key="i">
              <span v-if="result.request_names?.[i]" class="request-name">
                {{ result.request_names[i] }}：
              </span>
              {{ r }}
            </li>
          </ol>
        </el-card>

        <el-card shadow="never">
          <template #header>
            <div class="card-head">
              <span>执行计划（最后一次）</span>
              <div class="head-tags">
                <el-tag v-if="result.replan_count" type="warning" size="small">
                  重规划 {{ result.replan_count }} 次
                </el-tag>
                <el-tag type="info" size="small">
                  成功 {{ result.plan.filter((t) => t.status === 'success').length }}/{{
                    result.plan.length
                  }}
                  步
                </el-tag>
              </div>
            </div>
          </template>

          <el-table :data="result.plan" border size="small">
            <el-table-column prop="id" label="步骤" width="70" />
            <el-table-column label="执行角色" width="110">
              <template #default="{ row }">
                <el-tag :type="AGENT_TYPE[row.agent] || 'info'" size="small">
                  {{ row.agent }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="desc" label="任务描述" min-width="240" />
            <el-table-column label="依赖" width="100">
              <template #default="{ row }">
                {{ row.deps?.length ? row.deps.join(', ') : '—' }}
              </template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="STATUS_TYPE[row.status] || 'info'" size="small" effect="dark">
                  {{ STATUS_TEXT[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never">
          <template #header>各子任务产出</template>
          <el-collapse>
            <el-collapse-item
              v-for="t in result.plan"
              :key="t.id"
              :name="t.id"
              :disabled="!resultsOf(t.id)"
            >
              <template #title>
                <span class="collapse-title">
                  [{{ t.id }}] {{ t.agent }} — {{ t.desc }}
                </span>
              </template>
              <div class="output">
                <MarkdownView :content="resultsOf(t.id)" />
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-card>

        <el-card shadow="never" class="final">
          <template #header>最终输出</template>
          <MarkdownView :content="result.final_output" />
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.plan {
  height: 100%;
  display: flex;
  gap: 12px;
}

/* ---- 左：历史规划会话列表 ---- */
.sessions {
  width: 240px;
  flex: 0 0 240px;
  display: flex;
  flex-direction: column;
}

.sessions :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  padding: 8px;
}

.sessions-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
  font-weight: 600;
}

.sessions-body {
  height: 100%;
  overflow-y: auto;
}

.session-item {
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
}

.session-item:hover {
  background: #f5f7fa;
}

.session-item.active {
  background: #ecf5ff;
}

.session-preview {
  font-size: 13px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  margin-top: 4px;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: #909399;
}

.session-owner {
  color: #409eff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ---- 右：当前任务 ---- */
.main {
  flex: 1;
  min-width: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* flex 子项默认会被压缩：结果卡片一多，就会被挤成细条、看起来像大片空白。
   禁止收缩，内容超高时交给 .main 滚动。 */
.main > * {
  flex: 0 0 auto;
}

.tip :deep(.el-alert__title) {
  line-height: 1.6;
}

.composer {
  display: flex;
  gap: 12px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 13px;
  color: #606266;
}

.name-input {
  width: 140px;
}

.hint {
  font-size: 12px;
  color: #909399;
}

.new-task {
  margin-left: auto;
}

.running-tip {
  margin-top: 12px;
  color: #909399;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.requests {
  margin: 0;
  padding-left: 20px;
  font-size: 13px;
  color: #303133;
  line-height: 1.9;
}

.request-name {
  color: #409eff;
  font-weight: 600;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.head-tags {
  display: flex;
  gap: 8px;
}

.collapse-title {
  font-size: 13px;
}

.output {
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
}

.final :deep(.el-card__body) {
  background: #fafcff;
}
</style>
