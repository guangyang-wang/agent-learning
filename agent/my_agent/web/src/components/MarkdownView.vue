<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import DOMPurify from 'dompurify'
import 'highlight.js/styles/github.css'

const props = defineProps({
  content: { type: String, default: '' },
})

const md = new MarkdownIt({
  html: false, // 不解析原始 HTML，从源头挡掉注入
  linkify: true, // 裸 URL 自动变链接
  breaks: true, // 单个换行也换行，更贴近聊天场景
  highlight(str, lang) {
    // 只有认识的语言才高亮；返回 '' 则交给 markdown-it 默认转义
    if (!lang || !hljs.getLanguage(lang)) return ''
    try {
      const html = hljs.highlight(str, { language: lang, ignoreIllegals: true }).value
      // 返回以 <pre 开头的字符串时，markdown-it 会原样使用
      return `<pre class="hljs"><code class="language-${lang}">${html}</code></pre>`
    } catch {
      return ''
    }
  },
})

// 模型输出视为不可信内容，渲染后再消毒一遍（防 XSS）
const rendered = computed(() => DOMPurify.sanitize(md.render(props.content || '')))
</script>

<template>
  <div class="md" v-html="rendered" />
</template>

<style scoped>
.md {
  font-size: 14px;
  line-height: 1.75;
  color: #303133;
  word-break: break-word;
}

.md :deep(> :first-child) {
  margin-top: 0;
}

.md :deep(> :last-child) {
  margin-bottom: 0;
}

.md :deep(h1),
.md :deep(h2),
.md :deep(h3),
.md :deep(h4) {
  margin: 16px 0 8px;
  font-weight: 600;
  line-height: 1.4;
}

.md :deep(h1) {
  font-size: 20px;
}
.md :deep(h2) {
  font-size: 18px;
}
.md :deep(h3) {
  font-size: 16px;
}
.md :deep(h4) {
  font-size: 15px;
}

.md :deep(p) {
  margin: 8px 0;
}

.md :deep(ul),
.md :deep(ol) {
  margin: 8px 0;
  padding-left: 22px;
}

.md :deep(li) {
  margin: 4px 0;
}

.md :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid #dcdfe6;
  color: #606266;
  background: #fafafa;
}

.md :deep(a) {
  color: #409eff;
}

.md :deep(code) {
  font-family: ui-monospace, Consolas, 'Courier New', monospace;
  font-size: 13px;
}

/* 行内代码 */
.md :deep(:not(pre) > code) {
  padding: 2px 5px;
  border-radius: 4px;
  background: #f2f3f5;
  color: #c7254e;
}

.md :deep(pre) {
  margin: 10px 0;
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  background: #f6f8fa;
}

.md :deep(pre code) {
  padding: 0;
  background: none;
  color: inherit;
}

.md :deep(table) {
  width: 100%;
  margin: 10px 0;
  border-collapse: collapse;
  font-size: 13px;
}

.md :deep(th),
.md :deep(td) {
  padding: 6px 10px;
  border: 1px solid #e4e7ed;
  text-align: left;
}

.md :deep(th) {
  background: #fafafa;
  font-weight: 600;
}

.md :deep(hr) {
  margin: 16px 0;
  border: none;
  border-top: 1px solid #e4e7ed;
}
</style>
