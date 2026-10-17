<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { chat, getSession, getUsage, listSessions } from '../api/client'
import MarkdownView from '../components/MarkdownView.vue'

// 对话记录：{ role: 'user' | 'assistant', content, name?, failed? }
const messages = ref([])
const input = ref('')
const userName = ref('')
const usage = ref(null)
const loading = ref(false)
const scroller = ref(null)

// thread_id 是短期记忆的钥匙：同一个 id 连续多轮，后端会接上历史 messages
const threadId = ref(newThreadId())

// 历史会话列表
const sessions = ref([])
const sessionsLoading = ref(false)

function newThreadId() {
  return 't-' + Math.random().toString(36).slice(2, 10)
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

async function scrollToBottom() {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    sessions.value = await listSessions()
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

/** 点会话列表：把该会话的历史拉回来，并切到它的 thread_id 继续聊 */
async function openSession(session) {
  if (loading.value || session.thread_id === threadId.value) return
  try {
    const detail = await getSession(session.thread_id)
    messages.value = detail.messages
    threadId.value = detail.thread_id
    await scrollToBottom()
  } catch {
    // 拦截器已弹错
  }
}

async function newSession() {
  messages.value = []
  threadId.value = newThreadId()
  ElMessage.success('已开启新会话')
}

async function send() {
  const text = input.value.trim()
  const name = userName.value.trim()
  if (!text || loading.value) return
  if (!name) {
    ElMessage.warning('请先输入姓名')
    return
  }

  messages.value.push({ role: 'user', content: text, name })
  input.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    const res = await chat(text, threadId.value, name)
    threadId.value = res.thread_id
    messages.value.push({ role: 'assistant', content: res.output })
    usage.value = { used: res.used, limit: res.limit, remaining: res.remaining }
    loadSessions() // 刷新列表，让摘要、时间和提问人跟上
  } catch (err) {
    // 拦截器已弹提示；这里在对话流里也留个痕迹，并带上后端原因（如「别人正在使用」）
    const detail = err.response?.data?.detail
    messages.value.push({
      role: 'assistant',
      content: detail ? `（${detail}）` : '（请求失败，请确认后端已启动）',
      failed: true,
    })
    loadUsage()
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

onMounted(() => {
  loadSessions()
  loadUsage()
})
</script>

<template>
  <div class="chat">
    <!-- 左：历史会话 -->
    <el-card shadow="never" class="sessions">
      <template #header>
        <div class="sessions-head">
          <span>历史会话</span>
          <el-button size="small" type="primary" plain @click="newSession">新建</el-button>
        </div>
      </template>

      <div v-loading="sessionsLoading" class="sessions-body">
        <el-empty v-if="!sessions.length" description="还没有历史会话" :image-size="60" />
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
            <span>{{ formatTime(s.updated_at) }} · {{ s.message_count }} 条</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 右：当前对话 -->
    <div class="main">
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
          <span class="hint">同一 id 连续提问可验证短期记忆</span>
        </div>
      </el-card>

      <div ref="scroller" class="stream">
        <el-empty v-if="!messages.length" description="问点什么吧，比如「1+1 等于几」" />

        <div
          v-for="(m, i) in messages"
          :key="i"
          class="row"
          :class="m.role === 'user' ? 'row-right' : 'row-left'"
        >
          <div class="bubble" :class="[m.role, { failed: m.failed }]">
            <div v-if="m.role === 'user' && m.name" class="bubble-name">{{ m.name }}</div>
            <MarkdownView v-if="m.role === 'assistant' && !m.failed" :content="m.content" />
            <div v-else class="pre-wrap">{{ m.content }}</div>
          </div>
        </div>

        <div v-if="loading" class="row row-left">
          <div class="bubble assistant">
            <el-icon class="is-loading"><Loading /></el-icon>
            思考中…
          </div>
        </div>
      </div>

      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          :disabled="loading"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="loading" @click="send">发送</el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat {
  height: 100%;
  display: flex;
  gap: 12px;
}

/* ---- 左：会话列表 ---- */
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

/* ---- 右：对话 ---- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
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

.stream {
  flex: 1;
  overflow: auto;
  padding: 4px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.row {
  display: flex;
}

.row-right {
  justify-content: flex-end;
}

.row-left {
  justify-content: flex-start;
}

.bubble {
  max-width: 76%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
}

.bubble.user {
  background: #409eff;
  color: #fff;
  line-height: 1.6;
}

.bubble-name {
  margin-bottom: 2px;
  font-size: 11px;
  opacity: 0.85;
}

.bubble.assistant {
  background: #fff;
  border: 1px solid #e4e7ed;
}

.bubble.failed {
  background: #fef0f0;
  border-color: #fde2e2;
  color: #f56c6c;
}

.composer {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}
</style>
