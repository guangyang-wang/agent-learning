import axios from 'axios'
import { ElMessage } from 'element-plus'

// baseURL 用相对路径，交给 vite 的 dev proxy 转发到后端（见 vite.config.js）。
// timeout 不设（0 = 不超时）：/chat、/plan 要调大模型，单次可能几十秒，
// 靠页面的 loading 状态兜住，而不是让请求半路被 axios 掐断。
const client = axios.create({
  baseURL: '/api',
  timeout: 0,
})

// 统一错误处理：后端出错都是 {detail: "..."}，取出来弹提示，避免各页面各写一遍。
client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const detail = err.response?.data?.detail
    const fallback = err.response
      ? `请求失败（HTTP ${err.response.status}）`
      : '无法连接后端，请确认 uvicorn 已启动'
    const msg = detail || fallback
    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  },
)

/** 存活探针 */
export const health = () => client.get('/health')

/** 单 Agent ReAct 问答；thread_id 相同即接上历史（短期记忆） */
export const chat = (userInput, threadId, userName) =>
  client.post('/chat', {
    user_input: userInput,
    thread_id: threadId,
    user_name: userName,
  })

/** Plan-and-Execute 复杂任务；thread_id 相同即接上历史（planner 记得此前的请求） */
export const plan = (userInput, threadId, userName) =>
  client.post('/plan', {
    user_input: userInput,
    thread_id: threadId,
    user_name: userName,
  })

/** 全局使用次数（不消耗次数） */
export const getUsage = () => client.get('/usage')

/** 只跑检索，不过 LLM */
export const retrieve = (query, topK = 4) =>
  client.post('/retrieve', { query, top_k: topK })

/** 上传 PDF 课件入库 */
export function ingest(file) {
  const form = new FormData()
  form.append('file', file)
  return client.post('/ingest', form)
}

/** 上传历史（按上传时间倒序） */
export const listUploads = () => client.get('/ingest/history')

/** 下载某次上传的原文件 */
export async function downloadUpload(record) {
  const blob = await client.get(
    `/ingest/history/${encodeURIComponent(record.upload_id)}/download`,
    { responseType: 'blob' },
  )
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = record.filename || 'upload.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** 列出最近的会话（历史会话列表） */
export const listSessions = (limit = 20) =>
  client.get('/sessions', { params: { limit } })

/** 取某个会话的完整对话 */
export const getSession = (threadId) =>
  client.get(`/sessions/${encodeURIComponent(threadId)}`)

/** 列出最近的规划（plan）会话 */
export const listPlanSessions = (limit = 20) =>
  client.get('/plan/sessions', { params: { limit } })

/** 取某个规划会话：各轮请求 + 最后一次执行的计划与产出 */
export const getPlanSession = (threadId) =>
  client.get(`/plan/sessions/${encodeURIComponent(threadId)}`)
