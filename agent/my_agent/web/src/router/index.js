import { createRouter, createWebHistory } from 'vue-router'

// meta.title 同时用于：左侧菜单文案、顶部标题
// meta.icon  对应全局注册的 Element Plus 图标组件名
const routes = [
  { path: '/', redirect: '/chat' },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('../views/ChatView.vue'),
    meta: { title: '对话', icon: 'ChatDotRound' },
  },
  {
    path: '/plan',
    name: 'plan',
    component: () => import('../views/PlanView.vue'),
    meta: { title: '复杂任务', icon: 'List' },
  },
  {
    path: '/ingest',
    name: 'ingest',
    component: () => import('../views/IngestView.vue'),
    meta: { title: '课件上传', icon: 'UploadFilled' },
  },
  {
    path: '/retrieve',
    name: 'retrieve',
    component: () => import('../views/RetrieveView.vue'),
    meta: { title: '检索调试', icon: 'Search' },
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
