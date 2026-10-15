<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { chat, getSession, listSessions } from '../api/client'
import MarkdownView from '../components/MarkdownView.vue'

// 对话记录：{ role: 'user' | 'assistant', content, failed? }
const messages = ref([])
const input = ref('')
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
  if (!text || loading.value) return

  messages.value.push({ role: 'user', content: text })
  input.value = ''
  loading.value = true
  await scrollToBottom()

  try {
    const res = await chat(text, threadId.value)
    threadId.value = res.thread_id
    messages.value.push({ role: 'assistant', content: res.output })
    loadSessions() // 刷新列表，让摘要和时间跟上
  } catch {
    // 具体错误已由拦截器弹出，这里在对话流里留个痕迹便于排查
    messages.value.push({
      role: 'assistant',
      content: '（请求失败，请确认后端已启动）',
      failed: true,
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

onMounted(loadSessions)
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
            <span>{{ formatTime(s.updated_at) }}</span>
            <span>{{ s.message_count }} 条</span>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 右：当前对话 -->
    <div class="main">
      <el-card shadow="never" class="bar">
        <div class="bar-row">
          <span class="label">thread_id：</span>
          <el-tag type="info">{{ threadId }}</el-tag>
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
  font-size: 12px;
  color: #909399;
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
