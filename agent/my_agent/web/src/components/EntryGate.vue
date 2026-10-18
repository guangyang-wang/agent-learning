<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

// 前四个是「标准答案」，选其他（含自行填写）一律不通过
const RIGHT_ANSWERS = ['天选之子', '天纵奇才', '大帅哥', '神仙王广洋']
const OTHER = '其他'

const emit = defineEmits(['pass'])

const answer = ref('')
const custom = ref('')
const error = ref('')

function submit() {
  error.value = ''
  if (!answer.value) {
    ElMessage.warning('请先选择一个选项')
    return
  }
  if (RIGHT_ANSWERS.includes(answer.value)) {
    emit('pass')
    return
  }
  // 选了「其他」：自己填什么都不算对
  error.value = custom.value.trim()
    ? '回答错误，请重新选择'
    : '请先在下方填写你的答案'
}
</script>

<template>
  <div class="gate">
    <el-card class="panel" shadow="always">
      <div class="brand">多 Agent 学习系统</div>
      <div class="question">创造这个网站的是谁？</div>

      <el-select
        v-model="answer"
        placeholder="请选择"
        size="large"
        class="select"
        @change="error = ''"
      >
        <el-option v-for="opt in [...RIGHT_ANSWERS, OTHER]" :key="opt" :label="opt" :value="opt" />
      </el-select>

      <el-input
        v-if="answer === OTHER"
        v-model="custom"
        size="large"
        class="custom"
        placeholder="请填写你的答案"
        @keydown.enter.exact.prevent="submit"
      />

      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
        show-icon
        class="error"
      />

      <el-button type="primary" size="large" class="submit" @click="submit">进入</el-button>
    </el-card>
  </div>
</template>

<style scoped>
.gate {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #eef4ff 0%, #f7f9fc 55%, #eaf0ff 100%);
}

.panel {
  width: 420px;
  max-width: calc(100vw - 32px);
}

.panel :deep(.el-card__body) {
  padding: 32px;
}

.brand {
  text-align: center;
  font-size: 14px;
  color: #909399;
  letter-spacing: 1px;
}

.question {
  margin: 14px 0 24px;
  text-align: center;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.select {
  width: 100%;
}

.custom {
  margin-top: 12px;
}

.error {
  margin-top: 12px;
}

.submit {
  width: 100%;
  margin-top: 24px;
}
</style>
