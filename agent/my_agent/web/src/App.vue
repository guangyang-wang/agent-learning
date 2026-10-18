<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { health } from './api/client'
import EntryGate from './components/EntryGate.vue'

const route = useRoute()
const router = useRouter()

// 入口问答：答对后存 sessionStorage —— 同一标签页刷新不再问，新开/重新打开会再问。
const ENTRY_KEY = 'entry_passed'
const passed = ref(false)
try {
  passed.value = sessionStorage.getItem(ENTRY_KEY) === '1'
} catch {
  passed.value = false
}

const navs = computed(() => router.options.routes.filter((r) => r.meta?.title))
const currentTitle = computed(() => route.meta?.title || '')

// 后端连通性：启动时探一次，页面标题栏右侧显示小圆点
const backendUp = ref(null) // null=未知 true/false=结果

async function probe() {
  try {
    await health()
    backendUp.value = true
  } catch {
    backendUp.value = false // 拦截器已弹过提示，这里只记状态
  }
}

function onPass() {
  passed.value = true
  try {
    sessionStorage.setItem(ENTRY_KEY, '1')
  } catch {
    // 隐私模式写不进去，本次页面内仍然有效
  }
  probe()
}

onMounted(() => {
  if (passed.value) probe()
})
</script>

<template>
  <EntryGate v-if="!passed" @pass="onPass" />

  <el-container v-else class="layout">
    <el-aside width="220px" class="aside">
      <div class="brand">多 Agent 学习系统</div>
      <el-menu :default-active="route.path" router class="menu">
        <el-menu-item v-for="n in navs" :key="n.path" :index="n.path">
          <el-icon><component :is="n.meta.icon" /></el-icon>
          <span>{{ n.meta.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span class="title">{{ currentTitle }}</span>
        <el-tag
          v-if="backendUp !== null"
          :type="backendUp ? 'success' : 'danger'"
          effect="plain"
          size="small"
        >
          {{ backendUp ? '后端已连接' : '后端未连接' }}
        </el-tag>
        <el-button v-if="!backendUp" link size="small" @click="probe">重试</el-button>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}

.aside {
  background: #fff;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
}

.brand {
  height: 60px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-weight: 600;
  font-size: 15px;
  color: #303133;
  border-bottom: 1px solid #e4e7ed;
}

.menu {
  border-right: none;
  flex: 1;
}

.header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 16px;
  font-weight: 600;
  margin-right: auto;
}

.main {
  overflow: auto;
}
</style>
