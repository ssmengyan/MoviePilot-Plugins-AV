<script setup lang="ts">
/**
 * 空态（老实现 `ui/ui/widgets.js` 的 `emptyHtml(html)` + `app.css` 的 `.empty`）。
 *
 * 老用法与文案（逐字保持，视图侧只需传同一句话）：
 * - `emptyHtml('还没有订阅')` —— `views/subs.js`；
 * - `'没有待确认的任务'` / `'下载队列为空<br>在「任务」页挑好候选点「下载」，进度在这里看'` —— tasks / downloads；
 * - `'输入番号或关键词后点「搜索站点」'` —— sitesearch；
 * - `'还没有收藏演员<br><br>' + 按钮` —— actors（用默认插槽放按钮，见下方示例）。
 *
 * 默认插槽的内容插在文案下方（老实现允许空态里带按钮）。
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 主文案（可以含 `<br>` 当换行符：本组件按它拆行，**不当 HTML 渲染**）。 */
    text?: string
    /** 追加一行次要说明（比主文案小一号）。 */
    hint?: string
  }>(),
  { text: '', hint: '' },
)

/**
 * 文案按 `<br>` 拆成多行**纯文本**（0.9.3 B3：去掉了 `v-html`）。
 *
 * 老实现是 `emptyHtml(html)` 直接塞 HTML，调用方因此把 `<br>` 写进了文案。这里保留
 * `<br>` 的书写习惯、只把它当分隔符：逐行插值渲染 —— 换行不丢，HTML 注入面没了
 * （这个组件是公共的，迟早有人把外部文本传进来；真到那时也不会变成执行面）。
 */
const lines = computed(() =>
  String(props.text || '')
    .split(/<br\s*\/?>/i)
    .map(line => line.trim())
    .filter(line => line !== ''),
)
</script>

<template>
  <div class="avh-empty">
    <div v-if="lines.length" class="avh-empty__text">
      <div v-for="(line, index) in lines" :key="index">{{ line }}</div>
    </div>
    <div v-if="hint" class="avh-empty__hint">{{ hint }}</div>
    <div v-if="$slots.default" class="avh-empty__slot">
      <slot />
    </div>
  </div>
</template>

<style scoped>
/* 对齐 `app.css` 的 `.empty`：居中、上下留白、行高 2 */
.avh-empty {
  padding: 48px 20px;
  text-align: center;
  font-size: 13px;
  line-height: 2;
  color: rgba(var(--v-theme-on-surface), 0.5);
}

.avh-empty__hint {
  font-size: 12px;
  line-height: 1.8;
}

.avh-empty__slot {
  margin-top: 12px;
  line-height: 1.5;
}
</style>
