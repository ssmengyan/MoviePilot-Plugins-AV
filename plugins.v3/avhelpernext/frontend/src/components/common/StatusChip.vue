<script setup lang="ts">
/**
 * 状态标签（`.tag` / `.badge` 的语义化封装）。
 *
 * 与老实现的对应关系（老代码没有独立的状态组件，状态文字散在各视图里）：
 * - `await` = `views/tasks.js` 的 `renderTasks()` 标题「待确认（n）」与
 *   `app.js` 的 `renderPills()`（`t.state === 'await'` 计数）；
 * - `down` / `done` = `views/downloads.js` 的 `queueRow()`：
 *   `done ? '已下载' : '下载中…'`，进度条 `q.progress`；
 * - `pushed` = `tasks.py` 的 `download()` 里 `task_set_state(tid, "pushed")`（提交下载后的任务态）；
 * - `active/paused/stalled/seeding` 是老实现在下载器侧**只做了字符串包含判断**
 *   （`"upload" in state`）而没有单独文案的档位，这里补成全套字典，
 *   颜色只走语义（info / primary / warning / success / error），不写死色值。
 */
import { computed } from 'vue'

/** 状态色调 → 主题语义色。 */
export type StatusTone = 'neutral' | 'info' | 'primary' | 'success' | 'warning' | 'error'

/** 状态字典：`状态 → [文案, 色调]`。取值来源见组件头部注释。 */
const STATUS_MAP: Record<string, [string, StatusTone]> = {
  await: ['待确认', 'info'],
  pending: ['待确认', 'info'],
  down: ['下载中…', 'info'],
  downloading: ['下载中…', 'info'],
  pushed: ['已提交', 'primary'],
  queued: ['排队中', 'neutral'],
  active: ['下载中…', 'primary'],
  seeding: ['做种中', 'success'],
  done: ['已下载', 'success'],
  finished: ['已下载', 'success'],
  paused: ['已暂停', 'warning'],
  stalled: ['无进度', 'warning'],
  stopped: ['已停止', 'warning'],
  error: ['失败', 'error'],
  failed: ['失败', 'error'],
}

const props = withDefaults(
  defineProps<{
    /** 后端状态字符串（`await` / `down` / `done` / `pushed` …）。 */
    state?: string
    /** 直接给文案时覆盖字典（如候选行的「有 / 无」）。 */
    label?: string
    /** 直接给色调时覆盖字典。 */
    tone?: StatusTone
    /** 前缀图标（如 `mdi-clock-outline`）；不给就不画图标。 */
    icon?: string
    size?: 'x-small' | 'small'
  }>(),
  { state: '', label: '', tone: undefined, icon: '', size: 'small' },
)

const entry = computed(() => STATUS_MAP[String(props.state || '').toLowerCase()] || null)

/** 字典里没有的状态：原样显示后端给的字符串，比编一个中文名诚实。 */
const text = computed(() => props.label || entry.value?.[0] || String(props.state || '') || '—')

const tone = computed<StatusTone>(() => props.tone || entry.value?.[1] || 'neutral')
</script>

<template>
  <v-chip
    :color="tone === 'neutral' ? undefined : tone"
    :variant="tone === 'neutral' ? 'outlined' : 'flat'"
    :size="size"
    :prepend-icon="icon || undefined"
    label
    class="avh-status"
  >
    {{ text }}
  </v-chip>
</template>

<style scoped>
.avh-status {
  font-variant-numeric: tabular-nums;
}
</style>
